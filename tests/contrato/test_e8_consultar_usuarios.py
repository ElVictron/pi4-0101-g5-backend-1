"""E8 — consultarUsuarios (card #792): `GET /usuarios?busca&pagina&tamanho`.

Fontes: CT4, CT8 (EmprestimoResumo e situação efetiva), CT10, CT11; `00-convencoes.md` §3,
§6 (inclusive "CT4 em detalhe") e §7; `agentes.md` D3 e D17. Usuários, livros e
empréstimos semeados por SQL direto, sem `id` explícito, com datas relativas ao relógio
fixo (`instante_base` = 2026-10-13T19:20:00).
"""

import re
import unicodedata
from datetime import datetime, timedelta

import pytest

ROTA = "/usuarios"
CAMPOS_RESPOSTA = {"usuarios", "total", "pagina", "tamanho"}
CAMPOS_USUARIO = {"id", "nome", "cpf", "contato", "emprestimos"}
CAMPOS_EMPRESTIMO = {
    "emprestimoId",
    "usuarioId",
    "usuarioNome",
    "livroId",
    "livroTitulo",
    "status",
    "emprestadoEm",
    "dataLimiteDevolucao",
    "devolvidoEm",
}
FORMATO_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
TRECHOS_PROIBIDOS = ("syntax error", "psycopg", "sqlstate", "traceback", "like", "select")
PRAZO = timedelta(days=15)

# Usuários para busca: chave -> (nome, cpf, contato)
PESSOAS = {
    "lucas": ("Lucas Joaquim", "12345678900", "lucas@email.com"),
    "ana_lucas": ("Ana Lucas 10", "22222222222", "ana@email.com"),
    "maria": ("Maria Souza", "98765432000", "(19) 99999-0000"),
    "jose": ("José Antônio", "33344455566", "jose@email.com"),
    "sub": ("Ana_Maria Costa", "44455566677", "anamaria@email.com"),
    "pct": ("Leitor Cem%", "55566677788", "leitor@email.com"),
    "barra": ("Barra \\ Nome", "66677788899", "barra@email.com"),
}


# --------------------------------------------------------------------------- apoio


def semear_usuario(db, nome, cpf=None, contato="x@email.com") -> int:
    if cpf is None:
        quantos = db.execute("SELECT count(*) FROM usuarios").fetchone()[0]
        cpf = f"{70000000000 + quantos}"
    return db.execute(
        "INSERT INTO usuarios (nome, cpf, contato) VALUES (%s, %s, %s) RETURNING id",
        (nome, cpf, contato),
    ).fetchone()[0]


def semear_livro(db, titulo="Livro Semeado", exemplares=5) -> int:
    quantos = db.execute("SELECT count(*) FROM livros").fetchone()[0]
    return db.execute(
        "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (titulo, "Autor", f"{9780000000000 + quantos}", exemplares, exemplares),
    ).fetchone()[0]


def semear_emprestimo(db, usuario_id, livro_id, emprestado_em, *, limite=None, devolvido_em=None):
    limite = emprestado_em + PRAZO if limite is None else limite
    status = "devolvido" if devolvido_em else "ativo"
    return db.execute(
        "INSERT INTO emprestimos"
        " (usuario_id, livro_id, status, emprestado_em, data_limite_devolucao, devolvido_em)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (usuario_id, livro_id, status, emprestado_em, limite, devolvido_em),
    ).fetchone()[0]


@pytest.fixture
def pessoas(db):
    return {chave: semear_usuario(db, *dados) for chave, dados in PESSOAS.items()}


def consultar(client, **params):
    return client.get(ROTA, params=params)


def assert_ok(resposta) -> dict:
    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["content-type"].startswith("application/json")
    dados = resposta.json()
    assert set(dados) == CAMPOS_RESPOSTA
    return dados


def ids(dados) -> list[int]:
    return [usuario["id"] for usuario in dados["usuarios"]]


def iso(instante: datetime) -> str:
    return instante.strftime("%Y-%m-%dT%H:%M:%S")


def sem_acento_minusculo(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c)).lower()


def chave_de_ordem(texto: str) -> tuple[str, str]:
    """00-convencoes §6: sem caixa nem acento; empate → texto exato por código de caractere."""
    return (sem_acento_minusculo(texto), texto)


def esperados(pessoas, chaves) -> list[int]:
    return [
        pessoas[c]
        for c in sorted(chaves, key=lambda c: (chave_de_ordem(PESSOAS[c][0]), pessoas[c]))
    ]


