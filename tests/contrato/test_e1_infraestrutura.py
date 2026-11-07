"""E1 — Esqueleto: rota de saúde, formato de erro, CORS, configuração e relógio.

Fontes: `docs/contratos/00-convencoes.md` §3, §7, §9 e §10; `agentes.md` §8B.
Os módulos de `app` são importados dentro dos testes, para que cada teste falhe
isoladamente enquanto o módulo não existir.
"""

import dataclasses
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

ORIGEM_FRONT = "https://front.teste"
ORIGEM_OUTRA = "https://outro.teste"
VARIAVEIS = (
    "DATABASE_URL",
    "BACKEND2_URL",
    "BACKEND2_TIMEOUT_SEGUNDOS",
    "BACKEND2_VERIFY_TLS",
    "BACKEND2_CA_BUNDLE",
    "CORS_ORIGENS",
)
URL_BANCO = "postgresql://usuario@localhost:5432/biblioteca"
URL_BANCO_INACESSIVEL = "postgresql://ninguem@127.0.0.1:1/nada"


def _assert_corpo_de_erro(resposta, codigo: str) -> None:
    assert resposta.headers["content-type"].startswith("application/json")
    corpo = resposta.json()
    assert set(corpo) == {"erro"}
    assert set(corpo["erro"]) == {"codigo", "mensagem"}
    assert corpo["erro"]["codigo"] == codigo
    assert isinstance(corpo["erro"]["mensagem"], str)
    assert corpo["erro"]["mensagem"].strip()


def _preflight(cliente: TestClient, origem: str):
    return cliente.options(
        "/saude",
        headers={"Origin": origem, "Access-Control-Request-Method": "GET"},
    )


# --------------------------------------------------------------------------- GET /saude


# 00-convencoes §9 · GET /saude → 200 {"status": "ok"}
def test_saude_responde_ok(client):
    resposta = client.get("/saude")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/json")
    assert resposta.json() == {"status": "ok"}


# 8B · create_app() sem argumentos usa Config.from_env() e RelogioSistema()
def test_create_app_sem_argumentos_le_o_ambiente(monkeypatch, database_url):
    from app.main import create_app

    for nome in VARIAVEIS:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("DATABASE_URL", database_url)

    with TestClient(create_app()) as cliente:
        resposta = cliente.get("/saude")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


# 00-convencoes §9 · GET /saude não consulta o banco (funciona com banco inacessível)
def test_saude_nao_consulta_o_banco(criar_app):
    app_sem_banco = criar_app(database_url=URL_BANCO_INACESSIVEL)

    with TestClient(app_sem_banco) as cliente:
        resposta = cliente.get("/saude")

    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok"}


# --------------------------------------------------------------------------- formato de erro


# 00-convencoes §3 · rota inexistente → 404 ROTA_NAO_ENCONTRADA
@pytest.mark.parametrize(
    ("metodo", "caminho"),
    [("GET", "/nao-existe"), ("POST", "/nao-existe"), ("GET", "/nao/existe/mesmo")],
)
def test_rota_inexistente_devolve_404_no_formato_de_erro(client, metodo, caminho):
    resposta = client.request(metodo, caminho)

    assert resposta.status_code == 404
    _assert_corpo_de_erro(resposta, "ROTA_NAO_ENCONTRADA")


# 00-convencoes §3 · método não permitido → 405 ROTA_NAO_ENCONTRADA
@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE"])
def test_metodo_nao_permitido_devolve_405_no_formato_de_erro(client, metodo):
    resposta = client.request(metodo, "/saude")

    assert resposta.status_code == 405
    _assert_corpo_de_erro(resposta, "ROTA_NAO_ENCONTRADA")


