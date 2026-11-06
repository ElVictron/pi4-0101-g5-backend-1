"""Cliente do Backend 2, publicação com guarda do pendente e reenvio (CT12, §8, §8A, §8B)."""

import json
import logging
import ssl
from contextlib import contextmanager
from datetime import datetime

import certifi
import httpx
import psycopg
import pytest
import respx

from app import reenviar_eventos
from app.config import Config
from app.eventos import publicador as modulo_publicador
from app.eventos import servico
from app.eventos.publicador import (
    DEVOLUCAO_REGISTRADA,
    EMPRESTIMO_REGISTRADO,
    FALHA_CONEXAO,
    FALHA_INESPERADA,
    FALHA_NAO_ACEITO,
    FALHA_RESPOSTA_INVALIDA,
    FALHA_SEM_URL,
    FALHA_TIMEOUT,
    PublicadorHttp,
    classificar_resposta,
    montar_payload,
    url_de_eventos,
    verificacao_tls,
)
from app.eventos.repositorio import EventoPendente
from app.relogio import RelogioFixo

pytestmark = pytest.mark.unitario

BASE = "https://backend2.teste"
T0 = datetime(2026, 10, 13, 19, 20)
PAYLOAD = montar_payload(
    tipo=EMPRESTIMO_REGISTRADO,
    livro_id=7,
    usuario_id=5,
    emprestimo_id=9,
    status="ativo",
    quantidade_disponivel=2,
    atualizada_em=T0,
)


def _config(**campos) -> Config:
    return Config(database_url="postgresql://x/y_teste", **({"backend2_url": BASE} | campos))


# --------------------------------------------------------------------------- payload e URL


def test_payload_tem_exatamente_os_campos_do_ct12():
    assert PAYLOAD == {
        "tipo": "emprestimo_registrado",
        "livroId": 7,
        "usuarioId": 5,
        "emprestimoId": 9,
        "status": "ativo",
        "quantidadeDisponivel": 2,
        "atualizadaEm": "2026-10-13T19:20:00",
    }


def test_tipos_de_evento():
    assert (EMPRESTIMO_REGISTRADO, DEVOLUCAO_REGISTRADA) == (
        "emprestimo_registrado",
        "devolucao_registrada",
    )


@pytest.mark.parametrize(
    ("base", "esperada"),
    [
        (None, None),
        ("", None),
        (BASE, BASE + "/eventos/biblioteca"),
        (BASE + "/", BASE + "/eventos/biblioteca"),
        (BASE + "//", BASE + "/eventos/biblioteca"),
        ("https://b2:8443/api/", "https://b2:8443/api/eventos/biblioteca"),
    ],
)
def test_url_de_eventos_sem_barra_dupla(base, esperada):
    assert url_de_eventos(base) == esperada


# --------------------------------------------------------------------------- TLS


def test_verificacao_tls_padrao_ligada():
    assert verificacao_tls(_config()) is True


def test_verificacao_tls_desligada_por_configuracao():
    assert verificacao_tls(_config(backend2_verify_tls=False)) is False


def test_ca_bundle_proprio_vira_contexto_que_verifica():
    contexto = verificacao_tls(
        _config(backend2_ca_bundle=certifi.where(), backend2_verify_tls=False)
    )

    assert isinstance(contexto, ssl.SSLContext)
    assert contexto.verify_mode is ssl.CERT_REQUIRED


# ----------------------------------------------- classificação da resposta


@pytest.mark.parametrize(
    ("resposta", "motivo"),
    [
        (httpx.Response(200, json={"aceito": True, "eventoId": "x"}), None),
        (httpx.Response(202, json={"aceito": True}), None),
        (httpx.Response(503), "HTTP 503"),
        (httpx.Response(400, json={"aceito": True}), "HTTP 400"),
        (httpx.Response(302, headers={"Location": "/x"}), "HTTP 302"),
        (httpx.Response(200, json={"aceito": False}), FALHA_NAO_ACEITO),
        (httpx.Response(200, json={"aceito": "true"}), FALHA_NAO_ACEITO),
        (httpx.Response(200, json={"aceito": 1}), FALHA_NAO_ACEITO),
        (httpx.Response(200, json={"eventoId": "x"}), FALHA_NAO_ACEITO),
        (httpx.Response(200, text="ok"), FALHA_RESPOSTA_INVALIDA),
        (httpx.Response(200, content=b"\xff\xfe{"), FALHA_RESPOSTA_INVALIDA),
        (httpx.Response(200, json=[{"aceito": True}]), FALHA_RESPOSTA_INVALIDA),
        (httpx.Response(200, json=None), FALHA_RESPOSTA_INVALIDA),
    ],
    ids=[
        "200",
        "202",
        "503",
        "400-aceito",
        "302",
        "false",
        "texto",
        "um",
        "sem-aceito",
        "nao-json",
        "binario",
        "lista",
        "null",
    ],
)
def test_classificar_resposta(resposta, motivo):
    assert classificar_resposta(resposta) == motivo