def emprestimos_de(dados, usuario_id) -> list[dict]:
    (usuario,) = [u for u in dados["usuarios"] if u["id"] == usuario_id]
    return usuario["emprestimos"]


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


# CT4 / CT8 · chaves exatas da resposta, do UsuarioResumo e do EmprestimoResumo; tipos e datas
def test_saida_com_campos_e_tipos(client, db, instante_base):
    usuario_id = semear_usuario(db, "Lucas Joaquim", "12345678900", "lucas@email.com")
    livro_id = semear_livro(db, "Fundamentos de Sistemas de Informação")
    emprestado_em = instante_base - timedelta(days=1)
    emprestimo_id = semear_emprestimo(db, usuario_id, livro_id, emprestado_em)

    dados = assert_ok(consultar(client))

    assert (dados["total"], dados["pagina"], dados["tamanho"]) == (1, 1, 20)
    for campo in ("total", "pagina", "tamanho"):
        assert type(dados[campo]) is int
    (usuario,) = dados["usuarios"]
    assert set(usuario) == CAMPOS_USUARIO
    assert type(usuario["id"]) is int
    (emprestimo,) = usuario["emprestimos"]
    assert set(emprestimo) == CAMPOS_EMPRESTIMO
    for campo in ("emprestimoId", "usuarioId", "livroId"):
        assert type(emprestimo[campo]) is int, campo
    for campo in ("emprestadoEm", "dataLimiteDevolucao"):
        assert FORMATO_DATA.match(emprestimo[campo]), emprestimo[campo]
    assert usuario == {
        "id": usuario_id,
        "nome": "Lucas Joaquim",
        "cpf": "12345678900",
        "contato": "lucas@email.com",
        "emprestimos": [
            {
                "emprestimoId": emprestimo_id,
                "usuarioId": usuario_id,
                "usuarioNome": "Lucas Joaquim",
                "livroId": livro_id,
                "livroTitulo": "Fundamentos de Sistemas de Informação",
                "status": "ativo",
                "emprestadoEm": iso(emprestado_em),
                "dataLimiteDevolucao": iso(emprestado_em + PRAZO),
                "devolvidoEm": None,
            }
        ],
    }


# §7 · devolvidoEm presente: no formato AAAA-MM-DDTHH:MM:SS quando devolvido
def test_devolvido_em_formatado(client, db, instante_base):
    usuario_id = semear_usuario(db, "Lucas")
    devolvido_em = instante_base - timedelta(days=2, hours=3, seconds=7)
    semear_emprestimo(
        db,
        usuario_id,
        semear_livro(db),
        instante_base - timedelta(days=5),
        devolvido_em=devolvido_em,
    )

    (emprestimo,) = emprestimos_de(assert_ok(consultar(client)), usuario_id)

    assert emprestimo["devolvidoEm"] == iso(devolvido_em)
    assert FORMATO_DATA.match(emprestimo["devolvidoEm"])
    assert emprestimo["status"] == "devolvido"


# CT4 · banco vazio → lista vazia e total 0
def test_banco_vazio(client):
    assert assert_ok(consultar(client)) == {"usuarios": [], "total": 0, "pagina": 1, "tamanho": 20}


# §6 (CT4 em detalhe) · usuário sem empréstimos: `emprestimos` presente e vazio
def test_usuario_sem_emprestimos(client, db):
    usuario_id = semear_usuario(db, "Sem Empréstimos")

    (usuario,) = assert_ok(consultar(client))["usuarios"]

    assert usuario["id"] == usuario_id
    assert usuario["emprestimos"] == []


# CT4 · cada usuário vê só os próprios empréstimos
def test_emprestimos_separados_por_usuario(client, db, instante_base):
    ana = semear_usuario(db, "Ana")
    bia = semear_usuario(db, "Bia")
    livro = semear_livro(db)
    de_ana = semear_emprestimo(db, ana, livro, instante_base - timedelta(days=1))
    de_bia = semear_emprestimo(db, bia, livro, instante_base - timedelta(days=2))

    dados = assert_ok(consultar(client))

    assert [e["emprestimoId"] for e in emprestimos_de(dados, ana)] == [de_ana]
    assert [e["emprestimoId"] for e in emprestimos_de(dados, bia)] == [de_bia]
    assert emprestimos_de(dados, bia)[0]["usuarioNome"] == "Bia"


