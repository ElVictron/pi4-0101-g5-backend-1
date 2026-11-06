"""Criação da aplicação FastAPI do Backend 1 (agentes.md 8B; 00-convencoes §3 e §9).

Para servir: `uvicorn --factory app.main:create_app` (TLS por `--ssl-certfile`/`--ssl-keyfile`).
"""

from __future__ import annotations

from fastapi import FastAPI
from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.types import Receive, Scope, Send

from app.config import Config
from app.erros import CapturaDeErroInterno, registrar_tratadores
from app.relogio import Relogio, RelogioSistema

METODOS_CORS = ("GET", "POST", "PATCH")


class CorsNoFormatoDeErro(CORSMiddleware):
    """CORS do Starlette, mas um preflight recusado não devolve texto puro.

    Se a origem (ou o método pedido) não é permitida, o pedido segue como um `OPTIONS`
    comum, sem cabeçalhos CORS, e recebe o erro no formato padrão (405/404).
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] == "OPTIONS":
            headers = Headers(scope=scope)
            if "origin" in headers and "access-control-request-method" in headers:
                resposta = self.preflight_response(request_headers=headers)
                if resposta.status_code == 200:
                    await resposta(scope, receive, send)
                else:
                    await self.app(scope, receive, send)
                return
        await super().__call__(scope, receive, send)


def create_app(config: Config | None = None, relogio: Relogio | None = None) -> FastAPI:
    """Cria a aplicação. Sem argumentos, usa `Config.from_env()` e `RelogioSistema()`.

    Não abre conexão com o banco aqui.
    """
    config = config if config is not None else Config.from_env()
    relogio = relogio if relogio is not None else RelogioSistema()

    # Sem documentação automática (D12) e sem redirecionar barra final (00-convencoes §3).
    app = FastAPI(
        title="Backend 1 — Biblioteca",
        version="0.1.0",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
        redirect_slashes=False,
    )
    app.state.config = config
    app.state.relogio = relogio

    registrar_tratadores(app)
    # O último middleware adicionado fica por fora: CORS envolve a captura de erro interno.
    app.add_middleware(CapturaDeErroInterno)
    app.add_middleware(
        CorsNoFormatoDeErro,
        allow_origins=config.cors_origens,
        allow_methods=METODOS_CORS,
    )

    @app.get("/saude")
    async def saude() -> dict[str, str]:
        """Verificação de vida da aplicação; não consulta o banco."""
        return {"status": "ok"}

    return app
