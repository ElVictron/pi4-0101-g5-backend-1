"""E2 — Banco (card #781): `db/schema.sql`, testado só por SQL direto.

Fontes: CT9 (livros), CT10 (usuarios), CT11 (emprestimos), `00-convencoes.md` §7, §8 e
§11; `agentes.md` D3, D5 e D15. O `tests/conftest.py` aplica `db/schema.sql` na sessão e
esvazia as tabelas antes de cada teste; a fixture `db` é uma conexão com autocommit.
"""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from psycopg import errors
from psycopg.types.json import Jsonb

T0 = datetime(2026, 10, 13, 19, 20, 0)
LIMITE = T0 + timedelta(days=15)
FUSO_SP = ZoneInfo("America/Sao_Paulo")
SCHEMA_SQL = Path(__file__).resolve().parents[2] / "db" / "schema.sql"

INTEIRO = {"integer", "bigint"}
TEXTO = {"text", "character varying"}
DATA_HORA = {"timestamp without time zone"}
JSONB = {"jsonb"}

# coluna -> (tipos aceitos, aceita nulo)
COLUNAS = {
    # CT9 · livros
    "livros": {
        "id": (INTEIRO, False),
        "titulo": (TEXTO, False),
        "autor": (TEXTO, False),
        "isbn": (TEXTO, False),
        "quantidade_exemplares": (INTEIRO, False),
        "quantidade_disponivel": (INTEIRO, False),
        "criado_em": (DATA_HORA, False),
    },
    # CT10 · usuarios
    "usuarios": {
        "id": (INTEIRO, False),
        "nome": (TEXTO, False),
        "cpf": (TEXTO, False),
        "contato": (TEXTO, False),
        "criado_em": (DATA_HORA, False),
    },
    # CT11 · emprestimos
    "emprestimos": {
        "id": (INTEIRO, False),
        "usuario_id": (INTEIRO, False),
        "livro_id": (INTEIRO, False),
        "status": (TEXTO, False),
        "emprestado_em": (DATA_HORA, False),
        "data_limite_devolucao": (DATA_HORA, False),
        "devolvido_em": (DATA_HORA, True),
    },
    # 00-convencoes §8 e §11 · eventos_pendentes
    "eventos_pendentes": {
        "id": (INTEIRO, False),
        "payload": (JSONB, False),
        "tentativas": (INTEIRO, False),
        "ultimo_erro": (TEXTO, True),
        "criado_em": (DATA_HORA, False),
        "atualizado_em": (DATA_HORA, False),
    },
}

PAYLOAD = {
    "tipo": "emprestimo_registrado",
    "livroId": 1,
    "usuarioId": 1,
    "emprestimoId": 1,
    "status": "ativo",
    "quantidadeDisponivel": 2,
    "atualizadaEm": "2026-10-13T19:20:00",
}


# --------------------------------------------------------------------------- apoio


def inserir_livro(
    db,
    *,
    isbn="9780000000001",
    exemplares=3,
    disponivel=None,
    titulo="Fundamentos de Sistemas de Informação",
    autor="Ana Silva",
) -> int:
    disponivel = exemplares if disponivel is None else disponivel
    return db.execute(
        "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (titulo, autor, isbn, exemplares, disponivel),
    ).fetchone()[0]


def inserir_usuario(db, *, cpf="12345678900", nome="Lucas Joaquim", contato="l@email.com") -> int:
    return db.execute(
        "INSERT INTO usuarios (nome, cpf, contato) VALUES (%s, %s, %s) RETURNING id",
        (nome, cpf, contato),
    ).fetchone()[0]


def inserir_emprestimo(
    db,
    usuario_id,
    livro_id,
    *,
    status="ativo",
    emprestado_em=T0,
    data_limite=LIMITE,
    devolvido_em=None,
) -> int:
    return db.execute(
        "INSERT INTO emprestimos"
        " (usuario_id, livro_id, status, emprestado_em, data_limite_devolucao, devolvido_em)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (usuario_id, livro_id, status, emprestado_em, data_limite, devolvido_em),
    ).fetchone()[0]


