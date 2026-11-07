"""Regras de `Config.from_env` que os testes de contrato não cobrem (8B, 00-convencoes §10)."""

import pytest

from app.config import Config

pytestmark = pytest.mark.unitario

URL = "postgresql://usuario@localhost/biblioteca"


def test_valores_com_espacos_nas_pontas_sao_aparados():
    config = Config.from_env(
        {
            "DATABASE_URL": f"  {URL}  ",
            "BACKEND2_URL": " https://b2.teste ",
            "BACKEND2_TIMEOUT_SEGUNDOS": " 2.5 ",
            "BACKEND2_VERIFY_TLS": " False ",
            "BACKEND2_CA_BUNDLE": " /ca.pem ",
        }
    )

    assert config.database_url == URL
    assert config.backend2_url == "https://b2.teste"
    assert config.backend2_timeout_segundos == 2.5
    assert config.backend2_verify_tls is False
    assert config.backend2_ca_bundle == "/ca.pem"


@pytest.mark.parametrize("nome", ["BACKEND2_URL", "BACKEND2_CA_BUNDLE", "CORS_ORIGENS"])
def test_valor_so_com_espacos_vale_como_nao_configurado(nome):
    config = Config.from_env({"DATABASE_URL": URL, nome: "   "})

    assert config == Config(database_url=URL)


def test_database_url_so_com_espacos_levanta_value_error():
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Config.from_env({"DATABASE_URL": "   "})


def test_cors_origens_so_com_virgulas_fica_vazio():
    config = Config.from_env({"DATABASE_URL": URL, "CORS_ORIGENS": " , ,, "})

    assert config.cors_origens == ()


@pytest.mark.parametrize("valor", ["abc", "0", "-1", "nan", "inf"])
def test_timeout_invalido_levanta_value_error(valor):
    with pytest.raises(ValueError, match="BACKEND2_TIMEOUT_SEGUNDOS"):
        Config.from_env({"DATABASE_URL": URL, "BACKEND2_TIMEOUT_SEGUNDOS": valor})


@pytest.mark.parametrize("valor", ["sim", "yes", "2", "verdadeiro"])
def test_verify_tls_invalido_levanta_value_error(valor):
    with pytest.raises(ValueError, match="BACKEND2_VERIFY_TLS"):
        Config.from_env({"DATABASE_URL": URL, "BACKEND2_VERIFY_TLS": valor})


def test_variaveis_desconhecidas_sao_ignoradas():
    config = Config.from_env({"DATABASE_URL": URL, "OUTRA": "x", "SSL_CERTFILE": "/c.pem"})

    assert config == Config(database_url=URL)


@pytest.mark.parametrize("valor", ["*", " * ", "https://a.teste,*"])
def test_curinga_em_cors_origens_levanta_value_error(valor):
    with pytest.raises(ValueError, match="CORS_ORIGENS"):
        Config.from_env({"DATABASE_URL": URL, "CORS_ORIGENS": valor})


def test_construtor_tambem_recusa_curinga_em_cors_origens():
    with pytest.raises(ValueError, match="CORS_ORIGENS"):
        Config(database_url=URL, cors_origens=("https://a.teste", "*"))


def test_origem_que_so_contem_asterisco_no_meio_nao_e_o_curinga():
    config = Config.from_env({"DATABASE_URL": URL, "CORS_ORIGENS": "https://*.teste"})

    assert config.cors_origens == ("https://*.teste",)
