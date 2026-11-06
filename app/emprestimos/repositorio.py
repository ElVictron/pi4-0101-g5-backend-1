"""SQL da tabela `emprestimos` (CT11). Recebe uma conexão já dentro de `transacao`."""

from __future__ import annotations

from collections.abc import Sequence

from psycopg import sql

from app.db import Conexao
from app.emprestimos.esquemas import EmprestimoResumo

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
