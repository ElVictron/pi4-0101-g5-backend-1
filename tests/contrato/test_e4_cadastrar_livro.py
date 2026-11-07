"""E4 — cadastrarLivro (card #784): `POST /livros`.

Fontes: CT1, CT9; `00-convencoes.md` §2, §3, §4, §5, §7 e §11; `agentes.md` D12, D13,
D16 e D17. Dados de apoio semeados por SQL direto (fixture `db`), sem `id` explícito.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

ROTA = "/livros"
JSON = {"Content-Type": "application/json"}
LIMITE_CORPO = 64 * 1024

CORPO_VALIDO = {
    "titulo": "Fundamentos de Sistemas de Informação",
    "autor": "Ana Silva",
    "isbn": "9780000000001",
    "quantidadeExemplares": 3,
}
CAMPOS_SAIDA = {"id", "titulo", "autor", "isbn", "quantidadeExemplares", "quantidadeDisponivel"}
CAMPOS_TEXTO = ["titulo", "autor", "isbn"]
CAMPOS_OBRIGATORIOS = [*CAMPOS_TEXTO, "quantidadeExemplares"]

# D16(d): a mensagem nunca expõe nome de restrição nem texto do PostgreSQL
TRECHOS_PROIBIDOS = (
    "livros_isbn_unico",
    "duplicate key",
    "key (",
    "violates",
    "constraint",
    "psycopg",
    "sqlstate",
    "traceback",
)


# --------------------------------------------------------------------------- apoio


def corpo(**alteracoes):
    """Corpo válido com alterações; valor `...` remove o campo."""
    novo = dict(CORPO_VALIDO)
    for campo, valor in alteracoes.items():
        if valor is ...:
            novo.pop(campo, None)
        else:
            novo[campo] = valor
    return novo


def postar(client, dados):
    return client.post(ROTA, json=dados)


def postar_bruto(client, conteudo: bytes, headers=JSON):
    return client.post(ROTA, content=conteudo, headers=headers)


def semear_livro(db, *, isbn="9780000000001", titulo="Livro Semeado", exemplares=2) -> int:
    return db.execute(
        "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (titulo, "Autor Semeado", isbn, exemplares, exemplares),
    ).fetchone()[0]


def livros_no_banco(db):
    return db.execute(
        "SELECT id, titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel, criado_em"
        " FROM livros ORDER BY id"
    ).fetchall()


def assert_erro(resposta, status: int, codigo: str) -> None:
    """00-convencoes §3 · formato do corpo de erro; D16(d) · sem texto interno."""
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


@pytest.fixture
def banco_inalterado(db):
    """Confere, ao fim do teste de erro, que a tabela `livros` não mudou."""
    antes = livros_no_banco(db)
    yield
    assert livros_no_banco(db) == antes


def bytes_com_tamanho(total: int) -> bytes:
    """Corpo JSON válido (campo desconhecido de enchimento) com exatamente `total` bytes."""
    base = json.dumps(corpo(enchimento=""), separators=(",", ":")).encode("utf-8")
    conteudo = json.dumps(
        corpo(enchimento="a" * (total - len(base))), separators=(",", ":")
    ).encode("utf-8")
    assert len(conteudo) == total
    return conteudo


# --------------------------------------------------------------------------- sucesso


# CT1 · Saída · 201 com exatamente os campos do CT1; disponível = exemplares
def test_cadastra_livro_com_sucesso(client):
    resposta = postar(client, CORPO_VALIDO)

    assert resposta.status_code == 201, resposta.text
    assert resposta.headers["content-type"].startswith("application/json")
    dados = resposta.json()
    assert set(dados) == CAMPOS_SAIDA
    assert type(dados["id"]) is int
    assert type(dados["quantidadeExemplares"]) is int
    assert type(dados["quantidadeDisponivel"]) is int
    assert dados == {
        "id": dados["id"],
        "titulo": "Fundamentos de Sistemas de Informação",
        "autor": "Ana Silva",
        "isbn": "9780000000001",
        "quantidadeExemplares": 3,
        "quantidadeDisponivel": 3,
    }


# CT1/CT9 · efeito no banco: linha gravada; criado_em vem do relógio (D16 f)
def test_cadastro_grava_linha_no_banco(client, db, instante_base):
    resposta = postar(client, CORPO_VALIDO)
    assert resposta.status_code == 201, resposta.text
    dados = resposta.json()

    assert livros_no_banco(db) == [
        (
            dados["id"],
            "Fundamentos de Sistemas de Informação",
            "Ana Silva",
            "9780000000001",
            3,
            3,
            instante_base,
        )
    ]


# CT1 · cadastros seguidos recebem ids diferentes e crescentes
def test_cadastros_seguidos_tem_ids_crescentes(client):
    respostas = [postar(client, corpo(isbn=isbn)) for isbn in ("9780000000001", "9780000000002")]
    assert [r.status_code for r in respostas] == [201, 201], respostas[0].text
    primeiro, segundo = (r.json()["id"] for r in respostas)

    assert segundo > primeiro


# 00-convencoes §4 · espaços das pontas removidos antes de gravar (o miolo fica)
def test_remove_espacos_das_pontas_de_titulo_e_autor(client, db):
    resposta = postar(client, corpo(titulo="  Sistemas  de Informação  ", autor=" Ana Silva "))

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["titulo"] == "Sistemas  de Informação"
    assert resposta.json()["autor"] == "Ana Silva"
    assert livros_no_banco(db)[0][1:3] == ("Sistemas  de Informação", "Ana Silva")


# 00-convencoes §5 · ISBN: hífens e espaços removidos; gravado e devolvido normalizado
@pytest.mark.parametrize(
    ("isbn", "normalizado"),
    [
        ("978-0-00-000000-1", "9780000000001"),
        ("978 0 00 000000 1", "9780000000001"),
        (" 978-0 00-000000 1 ", "9780000000001"),
        ("0306406152", "0306406152"),
        ("0-306-40615-2", "0306406152"),
    ],
    ids=["hifens", "espacos", "misto", "isbn10", "isbn10-hifens"],
)
def test_isbn_normalizado(client, db, isbn, normalizado):
    resposta = postar(client, corpo(isbn=isbn))

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["isbn"] == normalizado
    assert livros_no_banco(db)[0][3] == normalizado


# 00-convencoes §5 · título e autor: até 200 caracteres (contados depois de remover as pontas)
@pytest.mark.parametrize(
    "texto",
    ["a" * 200, "ã" * 200, "  " + "a" * 200 + "  "],
    ids=["200-ascii", "200-acentuados", "200-com-espacos-nas-pontas"],
)
@pytest.mark.parametrize("campo", ["titulo", "autor"])
def test_titulo_e_autor_com_200_caracteres_aceitos(client, db, campo, texto):
    resposta = postar(client, corpo(**{campo: texto}))

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()[campo] == texto.strip()


# 00-convencoes §4 · campos desconhecidos são ignorados
def test_campo_desconhecido_ignorado(client, db):
    resposta = postar(client, corpo(editora="Qualquer", quantidadeDisponivel=99, id=777))

    assert resposta.status_code == 201, resposta.text
    dados = resposta.json()
    assert set(dados) == CAMPOS_SAIDA
    assert dados["quantidadeDisponivel"] == 3
    assert livros_no_banco(db)[0][5] == 3


# 00-convencoes §4 item 1 · Content-Type com parâmetro charset=utf-8 é aceito
def test_content_type_com_charset_aceito(client):
    resposta = postar_bruto(
        client,
        json.dumps(CORPO_VALIDO).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    assert resposta.status_code == 201, resposta.text


# 00-convencoes §4 item 1 · borda: corpo com exatamente 64 KiB é aceito
def test_corpo_com_exatamente_64_kib_aceito(client):
    resposta = postar_bruto(client, bytes_com_tamanho(LIMITE_CORPO))

    assert resposta.status_code == 201, resposta.text


# D6/CT12 · cadastrar livro não publica evento no Backend 2
def test_cadastro_nao_chama_o_backend2(client, backend2):
    assert postar(client, CORPO_VALIDO).status_code == 201

    assert backend2.calls.call_count == 0


# --------------------------------------------------------------------------- CAMPOS_OBRIGATORIOS


# CT1 · Erros · campo obrigatório ausente
@pytest.mark.parametrize("campo", CAMPOS_OBRIGATORIOS)
def test_campo_ausente(client, banco_inalterado, campo):
    assert_erro(postar(client, corpo(**{campo: ...})), 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 item 2 · campo obrigatório null
@pytest.mark.parametrize("campo", CAMPOS_OBRIGATORIOS)
def test_campo_nulo(client, banco_inalterado, campo):
    assert_erro(postar(client, corpo(**{campo: None})), 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 item 2 · texto vazio ou só com espaços
@pytest.mark.parametrize("valor", ["", "   "], ids=["vazio", "so-espacos"])
@pytest.mark.parametrize("campo", CAMPOS_TEXTO)
def test_texto_vazio(client, banco_inalterado, campo, valor):
    assert_erro(postar(client, corpo(**{campo: valor})), 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 item 2 · objeto vazio: todos os campos ausentes
def test_objeto_vazio(client, banco_inalterado):
    assert_erro(postar(client, {}), 400, "CAMPOS_OBRIGATORIOS")


# --------------------------------------------------------------------------- QUANTIDADE_INVALIDA


# CT1 · Erros · quantidade não inteira, menor que zero ou zero; §4 · só inteiro JSON
@pytest.mark.parametrize(
    "quantidade",
    [0, -1, 3.5, 3.0, "3", True, False, [3], {"valor": 3}],
    ids=[
        "zero",
        "negativa",
        "decimal",
        "decimal-inteiro",
        "texto",
        "true",
        "false",
        "lista",
        "obj",
    ],
)
def test_quantidade_invalida(client, banco_inalterado, quantidade):
    resposta = postar(client, corpo(quantidadeExemplares=quantidade))

    assert_erro(resposta, 400, "QUANTIDADE_INVALIDA")


# 00-convencoes §4 · `3.0` enviado literalmente no JSON (não só via serialização Python)
def test_quantidade_decimal_literal(client, banco_inalterado):
    bruto = b'{"titulo": "T", "autor": "A", "isbn": "9780000000001", "quantidadeExemplares": 3.0}'

    assert_erro(postar_bruto(client, bruto), 400, "QUANTIDADE_INVALIDA")


# 00-convencoes §5 · borda: quantidade 1 é aceita
def test_quantidade_um_aceita(client, db):
    resposta = postar(client, corpo(quantidadeExemplares=1))

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["quantidadeDisponivel"] == 1


# 00-convencoes §4 · inteiro de entrada vai até 2147483647; acima → código do campo
@pytest.mark.parametrize("quantidade", [2147483648, 10**20], ids=["2147483648", "10^20"])
def test_quantidade_acima_do_maximo(client, banco_inalterado, quantidade):
    resposta = postar(client, corpo(quantidadeExemplares=quantidade))

    assert_erro(resposta, 400, "QUANTIDADE_INVALIDA")


# 00-convencoes §4 · borda: 2147483647 é aceito e gravado
def test_quantidade_no_maximo_aceita(client, db):
    resposta = postar(client, corpo(quantidadeExemplares=2147483647))

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["quantidadeExemplares"] == 2147483647
    assert resposta.json()["quantidadeDisponivel"] == 2147483647
    assert livros_no_banco(db)[0][4:6] == (2147483647, 2147483647)


# 00-convencoes §4 · espaços em branco das pontas incluem tabulação e quebra de linha
@pytest.mark.parametrize("campo", ["titulo", "autor"])
def test_remove_tabulacao_e_quebra_de_linha_das_pontas(client, db, campo):
    resposta = postar(client, corpo(**{campo: "\t Livro \n"}))

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()[campo] == "Livro"
    indice = 1 if campo == "titulo" else 2
    assert livros_no_banco(db)[0][indice] == "Livro"


# 00-convencoes §4 e §5 · ISBN com tabulação/quebra de linha nas pontas é normalizado
def test_isbn_com_tabulacao_e_quebra_de_linha_nas_pontas(client, db):
    resposta = postar(client, corpo(isbn="\t978-0-00-000000-1\n"))

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["isbn"] == "9780000000001"


# 00-convencoes §4 · tamanho conta caracteres depois de remover tabulação/quebra de linha
def test_titulo_com_200_caracteres_e_brancos_nas_pontas_aceito(client):
    resposta = postar(client, corpo(titulo="\t\n" + "a" * 200 + "\n\t"))

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["titulo"] == "a" * 200


# 00-convencoes §4 item 2 · texto só com tabulação/quebra de linha = vazio
@pytest.mark.parametrize("valor", ["\t\n", " \t \n "], ids=["tab-quebra", "misturado"])
@pytest.mark.parametrize("campo", CAMPOS_TEXTO)
def test_texto_so_com_brancos_e_campo_obrigatorio(client, banco_inalterado, campo, valor):
    assert_erro(postar(client, corpo(**{campo: valor})), 400, "CAMPOS_OBRIGATORIOS")


# --------------------------------------------------------------------------- DADOS_INVALIDOS


# CT1 · Erros · ISBN fora do formato (10 ou 13 dígitos, só dígitos)
@pytest.mark.parametrize(
    "isbn",
    [
        "978000000000A",
        "030640615X",
        "978.0.00.000000.1",
        "978_0000000001",
        "9" * 9,
        "9" * 11,
        "9" * 12,
        "9" * 14,
        "-",
    ],
    ids=["letra", "isbn10-com-X", "pontos", "sublinhado", "9", "11", "12", "14", "so-hifen"],
)
def test_isbn_fora_do_formato(client, banco_inalterado, isbn):
    assert_erro(postar(client, corpo(isbn=isbn)), 400, "DADOS_INVALIDOS")


# CT1 · Erros · título ou autor acima de 200 caracteres
@pytest.mark.parametrize("texto", ["a" * 201, "ã" * 201], ids=["201-ascii", "201-acentuados"])
@pytest.mark.parametrize("campo", ["titulo", "autor"])
def test_titulo_ou_autor_com_201_caracteres(client, banco_inalterado, campo, texto):
    assert_erro(postar(client, corpo(**{campo: texto})), 400, "DADOS_INVALIDOS")


# CT1 · Erros · campo com tipo errado; §4 · texto com outro tipo → DADOS_INVALIDOS
@pytest.mark.parametrize(
    "valor",
    [9780000000001, 3.5, True, False, ["9780000000001"], {"v": "x"}],
    ids=["inteiro", "decimal", "true", "false", "lista", "objeto"],
)
@pytest.mark.parametrize("campo", CAMPOS_TEXTO)
def test_campo_de_texto_com_tipo_errado(client, banco_inalterado, campo, valor):
    assert_erro(postar(client, corpo(**{campo: valor})), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · corpo ausente, não JSON ou não objeto
@pytest.mark.parametrize(
    "bruto",
    [
        b"",
        b"   ",
        b'{"titulo": "T",',
        b"titulo=T&autor=A",
        b'[{"titulo": "T"}]',
        b"[]",
        b"3",
        b'"texto"',
        b"null",
        b"true",
    ],
    ids=[
        "vazio",
        "so-espacos",
        "json-quebrado",
        "formulario",
        "lista",
        "lista-vazia",
        "numero",
        "string",
        "null",
        "booleano",
    ],
)
def test_corpo_que_nao_e_objeto_json(client, banco_inalterado, bruto):
    assert_erro(postar_bruto(client, bruto), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · Content-Type diferente de application/json
@pytest.mark.parametrize(
    "tipo",
    ["text/plain", "application/x-www-form-urlencoded", "text/json", "application/xml"],
)
def test_content_type_diferente_de_json(client, banco_inalterado, tipo):
    resposta = postar_bruto(
        client, json.dumps(CORPO_VALIDO).encode("utf-8"), headers={"Content-Type": tipo}
    )

    assert_erro(resposta, 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · Content-Type ausente
def test_content_type_ausente(client, banco_inalterado):
    resposta = client.post(ROTA, content=json.dumps(CORPO_VALIDO).encode("utf-8"))

    assert "content-type" not in resposta.request.headers
    assert_erro(resposta, 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · corpo que não é UTF-8 válido
@pytest.mark.parametrize(
    "bruto",
    [
        json.dumps(CORPO_VALIDO).encode("utf-16"),
        json.dumps(CORPO_VALIDO).encode("utf-16-le"),
        json.dumps(CORPO_VALIDO, ensure_ascii=False).encode("latin-1"),
        b'{"titulo": "Fundamentos \xff", "autor": "A", "isbn": "9780000000001",'
        b' "quantidadeExemplares": 3}',
    ],
    ids=["utf-16-bom", "utf-16-le", "latin-1", "byte-invalido"],
)
def test_corpo_que_nao_e_utf8(client, banco_inalterado, bruto):
    assert_erro(postar_bruto(client, bruto), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · corpo acima de 64 KiB
def test_corpo_acima_de_64_kib(client, banco_inalterado):
    assert_erro(postar_bruto(client, bytes_com_tamanho(LIMITE_CORPO + 1)), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · JSON aninhado a ponto de não poder ser lido (corpo < 64 KiB)
def test_json_muito_aninhado(client, banco_inalterado):
    profundidade = 30_000
    bruto = (
        '{"titulo": ' + "[" * profundidade + "]" * profundidade + ', "autor": "A",'
        ' "isbn": "9780000000001", "quantidadeExemplares": 3}'
    ).encode()
    assert len(bruto) < LIMITE_CORPO

    assert_erro(postar_bruto(client, bruto), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · caractere Unicode inválido (\ud800 etc.) em chave ou valor
@pytest.mark.parametrize(
    "bruto",
    [
        r'{"titulo": "Livro \ud800", "autor": "A", "isbn": "9780000000001",'
        r' "quantidadeExemplares": 3}',
        r'{"titulo": "T", "autor": "\udc00", "isbn": "9780000000001",'
        r' "quantidadeExemplares": 3}',
        r'{"titulo": "T", "autor": "A", "isbn": "9780000000001",'
        r' "quantidadeExemplares": 3, "extra": "\ud800"}',
        r'{"titulo": "T", "autor": "A", "isbn": "9780000000001",'
        r' "quantidadeExemplares": 3, "\ud800": 1}',
    ],
    ids=["valor-titulo", "valor-autor-baixo", "valor-campo-desconhecido", "chave"],
)
def test_escape_unicode_invalido(client, banco_inalterado, bruto):
    assert_erro(postar_bruto(client, bruto.encode("ascii")), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · caractere NUL (\u0000) em qualquer chave ou valor
@pytest.mark.parametrize(
    "dados",
    [
        corpo(titulo="Livro\x00"),
        corpo(titulo="\x00"),
        corpo(autor="Ana\x00Silva"),
        corpo(isbn="978000000000\x001"),
        corpo(extra="\x00"),
        {**CORPO_VALIDO, "chave\x00": 1},
    ],
    ids=["titulo", "titulo-so-nul", "autor", "isbn", "valor-campo-desconhecido", "chave"],
)
def test_caractere_nul_recusado(client, banco_inalterado, dados):
    assert_erro(postar(client, dados), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · NUL como escape literal no JSON bruto
def test_caractere_nul_em_json_bruto(client, banco_inalterado):
    bruto = (
        rb'{"titulo": "Livro \u0000", "autor": "A", "isbn": "9780000000001",'
        rb' "quantidadeExemplares": 3}'
    )

    assert_erro(postar_bruto(client, bruto), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 2 · texto vazio também em campo inteiro → CAMPOS_OBRIGATORIOS
@pytest.mark.parametrize("valor", ["", "   ", "\t\n"], ids=["vazio", "espacos", "tab-quebra"])
def test_quantidade_texto_vazio_e_campo_obrigatorio(client, banco_inalterado, valor):
    resposta = postar(client, corpo(quantidadeExemplares=valor))

    assert_erro(resposta, 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 · item 2 vence o item 3: quantidade "" + título com 201 caracteres
def test_ordem_quantidade_vazia_antes_de_titulo_longo(client, banco_inalterado):
    resposta = postar(client, corpo(titulo="a" * 201, quantidadeExemplares=""))

    assert_erro(resposta, 400, "CAMPOS_OBRIGATORIOS")


# --------------------------------------------------------------------------- ordem do §4


# 00-convencoes §4 · item 1 antes do 2: Content-Type errado e campos ausentes
def test_ordem_content_type_antes_de_campos_ausentes(client, banco_inalterado):
    resposta = postar_bruto(client, b'{"titulo": "T"}', headers={"Content-Type": "text/plain"})

    assert_erro(resposta, 400, "DADOS_INVALIDOS")


# 00-convencoes §4 · item 2 antes do 3: campo ausente + quantidade 0
def test_ordem_campo_ausente_antes_de_quantidade(client, banco_inalterado):
    resposta = postar(client, corpo(titulo=..., quantidadeExemplares=0))

    assert_erro(resposta, 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 · item 2 antes do 3: campo nulo + outro campo com tipo errado
def test_ordem_campo_nulo_antes_de_tipo_errado(client, banco_inalterado):
    resposta = postar(client, corpo(titulo=None, autor=123))

    assert_erro(resposta, 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 · item 2 antes do 3: texto vazio + ISBN inválido
def test_ordem_texto_vazio_antes_de_isbn_invalido(client, banco_inalterado):
    resposta = postar(client, corpo(autor="  ", isbn="123"))

    assert_erro(resposta, 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 · item 3 antes do 4: ISBN inválido que também está gravado
def test_ordem_isbn_invalido_antes_de_duplicado(client, db):
    semear_livro(db, isbn="97800000000")
    antes = livros_no_banco(db)

    assert_erro(postar(client, corpo(isbn="97800000000")), 400, "DADOS_INVALIDOS")
    assert livros_no_banco(db) == antes


# 00-convencoes §4 · item 3 antes do 4: quantidade 0 + ISBN duplicado
def test_ordem_quantidade_antes_de_duplicado(client, db):
    semear_livro(db, isbn="9780000000001")
    antes = livros_no_banco(db)

    resposta = postar(client, corpo(isbn="9780000000001", quantidadeExemplares=0))

    assert_erro(resposta, 400, "QUANTIDADE_INVALIDA")
    assert livros_no_banco(db) == antes


# 00-convencoes §4 · item 3 antes do 4: título longo + ISBN duplicado
def test_ordem_titulo_longo_antes_de_duplicado(client, db):
    semear_livro(db, isbn="9780000000001")
    antes = livros_no_banco(db)

    assert_erro(postar(client, corpo(titulo="a" * 201)), 400, "DADOS_INVALIDOS")
    assert livros_no_banco(db) == antes


# 00-convencoes §4 · dentro do item 3, ordem do CT1: isbn antes de quantidadeExemplares
def test_ordem_isbn_invalido_antes_de_quantidade_zero(client, banco_inalterado):
    resposta = postar(client, corpo(isbn="123", quantidadeExemplares=0))

    assert_erro(resposta, 400, "DADOS_INVALIDOS")


# 00-convencoes §4 · dentro do item 3: titulo antes de quantidadeExemplares
def test_ordem_titulo_longo_antes_de_quantidade_booleana(client, banco_inalterado):
    resposta = postar(client, corpo(titulo="a" * 201, quantidadeExemplares=True))

    assert_erro(resposta, 400, "DADOS_INVALIDOS")


# 00-convencoes §4 · dentro do item 3: autor antes de quantidadeExemplares
def test_ordem_autor_com_tipo_errado_antes_de_quantidade_acima_do_maximo(client, banco_inalterado):
    resposta = postar(client, corpo(autor=42, quantidadeExemplares=2147483648))

    assert_erro(resposta, 400, "DADOS_INVALIDOS")


# 00-convencoes §4 · dentro do item 2: título ausente + autor null → CAMPOS_OBRIGATORIOS
def test_ordem_titulo_ausente_e_autor_nulo(client, banco_inalterado):
    resposta = postar(client, corpo(titulo=..., autor=None))

    assert_erro(resposta, 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 · item 2 antes do 3 mesmo quando o campo do item 3 vem antes na tabela
def test_ordem_item_2_vence_campo_anterior_do_item_3(client, banco_inalterado):
    resposta = postar(client, corpo(titulo="a" * 201, quantidadeExemplares=None))

    assert_erro(resposta, 400, "CAMPOS_OBRIGATORIOS")


# --------------------------------------------------------------------------- ISBN_DUPLICADO


# CT1 · Erros · ISBN já cadastrado (duplicidade avaliada após normalização, §5)
@pytest.mark.parametrize(
    "isbn",
    ["9780000000001", "978-0-00-000000-1", " 978 0 00 000000 1 "],
    ids=["igual", "com-hifens", "com-espacos"],
)
def test_isbn_duplicado(client, db, isbn):
    semear_livro(db, isbn="9780000000001")
    antes = livros_no_banco(db)

    resposta = postar(client, corpo(isbn=isbn, titulo="Outro Livro"))

    assert_erro(resposta, 409, "ISBN_DUPLICADO")
    assert livros_no_banco(db) == antes


# CT1 · ISBN_DUPLICADO também quando o primeiro foi cadastrado pela própria API
def test_isbn_duplicado_apos_cadastro_pela_api(client, db):
    assert postar(client, corpo(isbn="0-306-40615-2")).status_code == 201
    antes = livros_no_banco(db)

    assert_erro(postar(client, corpo(isbn="0306406152")), 409, "ISBN_DUPLICADO")
    assert livros_no_banco(db) == antes


# CT1 · depois de um ISBN_DUPLICADO, outro ISBN continua sendo aceito
def test_cadastro_continua_funcionando_apos_duplicado(client, db):
    semear_livro(db, isbn="9780000000001")
    assert postar(client, CORPO_VALIDO).status_code == 409

    resposta = postar(client, corpo(isbn="9780000000002"))

    assert resposta.status_code == 201, resposta.text
    assert len(livros_no_banco(db)) == 2


# --------------------------------------------------------------------------- concorrência


# D16(a) / CT1 · dois cadastros simultâneos com o mesmo ISBN: um 201, um 409, uma linha
def test_cadastros_simultaneos_com_mesmo_isbn(client, db):
    barreira = threading.Barrier(2, timeout=10)

    def cadastrar(titulo):
        barreira.wait()
        return client.post(ROTA, json=corpo(titulo=titulo))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(cadastrar, titulo) for titulo in ("Primeiro", "Segundo")]
        respostas = [futuro.result(timeout=30) for futuro in futuros]

    status = sorted(r.status_code for r in respostas)
    assert status == [201, 409], [r.text for r in respostas]
    conflito = next(r for r in respostas if r.status_code == 409)
    assert_erro(conflito, 409, "ISBN_DUPLICADO")
    vencedor = next(r for r in respostas if r.status_code == 201).json()
    linhas = livros_no_banco(db)
    assert len(linhas) == 1
    assert linhas[0][0] == vencedor["id"]
    assert linhas[0][1] == vencedor["titulo"]


# --------------------------------------------------------------------------- rota


# 00-convencoes §3 · barra no fim é rota inexistente, sem redirecionamento
def test_barra_no_fim(client, banco_inalterado):
    resposta = client.post("/livros/", json=CORPO_VALIDO, follow_redirects=False)

    assert_erro(resposta, 404, "ROTA_NAO_ENCONTRADA")