# 00-convencoes §3 / D12 · não há documentação automática: responde como rota inexistente
@pytest.mark.parametrize("caminho", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_rotas_de_documentacao_automatica_nao_existem(client, caminho):
    resposta = client.get(caminho, follow_redirects=False)

    assert resposta.status_code == 404
    _assert_corpo_de_erro(resposta, "ROTA_NAO_ENCONTRADA")


# 00-convencoes §3 · barra no fim é rota inexistente: 404, sem redirecionamento
def test_barra_no_fim_e_rota_inexistente_sem_redirecionamento(client):
    resposta = client.get("/saude/", follow_redirects=False)

    assert resposta.status_code == 404
    assert "location" not in resposta.headers
    _assert_corpo_de_erro(resposta, "ROTA_NAO_ENCONTRADA")


# --------------------------------------------------------------------------- CORS


# 00-convencoes §9 · CORS: origem listada em CORS_ORIGENS é aceita no preflight
def test_cors_preflight_aceita_origem_permitida(criar_app):
    with TestClient(criar_app(cors_origens=(ORIGEM_FRONT,))) as cliente:
        resposta = _preflight(cliente, ORIGEM_FRONT)

    assert resposta.headers.get("access-control-allow-origin") == ORIGEM_FRONT


# 00-convencoes §9 · CORS: origem listada recebe o cabeçalho numa requisição simples
def test_cors_requisicao_simples_de_origem_permitida(criar_app):
    with TestClient(criar_app(cors_origens=(ORIGEM_FRONT,))) as cliente:
        resposta = cliente.get("/saude", headers={"Origin": ORIGEM_FRONT})

    assert resposta.status_code == 200
    assert resposta.headers.get("access-control-allow-origin") == ORIGEM_FRONT


# 00-convencoes §9 · CORS: origem fora de CORS_ORIGENS não é liberada
def test_cors_recusa_origem_nao_listada(criar_app):
    with TestClient(criar_app(cors_origens=(ORIGEM_FRONT,))) as cliente:
        preflight = _preflight(cliente, ORIGEM_OUTRA)
        simples = cliente.get("/saude", headers={"Origin": ORIGEM_OUTRA})

    for resposta in (preflight, simples):
        assert resposta.headers.get("access-control-allow-origin") not in (ORIGEM_OUTRA, "*")


# 00-convencoes §9 · CORS_ORIGENS vazio = nenhuma origem externa
@pytest.mark.parametrize("origem", [ORIGEM_FRONT, ORIGEM_OUTRA])
def test_cors_vazio_nao_libera_nenhuma_origem(criar_app, origem):
    with TestClient(criar_app(cors_origens=())) as cliente:
        preflight = _preflight(cliente, origem)
        simples = cliente.get("/saude", headers={"Origin": origem})

    assert "access-control-allow-origin" not in preflight.headers
    assert "access-control-allow-origin" not in simples.headers


# 00-convencoes §9 · preflight recusado: sem cabeçalhos CORS, 4xx no formato de erro do §3
@pytest.mark.parametrize(
    ("cors_origens", "origem"),
    [((ORIGEM_FRONT,), ORIGEM_OUTRA), ((), ORIGEM_FRONT)],
    ids=["origem-nao-listada", "cors-vazio"],
)
def test_cors_preflight_recusado_segue_formato_de_erro(criar_app, cors_origens, origem):
    with TestClient(criar_app(cors_origens=cors_origens)) as cliente:
        resposta = _preflight(cliente, origem)

    assert 400 <= resposta.status_code < 500
    assert "access-control-allow-origin" not in resposta.headers
    assert resposta.headers["content-type"].startswith("application/json")
    corpo = resposta.json()
    assert set(corpo) == {"erro"}
    assert set(corpo["erro"]) == {"codigo", "mensagem"}
    assert isinstance(corpo["erro"]["codigo"], str)
    assert corpo["erro"]["codigo"]
    assert isinstance(corpo["erro"]["mensagem"], str)
    assert corpo["erro"]["mensagem"].strip()


# --------------------------------------------------------------------------- Config


# 8B · Config: campos e padrões
def test_config_padroes_do_construtor():
    from app.config import Config

    config = Config(database_url=URL_BANCO)

    assert config.database_url == URL_BANCO
    assert config.backend2_url is None
    assert config.backend2_timeout_segundos == 3.0
    assert config.backend2_verify_tls is True
    assert config.backend2_ca_bundle is None
    assert config.cors_origens == ()


# 8B · Config é imutável
def test_config_e_imutavel():
    from app.config import Config

    config = Config(database_url=URL_BANCO)

    assert dataclasses.is_dataclass(config)
    with pytest.raises(AttributeError):
        config.database_url = "postgresql://outro/banco"
    assert config.database_url == URL_BANCO


# 00-convencoes §10 / 8B · from_env: só DATABASE_URL → demais com os padrões
def test_from_env_le_database_url_e_aplica_padroes():
    from app.config import Config

    config = Config.from_env({"DATABASE_URL": URL_BANCO})

    assert config.database_url == URL_BANCO
    assert config.backend2_url is None
    assert config.backend2_timeout_segundos == 3.0
    assert isinstance(config.backend2_timeout_segundos, float)
    assert config.backend2_verify_tls is True
    assert config.backend2_ca_bundle is None
    assert config.cors_origens == ()


# 00-convencoes §10 / 8B · from_env: todas as variáveis preenchidas
def test_from_env_le_todas_as_variaveis():
    from app.config import Config

    config = Config.from_env(
        {
            "DATABASE_URL": URL_BANCO,
            "BACKEND2_URL": "https://backend2:8443",
            "BACKEND2_TIMEOUT_SEGUNDOS": "5",
            "BACKEND2_VERIFY_TLS": "false",
            "BACKEND2_CA_BUNDLE": "/certs/ca.pem",
            "CORS_ORIGENS": "https://a.teste",
        }
    )

    assert config.database_url == URL_BANCO
    assert config.backend2_url == "https://backend2:8443"
    assert config.backend2_timeout_segundos == 5.0
    assert isinstance(config.backend2_timeout_segundos, float)
    assert config.backend2_verify_tls is False
    assert config.backend2_ca_bundle == "/certs/ca.pem"
    assert config.cors_origens == ("https://a.teste",)


# 8B · BACKEND2_VERIFY_TLS aceita true/false/1/0 sem diferenciar maiúsculas
@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("true", True),
        ("TRUE", True),
        ("1", True),
    ],
)
def test_from_env_backend2_verify_tls(valor, esperado):
    from app.config import Config

    config = Config.from_env({"DATABASE_URL": URL_BANCO, "BACKEND2_VERIFY_TLS": valor})

    assert config.backend2_verify_tls is esperado


