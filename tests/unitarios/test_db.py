"""Acesso ao banco (`app/db.py`) e `db/schema.sql` aplicado por ele.

Usa um banco **próprio** no servidor de teste, criado e apagado por este módulo, para não
depender do `tests/conftest.py` nem mexer no banco dos testes de contrato. O nome vem do
banco de teste em uso (`<nome>_db_teste`): suítes com `TEST_DATABASE_URL` diferentes não
apagam o banco uma da outra. Só roda em banco cujo nome termina em `_teste`.
"""

import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from psycopg import errors, sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from app import db as modulo_db
from app.config import Config
from app.db import (
    CAMINHO_SCHEMA,
    aplicar_schema,
    conectar,
    filtro_de_busca,
    ordem_alfabetica,
    transacao,
    violacoes_como_erro,
)
from app.erros import CodigoErro, ErroDominio

pytestmark = pytest.mark.unitario

RAIZ = Path(__file__).resolve().parents[2]
SUFIXO_DE_TESTE = "_teste"
SUFIXO_BANCO_PROPRIO = "_db_teste"
SUFIXO_BANCO_CTYPE_C = "_db_c_teste"
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


@pytest.mark.parametrize(
    ("base", "esperado"),
    [
        ("biblioteca_teste", "biblioteca_teste_db_teste"),
        ("biblioteca_backend_teste", "biblioteca_backend_teste_db_teste"),
    ],
)
def test_nome_do_banco_proprio_deriva_do_banco_de_teste(base, esperado):
    assert nome_do_banco_proprio(base) == esperado


@pytest.mark.parametrize("base", [None, "", "biblioteca", "producao", "x_db_teste", "x_db_c_teste"])
def test_nome_do_banco_proprio_recusa_base_que_nao_e_de_teste(base):
    with pytest.raises(ValueError):
        nome_do_banco_proprio(base)


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


def nome_do_banco_proprio(nome_base: str | None, sufixo: str = SUFIXO_BANCO_PROPRIO) -> str:
    """`<nome_base><sufixo>`; recusa base que não seja banco de teste ou que já seja próprio."""
    assert sufixo.endswith(SUFIXO_DE_TESTE)
    if not nome_base or not nome_base.endswith(SUFIXO_DE_TESTE):
        raise ValueError(f"O banco de teste deve terminar em '{SUFIXO_DE_TESTE}': {nome_base!r}")
    if nome_base.endswith((SUFIXO_BANCO_PROPRIO, SUFIXO_BANCO_CTYPE_C)):
        raise ValueError(f"A base já é um banco próprio deste módulo: {nome_base!r}")
    return nome_base + sufixo


@contextmanager
def _banco_proprio(sufixo: str, *, locale_c: bool = False):
    """Cria `<banco de teste><sufixo>` vazio no servidor de teste e o apaga ao final."""
    url_base = _url_do_servidor_de_teste()
    try:
        nome_banco = nome_do_banco_proprio(conninfo_to_dict(url_base).get("dbname"), sufixo)
    except ValueError as exc:
        pytest.fail(str(exc))
    try:
        admin = psycopg.connect(url_base, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Banco de teste indisponível (rode scripts/test-db.sh start): {exc}")

    nome = sql.Identifier(nome_banco)
    criar = sql.SQL("CREATE DATABASE {}").format(nome)
    if locale_c:
        criar = sql.SQL(
            "CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C'"
        ).format(nome)
    with admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(nome))
        admin.execute(criar)
        try:
            yield Config(database_url=make_conninfo(url_base, dbname=nome_banco))
        finally:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(nome))


@pytest.fixture(scope="module")
def config_banco_proprio():
    with _banco_proprio(SUFIXO_BANCO_PROPRIO) as config:
        yield config


@pytest.fixture(scope="module")
def config_locale_c():
    """Banco com LC_COLLATE e LC_CTYPE `C`, já com o schema (para provar a independência do
    locale exigida pelo §6)."""
    with _banco_proprio(SUFIXO_BANCO_CTYPE_C, locale_c=True) as config:
        aplicar_schema(config)
        yield config


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


# ----------------------------------------------- filtro_de_busca e somente leitura (§6)


@pytest.fixture
def livros_para_busca(limpo):
    titulos = [
        "Informação e Sociedade",
        "PYTHON 100%",
        "Guia_Rapido",
        "Barra \\ Invertida",
        "O'Reilly",
        "Sem Relação",
    ]
    with transacao(limpo) as conexao:
        for numero, titulo in enumerate(titulos):
            _inserir_livro_com_titulo(conexao, titulo, f"97800000000{numero:02d}")
    return limpo


def _inserir_livro_com_titulo(conexao, titulo: str, isbn: str) -> None:
    conexao.execute(
        "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
        " VALUES (%s, 'Autor', %s, 1, 1)",
        (titulo, isbn),
    )


