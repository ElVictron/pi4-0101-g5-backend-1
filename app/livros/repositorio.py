"""SQL da tabela `livros` (CT9). Recebe uma conexão já dentro de `transacao`."""

from __future__ import annotations

from datetime import datetime

from app.db import Conexao
from app.livros.esquemas import Livro, NovoLivro

_COLUNAS = "id, titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel, criado_em"


def inserir(conexao: Conexao, novo: NovoLivro, criado_em: datetime) -> Livro:
    """Grava o livro com todos os exemplares disponíveis."""
    linha = conexao.execute(
        "INSERT INTO livros"
        " (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel, criado_em)"
        " VALUES (%s, %s, %s, %s, %s, %s)"
        f" RETURNING {_COLUNAS}",
        (
            novo.titulo,
            novo.autor,
            novo.isbn,
            novo.quantidade_exemplares,
            novo.quantidade_exemplares,
            criado_em,
        ),
    ).fetchone()
    assert linha is not None
    return Livro(**linha)
