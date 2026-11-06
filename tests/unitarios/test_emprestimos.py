"""Empréstimos: entrada e saída do CT5, situação efetiva, EmprestimoResumo e serviço (sem banco)."""

from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from app.config import Config
from app.emprestimos import repositorio, servico
from app.emprestimos.esquemas import (
    CAMPOS_ENTRADA,
    PRAZO_DE_DEVOLUCAO,
    Emprestimo,
    EmprestimoResumo,
    NovoEmprestimo,
    Situacao,
    data_hora_para_json,
    data_limite_para,
    emprestimo_para_json,
    emprestimo_resumo_para_json,
    ler_novo_emprestimo,
    situacao_efetiva,
)
from app.erros import CodigoErro, ErroDominio
from app.relogio import RelogioFixo
from app.validacao import INTEIRO_MAXIMO

pytestmark = pytest.mark.unitario

T0 = datetime(2026, 10, 13, 19, 20, 0)
LIMITE = T0 + timedelta(days=15)


@pytest.mark.parametrize(
    ("agora", "esperada"),
    [
        (T0, Situacao.ATIVO),
        (LIMITE - timedelta(seconds=1), Situacao.ATIVO),
        (LIMITE, Situacao.ATIVO),
        (LIMITE + timedelta(seconds=1), Situacao.ATRASADO),
        (LIMITE + timedelta(days=300), Situacao.ATRASADO),
    ],
    ids=["emprestimo", "1s-antes", "no-limite", "1s-depois", "muito-depois"],
)
def test_situacao_sem_devolucao(agora, esperada):
    assert situacao_efetiva(None, LIMITE, agora) is esperada


@pytest.mark.parametrize("agora", [T0, LIMITE + timedelta(days=30)])
def test_devolvido_vale_mesmo_depois_do_prazo(agora):
    assert situacao_efetiva(LIMITE + timedelta(days=1), LIMITE, agora) is Situacao.DEVOLVIDO


def test_valores_da_situacao():
    assert [s.value for s in Situacao] == ["ativo", "devolvido", "atrasado"]


@pytest.mark.parametrize(
    ("instante", "esperado"),
    [
        (None, None),
        (T0, "2026-10-13T19:20:00"),
        (datetime(2026, 1, 2, 3, 4, 5, 999_999), "2026-01-02T03:04:05"),
        (datetime(2026, 1, 2), "2026-01-02T00:00:00"),
    ],
)
def test_data_hora_sem_fuso_nem_fracao(instante, esperado):
    assert data_hora_para_json(instante) == esperado


def test_resumo_tem_os_campos_do_ct8_com_devolvido_em_nulo():
    emprestimo = EmprestimoResumo(9, 5, "Lucas", 7, "Livro", T0, LIMITE, None)

    assert emprestimo_resumo_para_json(emprestimo, LIMITE + timedelta(seconds=1)) == {
        "emprestimoId": 9,
        "usuarioId": 5,
        "usuarioNome": "Lucas",
        "livroId": 7,
        "livroTitulo": "Livro",
        "status": "atrasado",
        "emprestadoEm": "2026-10-13T19:20:00",
        "dataLimiteDevolucao": "2026-10-28T19:20:00",
        "devolvidoEm": None,
    }


def test_resumo_devolvido():
    devolucao = T0 + timedelta(days=2)
    emprestimo = EmprestimoResumo(9, 5, "Lucas", 7, "Livro", T0, LIMITE, devolucao)

    dados = emprestimo_resumo_para_json(emprestimo, LIMITE + timedelta(days=9))

    assert dados["status"] == "devolvido"
    assert dados["devolvidoEm"] == "2026-10-15T19:20:00"


def test_lista_vazia_de_usuarios_nao_consulta_o_banco():
    class ConexaoQueNaoPodeSerUsada:
        def execute(self, *args, **kwargs):
            raise AssertionError("não deveria consultar")

    assert repositorio.resumos_dos_usuarios(ConexaoQueNaoPodeSerUsada(), []) == []


