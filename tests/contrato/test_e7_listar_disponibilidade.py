"""E7 — listarDisponibilidade (card #790): `GET /livros/disponibilidade?busca`.

Fontes: CT7, CT9; `00-convencoes.md` §3, §6 (busca, ordem, sem paginação) e §11; card
#790: "devolve só os livros com quantidade disponível maior que zero"; `agentes.md` D17.
Livros semeados por SQL direto (fixture `db`), sem `id` explícito.
"""

import unicodedata

import pytest

ROTA = "/livros/disponibilidade"
CAMPOS_LIVRO = {"id", "titulo", "quantidadeExemplares", "quantidadeDisponivel", "disponivel"}
TRECHOS_PROIBIDOS = ("syntax error", "psycopg", "sqlstate", "traceback", "like", "select")

# Acervo para busca: chave -> (titulo, autor, isbn, exemplares, disponivel)
ACERVO = {
    "fundamentos": ("Fundamentos de Sistemas de Informação", "Ana Silva", "9780000000001", 3, 2),
    "banco": ("Banco de Dados", "Carlos Pereira", "9780000000002", 2, 2),
    "algoritmos": ("Algoritmos", "José Antônio", "0306406152", 4, 1),
    "python": ("Python 100%", "Maria Souza", "9780000000003", 1, 1),
    "guia": ("Guia_Rapido", "Pedro Lima", "9780000000004", 2, 1),
    "barra": ("Caminhos C:\\Windows", "Paula Reis", "9780000000005", 1, 1),
    "cpp": ("C++ Moderno", "Bjarne Teste", "9780000000006", 2, 2),
    "introducao": ("Introducao a Programacao", "Beatriz Costa", "9780000000007", 2, 1),
    # emprestados por completo: nunca aparecem
    "redes": ("Redes de Computadores", "Ana Silva", "9780000000008", 2, 0),
    "sistemas_op": ("Sistemas Operacionais", "Tanen Baum", "9780000000009", 1, 0),
}
DISPONIVEIS = [chave for chave, dados in ACERVO.items() if dados[4] > 0]


# --------------------------------------------------------------------------- apoio


def semear_livro(db, titulo, autor="Autor", isbn=None, exemplares=3, disponivel=None) -> int:
    disponivel = exemplares if disponivel is None else disponivel
    if isbn is None:
        quantos = db.execute("SELECT count(*) FROM livros").fetchone()[0]
        isbn = f"{9790000000000 + quantos}"
    return db.execute(
        "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (titulo, autor, isbn, exemplares, disponivel),
    ).fetchone()[0]


@pytest.fixture
def acervo(db):
    return {chave: semear_livro(db, *dados) for chave, dados in ACERVO.items()}


def listar(client, **params):
    return client.get(ROTA, params=params)


def assert_ok(resposta) -> list[dict]:
    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["content-type"].startswith("application/json")
    dados = resposta.json()
    assert set(dados) == {"livros"}
    assert isinstance(dados["livros"], list)
    return dados["livros"]


def ids(livros) -> list[int]:
    return [livro["id"] for livro in livros]


def esperados(acervo, chaves) -> list[int]:
    """Ids das chaves na ordem do §6 (título sem caixa nem acento, texto exato, id)."""
    return [
        acervo[c] for c in sorted(chaves, key=lambda c: (chave_de_ordem(ACERVO[c][0]), acervo[c]))
    ]


