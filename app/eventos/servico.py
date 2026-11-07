"""Publicar depois do commit e, se falhar, guardar o evento (D6, P10, §8)."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import psycopg

from app.config import Config
from app.db import transacao
from app.eventos import repositorio
from app.eventos.publicador import PublicadorDeEventos
from app.relogio import Relogio

logger = logging.getLogger(__name__)


def publicar_ou_guardar(
    config: Config,
    relogio: Relogio,
    publicador: PublicadorDeEventos,
    payload: Mapping[str, Any],
) -> bool:
    """Uma tentativa de publicação; na falha, grava em `eventos_pendentes`.

    Nunca levanta exceção: a operação do cliente já foi confirmada (§8). Devolve `True`
    se o Backend 2 aceitou o evento.
    """
    try:
        motivo = publicador.publicar(payload)
    except Exception:  # publicador fora do contrato: trata como falha, sem derrubar nada
        motivo = "erro inesperado na publicação"
    if motivo is None:
        return True

    logger.warning("Evento %s não publicado no Backend 2: %s", payload.get("tipo"), motivo)
    try:
        with transacao(config) as conexao:
            repositorio.inserir(conexao, payload, motivo, relogio.agora())
    except Exception as exc:
        # Sem texto do banco nem dados do evento no log (D16 d, §8).
        logger.error(
            "Falha ao guardar evento pendente %s: %s (sqlstate=%s)",
            payload.get("tipo"),
            type(exc).__name__,
            exc.sqlstate if isinstance(exc, psycopg.Error) else None,
        )
    return False
