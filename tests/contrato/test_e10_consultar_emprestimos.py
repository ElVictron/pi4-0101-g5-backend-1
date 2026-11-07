"""E10 — consultarEmprestimos (card #796): `GET /emprestimos?status&busca`.

Fontes: CT8 (situação efetiva e EmprestimoResumo), CT9–CT11; `00-convencoes.md` §3, §6
(inclusive "CT8 em detalhe") e §7; `agentes.md` D3 e D17. Dados semeados por SQL direto,
sem `id` explícito, com datas relativas ao relógio fixo (`instante_base`).
"""

import re
from datetime import datetime, timedelta

import pytest

ROTA = "/emprestimos"
PRAZO = timedelta(days=15)
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
SITUACOES = ("ativo", "atrasado", "devolvido")


# --------------------------------------------------------------------------- apoio


def semear_usuario(db, nome, cpf=None) -> int:
    if cpf is None:
        quantos = db.execute("SELECT count(*) FROM usuarios").fetchone()[0]
        cpf = f"{70000000000 + quantos}"
    return db.execute(
        "INSERT INTO usuarios (nome, cpf, contato) VALUES (%s, %s, %s) RETURNING id",
        (nome, cpf, "leitor@email.com"),
    ).fetchone()[0]


def semear_livro(db, titulo, autor="Autor") -> int:
    quantos = db.execute("SELECT count(*) FROM livros").fetchone()[0]
    return db.execute(
        "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
        " VALUES (%s, %s, %s, 10, 10) RETURNING id",
        (titulo, autor, f"{9780000000000 + quantos}"),
    ).fetchone()[0]


def semear_emprestimo(db, usuario_id, livro_id, emprestado_em, *, limite=None, devolvido_em=None):
    limite = emprestado_em + PRAZO if limite is None else limite
    return db.execute(
        "INSERT INTO emprestimos"
        " (usuario_id, livro_id, status, emprestado_em, data_limite_devolucao, devolvido_em)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (
            usuario_id,
            livro_id,
            "devolvido" if devolvido_em else "ativo",
            emprestado_em,
            limite,
            devolvido_em,
        ),
    ).fetchone()[0]


@pytest.fixture
def cenario(db, instante_base):
    """Usuários, livros e seis empréstimos com situações conhecidas no instante_base.

    Ordem esperada (emprestadoEm decrescente): ativo, dev_prazo, ativo2, atrasado2,
    atrasado, dev_vencido.
    """
    dia = timedelta(days=1)
    lucas = semear_usuario(db, "Lucas Joaquim", "12345678900")
    jose = semear_usuario(db, "José Antônio", "33344455566")
    ana = semear_usuario(db, "Ana_Maria Costa", "44455566677")
    leitor = semear_usuario(db, "Leitor Cem%", "55566677788")
    fundamentos = semear_livro(db, "Fundamentos de Sistemas de Informação", "Ana Silva")
    banco = semear_livro(db, "Banco de Dados", "Carlos Pereira")
    algebra = semear_livro(db, "Álgebra Linear", "Gilbert Strang")
    guia = semear_livro(db, "Guia_Rapido", "Pedro Lima")
    ids = {
        "ativo": semear_emprestimo(db, lucas, fundamentos, instante_base - dia),
        "atrasado": semear_emprestimo(db, jose, banco, instante_base - 20 * dia),
        "dev_vencido": semear_emprestimo(
            db, lucas, banco, instante_base - 40 * dia, devolvido_em=instante_base - 2 * dia
        ),
        "dev_prazo": semear_emprestimo(
            db, jose, algebra, instante_base - 3 * dia, devolvido_em=instante_base - dia
        ),
        "ativo2": semear_emprestimo(db, ana, guia, instante_base - 5 * dia),
        "atrasado2": semear_emprestimo(db, leitor, fundamentos, instante_base - 16 * dia),
    }
    ids.update(usuarios={"lucas": lucas, "jose": jose, "ana": ana, "leitor": leitor})
    ids.update(livros={"fundamentos": fundamentos, "banco": banco, "algebra": algebra})
    return ids


ORDEM = ["ativo", "dev_prazo", "ativo2", "atrasado2", "atrasado", "dev_vencido"]
SITUACAO = {
    "ativo": "ativo",
    "ativo2": "ativo",
    "atrasado": "atrasado",
    "atrasado2": "atrasado",
    "dev_vencido": "devolvido",
    "dev_prazo": "devolvido",
}


