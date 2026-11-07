"""E6 — consultarLivros (card #788): `GET /livros?busca&pagina&tamanho`.

Fontes: CT2, CT9; `00-convencoes.md` §2, §3, §6 e §11; `agentes.md` D13 e D17. Livros
semeados por SQL direto (fixture `db`), sem `id` explícito.
"""

import unicodedata

import pytest

ROTA = "/livros"
CAMPOS_RESPOSTA = {"livros", "total", "pagina", "tamanho"}
CAMPOS_LIVRO = {"id", "titulo", "autor", "isbn", "quantidadeExemplares", "quantidadeDisponivel"}
TRECHOS_PROIBIDOS = ("syntax error", "psycopg", "sqlstate", "traceback", "like", "select")

# Acervo para os testes de busca: (titulo, autor, isbn)
ACERVO = {
    "fundamentos": ("Fundamentos de Sistemas de Informação", "Ana Silva", "9780000000001"),
    "banco": ("Banco de Dados", "Carlos Pereira", "9780000000002"),
    "algoritmos": ("Algoritmos", "José Antônio", "0306406152"),
    "python": ("Python 100%", "Maria Souza", "9780000000003"),
    "guia": ("Guia_Rapido", "Pedro Lima", "9780000000004"),
    "oreilly": ("O'Reilly Guia", "Tim O'Reilly", "9780000000005"),
    "introducao": ("Introducao a Programacao", "Beatriz Costa", "9780000000006"),
}


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
    """Semeia o ACERVO e devolve {chave: id}."""
    return {chave: semear_livro(db, *dados) for chave, dados in ACERVO.items()}


def consultar(client, **params):
    return client.get(ROTA, params=params)


def assert_ok(resposta) -> dict:
    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["content-type"].startswith("application/json")
    dados = resposta.json()
    assert set(dados) == CAMPOS_RESPOSTA
    return dados


def ids(dados) -> list[int]:
    return [livro["id"] for livro in dados["livros"]]


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


# CT2 · Saída · chaves exatas da resposta e do LivroResumo, com tipos
def test_saida_com_campos_e_tipos_do_ct2(client, db):
    livro_id = semear_livro(
        db, "Fundamentos de Sistemas de Informação", "Ana Silva", "9780000000001", 3, 1
    )

    dados = assert_ok(consultar(client))

    assert type(dados["total"]) is int
    assert type(dados["pagina"]) is int
    assert type(dados["tamanho"]) is int
    assert len(dados["livros"]) == 1
    livro = dados["livros"][0]
    assert set(livro) == CAMPOS_LIVRO
    for campo in ("id", "quantidadeExemplares", "quantidadeDisponivel"):
        assert type(livro[campo]) is int, campo
    assert livro == {
        "id": livro_id,
        "titulo": "Fundamentos de Sistemas de Informação",
        "autor": "Ana Silva",
        "isbn": "9780000000001",
        "quantidadeExemplares": 3,
        "quantidadeDisponivel": 1,
    }


# CT2 · quantidadeDisponivel reflete o banco, inclusive zero (CT2 não filtra disponibilidade)
def test_quantidade_disponivel_reflete_o_banco(client, db):
    semear_livro(db, "Livro A", exemplares=5, disponivel=2)
    semear_livro(db, "Livro B", exemplares=2, disponivel=0)

    livros = assert_ok(consultar(client))["livros"]

    assert [(x["quantidadeExemplares"], x["quantidadeDisponivel"]) for x in livros] == [
        (5, 2),
        (2, 0),
    ]


# CT2 · banco vazio → lista vazia e total 0
def test_banco_vazio(client):
    assert assert_ok(consultar(client)) == {"livros": [], "total": 0, "pagina": 1, "tamanho": 20}


# --------------------------------------------------------------------------- padrões


# 00-convencoes §6 · sem parâmetros: página 1, tamanho 20, ecoados na resposta
def test_padroes_sem_parametros(client, db):
    for numero in range(25):
        semear_livro(db, f"Livro {numero:02d}")

    dados = assert_ok(consultar(client))

    assert dados["pagina"] == 1
    assert dados["tamanho"] == 20
    assert dados["total"] == 25
    assert len(dados["livros"]) == 20


