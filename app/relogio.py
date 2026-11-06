"""Relógio injetável (00-convencoes §7, agentes.md 8B).

Todo "agora" da aplicação vem de um `Relogio`: datas sem fuso, no horário de
`America/Sao_Paulo`, sem frações de segundo.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

FUSO_SAO_PAULO = ZoneInfo("America/Sao_Paulo")


class Relogio(Protocol):
    """Fonte do instante atual da aplicação."""

    def agora(self) -> datetime:
        """Instante atual, sem fuso (horário de São Paulo) e sem microssegundos."""
        ...


class RelogioSistema:
    """Relógio real: hora do sistema convertida para o horário de São Paulo."""

    def agora(self) -> datetime:
        return datetime.now(FUSO_SAO_PAULO).replace(tzinfo=None, microsecond=0)


class RelogioFixo:
    """Relógio parado num instante, que só anda com `avancar` (para testes)."""

    def __init__(self, instante: datetime) -> None:
        if instante.tzinfo is not None:
            raise ValueError("O instante do RelogioFixo deve ser sem fuso (horário de São Paulo).")
        self._instante = instante

    def agora(self) -> datetime:
        return self._instante.replace(microsecond=0)

    def avancar(self, delta: timedelta) -> None:
        self._instante += delta
