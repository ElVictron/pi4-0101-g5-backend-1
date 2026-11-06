"""Dependências FastAPI compartilhadas pelas rotas: configuração, relógio, publicador e corpo."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, Request

from app.config import Config
from app.entrada import corpo_json
from app.eventos.publicador import PublicadorDeEventos
from app.relogio import Relogio


def obter_config(request: Request) -> Config:
    return request.app.state.config


def obter_relogio(request: Request) -> Relogio:
    return request.app.state.relogio


def obter_publicador(request: Request) -> PublicadorDeEventos:
    return request.app.state.publicador


ConfigDaApp = Annotated[Config, Depends(obter_config)]
RelogioDaApp = Annotated[Relogio, Depends(obter_relogio)]
CorpoJson = Annotated[dict[str, Any], Depends(corpo_json)]
PublicadorDaApp = Annotated[PublicadorDeEventos, Depends(obter_publicador)]
