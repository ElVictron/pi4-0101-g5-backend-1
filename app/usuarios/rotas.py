"""Rotas HTTP de usuários (CT3, CT4). Rotas com banco são `def` (D16 e)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.dependencias import ConfigDaApp, CorpoJson, RelogioDaApp
from app.emprestimos.esquemas import emprestimo_resumo_para_json
from app.parametros import PARAMETROS_PAGINADOS, ler_consulta_paginada, primeiros_valores
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


@roteador.get("/usuarios", response_model=None)
def consultar_usuarios(
    request: Request, config: ConfigDaApp, relogio: RelogioDaApp
) -> dict[str, Any]:
    """CT4 · consultarUsuarios. Parâmetros lidos crus, sem validação do FastAPI (D13)."""
    consulta = ler_consulta_paginada(
        primeiros_valores(request.scope["query_string"], PARAMETROS_PAGINADOS)
    )
    pagina = servico.consultar_usuarios(config, relogio, consulta)
    return {
        "usuarios": [
            usuario_para_json(item.usuario)
            | {
                "emprestimos": [
                    emprestimo_resumo_para_json(emprestimo, pagina.agora)
                    for emprestimo in item.emprestimos
                ]
            }
            for item in pagina.usuarios
        ],
        "total": pagina.total,
        "pagina": consulta.pagina,
        "tamanho": consulta.tamanho,
    }
