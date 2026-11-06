"""Usuários: CPF, contato (e-mail ou telefone, §5), ordem do §4, saída e serviço (sem banco)."""

from contextlib import contextmanager
from datetime import datetime

import pytest

from app.config import Config
from app.erros import CodigoErro, ErroDominio
from app.relogio import RelogioFixo
from app.usuarios import servico
from app.usuarios.esquemas import (
    CAMPOS_ENTRADA,
    NovoUsuario,
    Usuario,
    contato,
    e_email,
    e_telefone,
    ler_novo_usuario,
    usuario_para_json,
)

pytestmark = pytest.mark.unitario

VALIDO = {"nome": "Lucas Joaquim", "cpf": "123.456.789-00", "contato": "lucas@email.com"}
INSTANTE = datetime(2026, 10, 13, 19, 20)


def _erro(**alteracoes) -> CodigoErro:
    dados = {k: v for k, v in {**VALIDO, **alteracoes}.items() if v is not ...}
    with pytest.raises(ErroDominio) as erro:
        ler_novo_usuario(dados)
    return erro.value.codigo


# --------------------------------------------------------------------------- e-mail


@pytest.mark.parametrize(
    "valor", ["a@b.c", "Lucas.Joaquim@Email.com.br", "a+b@x.y", "a@b..c", "á@ção.br"]
)
def test_emails_validos(valor):
    assert e_email(valor)


@pytest.mark.parametrize(
    "valor",
    [
        "lucasemail.com",
        "@email.com",
        "lucas@",
        "lucas@email",
        "lucas@.email.com",
        "lucas@email.com.",
        "lucas@@email.com",
        "a@b@c.d",
        "lucas @email.com",
        "lucas@email\t.com",
        "lucas@email.com\n",
        "lucas\r@email.com",
    ],
)
def test_emails_invalidos(valor):
    assert not e_email(valor)


# --------------------------------------------------------------------------- telefone


@pytest.mark.parametrize(
    "valor",
    ["1933334444", "(19) 99999-0000", "+55 19 99999-0000", "+5519999990000", "(+55) 19 3333-4444"],
)
def test_telefones_validos(valor):
    assert e_telefone(valor)


@pytest.mark.parametrize(
    "valor",
    [
        "199999999",
        "55199999900001",
        "++5519999990000",
        "55+19999990000",
        "19.9999.0000",
        "19\t99999-0000",
        "19\n99999-0000",
        "+55\u00a019 99999-0000",
        "\u0661" * 11,
        "+",
        "()",
        "-",
    ],
    ids=repr,
)
def test_telefones_invalidos(valor):
    assert not e_telefone(valor)


# --------------------------------------------------------------------------- contato


def test_contato_tira_os_brancos_das_pontas_e_mantem_o_resto():
    assert contato("\n (19) 3333-4444 \t") == "(19) 3333-4444"
    assert contato("  Lucas@Email.com ") == "Lucas@Email.com"


def test_contato_ate_120_caracteres():
    email = "a" * 114 + "@b.com"
    assert len(email) == 120
    assert contato(email) == email

    with pytest.raises(ErroDominio) as erro:
        contato("a" + email)
    assert erro.value.codigo is CodigoErro.DADOS_INVALIDOS


@pytest.mark.parametrize("valor", ["lucas", "telefone do Lucas", 19999990000, ["a@b.c"]])
def test_contato_que_nao_e_email_nem_telefone(valor):
    with pytest.raises(ErroDominio) as erro:
        contato(valor)

    assert erro.value.codigo is CodigoErro.DADOS_INVALIDOS


# --------------------------------------------------------------------------- corpo do CT3


def test_campos_na_ordem_do_ct3():
    assert CAMPOS_ENTRADA == ("nome", "cpf", "contato")


def test_le_e_normaliza():
    assert ler_novo_usuario({**VALIDO, "nome": "\t Lucas \n", "extra": 1}) == NovoUsuario(
        nome="Lucas", cpf="12345678900", contato="lucas@email.com"
    )


@pytest.mark.parametrize(
    "cpf", ["1234567890", "123456789000", "123/456/789-00", "+12345678900", ".-", "123\t45678900"]
)
def test_cpf_invalido(cpf):
    assert _erro(cpf=cpf) is CodigoErro.DADOS_INVALIDOS


