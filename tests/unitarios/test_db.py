"""Acesso ao banco (`app/db.py`) e `db/schema.sql` aplicado por ele.

Usa um banco **próprio** no servidor de teste (`biblioteca_unitarios_db_teste`), criado e
apagado por este módulo, para não depender do `tests/conftest.py` nem mexer no banco dos
testes de contrato. Só roda em banco cujo nome termina em `_teste`.
"""

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from psycopg import errors, sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from app import db as modulo_db
from app.config import Config
from app.db import CAMINHO_SCHEMA, aplicar_schema, conectar, transacao, violacoes_como_erro
from app.erros import CodigoErro, ErroDominio

pytestmark = pytest.mark.unitario

RAIZ = Path(__file__).resolve().parents[2]
NOME_BANCO = "biblioteca_unitarios_db_teste"
SUFIXO_DE_TESTE = "_teste"
TABELAS = {"livros", "usuarios", "emprestimos", "eventos_pendentes"}
RESTRICOES = {
    "livros_isbn_unico",
    "livros_quantidade_exemplares_minima",
    "livros_quantidade_disponivel_nao_negativa",
    "livros_disponivel_ate_exemplares",
    "usuarios_cpf_unico",
    "emprestimos_usuario_existe",
    "emprestimos_livro_existe",
    "emprestimos_status_valido",
    "emprestimos_status_coerente_com_devolucao",
    "emprestimos_prazo_depois_do_emprestimo",
    "emprestimos_devolucao_depois_do_emprestimo",
    "eventos_pendentes_tentativas_minima",
}


# --------------------------------------------------------------------------- sem banco


def test_conectar_usa_a_url_da_config_e_linhas_como_dicionario(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        modulo_db.psycopg, "connect", lambda *a, **kw: chamadas.append((a, kw)) or "conexao"
    )

    resultado = conectar(Config(database_url="postgresql://u@h/b_teste"), autocommit=True)

    assert resultado == "conexao"
    [(args, kwargs)] = chamadas
    assert args == ("postgresql://u@h/b_teste",)
    assert kwargs["autocommit"] is True
    assert kwargs["row_factory"] is psycopg.rows.dict_row
    assert kwargs["connect_timeout"] == modulo_db.TEMPO_LIMITE_CONEXAO_SEGUNDOS


def test_caminho_do_schema_aponta_para_db_schema_sql():
    assert CAMINHO_SCHEMA == RAIZ / "db" / "schema.sql"
    assert CAMINHO_SCHEMA.is_file()


# --------------------------------------------------------------------------- com banco próprio


def _url_do_servidor_de_teste() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if url:
        return url
    saida = subprocess.run(
        ["bash", str(RAIZ / "scripts" / "test-db.sh"), "url"],
        capture_output=True,
        text=True,
        check=True,
    )
    return saida.stdout.strip()


@pytest.fixture(scope="module")
def config_banco_proprio():
    """Cria `NOME_BANCO` vazio no servidor de teste e o apaga no fim do módulo."""
    url_base = _url_do_servidor_de_teste()
    if not (conninfo_to_dict(url_base).get("dbname") or "").endswith(SUFIXO_DE_TESTE):
        pytest.fail("O servidor de teste deve ser acessado por um banco terminado em '_teste'.")
    assert NOME_BANCO.endswith(SUFIXO_DE_TESTE)
    try:
        admin = psycopg.connect(url_base, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Banco de teste indisponível (rode scripts/test-db.sh start): {exc}")

    nome = sql.Identifier(NOME_BANCO)
    with admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(nome))
        admin.execute(sql.SQL("CREATE DATABASE {}").format(nome))
        yield Config(database_url=make_conninfo(url_base, dbname=NOME_BANCO))
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(nome))


@pytest.fixture(scope="module")
def config(config_banco_proprio):
    aplicar_schema(config_banco_proprio)
    return config_banco_proprio


@pytest.fixture
def limpo(config):
    with transacao(config) as conexao:
        conexao.execute(
            "TRUNCATE livros, usuarios, emprestimos, eventos_pendentes RESTART IDENTITY CASCADE"
        )
    return config


def _contar_livros(config: Config) -> int:
    with transacao(config) as conexao:
        return conexao.execute("SELECT count(*) AS n FROM livros").fetchone()["n"]


def _inserir_livro(conexao, isbn: str = "9780000000001") -> int:
    return conexao.execute(
        "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
        " VALUES ('T', 'A', %s, 1, 1) RETURNING id",
        (isbn,),
    ).fetchone()["id"]