def sem_acento_minusculo(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def chave_de_ordem(texto: str) -> tuple[str, str]:
    """00-convencoes §6: sem caixa nem acento; empate → texto exato por código de caractere."""
    return (sem_acento_minusculo(texto), texto)


def assert_erro(resposta, status: int, codigo: str) -> None:
    """00-convencoes §3 · formato do corpo de erro, sem texto interno."""
    assert resposta.status_code == status, resposta.text
    assert resposta.headers["content-type"].startswith("application/json")
    dados = resposta.json()
    assert set(dados) == {"erro"}
    assert set(dados["erro"]) == {"codigo", "mensagem"}
    assert dados["erro"]["codigo"] == codigo
    mensagem = dados["erro"]["mensagem"]
    assert isinstance(mensagem, str)
    assert mensagem.strip()
    for trecho in TRECHOS_PROIBIDOS:
        assert trecho not in mensagem.lower(), mensagem


# --------------------------------------------------------------------------- saída


# CT7 · Saída · chave única `livros`; LivroDisponibilidade com exatamente 5 campos e tipos
def test_saida_com_campos_e_tipos_do_ct7(client, db):
    livro_id = semear_livro(
        db, "Fundamentos de Sistemas de Informação", "Ana Silva", "9780000000001", 3, 2
    )

    livros = assert_ok(listar(client))

    assert len(livros) == 1
    livro = livros[0]
    assert set(livro) == CAMPOS_LIVRO
    assert "autor" not in livro
    assert "isbn" not in livro
    for campo in ("id", "quantidadeExemplares", "quantidadeDisponivel"):
        assert type(livro[campo]) is int, campo
    assert livro["disponivel"] is True
    assert livro == {
        "id": livro_id,
        "titulo": "Fundamentos de Sistemas de Informação",
        "quantidadeExemplares": 3,
        "quantidadeDisponivel": 2,
        "disponivel": True,
    }


# CT7 · `disponivel` é sempre true na lista; quantidades refletem o banco
def test_disponivel_sempre_true_e_quantidades_do_banco(client, acervo):
    livros = assert_ok(listar(client))

    assert all(livro["disponivel"] is True for livro in livros)
    por_id = {livro["id"]: livro for livro in livros}
    for chave in DISPONIVEIS:
        _, _, _, exemplares, disponivel = ACERVO[chave]
        livro = por_id[acervo[chave]]
        assert (livro["quantidadeExemplares"], livro["quantidadeDisponivel"]) == (
            exemplares,
            disponivel,
        )


# --------------------------------------------------------------------------- filtro


# Card #790 / CT7 · só livros com quantidade disponível > 0 (0 some, 1 aparece)
def test_so_livros_com_exemplar_livre(client, db):
    zero = semear_livro(db, "Livro Zero", exemplares=3, disponivel=0)
    um = semear_livro(db, "Livro Um", exemplares=3, disponivel=1)
    cheio = semear_livro(db, "Livro Cheio", exemplares=3, disponivel=3)

    livros = assert_ok(listar(client))

    assert zero not in ids(livros)
    assert sorted(ids(livros)) == sorted([um, cheio])


# CT7 · acervo completo: aparecem exatamente os disponíveis, na ordem do §6
def test_acervo_mostra_so_os_disponiveis(client, acervo):
    livros = assert_ok(listar(client))

    assert ids(livros) == esperados(acervo, DISPONIVEIS)


# CT7 · banco vazio → lista vazia
def test_banco_vazio(client):
    assert assert_ok(listar(client)) == []


# CT7 · acervo todo emprestado → lista vazia
def test_acervo_todo_emprestado(client, db):
    for numero in range(3):
        semear_livro(db, f"Emprestado {numero}", exemplares=2, disponivel=0)

    assert assert_ok(listar(client)) == []


# Card #790 · dados mudando: disponível vai a 0 → some; volta a 1 → reaparece
def test_lista_acompanha_mudanca_no_banco(client, db):
    livro_id = semear_livro(db, "Livro Móvel", exemplares=2, disponivel=1)
    outro = semear_livro(db, "Outro Livro", exemplares=1, disponivel=1)
    assert sorted(ids(assert_ok(listar(client)))) == sorted([livro_id, outro])

    db.execute("UPDATE livros SET quantidade_disponivel = 0 WHERE id = %s", (livro_id,))
    assert ids(assert_ok(listar(client))) == [outro]

    db.execute("UPDATE livros SET quantidade_disponivel = 1 WHERE id = %s", (livro_id,))
    assert sorted(ids(assert_ok(listar(client)))) == sorted([livro_id, outro])


# --------------------------------------------------------------------------- busca


# 00-convencoes §6 · busca em título, autor ou ISBN (mesmo sem autor/isbn na saída)
@pytest.mark.parametrize(
    ("busca", "chaves"),
    [
        ("sistemas", ["fundamentos"]),
        ("SISTEMAS", ["fundamentos"]),
        ("informacao", ["fundamentos"]),
        ("INFORMAÇÃO", ["fundamentos"]),
        ("Programação", ["introducao"]),
        ("stemas", ["fundamentos"]),
        ("silva", ["fundamentos"]),
        ("pereira", ["banco"]),
        ("jose", ["algoritmos"]),
        ("ANTÔNIO", ["algoritmos"]),
        ("9780000000002", ["banco"]),
        ("030640", ["algoritmos"]),
        ("de", ["banco", "cpp", "fundamentos"]),
    ],
    ids=lambda valor: valor if isinstance(valor, str) else None,
)
def test_busca(client, acervo, busca, chaves):
    assert ids(assert_ok(listar(client, busca=busca))) == esperados(acervo, chaves)


# CT7 · a busca só traz livros disponíveis (termos que só casam com emprestados → vazio)
@pytest.mark.parametrize(
    ("busca", "chaves"),
    [
        ("redes", []),
        ("operacionais", []),
        ("9780000000008", []),
        ("baum", []),
        ("ana silva", ["fundamentos"]),
        ("sistemas", ["fundamentos"]),
    ],
    ids=[
        "titulo-emprestado",
        "titulo-emprestado-2",
        "isbn-emprestado",
        "autor-emprestado",
        "autor-com-um-emprestado",
        "titulo-com-um-emprestado",
    ],
)
def test_busca_so_traz_disponiveis(client, acervo, busca, chaves):
    assert ids(assert_ok(listar(client, busca=busca))) == esperados(acervo, chaves)


# 00-convencoes §6 · %, _ e \\ são literais
@pytest.mark.parametrize(
    ("busca", "chaves"),
    [
        ("%", ["python"]),
        ("0%", ["python"]),
        ("%%", []),
        ("_", ["guia"]),
        ("a_r", ["guia"]),
        ("o_r", []),
        ("\\", ["barra"]),
        ("c:\\w", ["barra"]),
        ("\\%", []),
    ],
    ids=["pct", "zero-pct", "dois-pct", "sub", "a_r", "o_r", "barra", "c-barra-w", "barra-pct"],
)
def test_busca_com_literais(client, acervo, busca, chaves):
    assert ids(assert_ok(listar(client, busca=busca))) == esperados(acervo, chaves)


# 00-convencoes §6 · `+` na URL é espaço; `%2B` é o caractere +
@pytest.mark.parametrize(
    ("consulta", "chaves"),
    [
        ("busca=banco+de", ["banco"]),
        ("busca=+dados+", ["banco"]),
        ("busca=%2B%2B", ["cpp"]),
        ("busca=c%2B%2B", ["cpp"]),
        ("busca=C++Moderno", []),
        ("busca=+++", list(DISPONIVEIS)),
    ],
    ids=[
        "mais-e-espaco",
        "mais-nas-pontas",
        "pct2b",
        "c-pct2b",
        "mais-vira-espaco-no-meio",
        "so-mais",
    ],
)
def test_mais_na_url_e_espaco(client, acervo, consulta, chaves):
    assert ids(assert_ok(client.get(f"{ROTA}?{consulta}"))) == esperados(acervo, chaves)


# 00-convencoes §6 · busca com brancos nas pontas (espaço, tabulação, quebra de linha)
def test_busca_com_brancos_nas_pontas(client, acervo):
    assert ids(assert_ok(listar(client, busca="\t dados \n"))) == [acervo["banco"]]


# 00-convencoes §6 · busca vazia ou só brancos = sem filtro
@pytest.mark.parametrize("busca", ["", "   ", "\t\n"], ids=["vazia", "espacos", "tab-quebra"])
def test_busca_vazia_e_sem_filtro(client, acervo, busca):
    assert ids(assert_ok(listar(client, busca=busca))) == esperados(acervo, DISPONIVEIS)


# 00-convencoes §6 · busca sem resultado → lista vazia
def test_busca_sem_resultado(client, acervo):
    assert assert_ok(listar(client, busca="inexistente")) == []


# 00-convencoes §6 · hífens não são removidos ao buscar ISBN
def test_busca_por_isbn_com_hifens_nao_normaliza(client, acervo):
    assert assert_ok(listar(client, busca="978-0")) == []


# 00-convencoes §6 · aspas não quebram a consulta
@pytest.mark.parametrize("busca", ["'", "'; DROP TABLE livros; --", '"'])
def test_busca_com_aspas(client, db, acervo, busca):
    assert assert_ok(listar(client, busca=busca)) == []
    assert db.execute("SELECT count(*) FROM livros").fetchone()[0] == len(ACERVO)


# 00-convencoes §6 · parâmetro repetido: vale o primeiro valor
def test_busca_repetida_vale_a_primeira(client, acervo):
    assert ids(assert_ok(client.get(f"{ROTA}?busca=dados&busca=sistemas"))) == [acervo["banco"]]


# 00-convencoes §6 · 100 caracteres (depois do corte das pontas) aceitos
@pytest.mark.parametrize(
    "busca",
    ["a" * 100, "ã" * 100, " \t" + "a" * 100 + "\n "],
    ids=["100-ascii", "100-acentuados", "100-com-brancos"],
)
def test_busca_com_100_caracteres_aceita(client, acervo, busca):
    assert assert_ok(listar(client, busca=busca)) == []


# 00-convencoes §11 · busca sem caixa também para letras não latinas (locale UTF-8)
def test_busca_sem_caixa_em_letras_nao_latinas(client, db):
    grego = semear_livro(db, "Ελληνική Γραμματική")
    cirilico = semear_livro(db, "Книга Программиста")

    assert ids(assert_ok(listar(client, busca="ελληνική"))) == [grego]
    assert ids(assert_ok(listar(client, busca="КНИГА"))) == [cirilico]


# --------------------------------------------------------------------------- BUSCA_INVALIDA


# CT7 · Erros · termo de busca com mais de 100 caracteres
@pytest.mark.parametrize(
    "busca",
    ["a" * 101, "ã" * 101, "  " + "a" * 101 + "\t"],
    ids=["101-ascii", "101-acentuados", "101-com-brancos"],
)
def test_busca_com_101_caracteres(client, acervo, busca):
    assert_erro(listar(client, busca=busca), 400, "BUSCA_INVALIDA")


# 00-convencoes §6 · NUL, metade de par substituto ou bytes não UTF-8 → BUSCA_INVALIDA
@pytest.mark.parametrize(
    "busca_codificada",
    ["%00", "dados%00", "%ED%A0%80", "%ED%B0%80", "%FF", "dados%C3", "%C3%28"],
    ids=["nul", "nul-no-fim", "surrogate-alto", "surrogate-baixo", "byte-ff", "truncado", "c3-28"],
)
def test_busca_com_caractere_invalido(client, acervo, busca_codificada):
    assert_erro(client.get(f"{ROTA}?busca={busca_codificada}"), 400, "BUSCA_INVALIDA")


# --------------------------------------------------------------------------- ordem


# 00-convencoes §6 · ordem alfabética sem caixa nem acento; empate pelo texto exato; depois id
def test_ordem_alfabetica_do_paragrafo_6(client, db):
    titulos = [
        "Zoologia",
        "álgebra linear",
        "Banco de Dados",
        "cálculo",
        "Álgebra Linear",
        "algebra linear",
    ]
    por_titulo = {titulo: semear_livro(db, titulo) for titulo in titulos}
    repetido = semear_livro(db, "cálculo")

    livros = assert_ok(listar(client))

    esperada = sorted(titulos, key=chave_de_ordem)
    assert esperada[:3] == ["algebra linear", "Álgebra Linear", "álgebra linear"]
    ordem_ids = [por_titulo[t] for t in esperada]
    ordem_ids.insert(esperada.index("cálculo") + 1, repetido)
    assert ids(livros) == ordem_ids


# 00-convencoes §6 · ordem vale também com busca, e emprestados não entram
def test_ordem_com_busca(client, db):
    z = semear_livro(db, "Zoologia Aplicada")
    c = semear_livro(db, "cálculo aplicado")
    semear_livro(db, "Biologia Aplicada", exemplares=2, disponivel=0)
    a = semear_livro(db, "Álgebra Aplicada")

    assert ids(assert_ok(listar(client, busca="aplicad"))) == [a, c, z]


# --------------------------------------------------------------------------- sem paginação


@pytest.fixture
def trinta_livros(db):
    """30 livros disponíveis ('Livro 01'..'Livro 30') e 5 emprestados; devolve ids em ordem."""
    por_numero = {
        n: semear_livro(db, f"Livro {n:02d}") for n in [*range(30, 15, -1), *range(1, 16)]
    }
    for n in range(5):
        semear_livro(db, f"Emprestado {n}", disponivel=0)
    return [por_numero[n] for n in range(1, 31)]


# CT7 / 00-convencoes §6 · sem paginação: a lista vem inteira (mais de 20 livros)
def test_lista_vem_inteira(client, trinta_livros):
    assert ids(assert_ok(listar(client))) == trinta_livros


# 00-convencoes §6 · pagina/tamanho são desconhecidos aqui, portanto ignorados
@pytest.mark.parametrize(
    "consulta",
    ["pagina=0", "tamanho=0", "pagina=2&tamanho=5", "tamanho=abc", "pagina=%00", "foo=bar"],
)
def test_parametros_de_paginacao_ignorados(client, trinta_livros, consulta):
    assert ids(assert_ok(client.get(f"{ROTA}?{consulta}"))) == trinta_livros


# --------------------------------------------------------------------------- rotas


# CT7 · /livros/disponibilidade não é confundida com outra rota; GET /livros continua igual
def test_get_livros_continua_funcionando(client, acervo):
    resposta = client.get("/livros", params={"tamanho": "100"})

    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert set(dados) == {"livros", "total", "pagina", "tamanho"}
    assert dados["total"] == len(ACERVO)
    assert {"autor", "isbn"} <= set(dados["livros"][0])
    assert acervo["redes"] in [livro["id"] for livro in dados["livros"]]


# 00-convencoes §3 · barra no fim e caminhos vizinhos são rotas inexistentes
@pytest.mark.parametrize(
    "caminho",
    ["/livros/disponibilidade/", "/livros/disponibilidade/extra", "/livros/disponibilidades"],
)
def test_caminhos_vizinhos_inexistentes(client, caminho):
    assert_erro(client.get(caminho, follow_redirects=False), 404, "ROTA_NAO_ENCONTRADA")


# 00-convencoes §3 · métodos não permitidos em /livros/disponibilidade
@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE"])
def test_metodo_nao_permitido(client, db, metodo):
    resposta = client.request(metodo, ROTA, json={"titulo": "x"})

    assert_erro(resposta, 405, "ROTA_NAO_ENCONTRADA")
    assert db.execute("SELECT count(*) FROM livros").fetchone()[0] == 0
