"""Rotas HTTP de usuários (CT3). Rotas com banco são `def` (D16 e)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.dependencias import ConfigDaApp, CorpoJson, RelogioDaApp
from app.usuarios import servico
from app.usuarios.esquemas import ler_novo_usuario, usuario_para_json

roteador = APIRouter()


@roteador.post("/usuarios", status_code=201, response_model=None)
def cadastrar_usuario(
    dados: CorpoJson, config: ConfigDaApp, relogio: RelogioDaApp
) -> dict[str, Any]:
    """CT3 · cadastrarUsuario."""
    usuario = servico.cadastrar_usuario(config, relogio, ler_novo_usuario(dados))
    return usuario_para_json(usuario)
