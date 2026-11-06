"""Tabela de status, formato de erro e tratadores (00-convencoes §3)."""

import asyncio
import json
from datetime import datetime

import pytest
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException

from app.config import Config
from app.erros import (
    MENSAGENS_PADRAO,
    STATUS_POR_CODIGO,
    CodigoErro,
    ErroDominio,
    corpo_de_erro,
    resposta_de_erro,
    tratar_erro_inesperado,
)
from app.main import create_app
from app.relogio import RelogioFixo

pytestmark = pytest.mark.unitario

# 00-convencoes §3, tabela de status
TABELA_DA_CONVENCAO = {
    400: {
        "CAMPOS_OBRIGATORIOS",
        "DADOS_INVALIDOS",
        "QUANTIDADE_INVALIDA",
        "PAGINACAO_INVALIDA",
        "BUSCA_INVALIDA",
        "STATUS_INVALIDO",
    },
    404: {
        "USUARIO_NAO_ENCONTRADO",
        "LIVRO_NAO_ENCONTRADO",
        "EMPRESTIMO_NAO_ENCONTRADO",
        "ROTA_NAO_ENCONTRADA",
    },
    409: {"ISBN_DUPLICADO", "CPF_DUPLICADO", "LIVRO_INDISPONIVEL", "EMPRESTIMO_JA_DEVOLVIDO"},
    500: {"ERRO_INTERNO"},
}


def _corpo(resposta) -> dict:
    return json.loads(resposta.body)


def _assert_erro(resposta, status: int, codigo: str) -> None:
    assert resposta.status_code == status
    assert resposta.headers["content-type"].startswith("application/json")
    corpo = resposta.json()
    assert set(corpo) == {"erro"}
    assert set(corpo["erro"]) == {"codigo", "mensagem"}
    assert corpo["erro"]["codigo"] == codigo
    assert corpo["erro"]["mensagem"].strip()


# --------------------------------------------------------------------------- tabela


def test_tabela_de_status_e_exatamente_a_da_convencao():
    obtida: dict[int, set[str]] = {}
    for codigo, status in STATUS_POR_CODIGO.items():
        obtida.setdefault(status, set()).add(codigo.value)

    assert obtida == TABELA_DA_CONVENCAO
    assert set(STATUS_POR_CODIGO) == set(CodigoErro)


def test_todo_codigo_tem_mensagem_padrao_nao_vazia():
    assert set(MENSAGENS_PADRAO) == set(CodigoErro)
    assert all(mensagem.strip() for mensagem in MENSAGENS_PADRAO.values())


def test_valor_do_codigo_e_o_proprio_nome():
    assert all(codigo.value == codigo.name for codigo in CodigoErro)


# --------------------------------------------------------------------------- formato


def test_erro_dominio_usa_mensagem_padrao_e_status_da_tabela():
    erro = ErroDominio(CodigoErro.ISBN_DUPLICADO)

    assert erro.mensagem == MENSAGENS_PADRAO[CodigoErro.ISBN_DUPLICADO]
    assert erro.status_http == 409
    assert str(erro) == erro.mensagem


def test_erro_dominio_aceita_mensagem_propria():
    erro = ErroDominio(CodigoErro.DADOS_INVALIDOS, "CPF deve ter 11 dígitos.")

    assert erro.mensagem == "CPF deve ter 11 dígitos."


def test_corpo_de_erro():
    assert corpo_de_erro(CodigoErro.LIVRO_INDISPONIVEL, "Sem exemplar.") == {
        "erro": {"codigo": "LIVRO_INDISPONIVEL", "mensagem": "Sem exemplar."}
    }


def test_resposta_de_erro_usa_status_da_tabela_ou_o_informado():
    padrao = resposta_de_erro(CodigoErro.CPF_DUPLICADO)
    forcada = resposta_de_erro(
        CodigoErro.ROTA_NAO_ENCONTRADA, status_http=405, headers={"Allow": "GET"}
    )

    assert padrao.status_code == 409
    assert _corpo(padrao)["erro"]["codigo"] == "CPF_DUPLICADO"
    assert forcada.status_code == 405
    assert forcada.headers["allow"] == "GET"