def consultar(client, **params):
    return client.get(ROTA, params=params)


def assert_ok(resposta) -> list[dict]:
    assert resposta.status_code == 200, resposta.text
    assert resposta.headers["content-type"].startswith("application/json")
    dados = resposta.json()
    assert set(dados) == {"emprestimos", "total"}
    assert type(dados["total"]) is int
    assert dados["total"] == len(dados["emprestimos"])
    return dados["emprestimos"]


def ids(emprestimos) -> list[int]:
    return [e["emprestimoId"] for e in emprestimos]


def esperados(cenario, chaves) -> list[int]:
    return [cenario[c] for c in ORDEM if c in chaves]


def iso(instante: datetime) -> str:
    return instante.strftime("%Y-%m-%dT%H:%M:%S")


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


# CT8 · Saída · `emprestimos` e `total`; EmprestimoResumo com exatamente 9 campos; formatos
def test_saida_com_campos_e_formatos(client, db, instante_base):
    usuario = semear_usuario(db, "Lucas Joaquim")
    livro = semear_livro(db, "Fundamentos de Sistemas de Informação")
    emprestado = instante_base - timedelta(days=1, hours=2, seconds=5)
    devolvido = instante_base - timedelta(hours=3)
    aberto = semear_emprestimo(db, usuario, livro, emprestado)
    fechado = semear_emprestimo(
        db, usuario, livro, emprestado - timedelta(days=1), devolvido_em=devolvido
    )

    emprestimos = assert_ok(consultar(client))

    assert len(emprestimos) == 2
    for emprestimo in emprestimos:
        assert set(emprestimo) == CAMPOS_EMPRESTIMO
        for campo in ("emprestimoId", "usuarioId", "livroId"):
            assert type(emprestimo[campo]) is int, campo
        for campo in ("emprestadoEm", "dataLimiteDevolucao"):
            assert FORMATO_DATA.match(emprestimo[campo]), emprestimo[campo]
    assert emprestimos == [
        {
            "emprestimoId": aberto,
            "usuarioId": usuario,
            "usuarioNome": "Lucas Joaquim",
            "livroId": livro,
            "livroTitulo": "Fundamentos de Sistemas de Informação",
            "status": "ativo",
            "emprestadoEm": iso(emprestado),
            "dataLimiteDevolucao": iso(emprestado + PRAZO),
            "devolvidoEm": None,
        },
        {
            "emprestimoId": fechado,
            "usuarioId": usuario,
            "usuarioNome": "Lucas Joaquim",
            "livroId": livro,
            "livroTitulo": "Fundamentos de Sistemas de Informação",
            "status": "devolvido",
            "emprestadoEm": iso(emprestado - timedelta(days=1)),
            "dataLimiteDevolucao": iso(emprestado - timedelta(days=1) + PRAZO),
            "devolvidoEm": iso(devolvido),
        },
    ]


# CT8 · banco vazio → lista vazia e total 0
def test_banco_vazio(client):
    assert client.get(ROTA).json() == {"emprestimos": [], "total": 0}


# --------------------------------------------------------------------------- situação e filtro


# CT8 · sem filtro: todos, com a situação efetiva calculada (atrasado não é gravado, D3)
def test_sem_filtro_traz_todos_com_situacao_efetiva(client, db, cenario):
    emprestimos = assert_ok(consultar(client))

    assert ids(emprestimos) == esperados(cenario, ORDEM)
    assert [e["status"] for e in emprestimos] == [SITUACAO[c] for c in ORDEM]
    gravados = {
        linha[0] for linha in db.execute("SELECT DISTINCT status FROM emprestimos").fetchall()
    }
    assert gravados == {"ativo", "devolvido"}


# CT8 · filtro status usa a situação efetiva; a resposta bate com o filtro
@pytest.mark.parametrize("status", SITUACOES)
def test_filtro_status(client, cenario, status):
    emprestimos = assert_ok(consultar(client, status=status))

    chaves = [c for c in ORDEM if SITUACAO[c] == status]
    assert ids(emprestimos) == esperados(cenario, chaves)
    assert all(e["status"] == status for e in emprestimos)