def test_sql_do_resumo_usa_any_e_a_ordem_do_ct8():
    texto = repositorio.ORDEM_RESUMO.as_string(None)

    assert texto == "ORDER BY e.emprestado_em DESC, e.id DESC"
    assert "JOIN usuarios" in repositorio.SELECAO_RESUMO.as_string(None)
    assert "JOIN livros" in repositorio.SELECAO_RESUMO.as_string(None)


# ----------------------------------------------- CT5 registrarEmprestimo (sem banco)


def _erro_de_entrada(dados) -> CodigoErro:
    with pytest.raises(ErroDominio) as erro:
        ler_novo_emprestimo(dados)
    return erro.value.codigo


def test_campos_na_ordem_do_ct5():
    assert CAMPOS_ENTRADA == ("usuarioId", "livroId")


def test_le_ids_validos():
    assert ler_novo_emprestimo({"usuarioId": 1, "livroId": INTEIRO_MAXIMO, "x": 0}) == (
        NovoEmprestimo(usuario_id=1, livro_id=INTEIRO_MAXIMO)
    )


@pytest.mark.parametrize(
    ("dados", "codigo"),
    [
        ({"livroId": 1}, CodigoErro.CAMPOS_OBRIGATORIOS),
        ({"usuarioId": None, "livroId": 0}, CodigoErro.CAMPOS_OBRIGATORIOS),
        ({"usuarioId": 0, "livroId": None}, CodigoErro.CAMPOS_OBRIGATORIOS),
        ({"usuarioId": "", "livroId": 1}, CodigoErro.CAMPOS_OBRIGATORIOS),
        ({"usuarioId": 0, "livroId": 1}, CodigoErro.DADOS_INVALIDOS),
        ({"usuarioId": -1, "livroId": 1}, CodigoErro.DADOS_INVALIDOS),
        ({"usuarioId": True, "livroId": 1}, CodigoErro.DADOS_INVALIDOS),
        ({"usuarioId": 1.0, "livroId": 1}, CodigoErro.DADOS_INVALIDOS),
        ({"usuarioId": "1", "livroId": 1}, CodigoErro.DADOS_INVALIDOS),
        ({"usuarioId": 1, "livroId": INTEIRO_MAXIMO + 1}, CodigoErro.DADOS_INVALIDOS),
    ],
)
def test_validacao_de_entrada(dados, codigo):
    assert _erro_de_entrada(dados) is codigo


def test_mensagem_do_item_3_cita_usuario_antes_de_livro():
    with pytest.raises(ErroDominio) as erro:
        ler_novo_emprestimo({"usuarioId": 0, "livroId": 0})

    assert "'usuarioId'" in erro.value.mensagem


def test_prazo_de_15_dias_no_mesmo_horario():
    assert timedelta(days=15) == PRAZO_DE_DEVOLUCAO
    assert data_limite_para(T0) == datetime(2026, 10, 28, 19, 20, 0)


def test_saida_do_ct5():
    emprestimo = Emprestimo(9, 5, 7, "ativo", T0, LIMITE, None)

    assert emprestimo_para_json(emprestimo) == {
        "emprestimoId": 9,
        "usuarioId": 5,
        "livroId": 7,
        "status": "ativo",
        "emprestadoEm": "2026-10-13T19:20:00",
        "dataLimiteDevolucao": "2026-10-28T19:20:00",
        "devolvidoEm": None,
    }


@pytest.fixture
def cenario(monkeypatch):
    """Dublês do banco e da publicação; `estado` controla o que o banco 'tem'."""
    estado = {"usuario": True, "livro": True, "disponivel_depois": 2, "ops": []}

    @contextmanager
    def transacao_falsa(config, *, somente_leitura=False):
        estado["ops"].append("abre")
        try:
            yield "conexao"
        except BaseException:
            estado["ops"].append("desfaz")
            raise
        estado["ops"].append("confirma")

    def inserir(conexao, *, usuario_id, livro_id, emprestado_em, data_limite_devolucao):
        estado["ops"].append(
            ("inserir", usuario_id, livro_id, emprestado_em, data_limite_devolucao)
        )
        return Emprestimo(
            99, usuario_id, livro_id, "ativo", emprestado_em, data_limite_devolucao, None
        )

    def baixar(conexao, livro_id):
        estado["ops"].append(("baixar", livro_id))
        return estado["disponivel_depois"]

    def publicar(config, relogio, publicador, payload):
        estado["ops"].append(("publicar", dict(payload)))
        return True

    monkeypatch.setattr(servico, "transacao", transacao_falsa)
    monkeypatch.setattr(servico.repositorio_usuarios, "existe", lambda c, i: estado["usuario"])

    def livro_existe(conexao, livro_id):
        # `livro_some`: existe na primeira consulta e some antes da segunda (exclusão concorrente)
        if estado.get("livro_some"):
            estado["livro_some"] = False
            return True
        return estado["livro"]

    monkeypatch.setattr(servico.repositorio_livros, "existe", livro_existe)
    monkeypatch.setattr(servico.repositorio_livros, "baixar_exemplar", baixar)
    monkeypatch.setattr(servico.repositorio, "inserir", inserir)
    monkeypatch.setattr(servico, "publicar_ou_guardar", publicar)
    return estado