def inserir_evento(db, *, payload=PAYLOAD) -> int:
    return db.execute(
        "INSERT INTO eventos_pendentes (payload) VALUES (%s) RETURNING id",
        (Jsonb(payload) if payload is not None else None,),
    ).fetchone()[0]


@pytest.fixture
def usuario_e_livro(db):
    return inserir_usuario(db), inserir_livro(db)


def contar(db, tabela: str) -> int:
    return db.execute(f"SELECT count(*) FROM {tabela}").fetchone()[0]


def agora_sp() -> datetime:
    return datetime.now(FUSO_SP).replace(tzinfo=None)


# --------------------------------------------------------------------------- estrutura


# 00-convencoes §11 · as quatro tabelas existem no schema public
def test_tabelas_existem(db):
    tabelas = {
        linha[0]
        for linha in db.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    }

    assert set(COLUNAS) <= tabelas


# CT9/CT10/CT11, 00-convencoes §8 e §11 · colunas, tipos, nulabilidade, timestamp(0)
@pytest.mark.parametrize("tabela", list(COLUNAS))
def test_colunas_tipos_e_nulabilidade(db, tabela):
    linhas = db.execute(
        "SELECT column_name, data_type, is_nullable, datetime_precision"
        " FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = %s",
        (tabela,),
    ).fetchall()
    reais = {nome: (tipo, nulo == "YES", precisao) for nome, tipo, nulo, precisao in linhas}
    esperadas = COLUNAS[tabela]

    assert set(reais) == set(esperadas)
    for coluna, (tipos, aceita_nulo) in esperadas.items():
        tipo, nulo, precisao = reais[coluna]
        assert tipo in tipos, f"{tabela}.{coluna}: tipo {tipo}"
        assert nulo is aceita_nulo, f"{tabela}.{coluna}: nulabilidade"
        if tipos is DATA_HORA:
            assert precisao == 0, f"{tabela}.{coluna}: precisão {precisao}"


# 00-convencoes §11 · id = GENERATED BY DEFAULT AS IDENTITY
@pytest.mark.parametrize("tabela", list(COLUNAS))
def test_id_e_identidade_gerada_pelo_banco(db, tabela):
    linha = db.execute(
        "SELECT is_identity, identity_generation FROM information_schema.columns"
        " WHERE table_schema = 'public' AND table_name = %s AND column_name = 'id'",
        (tabela,),
    ).fetchone()

    assert linha is not None, f"{tabela}.id não existe"
    is_identity, geracao = linha
    assert is_identity == "YES"
    assert geracao == "BY DEFAULT"


# 00-convencoes §11 · extensão unaccent disponível (busca do §6)
def test_extensao_unaccent_disponivel(db):
    assert db.execute("SELECT 1 FROM pg_extension WHERE extname = 'unaccent'").fetchone()
    assert db.execute("SELECT unaccent('Informação')").fetchone()[0] == "Informacao"


# --------------------------------------------------------------------------- padrões


# 00-convencoes §11 · id gerado pelo banco: inteiros crescentes quando omitido
def test_ids_gerados_crescentes(db):
    livros = [inserir_livro(db, isbn="9780000000001"), inserir_livro(db, isbn="9780000000002")]
    usuarios = [inserir_usuario(db, cpf="11111111111"), inserir_usuario(db, cpf="22222222222")]
    emprestimos = [
        inserir_emprestimo(db, usuarios[0], livros[0]),
        inserir_emprestimo(db, usuarios[1], livros[1]),
    ]
    eventos = [inserir_evento(db), inserir_evento(db)]

    for ids in (livros, usuarios, emprestimos, eventos):
        assert all(isinstance(i, int) for i in ids)
        assert ids[0] < ids[1]


