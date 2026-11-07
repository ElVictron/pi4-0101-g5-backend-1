"""E9 — registrarEmprestimo (card #793): `POST /emprestimos` + publicação no Backend 2.

Fontes: CT5 (inclusive "Ordem dos erros de negócio"), CT9, CT10, CT11; `00-convencoes.md`
§3, §4, §5, §7, §8 e §11; `agentes.md` D6, P10, P11, D16, D17 e §8B. O Backend 2 é o
falso do `conftest` (respx em `https://backend2.teste/eventos/biblioteca`). Dados de apoio
semeados por SQL direto, sem `id` explícito.
"""

import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient

ROTA = "/emprestimos"
PRAZO = timedelta(days=15)
CAMPOS_SAIDA = {
    "emprestimoId",
    "usuarioId",
    "livroId",
    "status",
    "emprestadoEm",
    "dataLimiteDevolucao",
    "devolvidoEm",
}
CAMPOS_EVENTO = {
    "tipo",
    "livroId",
    "usuarioId",
    "emprestimoId",
    "status",
    "quantidadeDisponivel",
    "atualizadaEm",
}
FORMATO_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
TRECHOS_PROIBIDOS = ("psycopg", "sqlstate", "traceback", "violates", "constraint", "key (")

# Dados pessoais que nunca podem aparecer em `ultimo_erro` (§8)
NOME_SIGILOSO = "Fulano Sigiloso"
CPF_SIGILOSO = "98765432100"
CONTATO_SIGILOSO = "fulano.sigiloso@email.com"


# --------------------------------------------------------------------------- apoio


def semear_usuario(db, nome=None, cpf=None, contato="leitor@email.com") -> int:
    quantos = db.execute("SELECT count(*) FROM usuarios").fetchone()[0]
    nome = f"Leitor {quantos:02d}" if nome is None else nome
    cpf = f"{70000000000 + quantos}" if cpf is None else cpf
    return db.execute(
        "INSERT INTO usuarios (nome, cpf, contato) VALUES (%s, %s, %s) RETURNING id",
        (nome, cpf, contato),
    ).fetchone()[0]


def semear_livro(db, exemplares=3, disponivel=None, titulo="Livro Semeado") -> int:
    disponivel = exemplares if disponivel is None else disponivel
    quantos = db.execute("SELECT count(*) FROM livros").fetchone()[0]
    return db.execute(
        "INSERT INTO livros (titulo, autor, isbn, quantidade_exemplares, quantidade_disponivel)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (titulo, "Autor", f"{9780000000000 + quantos}", exemplares, disponivel),
    ).fetchone()[0]


@pytest.fixture
def usuario(db) -> int:
    return semear_usuario(db, NOME_SIGILOSO, CPF_SIGILOSO, CONTATO_SIGILOSO)


@pytest.fixture
def livro(db) -> int:
    return semear_livro(db, exemplares=3)


def emprestar(cliente, usuario_id, livro_id):
    return cliente.post(ROTA, json={"usuarioId": usuario_id, "livroId": livro_id})


def iso(instante: datetime) -> str:
    return instante.strftime("%Y-%m-%dT%H:%M:%S")


def disponivel(db, livro_id) -> int:
    return db.execute(
        "SELECT quantidade_disponivel FROM livros WHERE id = %s", (livro_id,)
    ).fetchone()[0]


def emprestimos_no_banco(db):
    return db.execute(
        "SELECT id, usuario_id, livro_id, status, emprestado_em, data_limite_devolucao,"
        " devolvido_em FROM emprestimos ORDER BY id"
    ).fetchall()


def pendentes(db):
    return db.execute(
        "SELECT payload, tentativas, ultimo_erro, criado_em, atualizado_em"
        " FROM eventos_pendentes ORDER BY id"
    ).fetchall()


def rota(backend2):
    """A rota falsa `POST /eventos/biblioteca` (para trocar a resposta)."""
    return backend2.routes["eventos"]