# --------------------------------------------------------------------------- PublicadorHttp


@pytest.fixture
def backend2():
    with respx.mock(base_url=BASE, assert_all_called=False) as mock:
        mock.post("/eventos/biblioteca", name="eventos").respond(200, json={"aceito": True})
        yield mock.routes["eventos"]


def test_publica_uma_vez_com_json_e_timeout_da_config(backend2):
    assert PublicadorHttp(_config(backend2_timeout_segundos=1.5)).publicar(PAYLOAD) is None

    assert backend2.call_count == 1
    requisicao = backend2.calls.last.request
    assert requisicao.headers["content-type"] == "application/json"
    assert json.loads(requisicao.content) == PAYLOAD
    assert requisicao.extensions["timeout"] == {
        "connect": 1.5,
        "read": 1.5,
        "write": 1.5,
        "pool": 1.5,
    }


@pytest.mark.parametrize(
    ("efeito", "motivo"),
    [
        (httpx.ConnectTimeout("lento"), FALHA_TIMEOUT),
        (httpx.ReadTimeout("lento"), FALHA_TIMEOUT),
        (httpx.WriteTimeout("lento"), FALHA_TIMEOUT),
        (httpx.PoolTimeout("lento"), FALHA_TIMEOUT),
        (httpx.ConnectError("recusada"), FALHA_CONEXAO),
        (httpx.RemoteProtocolError("quebrou"), FALHA_CONEXAO),
        (httpx.ReadError("caiu"), FALHA_CONEXAO),
        (RuntimeError("qualquer"), FALHA_INESPERADA),
    ],
)
def test_falhas_de_transporte_viram_motivo_curto(backend2, efeito, motivo):
    backend2.mock(side_effect=efeito)

    assert PublicadorHttp(_config()).publicar(PAYLOAD) == motivo
    assert backend2.call_count == 1


def test_resposta_de_falha_e_classificada(backend2):
    backend2.respond(503)

    assert PublicadorHttp(_config()).publicar(PAYLOAD) == "HTTP 503"


@pytest.mark.parametrize("url", [None, ""])
def test_sem_url_nao_chama_ninguem(backend2, url):
    assert PublicadorHttp(_config(backend2_url=url)).publicar(PAYLOAD) == FALHA_SEM_URL
    assert backend2.call_count == 0


def test_ca_bundle_ilegivel_e_falha_sem_derrubar(backend2, tmp_path):
    config = _config(backend2_ca_bundle=str(tmp_path / "nao-existe.pem"))

    assert PublicadorHttp(config).publicar(PAYLOAD) == FALHA_INESPERADA
    assert backend2.call_count == 0


def test_motivos_sao_curtos_e_nao_vazios():
    motivos = [
        FALHA_SEM_URL,
        FALHA_TIMEOUT,
        FALHA_CONEXAO,
        FALHA_RESPOSTA_INVALIDA,
        FALHA_NAO_ACEITO,
        FALHA_INESPERADA,
    ]
    assert all(0 < len(m) <= 40 for m in motivos)


def test_cliente_e_sincrono_e_a_url_vem_da_config(monkeypatch):
    criados = []

    class ClienteFalso:
        def __init__(self, **kwargs):
            criados.append(kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kwargs):
            criados.append(url)
            return httpx.Response(200, json={"aceito": True})

    monkeypatch.setattr(modulo_publicador.httpx, "Client", ClienteFalso)

    assert PublicadorHttp(_config(backend2_url=BASE + "/")).publicar(PAYLOAD) is None
    assert criados == [
        {"timeout": 3.0, "verify": True, "trust_env": False},
        BASE + "/eventos/biblioteca",
    ]


