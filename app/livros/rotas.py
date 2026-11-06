"""Rotas HTTP de livros (CT1).

Rotas com banco são `def` (D16 e): o FastAPI as roda fora do loop de eventos.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.dependencias import ConfigDaApp, CorpoJson, RelogioDaApp
from app.livros import servico
from app.livros.esquemas import ler_novo_livro, livro_para_json

roteador = APIRouter()


@roteador.post("/livros", status_code=201, response_model=None)
def cadastrar_livro(dados: CorpoJson, config: ConfigDaApp, relogio: RelogioDaApp) -> dict[str, Any]:
    """CT1 · cadastrarLivro."""
    livro = servico.cadastrar_livro(config, relogio, ler_novo_livro(dados))
    return livro_para_json(livro)