# 8B · CORS_ORIGENS: separado por vírgula, sem espaços nas pontas, sem itens vazios
def test_from_env_cors_origens_normalizadas():
    from app.config import Config

    config = Config.from_env(
        {"DATABASE_URL": URL_BANCO, "CORS_ORIGENS": " https://a.teste , ,https://b.teste "}
    )

    assert config.cors_origens == ("https://a.teste", "https://b.teste")


# 8B · valores vazios valem como não configurados (ficam com o padrão)
def test_from_env_valores_vazios_valem_como_nao_configurados():
    from app.config import Config

    config = Config.from_env(
        {
            "DATABASE_URL": URL_BANCO,
            "BACKEND2_URL": "",
            "BACKEND2_TIMEOUT_SEGUNDOS": "",
            "BACKEND2_VERIFY_TLS": "",
            "BACKEND2_CA_BUNDLE": "",
            "CORS_ORIGENS": "",
        }
    )

    assert config.backend2_url is None
    assert config.backend2_timeout_segundos == 3.0
    assert config.backend2_verify_tls is True
    assert config.backend2_ca_bundle is None
    assert config.cors_origens == ()


# 8B · sem DATABASE_URL (ausente ou vazia) → ValueError
@pytest.mark.parametrize("env", [{}, {"DATABASE_URL": ""}], ids=["ausente", "vazia"])
def test_from_env_sem_database_url_levanta_value_error(env):
    from app.config import Config

    with pytest.raises(ValueError):
        Config.from_env(env)


