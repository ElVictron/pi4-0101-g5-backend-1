"""Rotas HTTP de empréstimos (CT5). Rotas com banco são `def` (D16 e)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.dependencias import ConfigDaApp, CorpoJson, PublicadorDaApp, RelogioDaApp
from app.emprestimos import servico
from app.emprestimos.esquemas import emprestimo_para_json, ler_novo_emprestimo

roteador = APIRouter()


@roteador.post("/emprestimos", status_code=201, response_model=None)
def registrar_emprestimo(
    dados: CorpoJson, config: ConfigDaApp, relogio: RelogioDaApp, publicador: PublicadorDaApp
) -> dict[str, Any]:
    """CT5 · registrarEmprestimo."""
    emprestimo = servico.registrar_emprestimo(
        config, relogio, publicador, ler_novo_emprestimo(dados)
    )
    return emprestimo_para_json(emprestimo)