# 00-convencoes §11 · criado_em padrão = agora em America/Sao_Paulo (independe do fuso da sessão)
@pytest.mark.parametrize("tabela", ["livros", "usuarios", "eventos_pendentes"])
def test_criado_em_padrao_e_horario_de_sao_paulo(db, tabela):
    db.execute("SET TIME ZONE 'UTC'")
    inserir = {"livros": inserir_livro, "usuarios": inserir_usuario}.get(tabela, inserir_evento)
    novo_id = inserir(db)

    criado_em = db.execute(f"SELECT criado_em FROM {tabela} WHERE id = %s", (novo_id,)).fetchone()[
        0
    ]

    assert criado_em.tzinfo is None
    assert criado_em.microsecond == 0
    assert abs(criado_em - agora_sp()) < timedelta(minutes=2)


# 00-convencoes §11 · a aplicação pode informar criado_em explicitamente
def test_criado_em_pode_ser_informado(db):
    novo_id = db.execute(
        "INSERT INTO usuarios (nome, cpf, contato, criado_em) VALUES (%s, %s, %s, %s) RETURNING id",
        ("Lucas Joaquim", "12345678900", "l@email.com", T0),
    ).fetchone()[0]

    criado_em = db.execute("SELECT criado_em FROM usuarios WHERE id = %s", (novo_id,)).fetchone()
    assert criado_em == (T0,)


# 00-convencoes §8 e §11 · eventos_pendentes: tentativas 1, ultimo_erro nulo, datas padrão
def test_eventos_pendentes_valores_padrao(db):
    db.execute("SET TIME ZONE 'UTC'")
    novo_id = inserir_evento(db)

    payload, tentativas, ultimo_erro, criado_em, atualizado_em = db.execute(
        "SELECT payload, tentativas, ultimo_erro, criado_em, atualizado_em"
        " FROM eventos_pendentes WHERE id = %s",
        (novo_id,),
    ).fetchone()

    assert payload == PAYLOAD
    assert tentativas == 1
    assert ultimo_erro is None
    for instante in (criado_em, atualizado_em):
        assert instante.microsecond == 0
        assert abs(instante - agora_sp()) < timedelta(minutes=2)


# --------------------------------------------------------------------------- livros


# CT9 · Erros · ISBN duplicado → restrição única
def test_livros_isbn_duplicado_recusado(db):
    inserir_livro(db, isbn="9780000000001")

    with pytest.raises(errors.UniqueViolation):
        inserir_livro(db, isbn="9780000000001", titulo="Outro")

    assert contar(db, "livros") == 1
    inserir_livro(db, isbn="9780000000002")
    assert contar(db, "livros") == 2


# 00-convencoes §11 · quantidade_exemplares >= 1
def test_livros_quantidade_exemplares_zero_recusada(db):
    with pytest.raises(errors.CheckViolation):
        inserir_livro(db, exemplares=0, disponivel=0)


# 00-convencoes §11 · borda: quantidade_exemplares = 1 é aceita
def test_livros_quantidade_exemplares_um_aceita(db):
    inserir_livro(db, exemplares=1, disponivel=1)

    assert contar(db, "livros") == 1


# CT9 · Erros · quantidade_disponivel >= 0
def test_livros_quantidade_disponivel_negativa_recusada(db):
    with pytest.raises(errors.CheckViolation):
        inserir_livro(db, exemplares=3, disponivel=-1)


# CT9 · Erros · quantidade disponível ficaria menor que zero (alteração recusada)
def test_livros_baixar_disponivel_abaixo_de_zero_recusado(db):
    livro_id = inserir_livro(db, exemplares=1, disponivel=0)

    with pytest.raises(errors.CheckViolation):
        db.execute(
            "UPDATE livros SET quantidade_disponivel = quantidade_disponivel - 1 WHERE id = %s",
            (livro_id,),
        )

    disponivel = db.execute(
        "SELECT quantidade_disponivel FROM livros WHERE id = %s", (livro_id,)
    ).fetchone()[0]
    assert disponivel == 0


# 00-convencoes §11 · quantidade_disponivel <= quantidade_exemplares
def test_livros_disponivel_maior_que_exemplares_recusado(db):
    with pytest.raises(errors.CheckViolation):
        inserir_livro(db, exemplares=3, disponivel=4)


