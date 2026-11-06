"""Parâmetros de consulta lidos crus (00-convencoes §6; D13)."""

import pytest

from app.erros import CodigoErro, ErroDominio
from app.parametros import (
    PAGINA_PADRAO,
    PARAMETROS_PAGINADOS,
    TAMANHO_PADRAO,
    ConsultaPaginada,
    ler_busca,
    ler_consulta_paginada,
    ler_inteiro,
    ler_opcao,
    primeiros_valores,
    texto_do_parametro,
)
from app.validacao import INTEIRO_MAXIMO

pytestmark = pytest.mark.unitario

NOMES = PARAMETROS_PAGINADOS
PAGINACAO = CodigoErro.PAGINACAO_INVALIDA


def _codigo(funcao, *args, **kwargs) -> CodigoErro:
    with pytest.raises(ErroDominio) as erro:
        funcao(*args, **kwargs)
    return erro.value.codigo


def _consulta(query_string: bytes) -> ConsultaPaginada:
    return ler_consulta_paginada(primeiros_valores(query_string, NOMES))


# --------------------------------------------------------------------------- query string crua


def test_primeiro_valor_de_cada_parametro_conhecido():
    valores = primeiros_valores(b"pagina=2&busca=a&pagina=3&tamanho=&busca=b&x=1", NOMES)

    assert valores == {"pagina": b"2", "busca": b"a", "tamanho": b""}


def test_decodifica_percentual_e_mais():
    valores = primeiros_valores(b"busca=Informa%C3%A7%C3%A3o+de%20dados%2B1", NOMES)

    assert valores == {"busca": "Informação de dados+1".encode()}


def test_nome_codificado_tambem_e_reconhecido():
    assert primeiros_valores(b"b%75sca=x", NOMES) == {"busca": b"x"}


@pytest.mark.parametrize(
    "query_string", [b"", b"&&", b"Pagina=0&TAMANHO=0", b"foo=%FF&bar=%00", b"=1", b"busca"]
)
def test_desconhecidos_e_pedacos_vazios_nao_atrapalham(query_string):
    valores = primeiros_valores(query_string, NOMES)

    assert set(valores) <= {"busca"}
    assert _consulta(query_string) == ConsultaPaginada(None, PAGINA_PADRAO, TAMANHO_PADRAO)


def test_parametro_sem_igual_vale_vazio():
    assert primeiros_valores(b"busca", NOMES) == {"busca": b""}


def test_bytes_invalidos_ficam_crus_ate_a_validacao():
    assert primeiros_valores(b"busca=%FF%00", NOMES) == {"busca": b"\xff\x00"}


# --------------------------------------------------------------------------- texto


@pytest.mark.parametrize(
    "bruto", [b"\xff", b"dados\xc3", b"\xc3\x28", b"\xed\xa0\x80", b"\x00", b"a\x00b"], ids=repr
)
def test_texto_invalido_recebe_o_codigo_do_parametro(bruto):
    assert _codigo(texto_do_parametro, bruto, "x", CodigoErro.STATUS_INVALIDO) is (
        CodigoErro.STATUS_INVALIDO
    )


@pytest.mark.parametrize("bruto", [None, b"", b" ", b"\t\n\r "], ids=repr)
def test_texto_ausente_ou_em_branco_e_none(bruto):
    assert texto_do_parametro(bruto, "x", CodigoErro.BUSCA_INVALIDA) is None


def test_texto_corta_so_os_brancos_do_paragrafo_4():
    assert texto_do_parametro(b" \t a b \n", "x", CodigoErro.BUSCA_INVALIDA) == "a b"
    nbsp = "\u00a0a\u00a0"
    assert texto_do_parametro(nbsp.encode(), "x", CodigoErro.BUSCA_INVALIDA) == nbsp


# --------------------------------------------------------------------------- busca


def test_busca_ate_100_caracteres():
    assert ler_busca(("ç" * 100).encode()) == "ç" * 100
    assert ler_busca((" " + "a" * 100 + "\t").encode()) == "a" * 100
    assert _codigo(ler_busca, ("ç" * 101).encode()) is CodigoErro.BUSCA_INVALIDA


def test_busca_mantem_caracteres_especiais_como_estao():
    assert ler_busca(b"%_\\'\"-") == "%_\\'\"-"