def chamadas(backend2):
    """Chamadas recebidas pela rota (somente leitura: não configure a resposta por aqui)."""
    return backend2.routes["eventos"].calls


def corpo_enviado(chamada) -> dict:
    return json.loads(chamada.request.content)


def evento_esperado(usuario_id, livro_id, emprestimo_id, quantidade, instante) -> dict:
    return {
        "tipo": "emprestimo_registrado",
        "livroId": livro_id,
        "usuarioId": usuario_id,
        "emprestimoId": emprestimo_id,
        "status": "ativo",
        "quantidadeDisponivel": quantidade,
        "atualizadaEm": iso(instante),
    }


def assert_criado(resposta) -> dict:
    assert resposta.status_code == 201, resposta.text
    assert resposta.headers["content-type"].startswith("application/json")
    return resposta.json()


def assert_erro(resposta, status: int, codigo: str) -> None:
    """00-convencoes §3 · formato do corpo de erro, sem texto interno (D16 d)."""
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
def nada_muda(db, backend2):
    """Para testes de erro: nada gravado, estoque igual e nenhuma chamada ao Backend 2."""
    antes = (
        db.execute("SELECT * FROM livros ORDER BY id").fetchall(),
        emprestimos_no_banco(db),
        pendentes(db),
    )
    yield
    depois = (
        db.execute("SELECT * FROM livros ORDER BY id").fetchall(),
        emprestimos_no_banco(db),
        pendentes(db),
    )
    assert depois == antes
    assert backend2.calls.call_count == 0


# --------------------------------------------------------------------------- sucesso


# CT5 · Saída · 201 com exatamente os campos do CT5; datas do relógio; +15 dias
def test_registra_emprestimo_com_sucesso(client, db, usuario, livro, instante_base):
    dados = assert_criado(emprestar(client, usuario, livro))

    assert set(dados) == CAMPOS_SAIDA
    for campo in ("emprestimoId", "usuarioId", "livroId"):
        assert type(dados[campo]) is int, campo
    assert dados == {
        "emprestimoId": dados["emprestimoId"],
        "usuarioId": usuario,
        "livroId": livro,
        "status": "ativo",
        "emprestadoEm": iso(instante_base),
        "dataLimiteDevolucao": iso(instante_base + PRAZO),
        "devolvidoEm": None,
    }
    assert FORMATO_DATA.match(dados["emprestadoEm"])


# CT5 · Efeitos · empréstimo gravado e quantidade disponível −1 (exemplares não mudam)
def test_efeitos_no_banco(client, db, usuario, livro, instante_base):
    dados = assert_criado(emprestar(client, usuario, livro))

    assert emprestimos_no_banco(db) == [
        (
            dados["emprestimoId"],
            usuario,
            livro,
            "ativo",
            instante_base,
            instante_base + PRAZO,
            None,
        )
    ]
    assert db.execute(
        "SELECT quantidade_exemplares, quantidade_disponivel FROM livros WHERE id = %s",
        (livro,),
    ).fetchone() == (3, 2)


# D16(f) / §7 · emprestadoEm vem do relógio injetado; limite no mesmo horário +15 dias
def test_datas_vem_do_relogio(client, db, relogio, usuario, livro, instante_base):
    relogio.avancar(timedelta(days=50, hours=5, minutes=7, seconds=3))
    agora = instante_base + timedelta(days=50, hours=5, minutes=7, seconds=3)

    dados = assert_criado(emprestar(client, usuario, livro))

    assert dados["emprestadoEm"] == iso(agora)
    assert dados["dataLimiteDevolucao"] == iso(agora + PRAZO)
    assert emprestimos_no_banco(db)[0][4:6] == (agora, agora + PRAZO)


# CT5 · empréstimos seguidos do mesmo livro baixam o estoque um a um
def test_emprestimos_seguidos_baixam_um_a_um(client, db, livro):
    for esperado in (2, 1, 0):
        assert_criado(emprestar(client, semear_usuario(db), livro))
        assert disponivel(db, livro) == esperado


# --------------------------------------------------------------------------- publicação


