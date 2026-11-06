"""Rotas HTTP de empréstimos (CT5, CT8). Rotas com banco são `def` (D16 e)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.dependencias import ConfigDaApp, CorpoJson, PublicadorDaApp, RelogioDaApp
from app.emprestimos import servico
from app.emprestimos.esquemas import (
    Situacao,
    emprestimo_para_json,
    emprestimo_resumo_para_json,
    ler_novo_emprestimo,
)
from app.erros import CodigoErro
from app.parametros import ler_busca, ler_opcao, primeiros_valores

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


@roteador.get("/emprestimos", response_model=None)
def consultar_emprestimos(
    request: Request, config: ConfigDaApp, relogio: RelogioDaApp
) -> dict[str, Any]:
    """CT8 · consultarEmprestimos. Parâmetros crus (D13), na ordem `status`, `busca`."""
    valores = primeiros_valores(request.scope["query_string"], ("status", "busca"))
    status = ler_opcao(
        valores.get("status"),
        "status",
        opcoes=[situacao.value for situacao in Situacao],
        codigo=CodigoErro.STATUS_INVALIDO,
    )
    busca = ler_busca(valores.get("busca"))
    resultado = servico.consultar_emprestimos(
        config, relogio, None if status is None else Situacao(status), busca
    )
    return {
        "emprestimos": [
            emprestimo_resumo_para_json(emprestimo, resultado.agora)
            for emprestimo in resultado.emprestimos
        ],
        "total": len(resultado.emprestimos),
    }
