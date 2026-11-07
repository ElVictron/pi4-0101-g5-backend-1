"""Empréstimos: entrada e saída do CT5, situação efetiva, EmprestimoResumo e serviço (sem banco)."""

from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from app.config import Config
from app.emprestimos import repositorio, servico
from app.emprestimos.esquemas import (
    CAMPOS_ENTRADA,
    PRAZO_DE_DEVOLUCAO,
    Devolucao,
    Emprestimo,
    EmprestimoResumo,
    NovoEmprestimo,
    Situacao,
    data_hora_para_json,
    data_limite_para,
    devolucao_para_json,
    emprestimo_para_json,
    emprestimo_resumo_para_json,
    ler_id_do_caminho,
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


# ----------------------------------------------- CT8 consultarEmprestimos (sem banco)


def _resumo(id_, *, limite=LIMITE, devolvido_em=None):
    return EmprestimoResumo(id_, 5, "Lucas", 7, "Livro", T0, limite, devolvido_em)


# Bordas do §7 com agora = LIMITE: no instante exato ainda ativo; 1 s depois do limite, atrasado.
AGORA = LIMITE
BORDAS = [
    _resumo(1, limite=AGORA),  # ativo (no limite)
    _resumo(2, limite=AGORA - timedelta(seconds=1)),  # atrasado
    _resumo(3, limite=AGORA + timedelta(seconds=1)),  # ativo
    _resumo(4, limite=AGORA - timedelta(days=9), devolvido_em=AGORA),  # devolvido vencido
    _resumo(5, limite=AGORA + timedelta(days=9), devolvido_em=T0),  # devolvido no prazo
]


@pytest.fixture
def consulta(monkeypatch):
    chamadas = []

    @contextmanager
    def transacao_falsa(config, *, somente_leitura=False):
        chamadas.append(("abre", somente_leitura))
        yield "conexao"

    def buscar(conexao, termo):
        chamadas.append(("buscar", termo))
        return list(BORDAS)

    monkeypatch.setattr(servico, "transacao", transacao_falsa)
    monkeypatch.setattr(servico.repositorio, "buscar_resumos", buscar)
    return chamadas


@pytest.mark.parametrize(
    ("status", "ids"),
    [
        (None, [1, 2, 3, 4, 5]),
        (Situacao.ATIVO, [1, 3]),
        (Situacao.ATRASADO, [2]),
        (Situacao.DEVOLVIDO, [4, 5]),
    ],
)
def test_filtro_por_situacao_nas_bordas(consulta, status, ids):
    resultado = servico.consultar_emprestimos(
        Config(database_url="postgresql://x/y_teste"), RelogioFixo(AGORA), status, "lu"
    )

    assert [e.id for e in resultado.emprestimos] == ids
    assert resultado.agora == AGORA
    assert consulta == [("abre", True), ("buscar", "lu")]


@pytest.mark.parametrize("status", list(Situacao))
def test_filtro_e_resposta_concordam_na_situacao(consulta, status):
    resultado = servico.consultar_emprestimos(
        Config(database_url="postgresql://x/y_teste"), RelogioFixo(AGORA), status, None
    )

    situacoes = {
        emprestimo_resumo_para_json(e, resultado.agora)["status"] for e in resultado.emprestimos
    }
    assert situacoes == {status.value}


class _ConexaoQueGuarda:
    def __init__(self):
        self.consultas = []

    def execute(self, consulta, parametros):
        self.consultas.append((consulta.as_string(None), parametros))

        class _Cursor:
            def fetchall(self):
                return []

        return _Cursor()


@pytest.mark.parametrize("termo", [None, "lu"])
def test_sql_da_busca_de_emprestimos(termo):
    conexao = _ConexaoQueGuarda()

    assert repositorio.buscar_resumos(conexao, termo) == []

    [(texto, parametros)] = conexao.consultas
    assert repositorio.COLUNAS_DA_BUSCA == ("u.nome", "l.titulo")
    assert parametros == {"termo": termo}
    assert texto.endswith("ORDER BY e.emprestado_em DESC, e.id DESC")
    if termo is None:
        assert "WHERE" not in texto
    else:
        assert '"u"."nome"' in texto and '"l"."titulo"' in texto and "cpf" not in texto


@pytest.fixture
def cliente_consulta(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    recebidos = []

    def consultar(config, relogio, status, busca):
        recebidos.append((status, busca))
        return servico.EmprestimosConsultados(emprestimos=BORDAS[:2], agora=AGORA)

    monkeypatch.setattr(servico, "consultar_emprestimos", consultar)
    app = create_app(config=Config(database_url="postgresql://x/y_teste"))
    with TestClient(app) as cliente:
        yield cliente, recebidos


def test_rota_de_consulta_monta_lista_e_total(cliente_consulta):
    cliente, recebidos = cliente_consulta

    resposta = cliente.get("/emprestimos?status=+atrasado+&busca=+Lu+&status=ativo&pagina=0")

    assert resposta.status_code == 200
    dados = resposta.json()
    assert dados["total"] == 2
    assert [(e["emprestimoId"], e["status"]) for e in dados["emprestimos"]] == [
        (1, "ativo"),
        (2, "atrasado"),
    ]
    assert recebidos == [(Situacao.ATRASADO, "Lu")]


@pytest.mark.parametrize(
    ("consulta", "codigo"),
    [
        ("status=ATIVO", "STATUS_INVALIDO"),
        ("status=%00&busca=" + "a" * 101, "STATUS_INVALIDO"),
        ("busca=" + "a" * 101 + "&status=ativo", "BUSCA_INVALIDA"),
        ("busca=%FF", "BUSCA_INVALIDA"),
    ],
)
def test_rota_de_consulta_valida_status_antes_de_busca(cliente_consulta, consulta, codigo):
    cliente, recebidos = cliente_consulta

    resposta = cliente.get(f"/emprestimos?{consulta}")

    assert resposta.status_code == 400
    assert resposta.json()["erro"]["codigo"] == codigo
    assert recebidos == []


# ----------------------------------------------- CT6 registrarDevolucao (sem banco)


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("1", 1),
        ("9001", 9001),
        ("007", 7),
        ("0" * 30 + "5", 5),
        (str(INTEIRO_MAXIMO), INTEIRO_MAXIMO),
        ("0", None),
        ("000", None),
        (str(INTEIRO_MAXIMO + 1), None),
        ("9" * 5000, None),
        ("-1", None),
        ("+1", None),
        (" 1", None),
        ("1 ", None),
        ("1.0", None),
        ("1e3", None),
        ("0x1", None),
        ("abc", None),
        ("", None),
        ("1\x00", None),
        ("\x00", None),
        ("\uff11", None),
        ("\u0661", None),
        ("\ufffd", None),
    ],
    ids=repr,
)
def test_id_do_caminho(texto, esperado):
    assert ler_id_do_caminho(texto) == esperado


