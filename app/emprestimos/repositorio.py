"""SQL da tabela `emprestimos` (CT11). Recebe uma conexão já dentro de `transacao`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from psycopg import sql

from app.db import Conexao
from app.emprestimos.esquemas import Emprestimo, EmprestimoResumo, Situacao

# EmprestimoResumo (CT8): empréstimo com o nome do usuário e o título do livro.
SELECAO_RESUMO = sql.SQL(
    "SELECT e.id, e.usuario_id, u.nome AS usuario_nome, e.livro_id, l.titulo AS livro_titulo,"
    " e.emprestado_em, e.data_limite_devolucao, e.devolvido_em"
    " FROM emprestimos e"
    " JOIN usuarios u ON u.id = e.usuario_id"
    " JOIN livros l ON l.id = e.livro_id"
)
# Ordem do CT8 (§6): mais recente primeiro, depois id decrescente.
ORDEM_RESUMO = sql.SQL("ORDER BY e.emprestado_em DESC, e.id DESC")


def resumos_dos_usuarios(conexao: Conexao, usuario_ids: Sequence[int]) -> list[EmprestimoResumo]:
    """Todos os empréstimos (qualquer situação) dos usuários, numa só consulta."""
    if not usuario_ids:
        return []
    consulta = sql.SQL("{} WHERE e.usuario_id = ANY(%(ids)s) {}").format(
        SELECAO_RESUMO, ORDEM_RESUMO
    )
    linhas = conexao.execute(consulta, {"ids": list(usuario_ids)}).fetchall()
    return [EmprestimoResumo(**linha) for linha in linhas]


def inserir(
    conexao: Conexao,
    *,
    usuario_id: int,
    livro_id: int,
    emprestado_em: datetime,
    data_limite_devolucao: datetime,
) -> Emprestimo:
    """Grava o empréstimo `ativo` (CT5)."""
    linha = conexao.execute(
        "INSERT INTO emprestimos"
        " (usuario_id, livro_id, status, emprestado_em, data_limite_devolucao)"
        " VALUES (%s, %s, %s, %s, %s)"
        " RETURNING id, usuario_id, livro_id, status, emprestado_em, data_limite_devolucao,"
        " devolvido_em",
        (usuario_id, livro_id, Situacao.ATIVO.value, emprestado_em, data_limite_devolucao),
    ).fetchone()
    assert linha is not None
    return Emprestimo(**linha)