def test_cliente_nao_herda_proxy_nem_certificados_do_ambiente(monkeypatch, backend2, tmp_path):
    """D20: com `trust_env=True`, o `SSL_CERT_FILE` inexistente quebraria o cliente e o
    `HTTPS_PROXY` mandaria o envio para um proxy que não existe."""
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "nao-existe.pem"))
    monkeypatch.setenv("NETRC", str(tmp_path / "nao-existe.netrc"))
    clientes = []
    original = modulo_publicador.httpx.Client

    def registrar_cliente(**kwargs):
        cliente = original(**kwargs)
        clientes.append(cliente)
        return cliente

    monkeypatch.setattr(modulo_publicador.httpx, "Client", registrar_cliente)

    assert PublicadorHttp(_config()).publicar(PAYLOAD) is None
    assert backend2.call_count == 1
    [cliente] = clientes
    assert cliente.trust_env is False
    assert cliente._mounts == {}  # nenhum transporte de proxy montado


# --------------------------------------------------------------------------- publicar_ou_guardar


class PublicadorFalso:
    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.payloads = []

    def publicar(self, payload):
        self.payloads.append(dict(payload))
        resposta = self.respostas.pop(0)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta


@pytest.fixture
def guardados(monkeypatch):
    registros = []

    @contextmanager
    def transacao_falsa(config, *, somente_leitura=False):
        registros.append(("transacao", somente_leitura))
        yield "conexao"

    def inserir_falso(conexao, payload, ultimo_erro, agora):
        registros.append(("inserir", conexao, dict(payload), ultimo_erro, agora))
        return 1

    monkeypatch.setattr(servico, "transacao", transacao_falsa)
    monkeypatch.setattr(servico.repositorio, "inserir", inserir_falso)
    return registros


def test_sucesso_nao_guarda_nada(guardados):
    publicador = PublicadorFalso(None)

    assert servico.publicar_ou_guardar(_config(), RelogioFixo(T0), publicador, PAYLOAD) is True
    assert publicador.payloads == [PAYLOAD]
    assert guardados == []


def test_falha_guarda_o_pendente_com_o_relogio(guardados):
    publicador = PublicadorFalso("HTTP 503")

    assert servico.publicar_ou_guardar(_config(), RelogioFixo(T0), publicador, PAYLOAD) is False
    assert guardados == [("transacao", False), ("inserir", "conexao", PAYLOAD, "HTTP 503", T0)]


def test_publicador_que_levanta_excecao_conta_como_falha(guardados):
    publicador = PublicadorFalso(RuntimeError("bug"))

    assert servico.publicar_ou_guardar(_config(), RelogioFixo(T0), publicador, PAYLOAD) is False
    assert guardados[-1][3] == FALHA_INESPERADA


class _ErroDeBanco(psycopg.errors.UniqueViolation):
    pass


@pytest.mark.parametrize("erro", [_ErroDeBanco("Key (cpf)=(12345678900)"), OSError("disco")])
def test_falha_ao_guardar_nao_levanta_e_nao_vaza_dados(monkeypatch, caplog, erro):
    @contextmanager
    def transacao_que_falha(config, *, somente_leitura=False):
        raise erro
        yield  # pragma: no cover

    monkeypatch.setattr(servico, "transacao", transacao_que_falha)

    with caplog.at_level(logging.WARNING, logger="app.eventos.servico"):
        resultado = servico.publicar_ou_guardar(
            _config(), RelogioFixo(T0), PublicadorFalso("timeout"), PAYLOAD
        )

    assert resultado is False
    assert "12345678900" not in caplog.text
    assert "disco" not in caplog.text
    assert '"usuarioId"' not in caplog.text and "livroId" not in caplog.text
    assert type(erro).__name__ in caplog.text
    assert all(registro.exc_info is None for registro in caplog.records)


# --------------------------------------------------------------------------- reenvio