def test_saida_do_ct6():
    devolucao = Devolucao(9, 7, 5, datetime(2026, 10, 15, 16, 30), 3)

    assert devolucao_para_json(devolucao) == {
        "emprestimoId": 9,
        "livroId": 7,
        "status": "devolvido",
        "devolvidoEm": "2026-10-15T16:30:00",
        "quantidadeDisponivel": 3,
    }


@pytest.fixture
def devolucao(monkeypatch):
    """Dublês: `estado["linha"]` é o que o UPDATE devolve; `estado["existe"]`, o SELECT."""
    estado = {
        "linha": {"livro_id": 7, "usuario_id": 5, "devolvido_em": T0},
        "existe": True,
        "ops": [],
    }

    @contextmanager
    def transacao_falsa(config, *, somente_leitura=False):
        estado["ops"].append("abre")
        try:
            yield "conexao"
        except BaseException:
            estado["ops"].append("desfaz")
            raise
        estado["ops"].append("confirma")

    def marcar(conexao, emprestimo_id, agora):
        estado["ops"].append(("marcar", emprestimo_id, agora))
        return estado["linha"]

    def existe(conexao, emprestimo_id):
        estado["ops"].append(("existe", emprestimo_id))
        return estado["existe"]

    def devolver_exemplar(conexao, livro_id):
        estado["ops"].append(("repor", livro_id))
        return 3

    def publicar(config, relogio, publicador, payload):
        estado["ops"].append(("publicar", dict(payload)))
        return True

    monkeypatch.setattr(servico, "transacao", transacao_falsa)
    monkeypatch.setattr(servico.repositorio, "marcar_devolvido", marcar)
    monkeypatch.setattr(servico.repositorio, "existe", existe)
    monkeypatch.setattr(servico.repositorio_livros, "devolver_exemplar", devolver_exemplar)
    monkeypatch.setattr(servico, "publicar_ou_guardar", publicar)
    return estado


