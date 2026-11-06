"""Configuração da aplicação lida de variáveis de ambiente (00-convencoes §10, agentes.md 8B)."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass

TIMEOUT_PADRAO_SEGUNDOS = 3.0
CURINGA_CORS = "*"

_VERDADEIROS = frozenset({"true", "1"})
_FALSOS = frozenset({"false", "0"})


@dataclass(frozen=True)
class Config:
    """Configuração imutável do Backend 1."""

    database_url: str
    backend2_url: str | None = None
    backend2_timeout_segundos: float = TIMEOUT_PADRAO_SEGUNDOS
    backend2_verify_tls: bool = True
    backend2_ca_bundle: str | None = None
    cors_origens: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # 00-convencoes §9/§10: o curinga liberaria qualquer origem; a configuração é recusada.
        if CURINGA_CORS in self.cors_origens:
            raise ValueError("CORS_ORIGENS não aceita o curinga '*': liste as origens permitidas.")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Config:
        """Monta a configuração a partir de `env` (ou de `os.environ`, se omitido).

        Valores vazios (ou só com espaços) valem como não configurados.
        Levanta `ValueError` se `DATABASE_URL` faltar ou se algum valor for inválido.
        """
        origem: Mapping[str, str] = os.environ if env is None else env

        def ler(nome: str) -> str | None:
            valor = origem.get(nome, "").strip()
            return valor or None

        database_url = ler("DATABASE_URL")
        if database_url is None:
            raise ValueError("A variável de ambiente DATABASE_URL é obrigatória.")

        timeout = ler("BACKEND2_TIMEOUT_SEGUNDOS")
        verify_tls = ler("BACKEND2_VERIFY_TLS")
        cors = ler("CORS_ORIGENS")

        return cls(
            database_url=database_url,
            backend2_url=ler("BACKEND2_URL"),
            backend2_timeout_segundos=(
                TIMEOUT_PADRAO_SEGUNDOS if timeout is None else _ler_timeout(timeout)
            ),
            backend2_verify_tls=True if verify_tls is None else _ler_booleano(verify_tls),
            backend2_ca_bundle=ler("BACKEND2_CA_BUNDLE"),
            cors_origens=() if cors is None else _ler_lista(cors),
        )


def _ler_timeout(valor: str) -> float:
    try:
        segundos = float(valor)
    except ValueError:
        raise ValueError(
            f"BACKEND2_TIMEOUT_SEGUNDOS deve ser um número de segundos, recebido {valor!r}."
        ) from None
    if not math.isfinite(segundos) or segundos <= 0:
        raise ValueError(f"BACKEND2_TIMEOUT_SEGUNDOS deve ser maior que zero, recebido {valor!r}.")
    return segundos


def _ler_booleano(valor: str) -> bool:
    normalizado = valor.lower()
    if normalizado in _VERDADEIROS:
        return True
    if normalizado in _FALSOS:
        return False
    raise ValueError(f"BACKEND2_VERIFY_TLS deve ser true, false, 1 ou 0, recebido {valor!r}.")


def _ler_lista(valor: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in valor.split(",") if item.strip())