@pytest.mark.parametrize(
    ("alteracoes", "codigo"),
    [
        ({"nome": "a" * 151, "contato": None}, CodigoErro.CAMPOS_OBRIGATORIOS),
        ({"nome": 123, "cpf": ...}, CodigoErro.CAMPOS_OBRIGATORIOS),
        ({"cpf": "123", "contato": "  "}, CodigoErro.CAMPOS_OBRIGATORIOS),
        ({"nome": "a" * 151, "cpf": "123"}, CodigoErro.DADOS_INVALIDOS),
        ({"cpf": "123", "contato": "lucas"}, CodigoErro.DADOS_INVALIDOS),
    ],
)
def test_ordem_do_paragrafo_4(alteracoes, codigo):
    assert _erro(**alteracoes) is codigo


def test_mensagem_do_item_3_cita_o_primeiro_campo_da_tabela():
    with pytest.raises(ErroDominio) as erro:
        ler_novo_usuario({"nome": 1, "cpf": 2, "contato": 3})

    assert "'nome'" in erro.value.mensagem


def test_saida_tem_os_campos_do_ct3_sem_criado_em():
    usuario = Usuario(7, "Lucas", "12345678900", "lucas@email.com", INSTANTE)

    assert usuario_para_json(usuario) == {
        "id": 7,
        "nome": "Lucas",
        "cpf": "12345678900",
        "contato": "lucas@email.com",
    }


# --------------------------------------------------------------------------- serviço


def test_servico_grava_com_o_instante_do_relogio_dentro_da_transacao(monkeypatch):
    chamadas = []

    @contextmanager
    def transacao_falsa(config):
        chamadas.append(("abre", config))
        yield "conexao"
        chamadas.append(("confirma",))

    def inserir_falso(conexao, novo, criado_em):
        chamadas.append(("inserir", conexao, novo, criado_em))
        return "usuario"

    monkeypatch.setattr(servico, "transacao", transacao_falsa)
    monkeypatch.setattr(servico.repositorio, "inserir", inserir_falso)
    config = Config(database_url="postgresql://x/y_teste")
    novo = NovoUsuario("Lucas", "12345678900", "lucas@email.com")

    assert servico.cadastrar_usuario(config, RelogioFixo(INSTANTE), novo) == "usuario"
    assert chamadas == [("abre", config), ("inserir", "conexao", novo, INSTANTE), ("confirma",)]


def test_servico_mapeia_so_a_restricao_de_cpf():
    assert dict(servico.ERROS_POR_RESTRICAO) == {"usuarios_cpf_unico": CodigoErro.CPF_DUPLICADO}


# ----------------------------------------------- CT4 consultarUsuarios (sem banco)


@pytest.mark.parametrize(
    ("termo", "esperado"),
    [
        (None, None),
        ("Lucas", None),
        ("123.456", "123456"),
        ("Lucas 1", "1"),
        ("\u0661\u0662", None),  # dígitos não ASCII não contam
        ("a1b2-3", "123"),
    ],
)
def test_digitos_do_termo(termo, esperado):
    assert servico.digitos_do_termo(termo) == esperado


def test_where_da_consulta_de_usuarios():
    from app.usuarios import repositorio

    assert repositorio._onde(None, None).as_string(None) == ""
    so_nome = repositorio._onde("Lucas", None).as_string(None)
    com_cpf = repositorio._onde("Lucas 1", "1").as_string(None)

    assert so_nome.count("LIKE") == 1 and "cpf" not in so_nome
    assert com_cpf.endswith(") OR cpf LIKE %(padrao_cpf)s")
    assert repositorio._parametros("Lucas 1", "1") == {"termo": "Lucas 1", "padrao_cpf": "%1%"}
    assert repositorio._parametros("Lucas", None) == {"termo": "Lucas", "padrao_cpf": None}


def test_ordem_dos_usuarios_e_alfabetica_por_nome():
    from app.usuarios import repositorio

    assert repositorio._ORDEM.as_string(None) == (
        'ORDER BY lower(unaccent("nome")) COLLATE "C", "nome" COLLATE "C", "id"'
    )