def test_aplicar_schema_cria_tabelas_extensao_e_restricoes_nomeadas(config):
    with transacao(config) as conexao:
        tabelas = {
            linha["tablename"]
            for linha in conexao.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
        }
        extensao = conexao.execute(
            "SELECT 1 AS ok FROM pg_extension WHERE extname = 'unaccent'"
        ).fetchone()
        restricoes = {
            linha["conname"]
            for linha in conexao.execute(
                "SELECT conname FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace"
                " WHERE n.nspname = 'public' AND c.contype IN ('u', 'c', 'f')"
            )
        }

    assert tabelas == TABELAS
    assert extensao == {"ok": 1}
    assert restricoes == RESTRICOES


def test_aplicar_schema_de_novo_nao_falha_nem_apaga_dados(limpo):
    with transacao(limpo) as conexao:
        _inserir_livro(conexao)

    aplicar_schema(limpo)

    assert _contar_livros(limpo) == 1


def test_conectar_devolve_linhas_como_dicionario_fora_de_autocommit(config):
    with conectar(config) as conexao:
        assert conexao.autocommit is False
        assert conexao.execute("SELECT 1 AS um, 'x' AS letra").fetchone() == {
            "um": 1,
            "letra": "x",
        }


def test_transacao_confirma_ao_sair_sem_erro_e_fecha_a_conexao(limpo):
    with transacao(limpo) as conexao:
        _inserir_livro(conexao)

    assert conexao.closed
    assert _contar_livros(limpo) == 1


def test_transacao_desfaz_tudo_se_houver_excecao_e_fecha_a_conexao(limpo):
    with pytest.raises(RuntimeError), transacao(limpo) as conexao:
        _inserir_livro(conexao)
        raise RuntimeError("falha no meio da operação")

    assert conexao.closed
    assert _contar_livros(limpo) == 0


def test_violacao_de_restricao_desfaz_a_transacao_e_expoe_o_nome(limpo):
    with pytest.raises(errors.UniqueViolation) as erro, transacao(limpo) as conexao:
        _inserir_livro(conexao, isbn="9780000000001")
        _inserir_livro(conexao, isbn="9780000000001")

    assert erro.value.diag.constraint_name == "livros_isbn_unico"
    assert _contar_livros(limpo) == 0


def test_padrao_de_criado_em_corta_no_segundo(limpo):
    with transacao(limpo) as conexao:
        conexao.execute("SET LOCAL TIME ZONE 'Asia/Tokyo'")
        criado_em = conexao.execute(
            "INSERT INTO usuarios (nome, cpf, contato) VALUES ('N', '12345678900', 'a@b.co')"
            " RETURNING criado_em,"
            " date_trunc('second', now() AT TIME ZONE 'America/Sao_Paulo') AS esperado"
        ).fetchone()

    assert criado_em["criado_em"] == criado_em["esperado"]


# ----------------------------------------------- violacoes_como_erro (D16 a, d)


def _violacao(classe, restricao):
    falsa = type("Falsa", (classe,), {"diag": SimpleNamespace(constraint_name=restricao)})
    return falsa("Key (isbn)=(9780000000001) already exists.")


MAPA = {"livros_isbn_unico": CodigoErro.ISBN_DUPLICADO}


@pytest.mark.parametrize(
    "classe", [errors.UniqueViolation, errors.CheckViolation, errors.ForeignKeyViolation]
)
def test_restricao_mapeada_vira_erro_de_dominio_sem_texto_do_banco(classe):
    with pytest.raises(ErroDominio) as erro, violacoes_como_erro(MAPA):
        raise _violacao(classe, "livros_isbn_unico")

    assert erro.value.codigo is CodigoErro.ISBN_DUPLICADO
    assert erro.value.__cause__ is None
    assert erro.value.__suppress_context__ is True
    assert "9780000000001" not in erro.value.mensagem


@pytest.mark.parametrize("restricao", ["usuarios_cpf_unico", None])
def test_restricao_fora_do_mapa_segue_como_esta(restricao):
    original = _violacao(errors.UniqueViolation, restricao)

    with pytest.raises(errors.UniqueViolation) as erro, violacoes_como_erro(MAPA):
        raise original

    assert erro.value is original


def test_outros_erros_nao_sao_tocados():
    with pytest.raises(errors.OperationalError), violacoes_como_erro(MAPA):
        raise errors.OperationalError("conexão caiu")


def test_violacao_real_mapeada_desfaz_a_transacao(limpo):
    with transacao(limpo) as conexao:
        _inserir_livro(conexao, isbn="9780000000001")

    with pytest.raises(ErroDominio) as erro, violacoes_como_erro(MAPA), transacao(limpo) as c:
        _inserir_livro(c, isbn="9780000000002")
        _inserir_livro(c, isbn="9780000000001")

    assert erro.value.codigo is CodigoErro.ISBN_DUPLICADO
    assert _contar_livros(limpo) == 1