# §8 / D6 · uma única chamada, corpo exato do CT12, Content-Type JSON; sem pendente
def test_publica_evento_emprestimo_registrado(client, db, backend2, usuario, livro, instante_base):
    dados = assert_criado(emprestar(client, usuario, livro))

    assert chamadas(backend2).call_count == 1
    requisicao = chamadas(backend2).last.request
    assert requisicao.method == "POST"
    assert requisicao.url.path == "/eventos/biblioteca"
    assert requisicao.headers["content-type"].startswith("application/json")
    corpo = corpo_enviado(chamadas(backend2).last)
    assert set(corpo) == CAMPOS_EVENTO
    assert corpo == evento_esperado(usuario, livro, dados["emprestimoId"], 2, instante_base)
    for campo in ("livroId", "usuarioId", "emprestimoId", "quantidadeDisponivel"):
        assert type(corpo[campo]) is int, campo
    assert pendentes(db) == []


# §8 · a publicação acontece DEPOIS de o empréstimo estar gravado (visível a outra conexão)
def test_publica_so_depois_de_gravar(client, db, backend2, database_url, usuario, livro):
    vistos = []

    def conferir_banco(requisicao):
        corpo = json.loads(requisicao.content)
        with psycopg.connect(database_url, autocommit=True) as outra:
            vistos.append(
                (
                    outra.execute(
                        "SELECT count(*) FROM emprestimos WHERE id = %s",
                        (corpo["emprestimoId"],),
                    ).fetchone()[0],
                    outra.execute(
                        "SELECT quantidade_disponivel FROM livros WHERE id = %s",
                        (corpo["livroId"],),
                    ).fetchone()[0],
                )
            )
        return httpx.Response(200, json={"aceito": True, "eventoId": "evt_teste"})

    rota(backend2).mock(side_effect=conferir_banco)

    assert_criado(emprestar(client, usuario, livro))

    assert vistos == [(1, 2)]
    assert pendentes(db) == []


# §8 · aceito true com outro status 2xx também é sucesso
def test_resposta_202_aceita_e_sucesso(client, db, backend2, usuario, livro):
    rota(backend2).respond(202, json={"aceito": True, "eventoId": "evt_x"})

    assert_criado(emprestar(client, usuario, livro))

    assert chamadas(backend2).call_count == 1
    assert pendentes(db) == []


# §8 · BACKEND2_URL com barra final: a barra é removida (sem //)
def test_backend2_url_com_barra_final(criar_app, db, backend2, usuario, livro):
    with TestClient(criar_app(backend2_url="https://backend2.teste/")) as cliente:
        assert_criado(emprestar(cliente, usuario, livro))

    assert chamadas(backend2).call_count == 1
    assert chamadas(backend2).last.request.url.path == "/eventos/biblioteca"
    assert "//eventos" not in str(chamadas(backend2).last.request.url)
    assert pendentes(db) == []


# --------------------------------------------------------------------------- falhas do Backend 2

FALHAS = {
    "http-503": lambda rota: rota.respond(503),
    "http-500": lambda rota: rota.respond(500, json={"erro": "x"}),
    "http-404": lambda rota: rota.respond(404),
    "http-400-aceito": lambda rota: rota.respond(400, json={"aceito": True, "eventoId": "x"}),
    "aceito-false": lambda rota: rota.respond(200, json={"aceito": False, "eventoId": "x"}),
    "aceito-texto": lambda rota: rota.respond(200, json={"aceito": "true", "eventoId": "x"}),
    "aceito-um": lambda rota: rota.respond(200, json={"aceito": 1, "eventoId": "x"}),
    "nao-json": lambda rota: rota.respond(200, text="ok"),
    "sem-aceito": lambda rota: rota.respond(200, json={"eventoId": "x"}),
    "json-lista": lambda rota: rota.respond(200, json=[{"aceito": True}]),
    "connect-error": lambda rota: rota.mock(side_effect=httpx.ConnectError("recusada")),
    "read-timeout": lambda rota: rota.mock(side_effect=httpx.ReadTimeout("lento")),
    "connect-timeout": lambda rota: rota.mock(side_effect=httpx.ConnectTimeout("lento")),
}


