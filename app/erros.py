"""Códigos de erro, status HTTP e formato único de resposta de erro (00-convencoes §3).

Toda resposta de erro tem o corpo `{"erro": {"codigo": ..., "mensagem": ...}}`.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class CodigoErro(StrEnum):
    """Códigos de erro das fichas (CT1 a CT8) e de infraestrutura."""

    CAMPOS_OBRIGATORIOS = "CAMPOS_OBRIGATORIOS"
    DADOS_INVALIDOS = "DADOS_INVALIDOS"
    QUANTIDADE_INVALIDA = "QUANTIDADE_INVALIDA"
    PAGINACAO_INVALIDA = "PAGINACAO_INVALIDA"
    BUSCA_INVALIDA = "BUSCA_INVALIDA"
    STATUS_INVALIDO = "STATUS_INVALIDO"
    USUARIO_NAO_ENCONTRADO = "USUARIO_NAO_ENCONTRADO"
    LIVRO_NAO_ENCONTRADO = "LIVRO_NAO_ENCONTRADO"
    EMPRESTIMO_NAO_ENCONTRADO = "EMPRESTIMO_NAO_ENCONTRADO"
    ROTA_NAO_ENCONTRADA = "ROTA_NAO_ENCONTRADA"
    ISBN_DUPLICADO = "ISBN_DUPLICADO"
    CPF_DUPLICADO = "CPF_DUPLICADO"
    LIVRO_INDISPONIVEL = "LIVRO_INDISPONIVEL"
    EMPRESTIMO_JA_DEVOLVIDO = "EMPRESTIMO_JA_DEVOLVIDO"
    ERRO_INTERNO = "ERRO_INTERNO"


STATUS_POR_CODIGO: Mapping[CodigoErro, int] = MappingProxyType(
    {
        CodigoErro.CAMPOS_OBRIGATORIOS: 400,
        CodigoErro.DADOS_INVALIDOS: 400,
        CodigoErro.QUANTIDADE_INVALIDA: 400,
        CodigoErro.PAGINACAO_INVALIDA: 400,
        CodigoErro.BUSCA_INVALIDA: 400,
        CodigoErro.STATUS_INVALIDO: 400,
        CodigoErro.USUARIO_NAO_ENCONTRADO: 404,
        CodigoErro.LIVRO_NAO_ENCONTRADO: 404,
        CodigoErro.EMPRESTIMO_NAO_ENCONTRADO: 404,
        CodigoErro.ROTA_NAO_ENCONTRADA: 404,
        CodigoErro.ISBN_DUPLICADO: 409,
        CodigoErro.CPF_DUPLICADO: 409,
        CodigoErro.LIVRO_INDISPONIVEL: 409,
        CodigoErro.EMPRESTIMO_JA_DEVOLVIDO: 409,
        CodigoErro.ERRO_INTERNO: 500,
    }
)

MENSAGENS_PADRAO: Mapping[CodigoErro, str] = MappingProxyType(
    {
        CodigoErro.CAMPOS_OBRIGATORIOS: "Preencha todos os campos obrigatórios.",
        CodigoErro.DADOS_INVALIDOS: "Os dados enviados são inválidos.",
        CodigoErro.QUANTIDADE_INVALIDA: "A quantidade de exemplares deve ser um inteiro maior "
        "ou igual a 1.",
        CodigoErro.PAGINACAO_INVALIDA: "Os parâmetros de paginação são inválidos.",
        CodigoErro.BUSCA_INVALIDA: "O termo de busca é inválido.",
        CodigoErro.STATUS_INVALIDO: "O status informado é inválido.",
        CodigoErro.USUARIO_NAO_ENCONTRADO: "Usuário não encontrado.",
        CodigoErro.LIVRO_NAO_ENCONTRADO: "Livro não encontrado.",
        CodigoErro.EMPRESTIMO_NAO_ENCONTRADO: "Empréstimo não encontrado.",
        CodigoErro.ROTA_NAO_ENCONTRADA: "Rota não encontrada.",
        CodigoErro.ISBN_DUPLICADO: "Já existe um livro com este ISBN.",
        CodigoErro.CPF_DUPLICADO: "Já existe um usuário com este CPF.",
        CodigoErro.LIVRO_INDISPONIVEL: "Não há exemplar disponível deste livro.",
        CodigoErro.EMPRESTIMO_JA_DEVOLVIDO: "Este empréstimo já foi devolvido.",
        CodigoErro.ERRO_INTERNO: "Erro interno do servidor.",
    }
)


class ErroDominio(Exception):
    """Erro previsto pela especificação: vira resposta HTTP com código e mensagem."""

    def __init__(self, codigo: CodigoErro, mensagem: str | None = None) -> None:
        self.codigo = codigo
        self.mensagem = mensagem or MENSAGENS_PADRAO[codigo]
        super().__init__(self.mensagem)

    @property
    def status_http(self) -> int:
        return STATUS_POR_CODIGO[self.codigo]


def corpo_de_erro(codigo: CodigoErro, mensagem: str | None = None) -> dict[str, dict[str, str]]:
    """Corpo JSON padrão de erro."""
    return {"erro": {"codigo": codigo.value, "mensagem": mensagem or MENSAGENS_PADRAO[codigo]}}


def resposta_de_erro(
    codigo: CodigoErro,
    mensagem: str | None = None,
    *,
    status_http: int | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Resposta HTTP de erro; o status vem da tabela, salvo se informado (ex.: 405)."""
    return JSONResponse(
        corpo_de_erro(codigo, mensagem),
        status_code=status_http if status_http is not None else STATUS_POR_CODIGO[codigo],
        headers=dict(headers) if headers else None,
    )