def _titulos_achados(config: Config, termo: str) -> list[str]:
    consulta = sql.SQL("SELECT titulo FROM livros WHERE {} ORDER BY titulo").format(
        filtro_de_busca(["titulo"])
    )
    with transacao(config, somente_leitura=True) as conexao:
        return [linha["titulo"] for linha in conexao.execute(consulta, {"termo": termo})]


@pytest.mark.parametrize(
    ("termo", "esperados"),
    [
        ("informacao", ["Informação e Sociedade"]),
        ("INFORMAÇÃO", ["Informação e Sociedade"]),
        ("ção e soc", ["Informação e Sociedade"]),
        ("python", ["PYTHON 100%"]),
        ("%", ["PYTHON 100%"]),
        ("0%", ["PYTHON 100%"]),
        ("%%", []),
        ("_", ["Guia_Rapido"]),
        ("a_r", ["Guia_Rapido"]),
        ("o_r", []),
        ("\\", ["Barra \\ Invertida"]),
        ("\\ i", ["Barra \\ Invertida"]),
        ("\\%", []),
        ("'", ["O'Reilly"]),
        ("'; DROP TABLE livros; --", []),
    ],
)
def test_filtro_de_busca_literal_sem_acento_nem_maiuscula(livros_para_busca, termo, esperados):
    assert _titulos_achados(livros_para_busca, termo) == esperados


def test_filtro_de_busca_em_varias_colunas_usa_or():
    texto = filtro_de_busca(["titulo", "autor"]).as_string(None)

    assert texto.count("LIKE") == 2
    assert " OR " in texto
    assert '"titulo"' in texto and '"autor"' in texto
    assert "%(termo)s" in texto


def test_transacao_somente_leitura_recusa_escrita_e_usa_repeatable_read(limpo):
    with (
        pytest.raises(errors.ReadOnlySqlTransaction),
        transacao(limpo, somente_leitura=True) as conexao,
    ):
        nivel = conexao.execute("SHOW transaction_isolation").fetchone()
        assert nivel == {"transaction_isolation": "repeatable read"}
        _inserir_livro(conexao)

    assert _contar_livros(limpo) == 0


# ----------------------------------------------- ordem alfabética do §6 (título/nome)

TITULOS_MISTURADOS = ["Zoologia", "cálculo", "Banco", "álgebra", "Álgebra", "algebra", "Cálculo"]
# Sem caixa nem acento: algebra < banco < calculo < zoologia; empate → código de caractere
# ('a' 0x61 < 'Á' 0xC1 < 'á' 0xE1; 'C' 0x43 < 'c' 0x63).
ORDEM_ESPERADA = ["algebra", "Álgebra", "álgebra", "Banco", "Cálculo", "cálculo", "Zoologia"]


def _titulos_em_ordem(config: Config) -> list[str]:
    with transacao(config) as conexao:
        conexao.execute(
            "TRUNCATE livros, usuarios, emprestimos, eventos_pendentes RESTART IDENTITY CASCADE"
        )
        for numero, titulo in enumerate(TITULOS_MISTURADOS):
            _inserir_livro_com_titulo(conexao, titulo, f"97900000000{numero:02d}")
        consulta = sql.SQL("SELECT titulo FROM livros ORDER BY {}").format(
            ordem_alfabetica("titulo")
        )
        return [linha["titulo"] for linha in conexao.execute(consulta)]


def test_ordem_alfabetica_sem_caixa_nem_acento_e_desempate_por_codigo(config):
    assert _titulos_em_ordem(config) == ORDEM_ESPERADA


def test_ordem_alfabetica_igual_com_locale_c(config_locale_c):
    with conectar(config_locale_c) as conexao:
        locale = conexao.execute(
            "SELECT datcollate, datctype FROM pg_database WHERE datname = current_database()"
        ).fetchone()
        assert locale == {"datcollate": "C", "datctype": "C"}

    assert _titulos_em_ordem(config_locale_c) == ORDEM_ESPERADA


def test_busca_sem_acento_funciona_com_locale_c(config_locale_c):
    with transacao(config_locale_c) as conexao:
        conexao.execute("TRUNCATE livros RESTART IDENTITY CASCADE")
        _inserir_livro_com_titulo(conexao, "INFORMAÇÃO E SOCIEDADE", "9780000000001")

    assert _titulos_achados(config_locale_c, "informacao") == ["INFORMAÇÃO E SOCIEDADE"]
    assert _titulos_achados(config_locale_c, "Ção") == ["INFORMAÇÃO E SOCIEDADE"]


def test_desempate_por_id_com_titulos_identicos(config):
    with transacao(config) as conexao:
        conexao.execute("TRUNCATE livros RESTART IDENTITY CASCADE")
        for numero in range(3):
            _inserir_livro_com_titulo(conexao, "Mesmo", f"97800000001{numero:02d}")
        consulta = sql.SQL("SELECT id FROM livros ORDER BY {}").format(ordem_alfabetica("titulo"))
        ids = [linha["id"] for linha in conexao.execute(consulta)]

    assert ids == sorted(ids)


