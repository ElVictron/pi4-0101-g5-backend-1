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
        "+55 19 99999-0000",
        "١" * 11,
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
