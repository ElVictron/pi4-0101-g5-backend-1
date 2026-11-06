"""Acesso ao PostgreSQL (psycopg 3, SQL explícito; P1, P3, 00-convencoes §11).

Uma conexão por operação: as rotas abrem `transacao(config)` só quando precisam do banco,
então criar a aplicação (e o `GET /saude`) nunca depende dele.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql
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
def transacao(config: Config, *, somente_leitura: bool = False) -> Iterator[Conexao]:
    """Conexão dentro de uma transação: confirma ao sair sem erro, desfaz se houver exceção.

    `somente_leitura=True` (consultas): transação READ ONLY em REPEATABLE READ, para que
    várias leituras (ex.: página e `total`) vejam o mesmo retrato do banco.
    A conexão é fechada ao final nos dois casos.
    """
    conexao = conectar(config)
    if somente_leitura:
        conexao.read_only = True
        conexao.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    try:
        with conexao.transaction():
            yield conexao
    finally:
        conexao.close()


# Texto "sem maiúsculas nem acentos" (00-convencoes §6). `unaccent` vem antes de `lower`:
# assim a letra acentuada vira ASCII e o `lower` funciona em qualquer locale do servidor
# (com LC_CTYPE=C, `lower('Ç')` não muda e `unaccent(lower('Ç'))` daria 'C' maiúsculo).
_SEM_CAIXA_NEM_ACENTO = "lower(unaccent({}))"

# Padrão LIKE do termo de busca (§6): o termo passa pela mesma normalização das colunas e
# só depois tem `\`, `%` e `_` escapados, para valerem como texto literal.
# Usa o parâmetro nomeado `termo`.
_PADRAO_DA_BUSCA = sql.SQL(
    r"""('%%' || replace(replace(replace(lower(unaccent(%(termo)s::text)),"""
    r""" '\', '\\'), '%%', '\%%'), '_', '\_') || '%%')"""
)


def filtro_de_busca(colunas: Sequence[str]) -> sql.Composable:
    """Condição SQL: o termo `%(termo)s` aparece em alguma das `colunas`.

    Sem diferenciar maiúsculas nem acentos, em qualquer posição; `%`, `_` e a barra
    invertida valem como texto literal.
    Sempre por parâmetro SQL; o termo nunca é concatenado na consulta.
    """
    return sql.SQL(" OR ").join(
        sql.SQL(_SEM_CAIXA_NEM_ACENTO + r" LIKE {} ESCAPE '\'").format(
            _identificador(coluna), _PADRAO_DA_BUSCA
        )
        for coluna in colunas
    )


def ordem_alfabetica(coluna: str, desempate: str = "id") -> sql.Composable:
    """Critério de `ORDER BY` "por título/nome" do §6 (sem o `ORDER BY`).

    Alfabética sem diferenciar maiúsculas nem acentos; empate → texto exato por código de
    caractere; depois `desempate` crescente. `COLLATE "C"` deixa a ordem igual em qualquer
    locale do servidor. Aceita coluna qualificada (`u.nome`).
    """
    texto = _identificador(coluna)
    return sql.SQL(_SEM_CAIXA_NEM_ACENTO + ' COLLATE "C", {} COLLATE "C", {}').format(
        texto, texto, _identificador(desempate)
    )


def _identificador(nome: str) -> sql.Identifier:
    return sql.Identifier(*nome.split("."))


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