# 00-convencoes §11 · bordas aceitas: disponível = exemplares e disponível = 0
@pytest.mark.parametrize("disponivel", [3, 0])
def test_livros_disponivel_nas_bordas_aceito(db, disponivel):
    livro_id = inserir_livro(db, exemplares=3, disponivel=disponivel)

    gravado = db.execute(
        "SELECT quantidade_disponivel FROM livros WHERE id = %s", (livro_id,)
    ).fetchone()
    assert gravado == (disponivel,)


# CT9 / 00-convencoes §11 · campos obrigatórios de livros não aceitam nulo
@pytest.mark.parametrize(
    "coluna", ["titulo", "autor", "isbn", "quantidade_exemplares", "quantidade_disponivel"]
)
def test_livros_campos_obrigatorios_nao_nulos(db, coluna):
    valores = {
        "titulo": "Título",
        "autor": "Autor",
        "isbn": "9780000000001",
        "quantidade_exemplares": 3,
        "quantidade_disponivel": 3,
    }
    valores[coluna] = None

    with pytest.raises(errors.NotNullViolation):
        db.execute(
            "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
            " VALUES (%(titulo)s, %(autor)s, %(isbn)s, %(quantidade_exemplares)s,"
            " %(quantidade_disponivel)s)",
            valores,
        )


# --------------------------------------------------------------------------- usuarios


# CT10 · Erros · CPF duplicado → restrição única
def test_usuarios_cpf_duplicado_recusado(db):
    inserir_usuario(db, cpf="12345678900")

    with pytest.raises(errors.UniqueViolation):
        inserir_usuario(db, cpf="12345678900", nome="Outra Pessoa")

    assert contar(db, "usuarios") == 1
    inserir_usuario(db, cpf="12345678901")
    assert contar(db, "usuarios") == 2


# CT10 / 00-convencoes §11 · nome, cpf, contato não nulos
@pytest.mark.parametrize("coluna", ["nome", "cpf", "contato"])
def test_usuarios_campos_obrigatorios_nao_nulos(db, coluna):
    valores = {"nome": "Lucas Joaquim", "cpf": "12345678900", "contato": "l@email.com"}
    valores[coluna] = None

    with pytest.raises(errors.NotNullViolation):
        db.execute(
            "INSERT INTO usuarios (nome, cpf, contato) VALUES (%(nome)s, %(cpf)s, %(contato)s)",
            valores,
        )


# --------------------------------------------------------------------------- emprestimos


# CT11 · Erros · status fora da lista; D3 · 'atrasado' não é gravado
@pytest.mark.parametrize("status", ["atrasado", "qualquer"])
def test_emprestimos_status_fora_da_lista_recusado(db, usuario_e_livro, status):
    usuario_id, livro_id = usuario_e_livro

    with pytest.raises(errors.CheckViolation):
        inserir_emprestimo(db, usuario_id, livro_id, status=status)

    assert contar(db, "emprestimos") == 0


# CT11 · status 'ativo' (sem devolvido_em) e 'devolvido' (com devolvido_em) aceitos
@pytest.mark.parametrize(
    ("status", "devolvido_em"), [("ativo", None), ("devolvido", T0 + timedelta(days=3))]
)
def test_emprestimos_status_validos_aceitos(db, usuario_e_livro, status, devolvido_em):
    usuario_id, livro_id = usuario_e_livro

    emprestimo_id = inserir_emprestimo(
        db, usuario_id, livro_id, status=status, devolvido_em=devolvido_em
    )

    assert db.execute(
        "SELECT status, devolvido_em FROM emprestimos WHERE id = %s", (emprestimo_id,)
    ).fetchone() == (status, devolvido_em)


# 00-convencoes §11 · status 'devolvido' exige devolvido_em
def test_emprestimos_devolvido_sem_devolvido_em_recusado(db, usuario_e_livro):
    usuario_id, livro_id = usuario_e_livro

    with pytest.raises(errors.CheckViolation):
        inserir_emprestimo(db, usuario_id, livro_id, status="devolvido", devolvido_em=None)