def assert_pendente_unico(db, payload, instante):
    """§8 · uma linha em eventos_pendentes, com payload, tentativas 1, erro e datas certas."""
    linhas = pendentes(db)
    assert len(linhas) == 1
    payload_gravado, tentativas, ultimo_erro, criado_em, atualizado_em = linhas[0]
    assert payload_gravado == payload
    assert tentativas == 1
    assert isinstance(ultimo_erro, str)
    assert ultimo_erro.strip()
    for dado_pessoal in (NOME_SIGILOSO, CPF_SIGILOSO, CONTATO_SIGILOSO, "Sigiloso"):
        assert dado_pessoal.lower() not in ultimo_erro.lower(), ultimo_erro
    # §8 · texto curto (no máximo 200 caracteres) e sem o payload
    assert len(ultimo_erro) <= 200, ultimo_erro
    assert json.dumps(payload) not in ultimo_erro
    assert json.dumps(payload, separators=(",", ":")) not in ultimo_erro
    for trecho in ("emprestimoId", "emprestimo_registrado", "quantidadeDisponivel", "atualizadaEm"):
        assert trecho not in ultimo_erro, ultimo_erro
    assert (criado_em, atualizado_em) == (instante, instante)


# D6 / §8 · falha do Backend 2: 201 ao cliente, dado gravado, uma tentativa, evento pendente
@pytest.mark.parametrize("falha", list(FALHAS))
def test_falha_do_backend2_guarda_evento_pendente(
    client, db, backend2, relogio, usuario, livro, falha
):
    relogio.avancar(timedelta(hours=1))
    agora = relogio.agora()
    FALHAS[falha](rota(backend2))

    dados = assert_criado(emprestar(client, usuario, livro))

    assert dados["status"] == "ativo"
    assert len(emprestimos_no_banco(db)) == 1
    assert disponivel(db, livro) == 2
    assert chamadas(backend2).call_count == 1
    enviado = corpo_enviado(chamadas(backend2).last)
    assert enviado == evento_esperado(usuario, livro, dados["emprestimoId"], 2, agora)
    assert_pendente_unico(db, enviado, agora)


# §8 · BACKEND2_URL não configurado: toda publicação é falha (sem chamada), evento pendente
def test_sem_backend2_url_guarda_evento_pendente(
    criar_app, db, backend2, relogio, usuario, livro, instante_base
):
    with TestClient(criar_app(backend2_url=None)) as cliente:
        dados = assert_criado(emprestar(cliente, usuario, livro))

    assert backend2.calls.call_count == 0
    assert len(emprestimos_no_banco(db)) == 1
    assert disponivel(db, livro) == 2
    esperado = evento_esperado(usuario, livro, dados["emprestimoId"], 2, instante_base)
    assert_pendente_unico(db, esperado, instante_base)


# §8 · uma única tentativa por operação, mesmo quando a primeira falha
def test_nao_ha_nova_tentativa_na_requisicao(client, db, backend2, usuario, livro):
    respostas = iter([httpx.Response(503), httpx.Response(200, json={"aceito": True})])
    rota(backend2).mock(side_effect=lambda requisicao: next(respostas))

    assert_criado(emprestar(client, usuario, livro))

    assert chamadas(backend2).call_count == 1
    assert len(pendentes(db)) == 1


# §8 · se gravar o evento pendente também falhar: 201 mesmo assim, e o log não tem dados
# pessoais. A falha é provocada por um gatilho que recusa todo INSERT em eventos_pendentes.
TEXTO_DO_GATILHO = "recusado no teste"