# --------------------------------------------------------------------------- situação efetiva


# CT8 / §7 · situação efetiva com o relógio fixo
def test_situacao_efetiva(client, db, instante_base):
    usuario_id = semear_usuario(db, "Lucas")
    livro = semear_livro(db)
    no_prazo = semear_emprestimo(db, usuario_id, livro, instante_base - timedelta(days=1))
    vencido = semear_emprestimo(db, usuario_id, livro, instante_base - timedelta(days=20))
    devolvido_vencido = semear_emprestimo(
        db,
        usuario_id,
        livro,
        instante_base - timedelta(days=40),
        devolvido_em=instante_base - timedelta(days=2),
    )
    devolvido_no_prazo = semear_emprestimo(
        db,
        usuario_id,
        livro,
        instante_base - timedelta(days=3),
        devolvido_em=instante_base - timedelta(days=1),
    )

    emprestimos = emprestimos_de(assert_ok(consultar(client)), usuario_id)

    situacao = {e["emprestimoId"]: e["status"] for e in emprestimos}
    assert situacao == {
        no_prazo: "ativo",
        vencido: "atrasado",
        devolvido_vencido: "devolvido",
        devolvido_no_prazo: "devolvido",
    }
    status_gravado = db.execute(
        "SELECT status FROM emprestimos WHERE id = %s", (vencido,)
    ).fetchone()[0]
    assert status_gravado == "ativo"


# §7 · no instante exato da data limite ainda é `ativo`; 1 segundo depois, `atrasado`
def test_borda_exata_da_data_limite(client, db, relogio, instante_base):
    usuario_id = semear_usuario(db, "Lucas")
    emprestimo_id = semear_emprestimo(db, usuario_id, semear_livro(db), instante_base)

    def situacao():
        (emprestimo,) = emprestimos_de(assert_ok(consultar(client)), usuario_id)
        assert emprestimo["emprestimoId"] == emprestimo_id
        return emprestimo["status"]

    assert situacao() == "ativo"
    relogio.avancar(PRAZO - timedelta(seconds=1))
    assert situacao() == "ativo"
    relogio.avancar(timedelta(seconds=1))
    assert relogio.agora() == instante_base + PRAZO
    assert situacao() == "ativo"
    relogio.avancar(timedelta(seconds=1))
    assert situacao() == "atrasado"


# §7 · a data limite usada é a gravada (não recalculada): limite curto vence antes
def test_situacao_usa_a_data_limite_gravada(client, db, instante_base):
    usuario_id = semear_usuario(db, "Lucas")
    emprestimo_id = semear_emprestimo(
        db,
        usuario_id,
        semear_livro(db),
        instante_base - timedelta(days=2),
        limite=instante_base - timedelta(seconds=1),
    )

    (emprestimo,) = emprestimos_de(assert_ok(consultar(client)), usuario_id)

    assert emprestimo["emprestimoId"] == emprestimo_id
    assert emprestimo["status"] == "atrasado"
    assert emprestimo["dataLimiteDevolucao"] == iso(instante_base - timedelta(seconds=1))


# §7 · devolvido continua `devolvido` mesmo com o relógio muito à frente
def test_devolvido_nao_vira_atrasado(client, db, relogio, instante_base):
    usuario_id = semear_usuario(db, "Lucas")
    semear_emprestimo(db, usuario_id, semear_livro(db), instante_base, devolvido_em=instante_base)
    relogio.avancar(timedelta(days=365))

    (emprestimo,) = emprestimos_de(assert_ok(consultar(client)), usuario_id)

    assert emprestimo["status"] == "devolvido"


# --------------------------------------------------------------------------- ordem dos empréstimos


# §6 · empréstimos do usuário: emprestadoEm mais recente primeiro, depois id decrescente
def test_ordem_dos_emprestimos(client, db, instante_base):
    usuario_id = semear_usuario(db, "Lucas")
    livro = semear_livro(db)
    dez_a = semear_emprestimo(db, usuario_id, livro, instante_base - timedelta(days=10))
    dois = semear_emprestimo(db, usuario_id, livro, instante_base - timedelta(days=2))
    dez_b = semear_emprestimo(db, usuario_id, livro, instante_base - timedelta(days=10))
    cinco = semear_emprestimo(
        db,
        usuario_id,
        livro,
        instante_base - timedelta(days=5),
        devolvido_em=instante_base - timedelta(days=4),
    )
    trinta = semear_emprestimo(db, usuario_id, livro, instante_base - timedelta(days=30))

    emprestimos = emprestimos_de(assert_ok(consultar(client)), usuario_id)

    assert [e["emprestimoId"] for e in emprestimos] == [dois, cinco, dez_b, dez_a, trinta]
    assert [e["status"] for e in emprestimos] == [
        "ativo",
        "devolvido",
        "ativo",
        "ativo",
        "atrasado",
    ]