# --------------------------------------------------------------------------- tratadores


async def tratar_erro_dominio(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ErroDominio)
    return resposta_de_erro(exc.codigo, exc.mensagem)


async def tratar_http_exception(_request: Request, exc: Exception) -> JSONResponse:
    """Erros HTTP do roteamento e do framework, convertidos para o formato padrão.

    404 (rota inexistente) e 405 (método não permitido) → `ROTA_NAO_ENCONTRADA`;
    400 (corpo que o framework não conseguiu ler) → `DADOS_INVALIDOS`; o resto → 500.
    """
    assert isinstance(exc, StarletteHTTPException)
    if exc.status_code in (404, 405):
        return resposta_de_erro(
            CodigoErro.ROTA_NAO_ENCONTRADA, status_http=exc.status_code, headers=exc.headers
        )
    if exc.status_code == 400:
        return resposta_de_erro(CodigoErro.DADOS_INVALIDOS)
    return resposta_de_erro(CodigoErro.ERRO_INTERNO)


async def tratar_validacao(_request: Request, _exc: Exception) -> JSONResponse:
    """Validação automática do FastAPI (ex.: corpo que não é JSON) → `DADOS_INVALIDOS`."""
    return resposta_de_erro(CodigoErro.DADOS_INVALIDOS)


async def tratar_erro_inesperado(_request: Request, _exc: Exception) -> JSONResponse:
    """Último recurso: nunca expõe detalhes internos."""
    return resposta_de_erro(CodigoErro.ERRO_INTERNO)


class CapturaDeErroInterno:
    """Middleware ASGI que transforma exceção não prevista em 500 `ERRO_INTERNO`.

    Fica dentro do CORS, para que a resposta de erro também leve os cabeçalhos CORS.
    A exceção é registrada no log; o cliente recebe só a mensagem genérica.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        resposta_iniciada = False

        async def enviar(mensagem: Message) -> None:
            nonlocal resposta_iniciada
            if mensagem["type"] == "http.response.start":
                resposta_iniciada = True
            await send(mensagem)

        try:
            await self.app(scope, receive, enviar)
        except Exception:
            logger.exception("Erro não previsto em %s %s", scope["method"], scope["path"])
            if resposta_iniciada:
                raise
            await resposta_de_erro(CodigoErro.ERRO_INTERNO)(scope, receive, send)


def registrar_tratadores(app: FastAPI) -> None:
    """Liga todos os tratadores de erro na aplicação."""
    app.add_exception_handler(ErroDominio, tratar_erro_dominio)
    app.add_exception_handler(StarletteHTTPException, tratar_http_exception)
    app.add_exception_handler(RequestValidationError, tratar_validacao)
    app.add_exception_handler(Exception, tratar_erro_inesperado)