@pytest.fixture
def pendente_recusado(db):
    """Gatilho BEFORE INSERT que recusa gravar em eventos_pendentes; removido ao fim."""
    db.execute(
        "CREATE FUNCTION teste_recusar_pendente() RETURNS trigger LANGUAGE plpgsql AS"
        f" $$ BEGIN RAISE EXCEPTION '{TEXTO_DO_GATILHO}'; END $$"
    )
    try:
        db.execute(
            "CREATE TRIGGER teste_recusar_pendente BEFORE INSERT ON eventos_pendentes"
            " FOR EACH ROW EXECUTE FUNCTION teste_recusar_pendente()"
        )
        yield
    finally:
        db.execute("DROP TRIGGER IF EXISTS teste_recusar_pendente ON eventos_pendentes")
        db.execute("DROP FUNCTION IF EXISTS teste_recusar_pendente()")


def test_falha_ao_gravar_pendente_nao_falha_a_operacao(
    client, db, backend2, caplog, usuario, livro, pendente_recusado
):
    caplog.set_level(logging.DEBUG)
    rota(backend2).respond(503)

    dados = assert_criado(emprestar(client, usuario, livro))

    assert dados["status"] == "ativo"
    assert [linha[0] for linha in emprestimos_no_banco(db)] == [dados["emprestimoId"]]
    assert disponivel(db, livro) == 2
    assert chamadas(backend2).call_count == 1
    assert pendentes(db) == []
    # §8 · a falha vai para o log (garante também que o caplog capturou algo)
    assert any(registro.levelno >= logging.WARNING for registro in caplog.records)
    textos = [caplog.text] + [registro.getMessage() for registro in caplog.records]
    for texto in textos:
        for proibido in (NOME_SIGILOSO, CPF_SIGILOSO, CONTATO_SIGILOSO, TEXTO_DO_GATILHO):
            assert proibido.lower() not in texto.lower(), texto


# §8 · o gatilho do teste anterior foi removido: gravar pendente volta a funcionar
def test_gatilho_do_teste_foi_removido(client, db, backend2, usuario, livro):
    gatilhos = db.execute(
        "SELECT count(*) FROM pg_trigger WHERE tgname = 'teste_recusar_pendente'"
    ).fetchone()[0]
    assert gatilhos == 0
    rota(backend2).respond(503)

    assert_criado(emprestar(client, usuario, livro))

    assert len(pendentes(db)) == 1


# --------------------------------------------------------------------------- CAMPOS_OBRIGATORIOS


# CT5 · Erros · campo obrigatório ausente, nulo ou texto vazio (§4 item 2)
@pytest.mark.parametrize(
    "alteracao",
    [
        {"usuarioId": ...},
        {"livroId": ...},
        {"usuarioId": None},
        {"livroId": None},
        {"usuarioId": ""},
        {"livroId": "   "},
        {"usuarioId": ..., "livroId": ...},
    ],
    ids=[
        "sem-usuario",
        "sem-livro",
        "usuario-nulo",
        "livro-nulo",
        "usuario-vazio",
        "livro-brancos",
        "objeto-vazio",
    ],
)
def test_campos_obrigatorios(client, usuario, livro, nada_muda, alteracao):
    corpo = {"usuarioId": usuario, "livroId": livro}
    for campo, valor in alteracao.items():
        if valor is ...:
            corpo.pop(campo)
        else:
            corpo[campo] = valor

    assert_erro(client.post(ROTA, json=corpo), 400, "CAMPOS_OBRIGATORIOS")


# --------------------------------------------------------------------------- DADOS_INVALIDOS


# CT5 · Erros · usuarioId/livroId não é inteiro maior que zero; §4 · máximo 2147483647
@pytest.mark.parametrize(
    "valor",
    [0, -1, "1", 1.5, 1.0, True, False, 2147483648, [1], {"id": 1}],
    ids=[
        "zero",
        "negativo",
        "texto",
        "decimal",
        "decimal-inteiro",
        "true",
        "false",
        "acima-do-maximo",
        "lista",
        "objeto",
    ],
)
@pytest.mark.parametrize("campo", ["usuarioId", "livroId"])
def test_identificador_invalido(client, usuario, livro, nada_muda, campo, valor):
    corpo = {"usuarioId": usuario, "livroId": livro, campo: valor}

    assert_erro(client.post(ROTA, json=corpo), 400, "DADOS_INVALIDOS")