# --------------------------------------------------------------------------- busca


# §6 (CT4 em detalhe) · busca por nome (sem caixa nem acento) ou pelos dígitos do CPF
@pytest.mark.parametrize(
    ("busca", "chaves"),
    [
        ("lucas", ["ana_lucas", "lucas"]),
        ("JOAQUIM", ["lucas"]),
        ("quim", ["lucas"]),
        ("jose", ["jose"]),
        ("ANTÔNIO", ["jose"]),
        ("antonio", ["jose"]),
        ("12345678900", ["lucas"]),
        ("123.456.789-00", ["lucas"]),
        ("123.456", ["lucas"]),
        ("789-00", ["lucas"]),
        ("4567", ["lucas"]),
        ("123 456", ["lucas"]),
        ("765.432", ["maria"]),
        ("Lucas 1", ["ana_lucas", "lucas"]),
        ("Maria 9876", ["maria"]),
        ("lucas 10", ["ana_lucas"]),
    ],
    ids=lambda valor: valor if isinstance(valor, str) else None,
)
def test_busca(client, pessoas, busca, chaves):
    dados = assert_ok(consultar(client, busca=busca))

    assert ids(dados) == esperados(pessoas, chaves)
    assert dados["total"] == len(chaves)


# §6 (CT4 em detalhe) · termo sem dígito não procura no CPF (senão casaria com todos)
@pytest.mark.parametrize("busca", [".", "-", ".-.", "abc"])
def test_termo_sem_digito_nao_procura_no_cpf(client, pessoas, busca):
    dados = assert_ok(consultar(client, busca=busca))

    assert dados["usuarios"] == []
    assert dados["total"] == 0


# CT4 · a busca procura só no nome e no CPF (não no contato nem no título do livro);
# "(19)" está no contato de Maria e nenhum CPF semeado contém "19"
@pytest.mark.parametrize("busca", ["email", "(19)", "Fundamentos"])
def test_busca_nao_procura_em_contato_nem_livro(client, db, pessoas, instante_base, busca):
    livro = semear_livro(db, "Fundamentos de Sistemas")
    semear_emprestimo(db, pessoas["lucas"], livro, instante_base)

    dados = assert_ok(consultar(client, busca=busca))

    assert dados["usuarios"] == []
    assert dados["total"] == 0


# §6 · %, _ e \ são literais no nome
@pytest.mark.parametrize(
    ("busca", "chaves"),
    [
        ("%", ["pct"]),
        ("%%", []),
        ("_", ["sub"]),
        ("a_m", ["sub"]),
        ("\\", ["barra"]),
        ("a \\ n", ["barra"]),
        ("\\%", []),
    ],
    ids=["pct", "dois-pct", "sub", "a_m", "barra", "a-barra-n", "barra-pct"],
)
def test_busca_com_literais(client, pessoas, busca, chaves):
    assert ids(assert_ok(consultar(client, busca=busca))) == esperados(pessoas, chaves)


# §6 · busca com brancos nas pontas; vazia = sem filtro; sem resultado = vazia
def test_busca_brancos_vazia_e_sem_resultado(client, pessoas):
    assert ids(assert_ok(consultar(client, busca="\t joaquim \n"))) == [pessoas["lucas"]]
    assert assert_ok(consultar(client, busca=" \t "))["total"] == len(PESSOAS)
    sem = assert_ok(consultar(client, busca="inexistente"))
    assert (sem["usuarios"], sem["total"]) == ([], 0)


# §6 · `+` na URL é espaço
def test_mais_na_url_e_espaco(client, pessoas):
    assert ids(assert_ok(client.get(f"{ROTA}?busca=lucas+joaquim"))) == [pessoas["lucas"]]


