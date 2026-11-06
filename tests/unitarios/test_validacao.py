"""Validador reutilizável dos cadastros (00-convencoes §4 e §5)."""

import pytest

from app.erros import CodigoErro, ErroDominio
from app.validacao import BRANCOS, INTEIRO_MAXIMO, digitos, exigir_presentes, inteiro, texto

pytestmark = pytest.mark.unitario


def _codigo(funcao, *args, **kwargs) -> CodigoErro:
    with pytest.raises(ErroDominio) as erro:
        funcao(*args, **kwargs)
    return erro.value.codigo


# --------------------------------------------------------------------------- exigir_presentes


@pytest.mark.parametrize("valor", [None, "", " ", "\t\n\r ", ...], ids=repr)
def test_ausente_nulo_ou_em_branco_e_campos_obrigatorios(valor):
    dados = {} if valor is ... else {"a": valor}

    assert _codigo(exigir_presentes, dados, ["a"]) is CodigoErro.CAMPOS_OBRIGATORIOS


@pytest.mark.parametrize("valor", [0, False, [], {}, "x", "\u00a0"], ids=repr)
def test_valores_presentes_passam_mesmo_com_tipo_errado(valor):
    exigir_presentes({"a": valor}, ["a"])


def test_mensagem_cita_o_primeiro_campo_na_ordem_pedida():
    with pytest.raises(ErroDominio) as erro:
        exigir_presentes({"b": None}, ["a", "b"])

    assert "'a'" in erro.value.mensagem


def test_brancos_sao_espaco_tabulacao_e_quebra_de_linha():
    assert set(BRANCOS) == {" ", "\t", "\n", "\r"}


# --------------------------------------------------------------------------- texto


def test_texto_remove_so_os_brancos_das_pontas():
    assert texto(" \t Dom  Casmurro \r\n", "titulo", maximo=200) == "Dom  Casmurro"


def test_texto_nao_remove_espaco_inseparavel():
    assert texto("\u00a0a\u00a0", "titulo", maximo=200) == "\u00a0a\u00a0"


@pytest.mark.parametrize("valor", [1, 1.5, True, ["a"], {"a": 1}, None], ids=repr)
def test_texto_com_outro_tipo_e_invalido(valor):
    assert _codigo(texto, valor, "titulo", maximo=10) is CodigoErro.DADOS_INVALIDOS


def test_texto_conta_caracteres_e_nao_bytes():
    assert texto("ç" * 10, "titulo", maximo=10) == "ç" * 10
    assert _codigo(texto, "ç" * 11, "titulo", maximo=10) is CodigoErro.DADOS_INVALIDOS


def test_texto_usa_o_codigo_informado():
    erro = _codigo(texto, 1, "x", maximo=1, codigo=CodigoErro.BUSCA_INVALIDA)

    assert erro is CodigoErro.BUSCA_INVALIDA


# --------------------------------------------------------------------------- inteiro


@pytest.mark.parametrize("valor", [True, False, 3.0, 3.5, "3", [3], {"v": 3}, None], ids=repr)
def test_inteiro_so_aceita_int_json(valor):
    assert _codigo(inteiro, valor, "n", minimo=1) is CodigoErro.DADOS_INVALIDOS


@pytest.mark.parametrize("valor", [0, -1, INTEIRO_MAXIMO + 1, 10**30])
def test_inteiro_fora_da_faixa(valor):
    erro = _codigo(inteiro, valor, "n", minimo=1, codigo=CodigoErro.QUANTIDADE_INVALIDA)

    assert erro is CodigoErro.QUANTIDADE_INVALIDA


@pytest.mark.parametrize("valor", [1, INTEIRO_MAXIMO])
def test_inteiro_nas_bordas(valor):
    assert inteiro(valor, "n", minimo=1) == valor


def test_inteiro_maximo_e_o_do_integer_do_banco():
    assert INTEIRO_MAXIMO == 2**31 - 1


# --------------------------------------------------------------------------- digitos


ISBN = {"separadores": "- ", "tamanhos": (10, 13)}


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("978-0-00-000000-1", "9780000000001"),
        ("\t978 0 00 000000 1\n", "9780000000001"),
        ("0306406152", "0306406152"),
    ],
)
def test_digitos_normaliza(valor, esperado):
    assert digitos(valor, "isbn", **ISBN) == esperado


@pytest.mark.parametrize(
    "valor",
    [
        "978000000000A",
        "978.0.00.000000.1",
        "978\t0000000001",
        "9" * 11,
        "9" * 14,
        "-",
        "\u0661" * 10,  # dígitos arábico-índicos: str.isdigit() aceitaria
        "\u00b2" * 10,  # sobrescrito
        "\uff19" * 13,  # dígito de largura total
    ],
    ids=repr,
)
def test_digitos_invalidos(valor):
    assert _codigo(digitos, valor, "isbn", **ISBN) is CodigoErro.DADOS_INVALIDOS


@pytest.mark.parametrize("valor", [9780000000001, True, None, ["1"]], ids=repr)
def test_digitos_exige_texto(valor):
    assert _codigo(digitos, valor, "isbn", **ISBN) is CodigoErro.DADOS_INVALIDOS


def test_digitos_mensagem_cita_os_tamanhos():
    with pytest.raises(ErroDominio) as erro:
        digitos("123", "isbn", **ISBN)

    assert "10 ou 13" in erro.value.mensagem