# --------------------------------------------------------------------------- inteiro


def _inteiro(bruto: bytes | None, **kwargs) -> int:
    opcoes = {"padrao": 7, "minimo": 1, "maximo": 100, "codigo": PAGINACAO} | kwargs
    return ler_inteiro(bruto, "tamanho", **opcoes)


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [
        (None, 7),
        (b"", 7),
        (b" \t", 7),
        (b"1", 1),
        (b"01", 1),
        (b"\t100\n", 100),
        (b"0" * 50 + b"5", 5),
    ],
    ids=repr,
)
def test_inteiros_aceitos(bruto, esperado):
    assert _inteiro(bruto) == esperado


@pytest.mark.parametrize(
    "bruto",
    [
        b"0",
        b"-0",
        b"-1",
        b"101",
        b"+1",
        b"1.0",
        b"1e1",
        b"1_0",
        "\u0661".encode(),
        "\uff11".encode(),
        b"1 2",
        b"0x1",
        b"--1",
        b"9" * 5000,
        b"\x00",
        b"1\xff",
    ],
    ids=repr,
)
def test_inteiros_invalidos(bruto):
    assert _codigo(_inteiro, bruto) is PAGINACAO


def test_inteiro_vai_ate_o_maximo_do_paragrafo_4():
    maximo = str(INTEIRO_MAXIMO).encode()
    assert _inteiro(maximo, maximo=INTEIRO_MAXIMO) == INTEIRO_MAXIMO
    assert _codigo(_inteiro, str(INTEIRO_MAXIMO + 1).encode(), maximo=INTEIRO_MAXIMO) is PAGINACAO


# --------------------------------------------------------------------------- consulta paginada


def test_padroes():
    assert _consulta(b"") == ConsultaPaginada(busca=None, pagina=1, tamanho=20)


def test_le_os_tres_parametros():
    assert _consulta(b"busca=+dados+&pagina=02&tamanho=5") == ConsultaPaginada("dados", 2, 5)


@pytest.mark.parametrize(
    ("query_string", "codigo"),
    [
        (b"busca=%00&pagina=0&tamanho=0", CodigoErro.BUSCA_INVALIDA),
        (b"tamanho=0&pagina=0&busca=" + b"a" * 101, CodigoErro.BUSCA_INVALIDA),
        (b"tamanho=abc&pagina=0", PAGINACAO),
        (b"pagina=&pagina=abc&tamanho=0", PAGINACAO),
    ],
)
def test_ordem_busca_pagina_tamanho(query_string, codigo):
    assert _codigo(_consulta, query_string) is codigo


def test_repetido_com_primeiro_vazio_recebe_o_padrao():
    assert _consulta(b"pagina=&pagina=abc").pagina == PAGINA_PADRAO


@pytest.mark.parametrize(
    ("pagina", "tamanho", "deslocamento"),
    [(1, 20, 0), (3, 10, 20), (INTEIRO_MAXIMO, 100, (INTEIRO_MAXIMO - 1) * 100)],
)
def test_deslocamento(pagina, tamanho, deslocamento):
    consulta = ConsultaPaginada(None, pagina, tamanho)

    assert consulta.deslocamento == deslocamento
    assert consulta.deslocamento < 2**63


# ----------------------------------------------- opção exata (status do CT8)

OPCOES = ("ativo", "devolvido", "atrasado")


def _opcao(bruto):
    return ler_opcao(bruto, "status", opcoes=OPCOES, codigo=CodigoErro.STATUS_INVALIDO)


@pytest.mark.parametrize(
    ("bruto", "esperado"),
    [(None, None), (b"", None), (b" \t", None), (b"ativo", "ativo"), (b"\tatrasado\n", "atrasado")],
)
def test_opcao_valida_ou_ausente(bruto, esperado):
    assert _opcao(bruto) == esperado


@pytest.mark.parametrize(
    "bruto", [b"ATIVO", b"Ativo", b"ativos", b"at ivo", b"ativo\x00", b"\xff", b"\xc2\xa0ativo"]
)
def test_opcao_invalida(bruto):
    assert _codigo(_opcao, bruto) is CodigoErro.STATUS_INVALIDO