# 8B · from_env sem argumento lê os.environ
def test_from_env_sem_argumento_usa_os_environ(monkeypatch):
    from app.config import Config

    for nome in VARIAVEIS:
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("DATABASE_URL", URL_BANCO)
    monkeypatch.setenv("BACKEND2_TIMEOUT_SEGUNDOS", "7")

    config = Config.from_env()

    assert config.database_url == URL_BANCO
    assert config.backend2_timeout_segundos == 7.0


# 00-convencoes §10 · valor só com espaços vale como não configurado
def test_from_env_valores_so_com_espacos_valem_como_nao_configurados():
    from app.config import Config

    config = Config.from_env(
        {
            "DATABASE_URL": URL_BANCO,
            "BACKEND2_URL": "   ",
            "BACKEND2_TIMEOUT_SEGUNDOS": "   ",
            "BACKEND2_VERIFY_TLS": "   ",
            "BACKEND2_CA_BUNDLE": "   ",
            "CORS_ORIGENS": "   ",
        }
    )

    assert config.backend2_url is None
    assert config.backend2_timeout_segundos == 3.0
    assert config.backend2_verify_tls is True
    assert config.backend2_ca_bundle is None
    assert config.cors_origens == ()


# 00-convencoes §10 · DATABASE_URL só com espaços = ausente → ValueError
def test_from_env_database_url_so_com_espacos_levanta_value_error():
    from app.config import Config

    with pytest.raises(ValueError):
        Config.from_env({"DATABASE_URL": "   "})


# 00-convencoes §10 / D12 · timeout que não é número positivo → ValueError
@pytest.mark.parametrize("valor", ["abc", "0", "-1"])
def test_from_env_timeout_invalido_levanta_value_error(valor):
    from app.config import Config

    with pytest.raises(ValueError):
        Config.from_env({"DATABASE_URL": URL_BANCO, "BACKEND2_TIMEOUT_SEGUNDOS": valor})


# 00-convencoes §10 / D12 · BACKEND2_VERIFY_TLS fora de true/false/1/0 → ValueError
def test_from_env_verify_tls_invalido_levanta_value_error():
    from app.config import Config

    with pytest.raises(ValueError):
        Config.from_env({"DATABASE_URL": URL_BANCO, "BACKEND2_VERIFY_TLS": "talvez"})


# 00-convencoes §9 e §10 / D12 · curinga `*` em CORS_ORIGENS é recusado → ValueError
@pytest.mark.parametrize("valor", ["*", "https://a.teste,*"])
def test_from_env_cors_curinga_levanta_value_error(valor):
    from app.config import Config

    with pytest.raises(ValueError):
        Config.from_env({"DATABASE_URL": URL_BANCO, "CORS_ORIGENS": valor})


# --------------------------------------------------------------------------- relógio


# 8B / 00-convencoes §7 · RelogioFixo devolve o instante fixado
def test_relogio_fixo_devolve_o_instante(instante_base):
    from app.relogio import RelogioFixo

    relogio = RelogioFixo(instante_base)

    assert relogio.agora() == instante_base
    assert relogio.agora() == instante_base


# 8B · RelogioFixo.avancar move o instante (e acumula)
def test_relogio_fixo_avancar(instante_base):
    from app.relogio import RelogioFixo

    relogio = RelogioFixo(instante_base)
    relogio.avancar(timedelta(days=15))

    assert relogio.agora() == datetime(2026, 10, 28, 19, 20, 0)

    relogio.avancar(timedelta(seconds=1))

    assert relogio.agora() == datetime(2026, 10, 28, 19, 20, 1)


# 8B / 00-convencoes §7 · RelogioSistema: sem fuso, sem microssegundos, horário de São Paulo
def test_relogio_sistema_horario_de_sao_paulo():
    from app.relogio import RelogioSistema

    agora = RelogioSistema().agora()
    referencia = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)

    assert isinstance(agora, datetime)
    assert agora.tzinfo is None
    assert agora.microsecond == 0
    assert abs(agora - referencia) < timedelta(minutes=2)