# CT4 · a busca não filtra os empréstimos do usuário encontrado
def test_busca_traz_todos_os_emprestimos_do_usuario(client, db, pessoas, instante_base):
    livro_a = semear_livro(db, "Livro A")
    livro_b = semear_livro(db, "Livro B")
    e1 = semear_emprestimo(db, pessoas["lucas"], livro_a, instante_base - timedelta(days=1))
    e2 = semear_emprestimo(db, pessoas["lucas"], livro_b, instante_base - timedelta(days=30))

    dados = assert_ok(consultar(client, busca="123.456"))

    assert [e["emprestimoId"] for e in emprestimos_de(dados, pessoas["lucas"])] == [e1, e2]


# §6 · 100 caracteres aceitos (depois do corte das pontas)
@pytest.mark.parametrize("busca", ["a" * 100, "ã" * 100, "\t" + "a" * 100 + " "])
def test_busca_com_100_caracteres_aceita(client, pessoas, busca):
    assert assert_ok(consultar(client, busca=busca))["total"] == 0


# CT4 · Erros · busca com mais de 100 caracteres
@pytest.mark.parametrize("busca", ["a" * 101, "1" * 101, " " + "a" * 101 + "\n"])
def test_busca_com_101_caracteres(client, pessoas, busca):
    assert_erro(consultar(client, busca=busca), 400, "BUSCA_INVALIDA")


# §6 · NUL, metade de par substituto ou bytes não UTF-8 → BUSCA_INVALIDA
@pytest.mark.parametrize("codificada", ["%00", "lucas%00", "%ED%A0%80", "%FF", "lucas%C3"])
def test_busca_com_caractere_invalido(client, pessoas, codificada):
    assert_erro(client.get(f"{ROTA}?busca={codificada}"), 400, "BUSCA_INVALIDA")


# --------------------------------------------------------------------------- ordem dos usuários


# §6 · usuários por nome: sem caixa nem acento; empate → texto exato; depois id
def test_ordem_dos_usuarios(client, db):
    nomes = ["Zélia", "álvaro lima", "Bruno", "célia", "Álvaro Lima", "alvaro lima"]
    por_nome = {nome: semear_usuario(db, nome) for nome in nomes}
    repetido = semear_usuario(db, "Bruno")

    esperada = sorted(nomes, key=chave_de_ordem)
    assert esperada[:3] == ["alvaro lima", "Álvaro Lima", "álvaro lima"]
    ordem_ids = [por_nome[n] for n in esperada]
    ordem_ids.insert(esperada.index("Bruno") + 1, repetido)

    assert ids(assert_ok(consultar(client))) == ordem_ids


# --------------------------------------------------------------------------- paginação


@pytest.fixture
def vinte_e_cinco_usuarios(db, instante_base):
    """25 usuários ('Usuário 01'..'25', fora de ordem); o 03 tem 5 empréstimos."""
    por_numero = {
        n: semear_usuario(db, f"Usuário {n:02d}") for n in [*range(25, 12, -1), *range(1, 13)]
    }
    livro = semear_livro(db)
    for dias in range(5):
        semear_emprestimo(db, por_numero[3], livro, instante_base - timedelta(days=dias))
    return [por_numero[n] for n in range(1, 26)]


# CT4 / §6 · paginação conta usuários (o usuário com 5 empréstimos conta 1)
@pytest.mark.parametrize(
    ("pagina", "inicio", "fim"), [(1, 0, 10), (2, 10, 20), (3, 20, 25), (4, 25, 25)]
)
def test_paginacao_conta_usuarios(client, vinte_e_cinco_usuarios, pagina, inicio, fim):
    dados = assert_ok(consultar(client, pagina=str(pagina), tamanho="10"))

    assert ids(dados) == vinte_e_cinco_usuarios[inicio:fim]
    assert dados["total"] == 25
    assert (dados["pagina"], dados["tamanho"]) == (pagina, 10)


# CT4 · o usuário com vários empréstimos aparece uma vez, com todos eles
def test_usuario_com_varios_emprestimos_aparece_uma_vez(client, vinte_e_cinco_usuarios):
    dados = assert_ok(consultar(client, tamanho="3"))

    assert ids(dados) == vinte_e_cinco_usuarios[:3]
    assert len(emprestimos_de(dados, vinte_e_cinco_usuarios[2])) == 5
    assert dados["total"] == 25


