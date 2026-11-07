"""CORS: preflight recusado também responde no formato de erro (00-convencoes §3 e §9)."""

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.main import create_app

pytestmark = pytest.mark.unitario

FRONT = "https://front.teste"


@pytest.fixture
def cliente():
    app = create_app(config=Config(database_url="postgresql://x/y", cors_origens=(FRONT,)))
    with TestClient(app) as cliente:
        yield cliente


def _preflight(cliente, origem: str, metodo: str, caminho: str = "/saude"):
    return cliente.options(
        caminho, headers={"Origin": origem, "Access-Control-Request-Method": metodo}
    )


@pytest.mark.parametrize("metodo", ["GET", "POST", "PATCH"])
def test_preflight_aceito_para_os_metodos_da_api(cliente, metodo):
    resposta = _preflight(cliente, FRONT, metodo)

    assert resposta.status_code == 200
    assert resposta.headers["access-control-allow-origin"] == FRONT
    assert metodo in resposta.headers["access-control-allow-methods"]


def test_preflight_aceita_content_type_json(cliente):
    resposta = cliente.options(
        "/saude",
        headers={
            "Origin": FRONT,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert resposta.status_code == 200


@pytest.mark.parametrize(
    ("origem", "metodo"), [("https://outro.teste", "GET"), (FRONT, "DELETE"), (FRONT, "PUT")]
)
def test_preflight_recusado_vira_options_comum_no_formato_de_erro(cliente, origem, metodo):
    resposta = _preflight(cliente, origem, metodo)

    assert resposta.status_code == 405
    assert resposta.json()["erro"]["codigo"] == "ROTA_NAO_ENCONTRADA"
    assert "access-control-allow-origin" not in resposta.headers


def test_preflight_recusado_em_rota_inexistente_e_404(cliente):
    resposta = _preflight(cliente, "https://outro.teste", "GET", "/nao-existe")

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "ROTA_NAO_ENCONTRADA"


def test_options_sem_preflight_e_405(cliente):
    resposta = cliente.options("/saude", headers={"Origin": FRONT})

    assert resposta.status_code == 405
    assert resposta.json()["erro"]["codigo"] == "ROTA_NAO_ENCONTRADA"