# CT2 · pagina e tamanho informados são ecoados na resposta
def test_pagina_e_tamanho_ecoados(client, db):
    for numero in range(5):
        semear_livro(db, f"Livro {numero:02d}")

    dados = assert_ok(consultar(client, pagina="2", tamanho="3"))

    assert (dados["pagina"], dados["tamanho"], dados["total"]) == (2, 3, 5)
    assert len(dados["livros"]) == 2


# --------------------------------------------------------------------------- busca


# 00-convencoes §6 · busca por parte do título, do autor ou do ISBN; maiúsculas e acentos
@pytest.mark.parametrize(
    ("busca", "esperados"),
    [
        ("sistemas", ["fundamentos"]),
        ("SISTEMAS", ["fundamentos"]),
        ("SiStEmAs", ["fundamentos"]),
        ("informacao", ["fundamentos"]),
        ("INFORMAÇÃO", ["fundamentos"]),
        ("Programação", ["introducao"]),
        ("stemas", ["fundamentos"]),
        ("de sistemas de", ["fundamentos"]),
        ("dados", ["banco"]),
        ("silva", ["fundamentos"]),
        ("PEREIRA", ["banco"]),
        ("jose", ["algoritmos"]),
        ("antonio", ["algoritmos"]),
        ("José Antônio", ["algoritmos"]),
        ("9780000000001", ["fundamentos"]),
        ("0000000002", ["banco"]),
        ("030640", ["algoritmos"]),
        ("guia", ["guia", "oreilly"]),
        ("de", ["banco", "fundamentos"]),
    ],
    ids=lambda valor: valor if isinstance(valor, str) else None,
)
def test_busca(client, acervo, busca, esperados):
    dados = assert_ok(consultar(client, busca=busca))

    assert ids(dados) == [acervo[chave] for chave in esperados]
    assert dados["total"] == len(esperados)


# 00-convencoes §6 · espaços das pontas da busca são removidos
def test_busca_com_espacos_nas_pontas(client, acervo):
    dados = assert_ok(consultar(client, busca="   dados  "))

    assert ids(dados) == [acervo["banco"]]


# 00-convencoes §6 · busca vazia ou só espaços = sem filtro
@pytest.mark.parametrize("busca", ["", "   "], ids=["vazia", "so-espacos"])
def test_busca_vazia_e_sem_filtro(client, acervo, busca):
    dados = assert_ok(consultar(client, busca=busca))

    assert dados["total"] == len(ACERVO)
    assert sorted(ids(dados)) == sorted(acervo.values())


# 00-convencoes §6 · busca sem resultado → lista vazia e total 0
def test_busca_sem_resultado(client, acervo):
    dados = assert_ok(consultar(client, busca="inexistente"))

    assert dados["livros"] == []
    assert dados["total"] == 0


# 00-convencoes §6 · o termo é texto literal: %, _ e \ não funcionam como curinga
@pytest.mark.parametrize(
    ("busca", "esperados"),
    [
        ("%", ["python"]),
        ("0%", ["python"]),
        ("_", ["guia"]),
        ("a_r", ["guia"]),
        ("o_r", []),
        ("%%", []),
        ("\\", []),
        ("\\%", []),
    ],
    ids=[
        "porcento",
        "zero-porcento",
        "sublinhado",
        "a_r",
        "o_r",
        "dois-porcento",
        "barra",
        "barra-pct",
    ],
)
def test_busca_com_caracteres_especiais_do_like(client, acervo, busca, esperados):
    dados = assert_ok(consultar(client, busca=busca))

    assert ids(dados) == [acervo[chave] for chave in esperados]
    assert dados["total"] == len(esperados)


# 00-convencoes §6 / §3 · aspas simples na busca não quebram a consulta
@pytest.mark.parametrize(
    ("busca", "esperados"),
    [
        ("o'reilly", ["oreilly"]),
        ("'", ["oreilly"]),
        ("'; DROP TABLE livros; --", []),
        ('"', []),
    ],
    ids=["oreilly", "aspa", "injecao", "aspa-dupla"],
)
def test_busca_com_aspas(client, db, acervo, busca, esperados):
    dados = assert_ok(consultar(client, busca=busca))

    assert ids(dados) == [acervo[chave] for chave in esperados]
    assert db.execute("SELECT count(*) FROM livros").fetchone()[0] == len(ACERVO)