# §4 item 1 · corpo inválido (casos representativos; o E4 cobre todos)
@pytest.mark.parametrize(
    ("bruto", "tipo"),
    [
        (b"", "application/json"),
        (b"[1, 2]", "application/json"),
        (b'{"usuarioId": 1,', "application/json"),
        (b'{"usuarioId": 1, "livroId": 1}', "text/plain"),
        ('{"usuarioId": 1, "livroId": 1}'.encode("utf-16"), "application/json"),
        (rb'{"usuarioId": 1, "livroId": 1, "x\u0000": 1}', "application/json"),
    ],
    ids=["vazio", "lista", "quebrado", "text-plain", "utf-16", "nul"],
)
def test_corpo_invalido(client, usuario, livro, nada_muda, bruto, tipo):
    resposta = client.post(ROTA, content=bruto, headers={"Content-Type": tipo})

    assert_erro(resposta, 400, "DADOS_INVALIDOS")


# --------------------------------------------------------------------------- erros de negócio


# CT5 · Erros · usuário não existe (inclusive id válido no limite)
@pytest.mark.parametrize("inexistente", [999_999, 2147483647])
def test_usuario_nao_encontrado(client, livro, nada_muda, inexistente):
    assert_erro(emprestar(client, inexistente, livro), 404, "USUARIO_NAO_ENCONTRADO")


# CT5 · Erros · livro não existe
@pytest.mark.parametrize("inexistente", [999_999, 2147483647])
def test_livro_nao_encontrado(client, usuario, nada_muda, inexistente):
    assert_erro(emprestar(client, usuario, inexistente), 404, "LIVRO_NAO_ENCONTRADO")


# CT5 · Erros · livro sem exemplar disponível
def test_livro_indisponivel(client, db, usuario, backend2):
    livro_id = semear_livro(db, exemplares=2, disponivel=0)
    antes = db.execute("SELECT * FROM livros").fetchall()

    assert_erro(emprestar(client, usuario, livro_id), 409, "LIVRO_INDISPONIVEL")

    assert db.execute("SELECT * FROM livros").fetchall() == antes
    assert emprestimos_no_banco(db) == []
    assert pendentes(db) == []
    assert backend2.calls.call_count == 0


# CT5 · Ordem dos erros de negócio: usuário, depois livro, depois disponibilidade
def test_ordem_usuario_antes_de_livro(client, nada_muda):
    assert_erro(emprestar(client, 999_998, 999_999), 404, "USUARIO_NAO_ENCONTRADO")


def test_ordem_usuario_antes_de_indisponivel(client, db, backend2):
    livro_id = semear_livro(db, exemplares=1, disponivel=0)

    assert_erro(emprestar(client, 999_999, livro_id), 404, "USUARIO_NAO_ENCONTRADO")
    assert backend2.calls.call_count == 0


def test_ordem_livro_inexistente_com_usuario_ok(client, usuario, nada_muda):
    assert_erro(emprestar(client, usuario, 999_999), 404, "LIVRO_NAO_ENCONTRADO")


# §4 · validação de entrada antes das regras de negócio; ordem usuarioId, livroId
@pytest.mark.parametrize(
    ("corpo", "codigo"),
    [
        ({"usuarioId": 0, "livroId": 999_999}, "DADOS_INVALIDOS"),
        ({"usuarioId": 999_999, "livroId": "x"}, "DADOS_INVALIDOS"),
        ({"usuarioId": 0, "livroId": None}, "CAMPOS_OBRIGATORIOS"),
        ({"usuarioId": True}, "CAMPOS_OBRIGATORIOS"),
        ({"usuarioId": None, "livroId": 0}, "CAMPOS_OBRIGATORIOS"),
        ({"usuarioId": -5, "livroId": 1.5}, "DADOS_INVALIDOS"),
    ],
    ids=[
        "dados-antes-de-negocio",
        "livro-tipo-com-usuario-inexistente",
        "nulo-vence-invalido-anterior",
        "ausente-vence-bool",
        "nulo-e-zero",
        "dois-invalidos",
    ],
)
def test_ordem_do_paragrafo_4(client, nada_muda, corpo, codigo):
    assert_erro(client.post(ROTA, json=corpo), 400, codigo)


