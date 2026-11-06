"""SQL da tabela `usuarios` (CT10). Recebe uma conexão já dentro de `transacao`."""

from __future__ import annotations

from datetime import datetime

from app.db import Conexao
from app.usuarios.esquemas import NovoUsuario, Usuario


def inserir(conexao: Conexao, novo: NovoUsuario, criado_em: datetime) -> Usuario:
    linha = conexao.execute(
        "INSERT INTO usuarios (nome, cpf, contato, criado_em) VALUES (%s, %s, %s, %s)"
        " RETURNING id, nome, cpf, contato, criado_em",
        (novo.nome, novo.cpf, novo.contato, criado_em),
    ).fetchone()
    assert linha is not None
    return Usuario(**linha)
