"""Infraestrutura compartilhada dos testes (dono: agente de Teste).

Segue a seção 8B do `agentes.md`. Nada de `app` é importado no topo deste arquivo:
os imports ficam dentro das fixtures, para que os testes unitários do agente de
Backend rodem mesmo que algum módulo de `app` ainda não exista.
"""

import dataclasses
import os
import subprocess
from datetime import datetime
from pathlib import Path

import psycopg
import pytest
import respx
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

RAIZ = Path(__file__).resolve().parent.parent
PASTA_CONTRATO = (RAIZ / "tests" / "contrato").resolve()
SCHEMA_SQL = RAIZ / "db" / "schema.sql"
SCRIPT_BANCO = RAIZ / "scripts" / "test-db.sh"
SUFIXO_BANCO_DE_TESTE = "_teste"

BACKEND2_URL = "https://backend2.teste"
RESPOSTA_BACKEND2_PADRAO = {"aceito": True, "eventoId": "evt_teste"}


# --------------------------------------------------------------------------- marcação


def pytest_collection_modifyitems(config, items):
    """Marca com `contrato` todo teste que está em `tests/contrato/`."""
    for item in items:
        if PASTA_CONTRATO in Path(item.path).resolve().parents:
            item.add_marker(pytest.mark.contrato)


# --------------------------------------------------------------------------- banco


@pytest.fixture(scope="session")
def database_url() -> str:
    """URL do banco de teste: `TEST_DATABASE_URL` ou `scripts/test-db.sh url` (8B)."""
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if url:
        return url
    saida = subprocess.run(
        ["bash", str(SCRIPT_BANCO), "url"], capture_output=True, text=True, check=True
    )
    return saida.stdout.strip()


def _conectar(database_url: str) -> psycopg.Connection:
    try:
        return psycopg.connect(database_url, autocommit=True)
    except psycopg.OperationalError as exc:
        pytest.fail(
            f"Não foi possível conectar ao banco de teste ({database_url}). "
            f"Rode `scripts/test-db.sh start` ou defina TEST_DATABASE_URL. Detalhe: {exc}"
        )


def _recusar_banco_que_nao_e_de_teste(nome: str | None, origem: str) -> None:
    if not nome or not nome.endswith(SUFIXO_BANCO_DE_TESTE):
        pytest.fail(
            f"Recusado: o banco {nome!r} ({origem}) não termina em "
            f"'{SUFIXO_BANCO_DE_TESTE}'. Os testes apagam o schema public; use um banco "
            "de teste (ex.: biblioteca_teste, de `scripts/test-db.sh`) em TEST_DATABASE_URL."
        )


@pytest.fixture(scope="session")
def preparar_banco(database_url: str) -> None:
    """Recria o schema `public` e aplica `db/schema.sql`, se existir (uma vez por sessão).

    Só roda em banco cujo nome termina em `_teste` (proteção contra apagar dados reais).
    """
    try:
        nome_na_url = conninfo_to_dict(database_url).get("dbname")
    except psycopg.ProgrammingError as exc:
        pytest.fail(f"URL do banco de teste inválida ({database_url}): {exc}")
    _recusar_banco_que_nao_e_de_teste(nome_na_url, "nome na URL")
    with _conectar(database_url) as conn:
        nome_conectado = conn.execute("SELECT current_database()").fetchone()[0]
        _recusar_banco_que_nao_e_de_teste(nome_conectado, "banco conectado")
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        if SCHEMA_SQL.is_file():
            conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))


@pytest.fixture
def limpar_tabelas(preparar_banco: None, database_url: str) -> None:
    """Esvazia todas as tabelas do schema `public` antes do teste."""
    with _conectar(database_url) as conn:
        tabelas = [
            linha[0]
            for linha in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
        ]
        if tabelas:
            conn.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(
                    sql.SQL(", ").join(sql.Identifier("public", t) for t in tabelas)
                )
            )


@pytest.fixture(autouse=True)
def _banco_dos_testes_de_contrato(request: pytest.FixtureRequest) -> None:
    """Para testes `contrato`: banco preparado na sessão e tabelas limpas antes de cada teste.

    Testes sem a marca (ex.: unitários) não tocam no banco.
    """
    if request.node.get_closest_marker("contrato") is not None:
        request.getfixturevalue("limpar_tabelas")


@pytest.fixture
def db(database_url: str):
    """Conexão psycopg com autocommit, para semear e inspecionar dados por SQL."""
    with _conectar(database_url) as conn:
        yield conn


# --------------------------------------------------------------------------- relógio e config


@pytest.fixture
def instante_base() -> datetime:
    return datetime(2026, 10, 13, 19, 20, 0)


@pytest.fixture
def relogio(instante_base: datetime):
    from app.relogio import RelogioFixo

    return RelogioFixo(instante_base)


@pytest.fixture
def config(database_url: str):
    from app.config import Config

    return Config(database_url=database_url, backend2_url=BACKEND2_URL, cors_origens=())


# --------------------------------------------------------------------------- aplicação


@pytest.fixture
def backend2():
    """Backend 2 falso (respx): `POST /eventos/biblioteca` → 200 aceito, por padrão.

    Para trocar a resposta num teste: `backend2.routes["eventos"].respond(...)` ou
    `.mock(side_effect=...)`. As chamadas ficam em `backend2.routes["eventos"].calls`.
    """
    with respx.mock(base_url=BACKEND2_URL, assert_all_called=False) as mock:
        mock.post("/eventos/biblioteca", name="eventos").respond(200, json=RESPOSTA_BACKEND2_PADRAO)
        yield mock


@pytest.fixture
def app(config, relogio):
    from app.main import create_app

    return create_app(config=config, relogio=relogio)


@pytest.fixture
def client(app, backend2):
    """Cliente HTTP da aplicação. O Backend 2 fica sempre interceptado pelo `backend2`."""
    with TestClient(app) as cliente:
        yield cliente


@pytest.fixture
def criar_app(config, relogio):
    """Fábrica: `criar_app(**campos_de_config)` cria a aplicação com outra `Config`."""
    from app.main import create_app

    def _criar(**overrides):
        return create_app(config=dataclasses.replace(config, **overrides), relogio=relogio)

    return _criar
