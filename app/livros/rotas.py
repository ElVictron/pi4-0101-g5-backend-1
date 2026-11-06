"""Rotas HTTP de livros (CT1, CT2).

Rotas com banco são `def` (D16 e): o FastAPI as roda fora do loop de eventos.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.dependencias import ConfigDaApp, CorpoJson, RelogioDaApp
from app.livros import servico
from app.livros.esquemas import ler_novo_livro, livro_para_json
from app.parametros import PARAMETROS_PAGINADOS, ler_consulta_paginada, primeiros_valores

roteador = APIRouter()


@roteador.post("/livros", status_code=201, response_model=None)
def cadastrar_livro(dados: CorpoJson, config: ConfigDaApp, relogio: RelogioDaApp) -> dict[str, Any]:
    """CT1 · cadastrarLivro."""
    livro = servico.cadastrar_livro(config, relogio, ler_novo_livro(dados))
    return livro_para_json(livro)


@roteador.get("/livros", response_model=None)
def consultar_livros(request: Request, config: ConfigDaApp) -> dict[str, Any]:
    """CT2 · consultarLivros. Parâmetros lidos crus, sem validação do FastAPI (D13)."""
    consulta = ler_consulta_paginada(
        primeiros_valores(request.scope["query_string"], PARAMETROS_PAGINADOS)
    )
    pagina = servico.consultar_livros(config, consulta)
    return {
        "livros": [livro_para_json(livro) for livro in pagina.livros],
        "total": pagina.total,
        "pagina": consulta.pagina,
        "tamanho": consulta.tamanho,
    }