def test_tratador_de_ultimo_recurso_nao_vaza_detalhe():
    resposta = asyncio.run(tratar_erro_inesperado(None, RuntimeError("senha=segredo")))  # type: ignore[arg-type]

    assert resposta.status_code == 500
    assert "segredo" not in resposta.body.decode()
    assert _corpo(resposta)["erro"]["codigo"] == "ERRO_INTERNO"


# ------------------------------------------------------------------- tratadores na aplicação


@pytest.fixture
def aplicacao():
    app = create_app(
        config=Config(database_url="postgresql://ninguem@localhost/nada"),
        relogio=RelogioFixo(datetime(2026, 10, 13, 19, 20)),
    )

    @app.get("/teste/dominio")
    async def dominio():
        raise ErroDominio(CodigoErro.LIVRO_NAO_ENCONTRADO)

    @app.get("/teste/explode")
    async def explode():
        raise RuntimeError("detalhe interno: senha=segredo")

    @app.get("/teste/http/{status}")
    async def http(status: int):
        raise HTTPException(status_code=status)

    @app.get("/teste/inteiro")
    async def inteiro(numero: int):
        return {"numero": numero}

    @app.get("/teste/fluxo")
    async def fluxo():
        async def gerar():
            yield b"inicio"
            raise RuntimeError("quebrou no meio")

        return StreamingResponse(gerar())

    return app


@pytest.fixture
def cliente(aplicacao):
    with TestClient(aplicacao, raise_server_exceptions=False) as cliente:
        yield cliente


def test_create_app_guarda_config_e_relogio_no_estado():
    config = Config(database_url="postgresql://x/y")
    relogio = RelogioFixo(datetime(2026, 1, 1))

    app = create_app(config=config, relogio=relogio)

    assert app.state.config is config
    assert app.state.relogio is relogio


def test_erro_dominio_vira_resposta_no_formato(cliente):
    _assert_erro(cliente.get("/teste/dominio"), 404, "LIVRO_NAO_ENCONTRADO")


def test_excecao_nao_prevista_vira_500_sem_detalhe(cliente):
    resposta = cliente.get("/teste/explode")

    _assert_erro(resposta, 500, "ERRO_INTERNO")
    assert "segredo" not in resposta.text
    assert "RuntimeError" not in resposta.text


def test_excecao_depois_de_iniciar_a_resposta_e_repassada(aplicacao):
    with TestClient(aplicacao) as cliente, pytest.raises(RuntimeError, match="quebrou"):
        cliente.get("/teste/fluxo")


def test_500_leva_cabecalho_cors_da_origem_permitida():
    app = create_app(
        config=Config(database_url="postgresql://x/y", cors_origens=("https://front.teste",))
    )

    @app.get("/teste/explode")
    async def explode():
        raise RuntimeError("x")

    with TestClient(app, raise_server_exceptions=False) as cliente:
        resposta = cliente.get("/teste/explode", headers={"Origin": "https://front.teste"})

    _assert_erro(resposta, 500, "ERRO_INTERNO")
    assert resposta.headers["access-control-allow-origin"] == "https://front.teste"


@pytest.mark.parametrize(
    ("status", "esperado", "codigo"),
    [
        (404, 404, "ROTA_NAO_ENCONTRADA"),
        (405, 405, "ROTA_NAO_ENCONTRADA"),
        (400, 400, "DADOS_INVALIDOS"),
        (418, 500, "ERRO_INTERNO"),
        (503, 500, "ERRO_INTERNO"),
    ],
)
def test_http_exception_vira_formato_padrao(cliente, status, esperado, codigo):
    _assert_erro(cliente.get(f"/teste/http/{status}"), esperado, codigo)


def test_405_informa_metodos_permitidos(cliente):
    resposta = cliente.post("/saude")

    _assert_erro(resposta, 405, "ROTA_NAO_ENCONTRADA")
    assert resposta.headers["allow"] == "GET"


def test_validacao_automatica_vira_dados_invalidos(cliente):
    _assert_erro(cliente.get("/teste/inteiro", params={"numero": "abc"}), 400, "DADOS_INVALIDOS")


@pytest.mark.parametrize(
    "caminho",
    ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect", "/saude/", "/teste/dominio/"],
)
def test_documentacao_e_barra_final_sao_rota_inexistente(cliente, caminho):
    resposta = cliente.get(caminho, follow_redirects=False)

    _assert_erro(resposta, 404, "ROTA_NAO_ENCONTRADA")
    assert "location" not in resposta.headers