# 00-convencoes §6 · busca com 100 caracteres (contados depois de cortar as pontas) é aceita
@pytest.mark.parametrize(
    "busca",
    ["a" * 100, "ã" * 100, "  " + "a" * 100 + "  "],
    ids=["100-ascii", "100-acentuados", "100-com-espacos"],
)
def test_busca_com_100_caracteres_aceita(client, acervo, busca):
    dados = assert_ok(consultar(client, busca=busca))

    assert dados["total"] == 0


# --------------------------------------------------------------------------- ordem


# 00-convencoes §6 · ordem por título (títulos claramente distintos, semeados fora de ordem)
def test_ordem_por_titulo(client, db):
    titulos = ["Compiladores", "Algoritmos", "Engenharia de Software", "Banco de Dados", "Direito"]
    por_titulo = {titulo: semear_livro(db, titulo) for titulo in titulos}

    dados = assert_ok(consultar(client))

    assert ids(dados) == [por_titulo[t] for t in sorted(titulos)]


def sem_acento_minusculo(texto: str) -> str:
    """Equivalente, nos testes, a unaccent + lower."""
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def chave_de_ordem(texto: str) -> tuple[str, str]:
    """00-convencoes §6: sem caixa nem acento; empate → texto exato por código de caractere."""
    return (sem_acento_minusculo(texto), texto)


# 00-convencoes §6 · ordem alfabética sem diferenciar maiúsculas nem acentos; empate pelo
# texto exato por código de caractere (U+0061 'a' < U+00C1 'Á' < U+00E1 'á')
def test_ordem_sem_diferenciar_maiusculas_nem_acentos(client, db):
    titulos = [
        "Zoologia",
        "álgebra linear",
        "Banco de Dados",
        "cálculo",
        "Álgebra Linear",
        "algebra linear",
    ]
    esperada = [
        "algebra linear",
        "Álgebra Linear",
        "álgebra linear",
        "Banco de Dados",
        "cálculo",
        "Zoologia",
    ]
    assert sorted(titulos, key=chave_de_ordem) == esperada
    por_titulo = {titulo: semear_livro(db, titulo) for titulo in titulos}

    dados = assert_ok(consultar(client))

    assert [livro["titulo"] for livro in dados["livros"]] == esperada
    assert ids(dados) == [por_titulo[t] for t in esperada]


# 00-convencoes §6 · exemplo do próprio §6: álgebra, Banco, cálculo, Zoologia
def test_ordem_exemplo_do_paragrafo(client, db):
    por_titulo = {t: semear_livro(db, t) for t in ["Zoologia", "cálculo", "Banco", "álgebra"]}

    dados = assert_ok(consultar(client))

    assert ids(dados) == [por_titulo[t] for t in ["álgebra", "Banco", "cálculo", "Zoologia"]]


# 00-convencoes §6 · só a caixa difere: empate decidido pelo código de caractere ('A' < 'a')
def test_ordem_empate_so_por_caixa(client, db):
    minusculo = semear_livro(db, "redes")
    maiusculo = semear_livro(db, "REDES")
    misto = semear_livro(db, "Redes")

    dados = assert_ok(consultar(client))

    assert ids(dados) == [maiusculo, misto, minusculo]


# 00-convencoes §6 · ordem com busca também ignora caixa e acento
def test_ordem_sem_caixa_nem_acento_no_resultado_filtrado(client, db):
    z = semear_livro(db, "Zoologia Aplicada")
    c = semear_livro(db, "cálculo aplicado")
    a = semear_livro(db, "Álgebra Aplicada")
    semear_livro(db, "Outro Assunto")

    dados = assert_ok(consultar(client, busca="aplicad"))

    assert ids(dados) == [a, c, z]


# 00-convencoes §6 · títulos idênticos: desempate por id crescente
def test_titulos_identicos_desempatam_por_id(client, db):
    primeiro = semear_livro(db, "Mesmo Título")
    outro = semear_livro(db, "Algoritmos")
    segundo = semear_livro(db, "Mesmo Título")
    terceiro = semear_livro(db, "Mesmo Título")

    dados = assert_ok(consultar(client))

    assert ids(dados) == [outro, primeiro, segundo, terceiro]


# 00-convencoes §6 · a mesma consulta devolve sempre a mesma ordem
def test_ordem_estavel_entre_execucoes(client, acervo):
    primeira = ids(assert_ok(consultar(client)))

    for _ in range(3):
        assert ids(assert_ok(consultar(client))) == primeira