def _devolver(emprestimo_id):
    return servico.registrar_devolucao(
        Config(database_url="postgresql://x/y_teste"), RelogioFixo(T0), object(), emprestimo_id
    )


def test_devolve_repoe_e_publica_depois_do_commit(devolucao):
    resultado = _devolver(9)

    assert resultado == Devolucao(9, 7, 5, T0, 3)
    assert devolucao["ops"] == [
        "abre",
        ("marcar", 9, T0),
        ("repor", 7),
        "confirma",
        (
            "publicar",
            {
                "tipo": "devolucao_registrada",
                "livroId": 7,
                "usuarioId": 5,
                "emprestimoId": 9,
                "status": "devolvido",
                "quantidadeDisponivel": 3,
                "atualizadaEm": "2026-10-13T19:20:00",
            },
        ),
    ]


@pytest.mark.parametrize(
    ("existe", "codigo"),
    [(False, CodigoErro.EMPRESTIMO_NAO_ENCONTRADO), (True, CodigoErro.EMPRESTIMO_JA_DEVOLVIDO)],
)
def test_sem_linha_no_update_distingue_inexistente_de_ja_devolvido(devolucao, existe, codigo):
    devolucao.update(linha=None, existe=existe)

    with pytest.raises(ErroDominio) as erro:
        _devolver(9)

    assert erro.value.codigo is codigo
    assert devolucao["ops"] == ["abre", ("marcar", 9, T0), ("existe", 9), "desfaz"]


def test_id_invalido_nem_abre_transacao(devolucao):
    with pytest.raises(ErroDominio) as erro:
        _devolver(None)

    assert erro.value.codigo is CodigoErro.EMPRESTIMO_NAO_ENCONTRADO
    assert devolucao["ops"] == []


@pytest.fixture
def cliente_devolucao(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    recebidos = []

    def registrar(config, relogio, publicador, emprestimo_id):
        recebidos.append(emprestimo_id)
        if emprestimo_id is None:
            raise ErroDominio(CodigoErro.EMPRESTIMO_NAO_ENCONTRADO)
        return Devolucao(emprestimo_id, 7, 5, T0, 3)

    monkeypatch.setattr(servico, "registrar_devolucao", registrar)
    app = create_app(config=Config(database_url="postgresql://x/y_teste"))
    with TestClient(app) as cliente:
        yield cliente, recebidos


def test_rota_ignora_o_corpo_e_le_o_id_como_texto(cliente_devolucao):
    cliente, recebidos = cliente_devolucao

    resposta = cliente.patch(
        "/emprestimos/007/devolucao", content=b"\xff lixo", headers={"Content-Type": "text/plain"}
    )

    assert resposta.status_code == 200
    assert resposta.json()["emprestimoId"] == 7
    assert recebidos == [7]


@pytest.mark.parametrize("caminho", ["%00", "1%00", "%FF", "abc", "0", "-1", "%EF%BC%91"])
def test_rota_com_id_invalido_e_emprestimo_nao_encontrado(cliente_devolucao, caminho):
    cliente, recebidos = cliente_devolucao

    resposta = cliente.patch(f"/emprestimos/{caminho}/devolucao")

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "EMPRESTIMO_NAO_ENCONTRADO"
    assert recebidos == [None]