def test_consulta_agrupa_emprestimos_por_usuario_sem_n_mais_1(monkeypatch):
    from app.emprestimos.esquemas import EmprestimoResumo
    from app.parametros import ConsultaPaginada

    ana = Usuario(2, "Ana", "98765432100", "a@b.co", INSTANTE)
    lucas = Usuario(1, "Lucas", "12345678900", "l@b.co", INSTANTE)
    e1 = EmprestimoResumo(10, 1, "Lucas", 7, "L", INSTANTE, INSTANTE, None)
    e2 = EmprestimoResumo(9, 1, "Lucas", 8, "M", INSTANTE, INSTANTE, None)
    chamadas = []

    @contextmanager
    def transacao_falsa(config, *, somente_leitura=False):
        chamadas.append(("abre", somente_leitura))
        yield "conexao"
        chamadas.append(("fecha",))

    def buscar(conexao, termo, digitos, *, limite, deslocamento):
        chamadas.append(("buscar", termo, digitos, limite, deslocamento))
        return [ana, lucas]

    def contar(conexao, termo, digitos):
        chamadas.append(("contar", termo, digitos))
        return 2

    def resumos(conexao, ids):
        chamadas.append(("emprestimos", ids))
        return [e1, e2]

    monkeypatch.setattr(servico, "transacao", transacao_falsa)
    monkeypatch.setattr(servico.repositorio, "buscar", buscar)
    monkeypatch.setattr(servico.repositorio, "contar", contar)
    monkeypatch.setattr(servico.repositorio_emprestimos, "resumos_dos_usuarios", resumos)

    pagina = servico.consultar_usuarios(
        Config(database_url="postgresql://x/y_teste"),
        RelogioFixo(INSTANTE),
        ConsultaPaginada("123.4", 2, 5),
    )

    assert pagina.total == 2
    assert pagina.agora == INSTANTE
    assert [(i.usuario, i.emprestimos) for i in pagina.usuarios] == [(ana, []), (lucas, [e1, e2])]
    assert chamadas == [
        ("abre", True),
        ("buscar", "123.4", "1234", 5, 5),
        ("contar", "123.4", "1234"),
        ("emprestimos", [2, 1]),
        ("fecha",),
    ]


def test_rota_de_consulta_monta_usuario_resumo(monkeypatch):
    from fastapi.testclient import TestClient

    from app.emprestimos.esquemas import EmprestimoResumo
    from app.main import create_app

    recebidas = []
    lucas = Usuario(1, "Lucas", "12345678900", "l@b.co", INSTANTE)
    limite = datetime(2026, 10, 28, 19, 20)
    emprestimo = EmprestimoResumo(10, 1, "Lucas", 7, "Livro", INSTANTE, limite, None)

    def consultar(config, relogio, consulta):
        recebidas.append(consulta)
        return servico.PaginaDeUsuarios(
            usuarios=[servico.UsuarioComEmprestimos(lucas, [emprestimo])],
            total=1,
            agora=datetime(2026, 10, 28, 19, 20, 1),
        )

    monkeypatch.setattr(servico, "consultar_usuarios", consultar)
    app = create_app(config=Config(database_url="postgresql://x/y_teste"))
    with TestClient(app) as cliente:
        resposta = cliente.get("/usuarios?busca=+lu+&pagina=01&tamanho=5&x=%00")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "usuarios": [
            {
                "id": 1,
                "nome": "Lucas",
                "cpf": "12345678900",
                "contato": "l@b.co",
                "emprestimos": [
                    {
                        "emprestimoId": 10,
                        "usuarioId": 1,
                        "usuarioNome": "Lucas",
                        "livroId": 7,
                        "livroTitulo": "Livro",
                        "status": "atrasado",
                        "emprestadoEm": "2026-10-13T19:20:00",
                        "dataLimiteDevolucao": "2026-10-28T19:20:00",
                        "devolvidoEm": None,
                    }
                ],
            }
        ],
        "total": 1,
        "pagina": 1,
        "tamanho": 5,
    }
    assert [(c.busca, c.pagina, c.tamanho) for c in recebidas] == [("lu", 1, 5)]