# 00-convencoes §6 · ordem também vale para o resultado filtrado
def test_ordem_no_resultado_filtrado(client, db):
    zeta = semear_livro(db, "Zeta Sistemas")
    alfa = semear_livro(db, "Alfa Sistemas")
    semear_livro(db, "Outro Assunto")
    meio = semear_livro(db, "Meio", autor="Autora de Sistemas")

    dados = assert_ok(consultar(client, busca="sistemas"))

    assert ids(dados) == [alfa, meio, zeta]


# --------------------------------------------------------------------------- paginação


@pytest.fixture
def vinte_e_cinco_livros(db):
    """25 livros com títulos 'Livro 01'..'Livro 25' semeados fora de ordem; devolve ids em ordem."""
    por_numero = {}
    for numero in [*range(25, 12, -1), *range(1, 13)]:
        por_numero[numero] = semear_livro(db, f"Livro {numero:02d}")
    return [por_numero[n] for n in range(1, 26)]


# CT2 / 00-convencoes §6 · 25 livros, tamanho 10: páginas 1, 2, 3 e 4
@pytest.mark.parametrize(
    ("pagina", "inicio", "fim"),
    [(1, 0, 10), (2, 10, 20), (3, 20, 25), (4, 25, 25)],
)
def test_paginacao(client, vinte_e_cinco_livros, pagina, inicio, fim):
    dados = assert_ok(consultar(client, pagina=str(pagina), tamanho="10"))

    assert ids(dados) == vinte_e_cinco_livros[inicio:fim]
    assert dados["total"] == 25
    assert (dados["pagina"], dados["tamanho"]) == (pagina, 10)


# 00-convencoes §6 · página muito além da última: lista vazia, total correto (não é erro)
def test_pagina_muito_alem_da_ultima(client, vinte_e_cinco_livros):
    dados = assert_ok(consultar(client, pagina="1000", tamanho="100"))

    assert dados["livros"] == []
    assert dados["total"] == 25


# 00-convencoes §4/§6 · borda: pagina 2147483647 é aceita (lista vazia, total correto)
def test_pagina_no_maximo_aceita(client, vinte_e_cinco_livros):
    dados = assert_ok(consultar(client, pagina="2147483647", tamanho="100"))

    assert dados["livros"] == []
    assert dados["total"] == 25
    assert dados["pagina"] == 2147483647


# 00-convencoes §6 · as páginas juntas cobrem tudo, sem repetir, com títulos iguais na divisa
def test_paginas_sem_repeticao_com_titulos_iguais(client, db):
    esperados = [semear_livro(db, "Mesmo Título") for _ in range(12)]

    vistos = []
    for pagina in (1, 2, 3):
        vistos += ids(assert_ok(consultar(client, pagina=str(pagina), tamanho="5")))

    assert vistos == esperados


# CT2 · com busca, o total conta só o filtrado
def test_total_com_busca_conta_so_o_filtrado(client, db, vinte_e_cinco_livros):
    filtrados = [semear_livro(db, f"Sistemas {n}") for n in range(3)]

    dados = assert_ok(consultar(client, busca="sistemas", pagina="1", tamanho="2"))

    assert dados["total"] == 3
    assert ids(dados) == filtrados[:2]
    segunda = assert_ok(consultar(client, busca="sistemas", pagina="2", tamanho="2"))
    assert ids(segunda) == filtrados[2:]
    assert segunda["total"] == 3


# 00-convencoes §6 · bordas aceitas de tamanho: 1 e 100
@pytest.mark.parametrize("tamanho", [1, 100])
def test_tamanho_nas_bordas_aceito(client, vinte_e_cinco_livros, tamanho):
    dados = assert_ok(consultar(client, tamanho=str(tamanho)))

    assert dados["tamanho"] == tamanho
    assert ids(dados) == vinte_e_cinco_livros[:tamanho]


# --------------------------------------------------------------------------- vazios e repetidos


