"""E11 — registrarDevolucao (card #798): `PATCH /emprestimos/{emprestimoId}/devolucao`.

Fontes: CT6 (inclusive "Detalhes"), CT9, CT11; `00-convencoes.md` §3, §7, §8 e §11;
`agentes.md` D3, D4, D6, P10, D16 e D17. O Backend 2 é o falso do `conftest` (respx).
Dados semeados por SQL direto, sem `id` explícito, com datas relativas ao `instante_base`.
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

PRAZO = timedelta(days=15)
CAMPOS_SAIDA = {"emprestimoId", "livroId", "status", "devolvidoEm", "quantidadeDisponivel"}
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
NOME_SIGILOSO = "Fulano Sigiloso"
CPF_SIGILOSO = "98765432100"
CONTATO_SIGILOSO = "fulano.sigiloso@email.com"
TEXTO_DO_GATILHO = "recusado no teste"


# --------------------------------------------------------------------------- apoio


def caminho(emprestimo_id) -> str:
    return f"/emprestimos/{emprestimo_id}/devolucao"


def devolver(cliente, emprestimo_id, **kwargs):
    return cliente.patch(caminho(emprestimo_id), **kwargs)


def iso(instante: datetime) -> str:
    return instante.strftime("%Y-%m-%dT%H:%M:%S")


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


def semear_emprestimo(db, usuario_id, livro_id, emprestado_em, *, devolvido_em=None) -> int:
    return db.execute(
        "INSERT INTO emprestimos"
        " (usuario_id, livro_id, status, emprestado_em, data_limite_devolucao, devolvido_em)"
        " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (
            usuario_id,
            livro_id,
            "devolvido" if devolvido_em else "ativo",
            emprestado_em,
            emprestado_em + PRAZO,
            devolvido_em,
        ),
    ).fetchone()[0]


@pytest.fixture
def usuario(db) -> int:
    return semear_usuario(db, NOME_SIGILOSO, CPF_SIGILOSO, CONTATO_SIGILOSO)


@pytest.fixture
def livro(db) -> int:
    """3 exemplares, 1 emprestado (disponível 2)."""
    return semear_livro(db, exemplares=3, disponivel=2)


@pytest.fixture
def emprestimo(db, usuario, livro, instante_base) -> int:
    """Empréstimo ativo e no prazo."""
    return semear_emprestimo(db, usuario, livro, instante_base - timedelta(days=2))


def disponivel(db, livro_id) -> int:
    return db.execute(
        "SELECT quantidade_disponivel FROM livros WHERE id = %s", (livro_id,)
    ).fetchone()[0]


def linha_emprestimo(db, emprestimo_id):
    return db.execute(
        "SELECT status, devolvido_em FROM emprestimos WHERE id = %s", (emprestimo_id,)
    ).fetchone()


def pendentes(db):
    return db.execute(
        "SELECT payload, tentativas, ultimo_erro, criado_em, atualizado_em"
        " FROM eventos_pendentes ORDER BY id"
    ).fetchall()


def rota(backend2):
    """A rota falsa `POST /eventos/biblioteca` (para trocar a resposta)."""
    return backend2.routes["eventos"]


def chamadas(backend2):
    """Chamadas recebidas (somente leitura)."""
    return backend2.routes["eventos"].calls


def corpo_enviado(chamada) -> dict:
    return json.loads(chamada.request.content)


def evento_esperado(usuario_id, livro_id, emprestimo_id, quantidade, instante) -> dict:
    return {
        "tipo": "devolucao_registrada",
        "livroId": livro_id,
        "usuarioId": usuario_id,
        "emprestimoId": emprestimo_id,
        "status": "devolvido",
        "quantidadeDisponivel": quantidade,
        "atualizadaEm": iso(instante),
    }


def assert_ok(resposta) -> dict:
    assert resposta.status_code == 200, resposta.text
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


def estado(db):
    return (
        db.execute("SELECT * FROM livros ORDER BY id").fetchall(),
        db.execute("SELECT * FROM emprestimos ORDER BY id").fetchall(),
        pendentes(db),
    )


@pytest.fixture
def nada_muda(db, backend2):
    """Para testes de erro: banco igual e nenhuma chamada ao Backend 2 (CT6: erros não publicam)."""
    antes = estado(db)
    yield
    assert estado(db) == antes
    assert backend2.calls.call_count == 0


# --------------------------------------------------------------------------- sucesso


# CT6 · Saída · 200 com exatamente os campos do CT6; devolvidoEm = relógio; quantidade após alta
def test_devolve_emprestimo_ativo(client, db, emprestimo, livro, instante_base):
    dados = assert_ok(devolver(client, emprestimo))

    assert set(dados) == CAMPOS_SAIDA
    for campo in ("emprestimoId", "livroId", "quantidadeDisponivel"):
        assert type(dados[campo]) is int, campo
    assert dados == {
        "emprestimoId": emprestimo,
        "livroId": livro,
        "status": "devolvido",
        "devolvidoEm": iso(instante_base),
        "quantidadeDisponivel": 3,
    }
    assert FORMATO_DATA.match(dados["devolvidoEm"])


# CT6 / CT11 · efeitos no banco: status devolvido, devolvido_em = relógio, disponível +1
def test_efeitos_no_banco(client, db, emprestimo, livro, instante_base):
    assert_ok(devolver(client, emprestimo))

    assert linha_emprestimo(db, emprestimo) == ("devolvido", instante_base)
    assert db.execute(
        "SELECT quantidade_exemplares, quantidade_disponivel FROM livros WHERE id = %s",
        (livro,),
    ).fetchone() == (3, 3)


# D4 / CT6 · devolução de empréstimo efetivamente atrasado (ativo gravado, prazo vencido)
def test_devolve_emprestimo_atrasado(client, db, usuario, livro, instante_base):
    atrasado = semear_emprestimo(db, usuario, livro, instante_base - timedelta(days=40))

    dados = assert_ok(devolver(client, atrasado))

    assert dados["status"] == "devolvido"
    assert dados["devolvidoEm"] == iso(instante_base)
    assert linha_emprestimo(db, atrasado) == ("devolvido", instante_base)
    assert disponivel(db, livro) == 3


# CT6 Detalhes · devolvidoEm vem do relógio injetado (D16 f)
def test_devolvido_em_vem_do_relogio(client, db, relogio, emprestimo, instante_base):
    relogio.avancar(timedelta(days=3, hours=4, seconds=9))
    agora = instante_base + timedelta(days=3, hours=4, seconds=9)

    assert assert_ok(devolver(client, emprestimo))["devolvidoEm"] == iso(agora)
    assert linha_emprestimo(db, emprestimo) == ("devolvido", agora)


# CT6 Detalhes · id só do caminho; corpo de qualquer tipo é ignorado
@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"json": {}},
        {"json": {"emprestimoId": 999_999, "status": "ativo", "quantidadeDisponivel": 50}},
        {"json": [1, 2, 3]},
        {"content": b"lixo qualquer", "headers": {"Content-Type": "text/plain"}},
        {"content": b'{"quebrado":', "headers": {"Content-Type": "application/json"}},
        {"content": b"\xff\xfe\x00", "headers": {"Content-Type": "application/octet-stream"}},
    ],
    ids=[
        "sem-corpo",
        "objeto-vazio",
        "campos-falsos",
        "lista",
        "texto",
        "json-quebrado",
        "binario",
    ],
)
def test_corpo_e_ignorado(client, db, emprestimo, livro, kwargs):
    dados = assert_ok(devolver(client, emprestimo, **kwargs))

    assert dados["emprestimoId"] == emprestimo
    assert dados["quantidadeDisponivel"] == 3
    assert linha_emprestimo(db, emprestimo)[0] == "devolvido"


# CT6 Detalhes · id com zeros à esquerda ainda está no formato [0-9]+
def test_id_com_zeros_a_esquerda(client, db, emprestimo):
    assert assert_ok(devolver(client, f"000{emprestimo}"))["emprestimoId"] == emprestimo


# CT6 · devolução de um empréstimo não mexe nos outros
def test_devolucao_nao_mexe_em_outros(client, db, usuario, livro, instante_base):
    alvo = semear_emprestimo(db, usuario, livro, instante_base - timedelta(days=1))
    outro = semear_emprestimo(db, semear_usuario(db), livro, instante_base - timedelta(days=1))
    db.execute("UPDATE livros SET quantidade_disponivel = 1 WHERE id = %s", (livro,))

    assert assert_ok(devolver(client, alvo))["quantidadeDisponivel"] == 2

    assert linha_emprestimo(db, outro) == ("ativo", None)


# --------------------------------------------------------------------------- publicação


# CT6 Detalhes / §8 · uma chamada com o corpo exato do CT12; sem pendente
def test_publica_devolucao_registrada(client, db, backend2, usuario, livro, emprestimo):
    dados = assert_ok(devolver(client, emprestimo))

    assert chamadas(backend2).call_count == 1
    requisicao = chamadas(backend2).last.request
    assert requisicao.method == "POST"
    assert requisicao.url.path == "/eventos/biblioteca"
    assert requisicao.headers["content-type"].startswith("application/json")
    corpo = corpo_enviado(chamadas(backend2).last)
    assert set(corpo) == CAMPOS_EVENTO
    assert corpo == {
        "tipo": "devolucao_registrada",
        "livroId": livro,
        "usuarioId": usuario,
        "emprestimoId": emprestimo,
        "status": "devolvido",
        "quantidadeDisponivel": 3,
        "atualizadaEm": dados["devolvidoEm"],
    }
    assert pendentes(db) == []


# §8 · a publicação sai só depois de a devolução estar gravada (visível a outra conexão)
def test_publica_so_depois_de_gravar(client, db, backend2, database_url, emprestimo, livro):
    vistos = []

    def conferir_banco(requisicao):
        corpo = json.loads(requisicao.content)
        with psycopg.connect(database_url, autocommit=True) as outra:
            vistos.append(
                (
                    outra.execute(
                        "SELECT status FROM emprestimos WHERE id = %s", (corpo["emprestimoId"],)
                    ).fetchone()[0],
                    outra.execute(
                        "SELECT quantidade_disponivel FROM livros WHERE id = %s",
                        (corpo["livroId"],),
                    ).fetchone()[0],
                )
            )
        return httpx.Response(200, json={"aceito": True, "eventoId": "evt"})

    rota(backend2).mock(side_effect=conferir_banco)

    assert_ok(devolver(client, emprestimo))

    assert vistos == [("devolvido", 3)]


FALHAS = {
    "http-503": lambda r: r.respond(503),
    "aceito-false": lambda r: r.respond(200, json={"aceito": False}),
    "nao-json": lambda r: r.respond(200, text="ok"),
    "connect-error": lambda r: r.mock(side_effect=httpx.ConnectError("recusada")),
    "read-timeout": lambda r: r.mock(side_effect=httpx.ReadTimeout("lento")),
}


def assert_pendente_unico(db, payload, instante):
    """§8 · uma linha pendente: payload, tentativas 1, erro curto sem dados, datas do relógio."""
    (linha,) = pendentes(db)
    payload_gravado, tentativas, ultimo_erro, criado_em, atualizado_em = linha
    assert payload_gravado == payload
    assert tentativas == 1
    assert isinstance(ultimo_erro, str)
    assert ultimo_erro.strip()
    assert len(ultimo_erro) <= 200
    assert json.dumps(payload) not in ultimo_erro
    for proibido in (NOME_SIGILOSO, CPF_SIGILOSO, CONTATO_SIGILOSO, "devolucao_registrada"):
        assert proibido.lower() not in ultimo_erro.lower(), ultimo_erro
    assert (criado_em, atualizado_em) == (instante, instante)


# D6 / §8 · falha do Backend 2: 200 ao cliente, devolução gravada, uma tentativa, pendente
@pytest.mark.parametrize("falha", list(FALHAS))
def test_falha_do_backend2_guarda_pendente(
    client, db, backend2, relogio, usuario, livro, emprestimo, falha
):
    relogio.avancar(timedelta(hours=2))
    agora = relogio.agora()
    FALHAS[falha](rota(backend2))

    dados = assert_ok(devolver(client, emprestimo))

    assert dados["status"] == "devolvido"
    assert linha_emprestimo(db, emprestimo) == ("devolvido", agora)
    assert disponivel(db, livro) == 3
    assert chamadas(backend2).call_count == 1
    enviado = corpo_enviado(chamadas(backend2).last)
    assert enviado == evento_esperado(usuario, livro, emprestimo, 3, agora)
    assert_pendente_unico(db, enviado, agora)


# §8 · BACKEND2_URL não configurado: sem chamada, devolução gravada, pendente
def test_sem_backend2_url_guarda_pendente(
    criar_app, db, backend2, usuario, livro, emprestimo, instante_base
):
    with TestClient(criar_app(backend2_url=None)) as cliente:
        assert_ok(devolver(cliente, emprestimo))

    assert backend2.calls.call_count == 0
    assert linha_emprestimo(db, emprestimo)[0] == "devolvido"
    esperado = evento_esperado(usuario, livro, emprestimo, 3, instante_base)
    assert_pendente_unico(db, esperado, instante_base)


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


# §8 · falha ao gravar o pendente: 200 mesmo assim; o log não tem dados pessoais
def test_falha_ao_gravar_pendente_nao_falha_a_devolucao(
    client, db, backend2, caplog, livro, emprestimo, pendente_recusado
):
    caplog.set_level(logging.DEBUG)
    rota(backend2).respond(503)

    assert assert_ok(devolver(client, emprestimo))["status"] == "devolvido"

    assert linha_emprestimo(db, emprestimo)[0] == "devolvido"
    assert disponivel(db, livro) == 3
    assert pendentes(db) == []
    assert any(registro.levelno >= logging.WARNING for registro in caplog.records)
    for texto in [caplog.text] + [registro.getMessage() for registro in caplog.records]:
        for proibido in (NOME_SIGILOSO, CPF_SIGILOSO, CONTATO_SIGILOSO, TEXTO_DO_GATILHO):
            assert proibido.lower() not in texto.lower(), texto


# §8 · o gatilho do teste anterior foi removido
def test_gatilho_do_teste_foi_removido(db):
    assert db.execute(
        "SELECT count(*) FROM pg_trigger WHERE tgname = 'teste_recusar_pendente'"
    ).fetchone() == (0,)


# --------------------------------------------------------------------------- erros


# CT6 · Erros · empréstimo inexistente
@pytest.mark.parametrize("inexistente", ["999999", "2147483647"])
def test_emprestimo_inexistente(client, emprestimo, nada_muda, inexistente):
    assert_erro(devolver(client, inexistente), 404, "EMPRESTIMO_NAO_ENCONTRADO")


# CT6 Detalhes · id fora de [0-9]+ (ASCII, 1..2147483647) = empréstimo inexistente
@pytest.mark.parametrize(
    "bruto",
    [
        "0",
        "00",
        "-1",
        "abc",
        "1.5",
        "1e1",
        "2147483648",
        "99999999999999999999",
        "%00",
        "1%00",
        "%2B1",
        "%D9%A1",
        "%EF%BC%91",
        "%201",
        "1%20",
        "0x1",
        "1_0",
    ],
)
def test_id_invalido(client, emprestimo, nada_muda, bruto):
    assert_erro(client.patch(f"/emprestimos/{bruto}/devolucao"), 404, "EMPRESTIMO_NAO_ENCONTRADO")


# CT6 · Erros · já devolvido (semeado devolvido): nada muda
def test_emprestimo_ja_devolvido_semeado(client, db, usuario, livro, instante_base, backend2):
    devolvido = semear_emprestimo(
        db, usuario, livro, instante_base - timedelta(days=5), devolvido_em=instante_base
    )
    antes = estado(db)

    assert_erro(devolver(client, devolvido), 409, "EMPRESTIMO_JA_DEVOLVIDO")

    assert estado(db) == antes
    assert backend2.calls.call_count == 0


# CT6 / D4 · devolver duas vezes: a segunda dá EMPRESTIMO_JA_DEVOLVIDO; quantidade +1 só
def test_devolver_duas_vezes(client, db, relogio, backend2, emprestimo, livro, instante_base):
    assert_ok(devolver(client, emprestimo))
    relogio.avancar(timedelta(days=1))

    assert_erro(devolver(client, emprestimo), 409, "EMPRESTIMO_JA_DEVOLVIDO")

    assert linha_emprestimo(db, emprestimo) == ("devolvido", instante_base)
    assert disponivel(db, livro) == 3
    assert chamadas(backend2).call_count == 1


# CT11 / §11 · a quantidade disponível nunca passa de quantidade_exemplares
def test_quantidade_nunca_passa_dos_exemplares(client, db, instante_base):
    livro_id = semear_livro(db, exemplares=2, disponivel=0)
    emprestimos = [
        semear_emprestimo(db, semear_usuario(db), livro_id, instante_base - timedelta(days=1))
        for _ in range(2)
    ]

    quantidades = [assert_ok(devolver(client, e))["quantidadeDisponivel"] for e in emprestimos]

    assert quantidades == [1, 2]
    assert disponivel(db, livro_id) == 2
    for e in emprestimos:
        assert_erro(devolver(client, e), 409, "EMPRESTIMO_JA_DEVOLVIDO")
    assert disponivel(db, livro_id) == 2


# CT11 / §11 · dado inconsistente (estoque já cheio): não pode passar dos exemplares nem
# deixar a devolução pela metade
def test_estoque_cheio_nao_passa_dos_exemplares(client, db, usuario, instante_base):
    livro_id = semear_livro(db, exemplares=2, disponivel=2)
    inconsistente = semear_emprestimo(db, usuario, livro_id, instante_base - timedelta(days=1))

    resposta = devolver(client, inconsistente)

    assert disponivel(db, livro_id) == 2
    if resposta.status_code == 200:
        assert resposta.json()["quantidadeDisponivel"] <= 2
    else:
        corpo = resposta.json()
        assert set(corpo) == {"erro"} and set(corpo["erro"]) == {"codigo", "mensagem"}
        assert linha_emprestimo(db, inconsistente) == ("ativo", None)


# --------------------------------------------------------------------------- concorrência


def corrida(client, emprestimos):
    """Dispara um PATCH por item, todos liberados juntos por uma barreira."""
    barreira = threading.Barrier(len(emprestimos), timeout=10)

    def pedir(emprestimo_id):
        barreira.wait()
        return devolver(client, emprestimo_id)

    with ThreadPoolExecutor(max_workers=len(emprestimos)) as executor:
        futuros = [executor.submit(pedir, e) for e in emprestimos]
        return [f.result(timeout=30) for f in futuros]


# CT6 Detalhes · devoluções simultâneas do mesmo empréstimo: uma 200, as outras 409
@pytest.mark.parametrize("rodada", range(3))
def test_concorrencia_mesmo_emprestimo(client, db, backend2, emprestimo, livro, rodada):
    respostas = corrida(client, [emprestimo] * 5)

    assert sorted(r.status_code for r in respostas) == [200, 409, 409, 409, 409], [
        r.text for r in respostas
    ]
    for resposta in respostas:
        if resposta.status_code == 409:
            assert_erro(resposta, 409, "EMPRESTIMO_JA_DEVOLVIDO")
    assert disponivel(db, livro) == 3
    assert linha_emprestimo(db, emprestimo)[0] == "devolvido"
    assert chamadas(backend2).call_count == 1


# CT6 Detalhes · devoluções simultâneas de empréstimos diferentes do mesmo livro: todas 200
@pytest.mark.parametrize("rodada", range(3))
def test_concorrencia_emprestimos_diferentes(client, db, backend2, instante_base, rodada):
    livro_id = semear_livro(db, exemplares=5, disponivel=0)
    emprestimos = [
        semear_emprestimo(db, semear_usuario(db), livro_id, instante_base - timedelta(days=1))
        for _ in range(5)
    ]

    respostas = corrida(client, emprestimos)

    assert [r.status_code for r in respostas] == [200] * 5, [r.text for r in respostas]
    assert disponivel(db, livro_id) == 5
    na_resposta = {r.json()["emprestimoId"]: r.json()["quantidadeDisponivel"] for r in respostas}
    assert sorted(na_resposta.values()) == [1, 2, 3, 4, 5]
    no_evento = {
        corpo_enviado(c)["emprestimoId"]: corpo_enviado(c)["quantidadeDisponivel"]
        for c in chamadas(backend2)
    }
    assert no_evento == na_resposta


# --------------------------------------------------------------------------- rotas


# §3 · barra no fim é rota inexistente
def test_barra_no_fim(client, emprestimo, nada_muda):
    resposta = client.patch(f"/emprestimos/{emprestimo}/devolucao/", follow_redirects=False)

    assert_erro(resposta, 404, "ROTA_NAO_ENCONTRADA")


# §3 · métodos não permitidos no caminho da devolução
@pytest.mark.parametrize("metodo", ["GET", "POST", "PUT", "DELETE"])
def test_metodo_nao_permitido(client, emprestimo, nada_muda, metodo):
    assert_erro(client.request(metodo, caminho(emprestimo)), 405, "ROTA_NAO_ENCONTRADA")


# §3 · PATCH /emprestimos/{id} não existe (404 ou 405, sempre ROTA_NAO_ENCONTRADA)
def test_patch_no_emprestimo_sem_devolucao(client, emprestimo, nada_muda):
    resposta = client.patch(f"/emprestimos/{emprestimo}")

    assert resposta.status_code in (404, 405), resposta.text
    assert_erro(resposta, resposta.status_code, "ROTA_NAO_ENCONTRADA")


# CT6 Detalhes · id vazio ou barra codificada (%2F) não corresponde à rota: 404 de rota
@pytest.mark.parametrize(
    "caminho_bruto",
    ["/emprestimos//devolucao", "/emprestimos/%2F/devolucao", "/emprestimos/1%2F2/devolucao"],
    ids=["id-vazio", "barra-codificada", "um-barra-dois"],
)
def test_caminho_que_nao_corresponde_a_rota(client, db, emprestimo, nada_muda, caminho_bruto):
    assert emprestimo == 1
    assert linha_emprestimo(db, 1) == ("ativo", None)

    resposta = client.patch(caminho_bruto, follow_redirects=False)

    assert_erro(resposta, 404, "ROTA_NAO_ENCONTRADA")
    assert linha_emprestimo(db, 1) == ("ativo", None)


# --------------------------------------------------------------------------- fluxo completo


# CT5 → CT8 → CT6 → CT8 → CT7 · empréstimo e devolução de ponta a ponta pela API
def test_fluxo_completo(client, db, backend2, usuario, instante_base, relogio):
    livro_id = semear_livro(db, exemplares=1, titulo="Livro Único do Fluxo")

    criado = client.post("/emprestimos", json={"usuarioId": usuario, "livroId": livro_id})
    assert criado.status_code == 201, criado.text
    emprestimo_id = criado.json()["emprestimoId"]

    ativos = client.get("/emprestimos", params={"status": "ativo"}).json()["emprestimos"]
    assert [e["emprestimoId"] for e in ativos] == [emprestimo_id]
    disponiveis = client.get("/livros/disponibilidade").json()["livros"]
    assert livro_id not in [x["id"] for x in disponiveis]

    relogio.avancar(timedelta(days=4))
    devolucao = assert_ok(devolver(client, emprestimo_id))
    assert devolucao["quantidadeDisponivel"] == 1

    devolvidos = client.get("/emprestimos", params={"status": "devolvido"}).json()
    assert [e["emprestimoId"] for e in devolvidos["emprestimos"]] == [emprestimo_id]
    assert devolvidos["emprestimos"][0]["devolvidoEm"] == iso(instante_base + timedelta(days=4))
    assert client.get("/emprestimos", params={"status": "ativo"}).json()["emprestimos"] == []
    disponiveis = client.get("/livros/disponibilidade").json()["livros"]
    assert [x for x in disponiveis if x["id"] == livro_id] == [
        {
            "id": livro_id,
            "titulo": "Livro Único do Fluxo",
            "quantidadeExemplares": 1,
            "quantidadeDisponivel": 1,
            "disponivel": True,
        }
    ]
    assert [corpo_enviado(c)["tipo"] for c in chamadas(backend2)] == [
        "emprestimo_registrado",
        "devolucao_registrada",
    ]
    assert [corpo_enviado(c)["quantidadeDisponivel"] for c in chamadas(backend2)] == [0, 1]
