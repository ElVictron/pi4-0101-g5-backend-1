"""SQL da tabela `livros` (CT9). Recebe uma conexão já dentro de `transacao`."""

from __future__ import annotations

from datetime import datetime

from psycopg import sql

from app.db import Conexao, filtro_de_busca, ordem_alfabetica
from app.livros.esquemas import Livro, NovoLivro

_COLUNAS = sql.SQL(
    "id, titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel, criado_em"
)
# 00-convencoes §6: título, autor ou ISBN (o ISBN como digitado, sem normalizar o termo).
COLUNAS_DA_BUSCA = ("titulo", "autor", "isbn")
# Ordem do §6: por título (sem caixa nem acento, depois texto exato) e depois id.
_ORDEM = sql.SQL("ORDER BY {}").format(ordem_alfabetica("titulo"))


_SO_DISPONIVEIS = sql.SQL("quantidade_disponivel > 0")


def _onde(termo: str | None, *condicoes: sql.Composable) -> sql.Composable:
    """`WHERE` com as `condicoes` e, se houver termo, o filtro de busca (tudo com AND)."""
    partes = list(condicoes)
    if termo is not None:
        partes.append(sql.SQL("({})").format(filtro_de_busca(COLUNAS_DA_BUSCA)))
    if not partes:
        return sql.SQL("")
    return sql.SQL("WHERE {}").format(sql.SQL(" AND ").join(partes))


def inserir(conexao: Conexao, novo: NovoLivro, criado_em: datetime) -> Livro:
    """Grava o livro com todos os exemplares disponíveis."""
    linha = conexao.execute(
        sql.SQL(
            "INSERT INTO livros"
            " (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel, criado_em)"
            " VALUES (%s, %s, %s, %s, %s, %s) RETURNING {}"
        ).format(_COLUNAS),
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


def buscar(conexao: Conexao, termo: str | None, *, limite: int, deslocamento: int) -> list[Livro]:
    """Livros do filtro, na ordem do §6, a partir de `deslocamento`."""
    consulta = sql.SQL(
        "SELECT {} FROM livros {} {} LIMIT %(limite)s OFFSET %(deslocamento)s"
    ).format(_COLUNAS, _onde(termo), _ORDEM)
    linhas = conexao.execute(
        consulta, {"termo": termo, "limite": limite, "deslocamento": deslocamento}
    ).fetchall()
    return [Livro(**linha) for linha in linhas]


def contar(conexao: Conexao, termo: str | None) -> int:
    """Quantos livros o filtro encontra (o `total` do CT2)."""
    linha = conexao.execute(
        sql.SQL("SELECT count(*) AS total FROM livros {}").format(_onde(termo)), {"termo": termo}
    ).fetchone()
    assert linha is not None
    return linha["total"]


def listar_disponiveis(conexao: Conexao, termo: str | None) -> list[Livro]:
    """CT7: livros com exemplar livre (`quantidade_disponivel > 0`), na ordem do §6."""
    consulta = sql.SQL("SELECT {} FROM livros {} {}").format(
        _COLUNAS, _onde(termo, _SO_DISPONIVEIS), _ORDEM
    )
    return [Livro(**linha) for linha in conexao.execute(consulta, {"termo": termo}).fetchall()]