# CT8 · os três filtros particionam o resultado sem filtro
def test_filtros_particionam_o_total(client, cenario):
    todos = ids(assert_ok(consultar(client)))
    por_status = [ids(assert_ok(consultar(client, status=s))) for s in SITUACOES]

    assert sorted(sum(por_status, [])) == sorted(todos)
    assert len(set(sum(por_status, []))) == len(todos)


# §7 / CT8 · borda exata da data limite: no instante é `ativo`; 1 segundo depois, `atrasado`
def test_borda_exata_da_data_limite(client, db, relogio, instante_base):
    usuario = semear_usuario(db, "Lucas")
    emprestimo_id = semear_emprestimo(db, usuario, semear_livro(db, "Livro"), instante_base)

    def situacao():
        ativos = ids(assert_ok(consultar(client, status="ativo")))
        atrasados = ids(assert_ok(consultar(client, status="atrasado")))
        (unico,) = assert_ok(consultar(client))
        return ativos, atrasados, unico["status"]

    relogio.avancar(PRAZO - timedelta(seconds=1))
    assert situacao() == ([emprestimo_id], [], "ativo")
    relogio.avancar(timedelta(seconds=1))
    assert relogio.agora() == instante_base + PRAZO
    assert situacao() == ([emprestimo_id], [], "ativo")
    relogio.avancar(timedelta(seconds=1))
    assert situacao() == ([], [emprestimo_id], "atrasado")


# §7 · devolvido continua devolvido com o relógio muito à frente; nunca vira atrasado
def test_devolvido_nunca_vira_atrasado(client, cenario, relogio):
    relogio.avancar(timedelta(days=365))

    devolvidos = ids(assert_ok(consultar(client, status="devolvido")))
    atrasados = ids(assert_ok(consultar(client, status="atrasado")))

    assert devolvidos == esperados(cenario, ["dev_prazo", "dev_vencido"])
    assert atrasados == esperados(cenario, ["ativo", "ativo2", "atrasado2", "atrasado"])
    assert assert_ok(consultar(client, status="ativo")) == []


# CT8 · a situação usa a data limite gravada, não emprestadoEm + 15 recalculado
def test_situacao_usa_data_limite_gravada(client, db, instante_base):
    usuario = semear_usuario(db, "Lucas")
    curto = semear_emprestimo(
        db,
        usuario,
        semear_livro(db, "Livro"),
        instante_base - timedelta(days=1),
        limite=instante_base - timedelta(seconds=1),
    )

    assert ids(assert_ok(consultar(client, status="atrasado"))) == [curto]


# §6 (CT8 em detalhe) · status com brancos nas pontas é aceito
@pytest.mark.parametrize("valor", [" ativo ", "\tativo\n", "  ativo"])
def test_status_com_brancos_nas_pontas(client, cenario, valor):
    assert ids(assert_ok(consultar(client, status=valor))) == esperados(
        cenario, ["ativo", "ativo2"]
    )


# §6 · status vazio ou só brancos = sem filtro
@pytest.mark.parametrize("consulta", ["status=", "status=%20%20", "status=%09"])
def test_status_vazio_e_sem_filtro(client, cenario, consulta):
    assert ids(assert_ok(client.get(f"{ROTA}?{consulta}"))) == esperados(cenario, ORDEM)


# §6 · parâmetro repetido vale o primeiro
def test_status_repetido_vale_o_primeiro(client, cenario):
    resposta = client.get(f"{ROTA}?status=devolvido&status=xyz")

    assert ids(assert_ok(resposta)) == esperados(cenario, ["dev_prazo", "dev_vencido"])
    assert_erro(client.get(f"{ROTA}?status=xyz&status=ativo"), 400, "STATUS_INVALIDO")


# --------------------------------------------------------------------------- busca