# 00-convencoes §6 · parâmetro presente mas vazio ou só com espaços vale como não informado
@pytest.mark.parametrize(
    "consulta",
    [
        "pagina=&tamanho=",
        "pagina=%20&tamanho=%20%20",
        "busca=&pagina=&tamanho=",
        "busca=%20%20&pagina=%20",
    ],
    ids=["vazios", "espacos", "tres-vazios", "busca-e-pagina-espacos"],
)
def test_parametros_vazios_recebem_o_padrao(client, vinte_e_cinco_livros, consulta):
    dados = assert_ok(client.get(f"{ROTA}?{consulta}"))

    assert (dados["pagina"], dados["tamanho"], dados["total"]) == (1, 20, 25)
    assert ids(dados) == vinte_e_cinco_livros[:20]


# 00-convencoes §6 · parâmetro repetido: vale o primeiro valor
@pytest.mark.parametrize(
    ("consulta", "pagina", "tamanho"),
    [
        ("pagina=2&pagina=abc&tamanho=10", 2, 10),
        ("pagina=3&pagina=1&tamanho=10", 3, 10),
        ("tamanho=5&tamanho=500", 1, 5),
        ("tamanho=5&tamanho=0", 1, 5),
    ],
    ids=[
        "pagina-2-depois-invalida",
        "pagina-3-depois-1",
        "tamanho-5-depois-500",
        "tamanho-5-depois-0",
    ],
)
def test_parametro_repetido_vale_o_primeiro(
    client, vinte_e_cinco_livros, consulta, pagina, tamanho
):
    dados = assert_ok(client.get(f"{ROTA}?{consulta}"))

    assert (dados["pagina"], dados["tamanho"]) == (pagina, tamanho)
    inicio = (pagina - 1) * tamanho
    assert ids(dados) == vinte_e_cinco_livros[inicio : inicio + tamanho]


# 00-convencoes §6 · parâmetro repetido: primeiro valor inválido gera o erro
@pytest.mark.parametrize(
    "consulta", ["pagina=abc&pagina=2", "tamanho=0&tamanho=10", "pagina=0&pagina="]
)
def test_parametro_repetido_com_primeiro_invalido(client, acervo, consulta):
    assert_erro(client.get(f"{ROTA}?{consulta}"), 400, "PAGINACAO_INVALIDA")


# 00-convencoes §6 · repetido com o primeiro vazio: vale o primeiro, que recebe o padrão
def test_parametro_repetido_com_primeiro_vazio(client, vinte_e_cinco_livros):
    dados = assert_ok(client.get(f"{ROTA}?pagina=&pagina=abc&tamanho=10"))

    assert dados["pagina"] == 1
    assert ids(dados) == vinte_e_cinco_livros[:10]


# 00-convencoes §6 · busca repetida: vale o primeiro termo
def test_busca_repetida_vale_a_primeira(client, acervo):
    dados = assert_ok(client.get(f"{ROTA}?busca=dados&busca=sistemas"))

    assert ids(dados) == [acervo["banco"]]


# --------------------------------------------------------------------------- ordem entre erros


# 00-convencoes §6 · ordem da tabela de Entrada do CT2: busca, pagina, tamanho
@pytest.mark.parametrize(
    ("params", "codigo"),
    [
        ({"busca": "a" * 101, "pagina": "0"}, "BUSCA_INVALIDA"),
        ({"busca": "a" * 101, "tamanho": "101"}, "BUSCA_INVALIDA"),
        ({"busca": "a" * 101, "pagina": "abc", "tamanho": "0"}, "BUSCA_INVALIDA"),
        ({"pagina": "0", "tamanho": "101"}, "PAGINACAO_INVALIDA"),
        ({"pagina": "abc", "tamanho": "abc"}, "PAGINACAO_INVALIDA"),
    ],
    ids=["busca+pagina", "busca+tamanho", "busca+pagina+tamanho", "pagina+tamanho", "nao-inteiros"],
)
def test_ordem_entre_parametros(client, acervo, params, codigo):
    assert_erro(consultar(client, **params), 400, codigo)


# --------------------------------------------------------------------------- PAGINACAO_INVALIDA


# CT2 · Erros · página menor que 1, ou valor não inteiro; §4 · acima de 2147483647
@pytest.mark.parametrize(
    "pagina", ["0", "-1", "abc", "1.5", "1,5", "2147483648", "99999999999999999999"]
)
def test_pagina_invalida(client, acervo, pagina):
    assert_erro(consultar(client, pagina=pagina), 400, "PAGINACAO_INVALIDA")