# 00-convencoes §11 · status 'ativo' não pode ter devolvido_em
def test_emprestimos_ativo_com_devolvido_em_recusado(db, usuario_e_livro):
    usuario_id, livro_id = usuario_e_livro

    with pytest.raises(errors.CheckViolation):
        inserir_emprestimo(
            db, usuario_id, livro_id, status="ativo", devolvido_em=T0 + timedelta(days=1)
        )


# CT11 / CT6 · devolução: ativo → devolvido com devolvido_em é aceita
def test_emprestimos_atualizar_para_devolvido_aceito(db, usuario_e_livro):
    usuario_id, livro_id = usuario_e_livro
    emprestimo_id = inserir_emprestimo(db, usuario_id, livro_id)
    devolucao = LIMITE + timedelta(days=2)

    db.execute(
        "UPDATE emprestimos SET status = 'devolvido', devolvido_em = %s WHERE id = %s",
        (devolucao, emprestimo_id),
    )

    assert db.execute(
        "SELECT status, devolvido_em FROM emprestimos WHERE id = %s", (emprestimo_id,)
    ).fetchone() == ("devolvido", devolucao)


# 00-convencoes §11 · data_limite_devolucao > emprestado_em
@pytest.mark.parametrize("data_limite", [T0, T0 - timedelta(seconds=1)], ids=["igual", "anterior"])
def test_emprestimos_data_limite_nao_posterior_recusada(db, usuario_e_livro, data_limite):
    usuario_id, livro_id = usuario_e_livro

    with pytest.raises(errors.CheckViolation):
        inserir_emprestimo(db, usuario_id, livro_id, data_limite=data_limite)


# 00-convencoes §11 · borda: data limite um segundo depois de emprestado_em é aceita
def test_emprestimos_data_limite_um_segundo_depois_aceita(db, usuario_e_livro):
    usuario_id, livro_id = usuario_e_livro

    inserir_emprestimo(db, usuario_id, livro_id, data_limite=T0 + timedelta(seconds=1))

    assert contar(db, "emprestimos") == 1


# 00-convencoes §11 · devolvido_em >= emprestado_em
def test_emprestimos_devolvido_antes_de_emprestado_recusado(db, usuario_e_livro):
    usuario_id, livro_id = usuario_e_livro

    with pytest.raises(errors.CheckViolation):
        inserir_emprestimo(
            db,
            usuario_id,
            livro_id,
            status="devolvido",
            devolvido_em=T0 - timedelta(seconds=1),
        )


# 00-convencoes §11 · borda: devolvido_em = emprestado_em é aceito
def test_emprestimos_devolvido_no_mesmo_instante_aceito(db, usuario_e_livro):
    usuario_id, livro_id = usuario_e_livro

    inserir_emprestimo(db, usuario_id, livro_id, status="devolvido", devolvido_em=T0)

    assert contar(db, "emprestimos") == 1


# CT10 / CT11 · Erros · usuário referenciado não existe → chave estrangeira
def test_emprestimos_usuario_inexistente_recusado(db):
    livro_id = inserir_livro(db)

    with pytest.raises(errors.ForeignKeyViolation):
        inserir_emprestimo(db, 999_999, livro_id)


# CT9 / CT11 · Erros · livro referenciado não existe → chave estrangeira
def test_emprestimos_livro_inexistente_recusado(db):
    usuario_id = inserir_usuario(db)

    with pytest.raises(errors.ForeignKeyViolation):
        inserir_emprestimo(db, usuario_id, 999_999)


# 00-convencoes §11 · excluir livro ou usuário com empréstimo é recusado (sem cascata)
@pytest.mark.parametrize("tabela", ["livros", "usuarios"])
def test_excluir_com_emprestimo_recusado(db, usuario_e_livro, tabela):
    usuario_id, livro_id = usuario_e_livro
    inserir_emprestimo(db, usuario_id, livro_id)
    alvo = livro_id if tabela == "livros" else usuario_id

    with pytest.raises(errors.ForeignKeyViolation):
        db.execute(f"DELETE FROM {tabela} WHERE id = %s", (alvo,))

    assert contar(db, tabela) == 1
    assert contar(db, "emprestimos") == 1