# §6 (CT8 em detalhe) · busca no nome do usuário ou no título do livro
@pytest.mark.parametrize(
    ("busca", "chaves"),
    [
        ("lucas", ["ativo", "dev_vencido"]),
        ("JOAQUIM", ["ativo", "dev_vencido"]),
        ("jose", ["atrasado", "dev_prazo"]),
        ("ANTÔNIO", ["atrasado", "dev_prazo"]),
        ("sistemas", ["ativo", "atrasado2"]),
        ("informacao", ["ativo", "atrasado2"]),
        ("ALGEBRA", ["dev_prazo"]),
        ("álgebra", ["dev_prazo"]),
        ("dados", ["atrasado", "dev_vencido"]),
        ("stemas de inf", ["ativo", "atrasado2"]),
        ("costa", ["ativo2"]),
    ],
    ids=lambda valor: valor if isinstance(valor, str) else None,
)
def test_busca(client, cenario, busca, chaves):
    assert ids(assert_ok(consultar(client, busca=busca))) == esperados(cenario, chaves)


# §6 (CT8 em detalhe) · não procura no CPF nem no autor (nem no contato)
@pytest.mark.parametrize(
    "busca", ["12345678900", "123.456", "33344", "silva", "pereira", "strang", "email"]
)
def test_busca_nao_procura_em_cpf_autor_ou_contato(client, cenario, busca):
    assert assert_ok(consultar(client, busca=busca)) == []


# §6 · %, _ e \ são literais
@pytest.mark.parametrize(
    ("busca", "chaves"),
    [
        ("%", ["atrasado2"]),
        ("%%", []),
        ("_", ["ativo2"]),
        ("a_r", ["ativo2"]),
        ("o_r", []),
        ("\\", []),
        ("\\%", []),
    ],
    ids=["pct", "dois-pct", "sub", "a_r", "o_r", "barra", "barra-pct"],
)
def test_busca_com_literais(client, cenario, busca, chaves):
    assert ids(assert_ok(consultar(client, busca=busca))) == esperados(cenario, chaves)


# §6 · brancos nas pontas; vazia = sem filtro; `+` na URL é espaço; sem resultado
def test_busca_brancos_vazia_mais_e_sem_resultado(client, cenario):
    lucas = esperados(cenario, ["ativo", "dev_vencido"])
    assert ids(assert_ok(consultar(client, busca="\t lucas \n"))) == lucas
    assert ids(assert_ok(consultar(client, busca=" \t "))) == esperados(cenario, ORDEM)
    assert ids(assert_ok(client.get(f"{ROTA}?busca=lucas+joaquim"))) == lucas
    assert assert_ok(consultar(client, busca="inexistente")) == []


# §6 · busca com 100 caracteres aceita
def test_busca_com_100_caracteres_aceita(client, cenario):
    assert assert_ok(consultar(client, busca="a" * 100)) == []


# --------------------------------------------------------------------------- combinação


# CT8 · status + busca combinados
@pytest.mark.parametrize(
    ("status", "busca", "chaves"),
    [
        ("ativo", "lucas", ["ativo"]),
        ("devolvido", "lucas", ["dev_vencido"]),
        ("atrasado", "sistemas", ["atrasado2"]),
        ("atrasado", "lucas", []),
        ("devolvido", "dados", ["dev_vencido"]),
        ("ativo", "guia", ["ativo2"]),
    ],
)
def test_status_e_busca(client, cenario, status, busca, chaves):
    emprestimos = assert_ok(consultar(client, status=status, busca=busca))

    assert ids(emprestimos) == esperados(cenario, chaves)
    assert all(e["status"] == status for e in emprestimos)


# --------------------------------------------------------------------------- erros


# CT8 · Erros · status inválido (só minúsculas e exato, §6 CT8 em detalhe)
@pytest.mark.parametrize(
    "valor",
    ["ATIVO", "Ativo", "ativos", "pendente", "atrasada", "ativo,devolvido", "a tivo", "0"],
)
def test_status_invalido(client, cenario, valor):
    assert_erro(consultar(client, status=valor), 400, "STATUS_INVALIDO")


# §6 · NUL, metade de par substituto ou bytes não UTF-8 em status → STATUS_INVALIDO
@pytest.mark.parametrize("codificado", ["%00", "ativo%00", "%FF", "ativo%C3", "%ED%A0%80"])
def test_status_com_caractere_invalido(client, cenario, codificado):
    assert_erro(client.get(f"{ROTA}?status={codificado}"), 400, "STATUS_INVALIDO")


# CT8 · Erros · busca com mais de 100 caracteres
@pytest.mark.parametrize("busca", ["a" * 101, " " + "a" * 101 + "\t"])
def test_busca_com_101_caracteres(client, cenario, busca):
    assert_erro(consultar(client, busca=busca), 400, "BUSCA_INVALIDA")