# CT2 · Erros · tamanho fora de 1 a 100, ou valor não inteiro
@pytest.mark.parametrize("tamanho", ["0", "-1", "101", "abc", "1.5", "2147483648"])
def test_tamanho_invalido(client, acervo, tamanho):
    assert_erro(consultar(client, tamanho=tamanho), 400, "PAGINACAO_INVALIDA")


# CT2 · PAGINACAO_INVALIDA com busca válida junto
def test_paginacao_invalida_com_busca_valida(client, acervo):
    assert_erro(consultar(client, busca="sistemas", pagina="0"), 400, "PAGINACAO_INVALIDA")


# --------------------------------------------------------------------------- BUSCA_INVALIDA


# CT2 · Erros · busca com mais de 100 caracteres (depois de cortar as pontas)
@pytest.mark.parametrize(
    "busca",
    ["a" * 101, "ã" * 101, "  " + "a" * 101 + "  "],
    ids=["101-ascii", "101-acentuados", "101-com-espacos"],
)
def test_busca_com_101_caracteres(client, acervo, busca):
    assert_erro(consultar(client, busca=busca), 400, "BUSCA_INVALIDA")


# CT2 · BUSCA_INVALIDA com paginação válida junto
def test_busca_invalida_com_paginacao_valida(client, acervo):
    resposta = consultar(client, busca="a" * 101, pagina="1", tamanho="10")

    assert_erro(resposta, 400, "BUSCA_INVALIDA")


# --------------------------------------------------------------------------- formatos (§6)


# 00-convencoes §6 · inteiro: brancos das pontas cortados; só -?[0-9]+; "01" vale 1
@pytest.mark.parametrize(
    ("pagina", "tamanho", "esperado"),
    [
        ("01", "05", (1, 5)),
        ("002", "010", (2, 10)),
        ("\t2\n", " 10 ", (2, 10)),
        (" 1", "\n\t7\t", (1, 7)),
    ],
    ids=["zeros-a-esquerda", "zeros-a-esquerda-2", "tab-quebra", "espaco-e-brancos"],
)
def test_inteiros_aceitos(client, vinte_e_cinco_livros, pagina, tamanho, esperado):
    dados = assert_ok(consultar(client, pagina=pagina, tamanho=tamanho))

    assert (dados["pagina"], dados["tamanho"]) == esperado
    inicio = (esperado[0] - 1) * esperado[1]
    assert ids(dados) == vinte_e_cinco_livros[inicio : inicio + esperado[1]]


FORMAS_INVALIDAS = ["+1", "1.0", "1e1", "1_0", "\u0661", "\uff11", "1 2", "0x1", "-0", "--1"]
IDS_FORMAS = [
    "mais",
    "decimal",
    "expoente",
    "sublinhado",
    "arabe",
    "largo",
    "espaco-meio",
    "hexa",
    "-0",
    "--1",
]


# 00-convencoes §6 · pagina em qualquer forma que não seja -?[0-9]+ ASCII (ou < 1)
@pytest.mark.parametrize("valor", FORMAS_INVALIDAS, ids=IDS_FORMAS)
def test_pagina_em_forma_invalida(client, acervo, valor):
    assert_erro(consultar(client, pagina=valor), 400, "PAGINACAO_INVALIDA")


# 00-convencoes §6 · tamanho em qualquer forma que não seja -?[0-9]+ ASCII (ou fora de 1..100)
@pytest.mark.parametrize("valor", FORMAS_INVALIDAS, ids=IDS_FORMAS)
def test_tamanho_em_forma_invalida(client, acervo, valor):
    assert_erro(consultar(client, tamanho=valor), 400, "PAGINACAO_INVALIDA")


# 00-convencoes §6 · brancos das pontas da busca incluem tabulação e quebra de linha
def test_busca_com_tabulacao_e_quebra_nas_pontas(client, acervo):
    dados = assert_ok(consultar(client, busca="\t dados \n"))

    assert ids(dados) == [acervo["banco"]]


# 00-convencoes §6 · parâmetros só com tabulação/quebra valem como não informados
def test_parametros_so_com_tabulacao_e_quebra(client, vinte_e_cinco_livros):
    dados = assert_ok(consultar(client, busca="\t\n", pagina="\t", tamanho="\n"))

    assert (dados["pagina"], dados["tamanho"], dados["total"]) == (1, 20, 25)