def test_ordem_alfabetica_aceita_coluna_qualificada_e_outro_desempate():
    texto = ordem_alfabetica("u.nome", desempate="u.id").as_string(None)

    assert texto == 'lower(unaccent("u"."nome")) COLLATE "C", "u"."nome" COLLATE "C", "u"."id"'


# ----------------------------------------------- baixa atômica (P11) e trava do reenvio


def test_baixa_de_exemplar_para_no_zero(limpo):
    from app.livros import repositorio as livros

    with transacao(limpo) as conexao:
        livro_id = conexao.execute(
            "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
            " VALUES ('T', 'A', '9780000000001', 2, 1) RETURNING id"
        ).fetchone()["id"]
        assert livros.baixar_exemplar(conexao, livro_id) == 0
        assert livros.baixar_exemplar(conexao, livro_id) is None
        assert livros.baixar_exemplar(conexao, 999_999) is None
        assert livros.existe(conexao, livro_id) and not livros.existe(conexao, 999_999)


def test_evento_travado_por_um_reenvio_e_pulado_pelo_outro(limpo):
    from datetime import datetime

    from app.eventos import repositorio as eventos

    agora = datetime(2026, 10, 13, 19, 20)
    with transacao(limpo) as conexao:
        primeiro = eventos.inserir(conexao, {"tipo": "x"}, "timeout", agora)
        segundo = eventos.inserir(conexao, {"tipo": "y"}, "HTTP 503", agora)

    with transacao(limpo) as conexao_a, transacao(limpo) as conexao_b:
        assert eventos.ids_em_ordem(conexao_a) == [primeiro, segundo]
        travado = eventos.travar(conexao_a, primeiro)
        assert travado == eventos.EventoPendente(primeiro, {"tipo": "x"}, 1)
        assert eventos.travar(conexao_b, primeiro) is None
        assert eventos.travar(conexao_b, segundo) is not None
        eventos.registrar_falha(conexao_a, primeiro, "falha de conexão", agora)
        eventos.apagar(conexao_b, segundo)

    with transacao(limpo) as conexao:
        linhas = conexao.execute(
            "SELECT id, tentativas, ultimo_erro FROM eventos_pendentes ORDER BY id"
        ).fetchall()
    assert linhas == [{"id": primeiro, "tentativas": 2, "ultimo_erro": "falha de conexão"}]


def test_ultimo_erro_gravado_no_maximo_com_200_caracteres(limpo):
    from datetime import datetime

    from app.eventos import repositorio as eventos

    agora = datetime(2026, 10, 13, 19, 20)
    with transacao(limpo) as conexao:
        evento_id = eventos.inserir(conexao, {"tipo": "x"}, "a" * 300, agora)
        gravado = conexao.execute(
            "SELECT ultimo_erro FROM eventos_pendentes WHERE id = %s", (evento_id,)
        ).fetchone()["ultimo_erro"]
        eventos.registrar_falha(conexao, evento_id, "b" * 300, agora)
        atualizado = conexao.execute(
            "SELECT ultimo_erro FROM eventos_pendentes WHERE id = %s", (evento_id,)
        ).fetchone()["ultimo_erro"]

    assert (gravado, atualizado) == ("a" * 200, "b" * 200)


def test_devolucao_so_marca_ativo_e_repoe_um_exemplar(limpo):
    from datetime import datetime, timedelta

    from app.emprestimos import repositorio as emprestimos
    from app.livros import repositorio as livros

    t0 = datetime(2026, 10, 13, 19, 20)
    with transacao(limpo) as conexao:
        usuario = conexao.execute(
            "INSERT INTO usuarios (nome, cpf, contato) VALUES ('N', '12345678900', 'a@b.co')"
            " RETURNING id"
        ).fetchone()["id"]
        livro = conexao.execute(
            "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
            " VALUES ('T', 'A', '9780000000001', 2, 1) RETURNING id"
        ).fetchone()["id"]
        emprestimo = emprestimos.inserir(
            conexao,
            usuario_id=usuario,
            livro_id=livro,
            emprestado_em=t0,
            data_limite_devolucao=t0 + timedelta(days=15),
        ).id
        devolvido_em = t0 + timedelta(days=20)  # atrasado: gravado como ativo (D3)

        assert emprestimos.marcar_devolvido(conexao, emprestimo, devolvido_em) == {
            "livro_id": livro,
            "usuario_id": usuario,
            "devolvido_em": devolvido_em,
        }
        assert emprestimos.marcar_devolvido(conexao, emprestimo, devolvido_em) is None
        assert emprestimos.marcar_devolvido(conexao, 999_999, devolvido_em) is None
        assert emprestimos.existe(conexao, emprestimo) and not emprestimos.existe(conexao, 999_999)
        assert livros.devolver_exemplar(conexao, livro) == 2