# CT11 · campos obrigatórios de emprestimos não aceitam nulo
@pytest.mark.parametrize(
    "coluna", ["usuario_id", "livro_id", "status", "emprestado_em", "data_limite_devolucao"]
)
def test_emprestimos_campos_obrigatorios_nao_nulos(db, usuario_e_livro, coluna):
    usuario_id, livro_id = usuario_e_livro
    valores = {
        "usuario_id": usuario_id,
        "livro_id": livro_id,
        "status": "ativo",
        "emprestado_em": T0,
        "data_limite_devolucao": LIMITE,
    }
    valores[coluna] = None

    with pytest.raises(errors.NotNullViolation):
        db.execute(
            "INSERT INTO emprestimos"
            " (usuario_id, livro_id, status, emprestado_em, data_limite_devolucao)"
            " VALUES (%(usuario_id)s, %(livro_id)s, %(status)s, %(emprestado_em)s,"
            " %(data_limite_devolucao)s)",
            valores,
        )


# --------------------------------------------------------------------------- eventos_pendentes


# 00-convencoes §11 · tentativas >= 1
def test_eventos_tentativas_zero_recusada(db):
    with pytest.raises(errors.CheckViolation):
        db.execute(
            "INSERT INTO eventos_pendentes (payload, tentativas) VALUES (%s, 0)",
            (Jsonb(PAYLOAD),),
        )


# 00-convencoes §11 · borda: tentativas = 1 informada é aceita; ultimo_erro aceita texto
def test_eventos_tentativas_um_e_ultimo_erro_aceitos(db):
    db.execute(
        "INSERT INTO eventos_pendentes (payload, tentativas, ultimo_erro) VALUES (%s, 1, %s)",
        (Jsonb(PAYLOAD), "timeout"),
    )

    assert db.execute("SELECT tentativas, ultimo_erro FROM eventos_pendentes").fetchone() == (
        1,
        "timeout",
    )


# 00-convencoes §11 · payload jsonb não nulo
def test_eventos_payload_nulo_recusado(db):
    with pytest.raises(errors.NotNullViolation):
        inserir_evento(db, payload=None)


# --------------------------------------------------------------------------- conexão


# 8B (conftest) · após um erro, a conexão autocommit continua utilizável e nada se perde
def test_conexao_continua_utilizavel_apos_erro(db):
    inserir_livro(db, isbn="9780000000001")

    with pytest.raises(errors.UniqueViolation):
        inserir_livro(db, isbn="9780000000001")

    inserir_livro(db, isbn="9780000000002")
    assert db.execute("SELECT 1").fetchone()[0] == 1
    assert contar(db, "livros") == 2


# --------------------------------------------------------------------------- idempotência


# agentes.md §7 E2 / D18 · o script é idempotente: reaplicar não falha nem apaga dados
def test_schema_reaplicavel_sem_erro_e_sem_perder_dados(db, usuario_e_livro):
    usuario_id, livro_id = usuario_e_livro
    emprestimo_id = inserir_emprestimo(db, usuario_id, livro_id)
    evento_id = inserir_evento(db)
    antes = {
        tabela: db.execute(f"SELECT * FROM {tabela} ORDER BY id").fetchall() for tabela in COLUNAS
    }

    db.execute(SCHEMA_SQL.read_text(encoding="utf-8"))

    for tabela, linhas in antes.items():
        assert len(linhas) == 1, tabela
        assert db.execute(f"SELECT * FROM {tabela} ORDER BY id").fetchall() == linhas, tabela
    assert antes["emprestimos"][0][0] == emprestimo_id
    assert antes["eventos_pendentes"][0][0] == evento_id
    with pytest.raises(errors.UniqueViolation):
        inserir_livro(db, isbn="9780000000001", titulo="Outro")
    assert contar(db, "livros") == 1