# --------------------------------------------------------------------------- último exemplar


# CT5 / P11 · com disponível 1, um empréstimo passa e o seguinte dá LIVRO_INDISPONIVEL
def test_ultimo_exemplar_sequencial(client, db, backend2):
    livro_id = semear_livro(db, exemplares=2, disponivel=1)

    assert_criado(emprestar(client, semear_usuario(db), livro_id))
    assert_erro(emprestar(client, semear_usuario(db), livro_id), 409, "LIVRO_INDISPONIVEL")

    assert disponivel(db, livro_id) == 0
    assert len(emprestimos_no_banco(db)) == 1
    assert chamadas(backend2).call_count == 1
    assert corpo_enviado(chamadas(backend2).last)["quantidadeDisponivel"] == 0


def corrida(client, usuarios, livro_id):
    """Dispara um POST por usuário, todos liberados juntos por uma barreira."""
    barreira = threading.Barrier(len(usuarios), timeout=10)

    def pedir(usuario_id):
        barreira.wait()
        return emprestar(client, usuario_id, livro_id)

    with ThreadPoolExecutor(max_workers=len(usuarios)) as executor:
        futuros = [executor.submit(pedir, u) for u in usuarios]
        return [f.result(timeout=30) for f in futuros]


# P11 · concorrência forçada: disponível 1, 5 pedidos simultâneos → 1 × 201 e 4 × 409
@pytest.mark.parametrize("rodada", range(3))
def test_concorrencia_ultimo_exemplar(client, db, backend2, rodada):
    livro_id = semear_livro(db, exemplares=4, disponivel=1)
    usuarios = [semear_usuario(db) for _ in range(5)]

    respostas = corrida(client, usuarios, livro_id)

    assert sorted(r.status_code for r in respostas) == [201, 409, 409, 409, 409], [
        r.text for r in respostas
    ]
    for resposta in respostas:
        if resposta.status_code == 409:
            assert_erro(resposta, 409, "LIVRO_INDISPONIVEL")
    assert disponivel(db, livro_id) == 0
    assert len(emprestimos_no_banco(db)) == 1
    assert chamadas(backend2).call_count == 1
    assert corpo_enviado(chamadas(backend2).last)["quantidadeDisponivel"] == 0
    assert pendentes(db) == []


# P11 · concorrência forçada: disponível 3, 5 pedidos simultâneos → 3 × 201 e 2 × 409
@pytest.mark.parametrize("rodada", range(3))
def test_concorrencia_tres_exemplares(client, db, backend2, rodada):
    livro_id = semear_livro(db, exemplares=3, disponivel=3)
    usuarios = [semear_usuario(db) for _ in range(5)]

    respostas = corrida(client, usuarios, livro_id)

    assert sorted(r.status_code for r in respostas) == [201, 201, 201, 409, 409], [
        r.text for r in respostas
    ]
    assert disponivel(db, livro_id) == 0
    gravados = emprestimos_no_banco(db)
    assert len(gravados) == 3
    vencedores = {r.json()["usuarioId"] for r in respostas if r.status_code == 201}
    assert {linha[1] for linha in gravados} == vencedores
    assert chamadas(backend2).call_count == 3
    quantidades = sorted(corpo_enviado(c)["quantidadeDisponivel"] for c in chamadas(backend2))
    assert quantidades == [0, 1, 2]


# --------------------------------------------------------------------------- rotas


# §3 · barra no fim
def test_barra_no_fim(client, usuario, livro, nada_muda):
    resposta = client.post(
        "/emprestimos/", json={"usuarioId": usuario, "livroId": livro}, follow_redirects=False
    )

    assert_erro(resposta, 404, "ROTA_NAO_ENCONTRADA")
