"""Acesso ao PostgreSQL (psycopg 3, SQL explícito; P1, P3, 00-convencoes §11).

Uma conexão por operação: as rotas abrem `transacao(config)` só quando precisam do banco,
então criar a aplicação (e o `GET /saude`) nunca depende dele.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.config import Config
from app.erros import CodigoErro, ErroDominio

CAMINHO_SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"
TEMPO_LIMITE_CONEXAO_SEGUNDOS = 5

Conexao = psycopg.Connection[dict[str, Any]]


def conectar(config: Config, *, autocommit: bool = False) -> Conexao:
    """Abre uma conexão nova; cada linha lida vem como dicionário (coluna → valor)."""
    return psycopg.connect(
        config.database_url,
        autocommit=autocommit,
        row_factory=dict_row,
        connect_timeout=TEMPO_LIMITE_CONEXAO_SEGUNDOS,
    )


@contextmanager
def transacao(config: Config) -> Iterator[Conexao]:
    """Conexão dentro de uma transação: confirma ao sair sem erro, desfaz se houver exceção.

    A conexão é fechada ao final nos dois casos.
    """
    conexao = conectar(config)
    try:
        with conexao.transaction():
            yield conexao
    finally:
        conexao.close()


def aplicar_schema(config: Config, caminho: Path = CAMINHO_SCHEMA) -> None:
    """Aplica `db/schema.sql` (cria extensão e tabelas que ainda não existem), numa transação."""
    sql = caminho.read_text(encoding="utf-8")
    with transacao(config) as conexao:
        # Texto do próprio projeto, sem parâmetros: vários comandos numa só execução.
        conexao.execute(sql)  # type: ignore[arg-type]


@contextmanager
def violacoes_como_erro(mapa: Mapping[str, CodigoErro]) -> Iterator[None]:
    """Traduz violação de integridade em `ErroDominio` pelo nome da restrição (D16 a).

    Restrição fora do `mapa` (ou sem nome) segue como está e vira `ERRO_INTERNO` (D16 d).
    A exceção do banco não é encadeada, para nenhum texto dele chegar à resposta.
    Use por fora de `transacao`, para o rollback acontecer antes da tradução.
    """
    try:
        yield
    except psycopg.errors.IntegrityError as exc:
        codigo = mapa.get(exc.diag.constraint_name or "")
        if codigo is None:
            raise
        raise ErroDominio(codigo) from None