def _registrar():
    return servico.registrar_emprestimo(
        Config(database_url="postgresql://x/y_teste"),
        RelogioFixo(T0),
        object(),
        NovoEmprestimo(usuario_id=5, livro_id=7),
    )


def test_registra_e_publica_so_depois_do_commit(cenario):
    emprestimo = _registrar()

    assert emprestimo == Emprestimo(99, 5, 7, "ativo", T0, LIMITE, None)
    assert cenario["ops"] == [
        "abre",
        ("baixar", 7),
        ("inserir", 5, 7, T0, LIMITE),
        "confirma",
        (
            "publicar",
            {
                "tipo": "emprestimo_registrado",
                "livroId": 7,
                "usuarioId": 5,
                "emprestimoId": 99,
                "status": "ativo",
                "quantidadeDisponivel": 2,
                "atualizadaEm": "2026-10-13T19:20:00",
            },
        ),
    ]


@pytest.mark.parametrize(
    ("ajuste", "codigo"),
    [
        ({"usuario": False, "livro": False, "disponivel_depois": None}, "USUARIO_NAO_ENCONTRADO"),
        ({"livro": False, "disponivel_depois": None}, "LIVRO_NAO_ENCONTRADO"),
        ({"disponivel_depois": None}, "LIVRO_INDISPONIVEL"),
        (
            {"livro_some": True, "livro": False, "disponivel_depois": None},
            "LIVRO_NAO_ENCONTRADO",
        ),
    ],
    ids=["usuario", "livro", "indisponivel", "livro-excluido-no-meio"],
)
def test_ordem_dos_erros_de_negocio_desfaz_e_nao_publica(cenario, ajuste, codigo):
    cenario.update(ajuste)

    with pytest.raises(ErroDominio) as erro:
        _registrar()

    assert erro.value.codigo.value == codigo
    assert cenario["ops"][-1] == "desfaz"
    assert not any(
        isinstance(op, tuple) and op[0] in ("inserir", "publicar") for op in cenario["ops"]
    )


def test_chave_estrangeira_e_rede_de_seguranca():
    assert dict(servico.ERROS_POR_RESTRICAO) == {
        "emprestimos_usuario_existe": CodigoErro.USUARIO_NAO_ENCONTRADO,
        "emprestimos_livro_existe": CodigoErro.LIVRO_NAO_ENCONTRADO,
    }


def test_rota_usa_o_publicador_do_estado_da_aplicacao(monkeypatch):
    from fastapi.testclient import TestClient

    from app.eventos.publicador import PublicadorHttp
    from app.main import create_app

    recebidos = []

    def registrar(config, relogio, publicador, novo):
        recebidos.append((publicador, novo))
        return Emprestimo(1, novo.usuario_id, novo.livro_id, "ativo", T0, LIMITE, None)

    monkeypatch.setattr(servico, "registrar_emprestimo", registrar)
    app = create_app(config=Config(database_url="postgresql://x/y_teste"))
    assert isinstance(app.state.publicador, PublicadorHttp)

    with TestClient(app) as cliente:
        resposta = cliente.post("/emprestimos", json={"usuarioId": 3, "livroId": 4})

    assert resposta.status_code == 201
    assert resposta.json()["emprestimoId"] == 1
    assert recebidos == [(app.state.publicador, NovoEmprestimo(3, 4))]