@pytest.fixture
def fila(monkeypatch):
    """Fila falsa de pendentes: {id: EventoPendente}; registra as operações."""
    estado = {
        "linhas": {
            1: EventoPendente(1, {"n": 1}, 1),
            2: EventoPendente(2, {"n": 2}, 3),
            3: EventoPendente(3, {"n": 3}, 1),
        },
        "travados_por_outro": set(),
        "ops": [],
    }

    @contextmanager
    def transacao_falsa(config, *, somente_leitura=False):
        estado["ops"].append(("transacao", somente_leitura))
        yield "conexao"

    repo = reenviar_eventos.repositorio
    monkeypatch.setattr(reenviar_eventos, "transacao", transacao_falsa)
    monkeypatch.setattr(repo, "ids_em_ordem", lambda c: sorted(estado["linhas"]))
    monkeypatch.setattr(
        repo,
        "travar",
        lambda c, i: None if i in estado["travados_por_outro"] else estado["linhas"].get(i),
    )
    monkeypatch.setattr(repo, "apagar", lambda c, i: estado["ops"].append(("apagar", i)))
    monkeypatch.setattr(
        repo,
        "registrar_falha",
        lambda c, i, erro, agora: estado["ops"].append(("falha", i, erro, agora)),
    )
    return estado


def test_reenvio_apaga_sucesso_e_conta_falha_na_ordem(fila):
    publicador = PublicadorFalso(None, "timeout", None)

    restantes = reenviar_eventos.reenviar(_config(), RelogioFixo(T0), publicador)

    assert restantes == 1
    assert publicador.payloads == [{"n": 1}, {"n": 2}, {"n": 3}]
    assert [op for op in fila["ops"] if op[0] != "transacao"] == [
        ("apagar", 1),
        ("falha", 2, "timeout", T0),
        ("apagar", 3),
    ]
    assert fila["ops"][0] == ("transacao", True)


def test_reenvio_pula_evento_travado_por_outro_e_conta_como_pendente(fila):
    fila["travados_por_outro"].add(2)
    publicador = PublicadorFalso(None, None)

    assert reenviar_eventos.reenviar(_config(), RelogioFixo(T0), publicador) == 1
    assert publicador.payloads == [{"n": 1}, {"n": 3}]
    assert [op for op in fila["ops"] if op[0] != "transacao"] == [("apagar", 1), ("apagar", 3)]


def test_reenvio_sem_pendentes(fila):
    fila["linhas"].clear()

    assert reenviar_eventos.reenviar(_config(), RelogioFixo(T0), PublicadorFalso()) == 0


@pytest.mark.parametrize(("restantes", "codigo"), [(0, 0), (1, 1), (5, 1)])
def test_main_devolve_0_ou_1_e_usa_o_publicador_http(monkeypatch, restantes, codigo):
    recebidos = []

    def reenviar_falso(config, relogio, publicador):
        recebidos.append((config, relogio, publicador))
        return restantes

    monkeypatch.setattr(reenviar_eventos, "reenviar", reenviar_falso)
    config = _config()
    relogio = RelogioFixo(T0)

    assert reenviar_eventos.main(config, relogio) == codigo
    [(config_usada, relogio_usado, publicador)] = recebidos
    assert (config_usada, relogio_usado) == (config, relogio)
    assert isinstance(publicador, PublicadorHttp)


def test_main_sem_argumentos_le_o_ambiente(monkeypatch):
    recebidos = []
    monkeypatch.setattr(reenviar_eventos, "reenviar", lambda c, r, p: recebidos.append((c, r)) or 0)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@h/amb_teste")
    monkeypatch.setenv("BACKEND2_URL", BASE)

    assert reenviar_eventos.main() == 0
    [(config, relogio)] = recebidos
    assert (config.database_url, config.backend2_url) == ("postgresql://u@h/amb_teste", BASE)
    assert isinstance(relogio, reenviar_eventos.RelogioSistema)


# ----------------------------------------------- ultimo_erro (§8, D20)


@pytest.mark.parametrize(
    ("motivo", "esperado"),
    [
        ("timeout", "timeout"),
        ("  HTTP 503 \n", "HTTP 503"),
        ("x" * 200, "x" * 200),
        ("y" * 500, "y" * 200),
        ("", "falha sem descrição"),
        ("   ", "falha sem descrição"),
    ],
    ids=["curto", "pontas", "200", "500", "vazio", "brancos"],
)
def test_resumo_do_erro_curto_e_nao_vazio(motivo, esperado):
    from app.eventos.repositorio import LIMITE_ULTIMO_ERRO, resumo_do_erro

    assert LIMITE_ULTIMO_ERRO == 200
    assert resumo_do_erro(motivo) == esperado