# §6 · NUL ou UTF-8 inválido na busca → BUSCA_INVALIDA
@pytest.mark.parametrize("codificado", ["%00", "lucas%00", "%FF", "%ED%A0%80"])
def test_busca_com_caractere_invalido(client, cenario, codificado):
    assert_erro(client.get(f"{ROTA}?busca={codificado}"), 400, "BUSCA_INVALIDA")


# §6 (CT8 em detalhe) · ordem entre parâmetros: status, depois busca
@pytest.mark.parametrize(
    ("consulta", "codigo"),
    [
        ("status=ATIVO&busca=" + "a" * 101, "STATUS_INVALIDO"),
        ("busca=%00&status=xyz", "STATUS_INVALIDO"),
        ("status=ativo&busca=" + "a" * 101, "BUSCA_INVALIDA"),
        ("status=&busca=%00", "BUSCA_INVALIDA"),
    ],
    ids=["status-e-busca", "ordem-na-url-nao-importa", "so-busca", "status-vazio-e-busca"],
)
def test_ordem_entre_parametros(client, cenario, consulta, codigo):
    assert_erro(client.get(f"{ROTA}?{consulta}"), 400, codigo)


# --------------------------------------------------------------------------- ordem e tamanho


# CT8 · emprestadoEm decrescente; empate de data → id decrescente
def test_ordem_decrescente_com_empate(client, db, instante_base):
    usuario = semear_usuario(db, "Lucas")
    livro = semear_livro(db, "Livro")
    dia = timedelta(days=1)
    antigo = semear_emprestimo(db, usuario, livro, instante_base - 9 * dia)
    empate_a = semear_emprestimo(db, usuario, livro, instante_base - 2 * dia)
    recente = semear_emprestimo(db, usuario, livro, instante_base - timedelta(hours=1))
    empate_b = semear_emprestimo(db, usuario, livro, instante_base - 2 * dia)
    empate_c = semear_emprestimo(
        db, usuario, livro, instante_base - 2 * dia, devolvido_em=instante_base - dia
    )

    assert ids(assert_ok(consultar(client))) == [recente, empate_c, empate_b, empate_a, antigo]


# §6 · sem paginação: lista inteira; total = tamanho; pagina/tamanho são ignorados
@pytest.mark.parametrize("consulta", ["", "pagina=2&tamanho=5", "tamanho=0", "foo=bar"])
def test_sem_paginacao(client, db, instante_base, consulta):
    usuario = semear_usuario(db, "Lucas")
    livro = semear_livro(db, "Livro")
    criados = [
        semear_emprestimo(db, usuario, livro, instante_base - timedelta(hours=n)) for n in range(30)
    ]

    emprestimos = assert_ok(client.get(f"{ROTA}?{consulta}"))

    assert ids(emprestimos) == criados
    assert len(emprestimos) == 30


# --------------------------------------------------------------------------- rotas


# §3 · barra no fim
def test_barra_no_fim(client):
    assert_erro(client.get("/emprestimos/", follow_redirects=False), 404, "ROTA_NAO_ENCONTRADA")


# §3 · métodos não permitidos em /emprestimos
@pytest.mark.parametrize("metodo", ["PUT", "PATCH", "DELETE"])
def test_metodo_nao_permitido(client, metodo):
    assert_erro(client.request(metodo, ROTA), 405, "ROTA_NAO_ENCONTRADA")


# CT5 · regressão: POST /emprestimos continua funcionando e o novo aparece como ativo
def test_post_emprestimos_continua_funcionando(client, db, instante_base):
    usuario = semear_usuario(db, "Novo Leitor")
    livro = semear_livro(db, "Livro Novo")

    resposta = client.post(ROTA, json={"usuarioId": usuario, "livroId": livro})

    assert resposta.status_code == 201, resposta.text
    (emprestimo,) = assert_ok(consultar(client, status="ativo", busca="novo"))
    assert emprestimo["emprestimoId"] == resposta.json()["emprestimoId"]
    assert emprestimo["status"] == "ativo"
    assert emprestimo["emprestadoEm"] == iso(instante_base)
    assert emprestimo["usuarioNome"] == "Novo Leitor"
    assert emprestimo["livroTitulo"] == "Livro Novo"