# 00-convencoes §6 · busca de 100 caracteres com tabulação/quebra nas pontas é aceita
def test_busca_100_com_tabulacao_nas_pontas(client, acervo):
    assert assert_ok(consultar(client, busca="\t" + "a" * 100 + "\n"))["total"] == 0


# 00-convencoes §6 · busca com NUL, metade de par substituto ou bytes não UTF-8
@pytest.mark.parametrize(
    "busca_codificada",
    ["%00", "dados%00", "%ED%A0%80", "dados%ED%B0%80", "%FF", "dados%C3", "%C3%28"],
    ids=["nul", "nul-no-fim", "surrogate-alto", "surrogate-baixo", "byte-ff", "truncado", "c3-28"],
)
def test_busca_com_caractere_invalido(client, acervo, busca_codificada):
    resposta = client.get(f"{ROTA}?busca={busca_codificada}")

    assert_erro(resposta, 400, "BUSCA_INVALIDA")


# 00-convencoes §6 · NUL ou UTF-8 inválido em pagina/tamanho → código do parâmetro
@pytest.mark.parametrize(
    "consulta",
    ["pagina=%00", "pagina=1%00", "tamanho=%FF", "tamanho=1%ED%A0%80"],
    ids=["pagina-nul", "pagina-1-nul", "tamanho-ff", "tamanho-surrogate"],
)
def test_paginacao_com_caractere_invalido(client, acervo, consulta):
    assert_erro(client.get(f"{ROTA}?{consulta}"), 400, "PAGINACAO_INVALIDA")


# 00-convencoes §6 · ordem: busca com NUL vence página inválida
def test_ordem_busca_com_nul_antes_de_pagina_invalida(client, acervo):
    assert_erro(client.get(f"{ROTA}?busca=%00&pagina=0"), 400, "BUSCA_INVALIDA")


# 00-convencoes §6 · ISBN: hífens do termo não são removidos ao buscar
@pytest.mark.parametrize("busca", ["978-0", "978-0-00-000000-1", "0306-406152"])
def test_busca_por_isbn_com_hifens_nao_normaliza(client, acervo, busca):
    dados = assert_ok(consultar(client, busca=busca))

    assert dados["livros"] == []
    assert dados["total"] == 0


# 00-convencoes §6 · parâmetros desconhecidos são ignorados (mesmo com conteúdo estranho)
@pytest.mark.parametrize(
    "consulta",
    ["foo=bar", "ordem=desc&limite=1", "status=qualquer", "foo=%00&bar=%FF", "Pagina=0&TAMANHO=0"],
    ids=["simples", "dois", "status", "conteudo-invalido", "maiusculas"],
)
def test_parametros_desconhecidos_ignorados(client, acervo, consulta):
    sem_parametros = assert_ok(client.get(ROTA))

    assert assert_ok(client.get(f"{ROTA}?{consulta}")) == sem_parametros


# 00-convencoes §6 · parâmetro desconhecido não interfere nos conhecidos
def test_parametro_desconhecido_junto_com_conhecidos(client, acervo):
    dados = assert_ok(client.get(f"{ROTA}?foo=1&busca=dados&bar=2&tamanho=5"))

    assert ids(dados) == [acervo["banco"]]
    assert dados["tamanho"] == 5


# --------------------------------------------------------------------------- rota


# 00-convencoes §3 · barra no fim é rota inexistente, sem redirecionamento
def test_barra_no_fim(client):
    resposta = client.get("/livros/", follow_redirects=False)

    assert_erro(resposta, 404, "ROTA_NAO_ENCONTRADA")


# 00-convencoes §3 · método não permitido em /livros
@pytest.mark.parametrize("metodo", ["PUT", "PATCH", "DELETE"])
def test_metodo_nao_permitido(client, metodo):
    assert_erro(client.request(metodo, ROTA), 405, "ROTA_NAO_ENCONTRADA")


# CT1 · regressão: POST /livros continua funcionando junto com o GET
def test_post_livros_continua_funcionando(client, db):
    resposta = client.post(
        ROTA,
        json={
            "titulo": "Novo",
            "autor": "Autor",
            "isbn": "9780000000099",
            "quantidadeExemplares": 2,
        },
    )

    assert resposta.status_code == 201, resposta.text
    dados = assert_ok(consultar(client, busca="novo"))
    assert ids(dados) == [resposta.json()["id"]]
