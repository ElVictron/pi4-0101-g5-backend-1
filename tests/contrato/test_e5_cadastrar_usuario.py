"""E5 — cadastrarUsuario (card #786): `POST /usuarios`.

Fontes: CT3, CT10; `00-convencoes.md` §2, §3, §4, §5, §7 e §11; `agentes.md` P7, D16 e
D17. Ordem dos campos (tabela de Entrada do CT3): `nome`, `cpf`, `contato`. Dados de
apoio semeados por SQL direto (fixture `db`), sem `id` explícito.
"""

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

ROTA = "/usuarios"
JSON = {"Content-Type": "application/json"}
LIMITE_CORPO = 64 * 1024

CORPO_VALIDO = {"nome": "Lucas Joaquim", "cpf": "12345678900", "contato": "lucas@email.com"}
CAMPOS_SAIDA = {"id", "nome", "cpf", "contato"}
CAMPOS = ["nome", "cpf", "contato"]

# D16(d): a mensagem nunca expõe nome de restrição nem texto do PostgreSQL
TRECHOS_PROIBIDOS = (
    "usuarios_cpf_unico",
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


def semear_usuario(db, *, cpf="12345678900", nome="Usuário Semeado") -> int:
    return db.execute(
        "INSERT INTO usuarios (nome, cpf, contato) VALUES (%s, %s, %s) RETURNING id",
        (nome, cpf, "semeado@email.com"),
    ).fetchone()[0]


def usuarios_no_banco(db):
    return db.execute(
        "SELECT id, nome, cpf, contato, criado_em FROM usuarios ORDER BY id"
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


def assert_criado(resposta) -> dict:
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


@pytest.fixture
def banco_inalterado(db):
    """Confere, ao fim do teste de erro, que a tabela `usuarios` não mudou."""
    antes = usuarios_no_banco(db)
    yield
    assert usuarios_no_banco(db) == antes


def email_com_tamanho(total: int) -> str:
    sufixo = "@email.com"
    return "a" * (total - len(sufixo)) + sufixo


def bytes_com_tamanho(total: int) -> bytes:
    """Corpo JSON válido (campo desconhecido de enchimento) com exatamente `total` bytes."""
    base = json.dumps(corpo(enchimento=""), separators=(",", ":")).encode("utf-8")
    conteudo = json.dumps(
        corpo(enchimento="a" * (total - len(base))), separators=(",", ":")
    ).encode("utf-8")
    assert len(conteudo) == total
    return conteudo


# --------------------------------------------------------------------------- sucesso


# CT3 · Saída · 201 com exatamente os campos do CT3
def test_cadastra_usuario_com_sucesso(client):
    dados = assert_criado(postar(client, CORPO_VALIDO))

    assert set(dados) == CAMPOS_SAIDA
    assert type(dados["id"]) is int
    assert dados == {
        "id": dados["id"],
        "nome": "Lucas Joaquim",
        "cpf": "12345678900",
        "contato": "lucas@email.com",
    }


# CT3/CT10 · efeito no banco; P7 · CPF do exemplo aceito; D16(f) · criado_em do relógio
def test_cadastro_grava_linha_no_banco(client, db, instante_base):
    dados = assert_criado(postar(client, CORPO_VALIDO))

    assert usuarios_no_banco(db) == [
        (dados["id"], "Lucas Joaquim", "12345678900", "lucas@email.com", instante_base)
    ]


# CT3 · cadastros seguidos recebem ids diferentes e crescentes
def test_cadastros_seguidos_tem_ids_crescentes(client):
    primeiro = assert_criado(postar(client, corpo(cpf="11111111111")))["id"]
    segundo = assert_criado(postar(client, corpo(cpf="22222222222")))["id"]

    assert segundo > primeiro


# 00-convencoes §5 · CPF: pontos, traço e espaços removidos; gravado e devolvido normalizado
@pytest.mark.parametrize(
    "cpf",
    ["123.456.789-00", "123 456 789 00", "123.456.789 - 00", "\t123.456.789-00\n"],
    ids=["pontuado", "espacos", "misto", "brancos-nas-pontas"],
)
def test_cpf_normalizado(client, db, cpf):
    dados = assert_criado(postar(client, corpo(cpf=cpf)))

    assert dados["cpf"] == "12345678900"
    assert usuarios_no_banco(db)[0][2] == "12345678900"


# P7 / 00-convencoes §5 · dígito verificador não é conferido
@pytest.mark.parametrize("cpf", ["12345678900", "00000000000", "99999999999"])
def test_cpf_sem_conferir_digito_verificador(client, cpf):
    assert assert_criado(postar(client, corpo(cpf=cpf)))["cpf"] == cpf


# 00-convencoes §5 · contato gravado como recebido, só sem os brancos das pontas
@pytest.mark.parametrize(
    ("contato", "gravado"),
    [
        ("lucas@email.com", "lucas@email.com"),
        ("Lucas.Joaquim@Email.com.br", "Lucas.Joaquim@Email.com.br"),
        ("  lucas@email.com\t", "lucas@email.com"),
        ("(19) 99999-0000", "(19) 99999-0000"),
        ("+55 19 99999-0000", "+55 19 99999-0000"),
        ("1933334444", "1933334444"),
        ("\n(19) 3333-4444 ", "(19) 3333-4444"),
        ("+5519999990000", "+5519999990000"),
        ("a@b.c", "a@b.c"),
        ("lucas@mail.email.com", "lucas@mail.email.com"),
    ],
    ids=[
        "email",
        "email-maiusculas",
        "email-brancos",
        "tel-parenteses",
        "tel-ddi",
        "tel-10",
        "tel-brancos",
        "tel-13-com-mais",
        "email-minimo",
        "email-subdominio",
    ],
)
def test_contato_gravado_como_recebido(client, db, contato, gravado):
    dados = assert_criado(postar(client, corpo(contato=contato)))

    assert dados["contato"] == gravado
    assert usuarios_no_banco(db)[0][3] == gravado


# 00-convencoes §4 · brancos das pontas (espaço, tabulação, quebra de linha) do nome
def test_remove_brancos_das_pontas_do_nome(client, db):
    dados = assert_criado(postar(client, corpo(nome="\t Lucas  Joaquim \n")))

    assert dados["nome"] == "Lucas  Joaquim"
    assert usuarios_no_banco(db)[0][1] == "Lucas  Joaquim"


# 00-convencoes §5 · nome até 150 caracteres (depois do corte das pontas)
@pytest.mark.parametrize(
    "nome",
    ["a" * 150, "ã" * 150, " \t" + "a" * 150 + "\n "],
    ids=["150-ascii", "150-acentuados", "150-com-brancos"],
)
def test_nome_com_150_caracteres_aceito(client, nome):
    assert assert_criado(postar(client, corpo(nome=nome)))["nome"] == nome.strip(" \t\n")


# 00-convencoes §5 · contato até 120 caracteres (depois do corte das pontas)
@pytest.mark.parametrize("brancos", ["", "  "], ids=["120", "120-com-brancos"])
def test_contato_com_120_caracteres_aceito(client, brancos):
    contato = email_com_tamanho(120)

    dados = assert_criado(postar(client, corpo(contato=brancos + contato + brancos)))

    assert dados["contato"] == contato


# 00-convencoes §4 · campos desconhecidos são ignorados
def test_campo_desconhecido_ignorado(client, db):
    dados = assert_criado(postar(client, corpo(id=777, email="outro@email.com", ativo=True)))

    assert set(dados) == CAMPOS_SAIDA
    assert dados["contato"] == "lucas@email.com"
    assert len(usuarios_no_banco(db)) == 1


# 00-convencoes §4 item 1 · Content-Type com charset=utf-8 aceito
def test_content_type_com_charset_aceito(client):
    resposta = postar_bruto(
        client,
        json.dumps(CORPO_VALIDO).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
    )

    assert_criado(resposta)


# D6/CT12 · cadastrar usuário não publica evento no Backend 2
def test_cadastro_nao_chama_o_backend2(client, backend2):
    assert_criado(postar(client, CORPO_VALIDO))

    assert backend2.calls.call_count == 0


# --------------------------------------------------------------------------- CAMPOS_OBRIGATORIOS


# CT3 · Erros · campo obrigatório ausente
@pytest.mark.parametrize("campo", CAMPOS)
def test_campo_ausente(client, banco_inalterado, campo):
    assert_erro(postar(client, corpo(**{campo: ...})), 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 item 2 · campo null
@pytest.mark.parametrize("campo", CAMPOS)
def test_campo_nulo(client, banco_inalterado, campo):
    assert_erro(postar(client, corpo(**{campo: None})), 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 item 2 · texto vazio ou só com brancos (espaço, tabulação, quebra)
@pytest.mark.parametrize("valor", ["", "   ", "\t\n", " \t \n "])
@pytest.mark.parametrize("campo", CAMPOS)
def test_texto_vazio_ou_so_brancos(client, banco_inalterado, campo, valor):
    assert_erro(postar(client, corpo(**{campo: valor})), 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 item 2 · objeto vazio
def test_objeto_vazio(client, banco_inalterado):
    assert_erro(postar(client, {}), 400, "CAMPOS_OBRIGATORIOS")


# --------------------------------------------------------------------------- DADOS_INVALIDOS


# CT3 · Erros · CPF sem 11 dígitos (depois de remover pontos, traço e espaços)
@pytest.mark.parametrize(
    "cpf",
    [
        "1234567890",
        "123456789000",
        "123.456.789-0",
        "1234567890a",
        "123.456.789-0X",
        "123/456/789-00",
        "123_456_789_00",
        "123,456,789-00",
        "+12345678900",
        ".-",
    ],
    ids=[
        "10-digitos",
        "12-digitos",
        "10-pontuado",
        "letra",
        "letra-pontuado",
        "barra",
        "sublinhado",
        "virgula",
        "mais",
        "so-separadores",
    ],
)
def test_cpf_invalido(client, banco_inalterado, cpf):
    assert_erro(postar(client, corpo(cpf=cpf)), 400, "DADOS_INVALIDOS")


# CT3 · Erros · nome acima de 150 caracteres
@pytest.mark.parametrize("nome", ["a" * 151, "ã" * 151], ids=["151-ascii", "151-acentuados"])
def test_nome_com_151_caracteres(client, banco_inalterado, nome):
    assert_erro(postar(client, corpo(nome=nome)), 400, "DADOS_INVALIDOS")


# 00-convencoes §5 · contato acima de 120 caracteres
def test_contato_com_121_caracteres(client, banco_inalterado):
    assert_erro(postar(client, corpo(contato=email_com_tamanho(121))), 400, "DADOS_INVALIDOS")


# CT3 · Erros · e-mail fora do formato do §5 (sem brancos, um @, parte antes não vazia,
# domínio com ponto que não começa nem termina com ponto)
@pytest.mark.parametrize(
    "contato",
    [
        "lucasemail.com",
        "lucas@@email.com",
        "lucas@email@com.br",
        "lucas@email",
        "lucas.joaquim@email",
        "lucas @email.com",
        "lucas@ email.com",
        "lucas@email .com",
        "lucas\t@email.com",
        "@email.com",
        "lucas@.com",
        "lucas@email.",
        "lucas@.email.com",
        "lucas@email.com.",
        "lucas@email\n.com",
        "lucas@email.com\tbr",
    ],
    ids=[
        "sem-arroba",
        "dois-arrobas-juntos",
        "dois-arrobas",
        "sem-ponto-depois",
        "ponto-so-antes",
        "espaco-antes-arroba",
        "espaco-depois-arroba",
        "espaco-no-dominio",
        "tab-no-meio",
        "antes-do-arroba-vazio",
        "dominio-comeca-com-ponto-curto",
        "dominio-termina-com-ponto",
        "dominio-comeca-com-ponto",
        "dominio-termina-com-ponto-longo",
        "quebra-de-linha-no-meio",
        "tab-no-dominio",
    ],
)
def test_email_invalido(client, banco_inalterado, contato):
    assert_erro(postar(client, corpo(contato=contato)), 400, "DADOS_INVALIDOS")


# CT3 · Erros · telefone fora de 10 a 13 dígitos ou com caractere não permitido
# (§5: só o espaço U+0020 é removido; tabulação/quebra no meio é inválida)
@pytest.mark.parametrize(
    "contato",
    [
        "199999999",
        "(19) 9999-999",
        "55199999900001",
        "+55 19 99999-00001",
        "++5519999990000",
        "55+19999990000",
        "19.9999.0000",
        "19/99999-0000",
        "1999999000a",
        "+",
        "19\t99999-0000",
        "19\n99999-0000",
        "(19)\t3333-4444",
        "+55\u00a019 99999-0000",
    ],
    ids=[
        "9-digitos",
        "9-formatado",
        "14-digitos",
        "14-com-ddi",
        "dois-mais",
        "mais-no-meio",
        "pontos",
        "barra",
        "letra",
        "so-mais",
        "tab-no-meio",
        "quebra-de-linha-no-meio",
        "tab-apos-parenteses",
        "espaco-nao-separavel",
    ],
)
def test_telefone_invalido(client, banco_inalterado, contato):
    assert_erro(postar(client, corpo(contato=contato)), 400, "DADOS_INVALIDOS")


# CT3 · Erros · texto que não é nem e-mail nem telefone
@pytest.mark.parametrize("contato", ["lucas", "telefone do Lucas", "-", "()"])
def test_contato_nem_email_nem_telefone(client, banco_inalterado, contato):
    assert_erro(postar(client, corpo(contato=contato)), 400, "DADOS_INVALIDOS")


# CT3 · Erros · campo com tipo errado (§4: texto com outro tipo → DADOS_INVALIDOS)
@pytest.mark.parametrize(
    "valor",
    [12345678900, 3.5, True, False, ["12345678900"], {"v": "x"}],
    ids=["inteiro", "decimal", "true", "false", "lista", "objeto"],
)
@pytest.mark.parametrize("campo", CAMPOS)
def test_campo_com_tipo_errado(client, banco_inalterado, campo, valor):
    assert_erro(postar(client, corpo(**{campo: valor})), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · corpos inválidos representativos (o E4 cobre todos)
@pytest.mark.parametrize(
    ("bruto", "headers"),
    [
        (b"", JSON),
        (b'{"nome": "Lucas",', JSON),
        (b'[{"nome": "Lucas"}]', JSON),
        (b'"texto"', JSON),
        (json.dumps(CORPO_VALIDO).encode(), {"Content-Type": "text/plain"}),
        (json.dumps(CORPO_VALIDO).encode("utf-16"), JSON),
        (
            rb'{"nome": "Lucas \ud800", "cpf": "12345678900", "contato": "lucas@email.com"}',
            JSON,
        ),
    ],
    ids=["vazio", "json-quebrado", "lista", "escalar", "text-plain", "utf-16", "surrogate"],
)
def test_corpo_invalido(client, banco_inalterado, bruto, headers):
    assert_erro(postar_bruto(client, bruto, headers=headers), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · Content-Type ausente
def test_content_type_ausente(client, banco_inalterado):
    resposta = client.post(ROTA, content=json.dumps(CORPO_VALIDO).encode("utf-8"))

    assert "content-type" not in resposta.request.headers
    assert_erro(resposta, 400, "DADOS_INVALIDOS")


# 00-convencoes §4 item 1 · corpo acima de 64 KiB (e exatamente 64 KiB aceito)
def test_limite_de_64_kib(client, db):
    assert_erro(postar_bruto(client, bytes_com_tamanho(LIMITE_CORPO + 1)), 400, "DADOS_INVALIDOS")
    assert usuarios_no_banco(db) == []

    assert_criado(postar_bruto(client, bytes_com_tamanho(LIMITE_CORPO)))


# 00-convencoes §4 item 1 · caractere NUL em qualquer chave ou valor
@pytest.mark.parametrize(
    "dados",
    [
        corpo(nome="Lucas\x00"),
        corpo(cpf="123456789\x0000"),
        corpo(contato="lucas@email.com\x00"),
        corpo(extra="\x00"),
        {**CORPO_VALIDO, "chave\x00": 1},
    ],
    ids=["nome", "cpf", "contato", "valor-campo-desconhecido", "chave"],
)
def test_caractere_nul_recusado(client, banco_inalterado, dados):
    assert_erro(postar(client, dados), 400, "DADOS_INVALIDOS")


# --------------------------------------------------------------------------- ordem do §4


# 00-convencoes §4 · item 1 antes do 2: Content-Type errado e campos ausentes
def test_ordem_content_type_antes_de_campos_ausentes(client, banco_inalterado):
    resposta = postar_bruto(client, b'{"nome": "L"}', headers={"Content-Type": "text/plain"})

    assert_erro(resposta, 400, "DADOS_INVALIDOS")


# 00-convencoes §4 · item 1 antes do 2: NUL num campo e outro campo ausente
def test_ordem_nul_antes_de_campo_ausente(client, banco_inalterado):
    assert_erro(postar(client, corpo(nome="L\x00", contato=...)), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 · item 2 antes do 3, mesmo com o campo do item 3 antes na tabela
@pytest.mark.parametrize(
    "alteracoes",
    [
        {"nome": "a" * 151, "contato": None},
        {"nome": 123, "cpf": ...},
        {"cpf": "123", "contato": "   "},
        {"nome": True, "cpf": "", "contato": "x"},
    ],
    ids=["nome-longo+contato-nulo", "nome-tipo+cpf-ausente", "cpf-invalido+contato-branco", "3"],
)
def test_ordem_item_2_antes_do_3(client, banco_inalterado, alteracoes):
    assert_erro(postar(client, corpo(**alteracoes)), 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 · dentro do item 2: vários campos ausentes ou nulos
def test_ordem_dentro_do_item_2(client, banco_inalterado):
    resposta = postar(client, corpo(nome=..., cpf=None, contato=""))

    assert_erro(resposta, 400, "CAMPOS_OBRIGATORIOS")


# 00-convencoes §4 · dentro do item 3: nome, cpf, contato (todos DADOS_INVALIDOS no CT3)
@pytest.mark.parametrize(
    "alteracoes",
    [
        {"nome": "a" * 151, "cpf": "123"},
        {"cpf": "123", "contato": "lucas"},
        {"nome": 1, "cpf": 2, "contato": 3},
    ],
    ids=["nome+cpf", "cpf+contato", "todos"],
)
def test_ordem_dentro_do_item_3(client, banco_inalterado, alteracoes):
    assert_erro(postar(client, corpo(**alteracoes)), 400, "DADOS_INVALIDOS")


# 00-convencoes §4 · item 3 antes do 4: CPF inválido que também está gravado
def test_ordem_cpf_invalido_antes_de_duplicado(client, db):
    semear_usuario(db, cpf="1234567890")
    antes = usuarios_no_banco(db)

    assert_erro(postar(client, corpo(cpf="1234567890")), 400, "DADOS_INVALIDOS")
    assert usuarios_no_banco(db) == antes


# 00-convencoes §4 · item 3 antes do 4: contato inválido + CPF duplicado
def test_ordem_contato_invalido_antes_de_cpf_duplicado(client, db):
    semear_usuario(db, cpf="12345678900")
    antes = usuarios_no_banco(db)

    assert_erro(postar(client, corpo(contato="lucas")), 400, "DADOS_INVALIDOS")
    assert usuarios_no_banco(db) == antes


# 00-convencoes §4 · item 3 antes do 4: nome longo + CPF duplicado
def test_ordem_nome_longo_antes_de_cpf_duplicado(client, db):
    semear_usuario(db, cpf="12345678900")
    antes = usuarios_no_banco(db)

    assert_erro(postar(client, corpo(nome="a" * 151)), 400, "DADOS_INVALIDOS")
    assert usuarios_no_banco(db) == antes


# --------------------------------------------------------------------------- CPF_DUPLICADO


# CT3 · Erros · CPF já cadastrado (duplicidade avaliada após normalização, §5)
@pytest.mark.parametrize(
    "cpf",
    ["12345678900", "123.456.789-00", " 123 456 789 00 "],
    ids=["igual", "pontuado", "espacos"],
)
def test_cpf_duplicado(client, db, cpf):
    semear_usuario(db, cpf="12345678900")
    antes = usuarios_no_banco(db)

    resposta = postar(client, corpo(cpf=cpf, nome="Outra Pessoa", contato="outra@email.com"))

    assert_erro(resposta, 409, "CPF_DUPLICADO")
    assert usuarios_no_banco(db) == antes


# CT3 · CPF_DUPLICADO quando o primeiro foi cadastrado pela própria API, com pontuação
def test_cpf_duplicado_apos_cadastro_pela_api(client, db):
    assert_criado(postar(client, corpo(cpf="987.654.321-00")))
    antes = usuarios_no_banco(db)

    assert_erro(postar(client, corpo(cpf="98765432100")), 409, "CPF_DUPLICADO")
    assert usuarios_no_banco(db) == antes


# CT3 · depois de um CPF_DUPLICADO, outro CPF continua sendo aceito
def test_cadastro_continua_funcionando_apos_duplicado(client, db):
    semear_usuario(db, cpf="12345678900")
    assert_erro(postar(client, CORPO_VALIDO), 409, "CPF_DUPLICADO")

    assert_criado(postar(client, corpo(cpf="12345678901")))
    assert len(usuarios_no_banco(db)) == 2


# --------------------------------------------------------------------------- concorrência


# D16(a) / CT3 · dois cadastros simultâneos com o mesmo CPF: um 201, um 409, uma linha.
# A corrida é forçada: as duas threads saem juntas da barreira, em várias rodadas.
@pytest.mark.parametrize("rodada", range(5))
def test_cadastros_simultaneos_com_mesmo_cpf(client, db, rodada):
    cpf = f"{rodada:011d}"
    barreira = threading.Barrier(2, timeout=10)

    def cadastrar(nome, cpf_enviado):
        barreira.wait()
        return client.post(ROTA, json=corpo(nome=nome, cpf=cpf_enviado))

    pedidos = [
        ("Primeira Pessoa", cpf),
        ("Segunda Pessoa", f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"),
    ]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(cadastrar, nome, enviado) for nome, enviado in pedidos]
        respostas = [futuro.result(timeout=30) for futuro in futuros]

    assert sorted(r.status_code for r in respostas) == [201, 409], [r.text for r in respostas]
    assert_erro(next(r for r in respostas if r.status_code == 409), 409, "CPF_DUPLICADO")
    vencedor = next(r for r in respostas if r.status_code == 201).json()
    linhas = usuarios_no_banco(db)
    assert len(linhas) == 1
    assert linhas[0][:3] == (vencedor["id"], vencedor["nome"], cpf)


# --------------------------------------------------------------------------- rota


# 00-convencoes §3 · barra no fim é rota inexistente, sem redirecionamento
def test_barra_no_fim(client, banco_inalterado):
    resposta = client.post("/usuarios/", json=CORPO_VALIDO, follow_redirects=False)

    assert_erro(resposta, 404, "ROTA_NAO_ENCONTRADA")