# §6 · padrões, ecoados; bordas aceitas; página além da última
def test_padroes_e_bordas(client, vinte_e_cinco_usuarios):
    padrao = assert_ok(consultar(client))
    assert (padrao["pagina"], padrao["tamanho"], len(padrao["usuarios"])) == (1, 20, 20)
    assert len(assert_ok(consultar(client, tamanho="1"))["usuarios"]) == 1
    assert len(assert_ok(consultar(client, tamanho="100"))["usuarios"]) == 25
    alem = assert_ok(consultar(client, pagina="2147483647"))
    assert (alem["usuarios"], alem["total"]) == ([], 25)


# §6 · com busca, o total conta só os usuários filtrados
def test_total_com_busca(client, db, vinte_e_cinco_usuarios):
    filtrados = [semear_usuario(db, f"Especial {letra}") for letra in "ABC"]

    primeira = assert_ok(consultar(client, busca="especial", tamanho="2"))
    segunda = assert_ok(consultar(client, busca="especial", pagina="2", tamanho="2"))

    assert (primeira["total"], segunda["total"]) == (3, 3)
    assert ids(primeira) == filtrados[:2]
    assert ids(segunda) == filtrados[2:]


# §6 · vazio = padrão; repetido = primeiro valor; parâmetro desconhecido ignorado
@pytest.mark.parametrize(
    ("consulta", "pagina", "tamanho"),
    [
        ("pagina=&tamanho=%20", 1, 20),
        ("pagina=2&pagina=abc&tamanho=10", 2, 10),
        ("tamanho=5&tamanho=0", 1, 5),
        ("foo=bar&status=x&tamanho=07", 1, 7),
    ],
    ids=["vazios", "repetido", "repetido-tamanho", "desconhecido"],
)
def test_parametros_vazios_repetidos_desconhecidos(
    client, vinte_e_cinco_usuarios, consulta, pagina, tamanho
):
    dados = assert_ok(client.get(f"{ROTA}?{consulta}"))

    assert (dados["pagina"], dados["tamanho"]) == (pagina, tamanho)
    inicio = (pagina - 1) * tamanho
    assert ids(dados) == vinte_e_cinco_usuarios[inicio : inicio + tamanho]


# CT4 · Erros · página < 1, tamanho fora de 1..100, valor não inteiro; §6 · formas inválidas
@pytest.mark.parametrize(
    "consulta",
    [
        "pagina=0",
        "pagina=-1",
        "pagina=abc",
        "pagina=1.5",
        "pagina=%2B1",
        "pagina=2147483648",
        "pagina=%00",
        "tamanho=0",
        "tamanho=101",
        "tamanho=1e1",
        "pagina=abc&pagina=2",
    ],
)
def test_paginacao_invalida(client, pessoas, consulta):
    assert_erro(client.get(f"{ROTA}?{consulta}"), 400, "PAGINACAO_INVALIDA")


# §6 · ordem entre parâmetros: busca, pagina, tamanho
@pytest.mark.parametrize(
    ("params", "codigo"),
    [
        ({"busca": "a" * 101, "pagina": "0"}, "BUSCA_INVALIDA"),
        ({"busca": "a" * 101, "tamanho": "0"}, "BUSCA_INVALIDA"),
        ({"pagina": "0", "tamanho": "101"}, "PAGINACAO_INVALIDA"),
    ],
    ids=["busca+pagina", "busca+tamanho", "pagina+tamanho"],
)
def test_ordem_entre_parametros(client, pessoas, params, codigo):
    assert_erro(consultar(client, **params), 400, codigo)


# --------------------------------------------------------------------------- rotas


# §3 · barra no fim
def test_barra_no_fim(client):
    assert_erro(client.get("/usuarios/", follow_redirects=False), 404, "ROTA_NAO_ENCONTRADA")


# §3 · métodos não permitidos em /usuarios
@pytest.mark.parametrize("metodo", ["PUT", "PATCH", "DELETE"])
def test_metodo_nao_permitido(client, metodo):
    assert_erro(client.request(metodo, ROTA), 405, "ROTA_NAO_ENCONTRADA")


# CT3 · regressão: POST /usuarios continua funcionando e o usuário aparece na consulta
def test_post_usuarios_continua_funcionando(client):
    resposta = client.post(
        ROTA, json={"nome": "Novo Leitor", "cpf": "111.222.333-44", "contato": "novo@email.com"}
    )

    assert resposta.status_code == 201, resposta.text
    dados = assert_ok(consultar(client, busca="111.222"))
    assert ids(dados) == [resposta.json()["id"]]
    assert dados["usuarios"][0]["emprestimos"] == []
