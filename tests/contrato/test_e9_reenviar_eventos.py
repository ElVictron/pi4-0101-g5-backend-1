"""E9 — reenvio de eventos pendentes: `app.reenviar_eventos.main(config, relogio) -> int`.

Fontes: `00-convencoes.md` §8 (reenvio na ordem de criação; apaga em sucesso; em falha
soma 1 em `tentativas` e atualiza `ultimo_erro`; saída 0/1) e §11; `agentes.md` P10 e §8B
(linha "Reenvio"). Sem API: `eventos_pendentes` semeado por SQL, sem `id` explícito; o
Backend 2 é o falso do `conftest` (respx).
"""

import dataclasses
import json
from datetime import timedelta

import httpx
import pytest
from psycopg.types.json import Jsonb

ERRO_ANTIGO = "erro antigo semeado pelo teste"


def payload(emprestimo_id: int, tipo="emprestimo_registrado", status="ativo") -> dict:
    return {
        "tipo": tipo,
        "livroId": 10 + emprestimo_id,
        "usuarioId": 20 + emprestimo_id,
        "emprestimoId": emprestimo_id,
        "status": status,
        "quantidadeDisponivel": emprestimo_id % 3,
        "atualizadaEm": f"2026-10-{emprestimo_id:02d}T08:00:00",
    }


def semear_pendente(db, dados: dict, criado_em, tentativas=1) -> int:
    return db.execute(
        "INSERT INTO eventos_pendentes (payload, tentativas, ultimo_erro, criado_em,"
        " atualizado_em) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (Jsonb(dados), tentativas, ERRO_ANTIGO, criado_em, criado_em),
    ).fetchone()[0]


def pendentes(db):
    return db.execute(
        "SELECT id, payload, tentativas, ultimo_erro, criado_em, atualizado_em"
        " FROM eventos_pendentes ORDER BY id"
    ).fetchall()


def enviados(backend2) -> list[dict]:
    return [json.loads(c.request.content) for c in backend2.routes["eventos"].calls]


def reenviar(config, relogio) -> int:
    from app.reenviar_eventos import main

    return main(config=config, relogio=relogio)


@pytest.fixture
def tres_pendentes(db, instante_base):
    """Três pendentes; a ordem de criação (criado_em, depois id) difere da ordem de id."""
    ontem = instante_base - timedelta(days=1)
    terceiro = semear_pendente(db, payload(3), ontem)
    primeiro = semear_pendente(db, payload(1), ontem - timedelta(hours=2))
    segundo = semear_pendente(db, payload(2), ontem)
    return {"primeiro": primeiro, "segundo": segundo, "terceiro": terceiro}


# §8 · todos enviados com sucesso: linhas apagadas, saída 0, um envio por evento, em ordem
def test_reenvia_todos_com_sucesso(db, backend2, config, relogio, tres_pendentes):
    assert reenviar(config, relogio) == 0

    assert pendentes(db) == []
    assert backend2.routes["eventos"].call_count == 3
    # ordem de criação: criado_em; empate (payload 3 e 2 com o mesmo instante) → id
    assert enviados(backend2) == [payload(1), payload(3), payload(2)]


# §8 · o payload é reenviado intacto, com Content-Type JSON, para /eventos/biblioteca
def test_reenvio_envia_payload_intacto(db, backend2, config, relogio, instante_base):
    devolucao = payload(7, tipo="devolucao_registrada", status="devolvido")
    semear_pendente(db, devolucao, instante_base)

    assert reenviar(config, relogio) == 0

    (chamada,) = backend2.routes["eventos"].calls
    assert chamada.request.method == "POST"
    assert chamada.request.url.path == "/eventos/biblioteca"
    assert chamada.request.headers["content-type"].startswith("application/json")
    assert json.loads(chamada.request.content) == devolucao


# §8 · falha num deles: os outros apagados; o que falhou tem tentativas +1 e erro novo
@pytest.mark.parametrize(
    "falha",
    [
        httpx.Response(503),
        httpx.Response(200, json={"aceito": False}),
        httpx.Response(200, text="nao e json"),
        httpx.ConnectError("recusada"),
        httpx.ReadTimeout("lento"),
    ],
    ids=["http-503", "aceito-false", "nao-json", "connect-error", "read-timeout"],
)
def test_falha_num_dos_eventos(db, backend2, config, relogio, tres_pendentes, falha):
    relogio.avancar(timedelta(hours=3))

    def responder(requisicao):
        if json.loads(requisicao.content)["emprestimoId"] == 3:
            if isinstance(falha, Exception):
                raise falha
            return falha
        return httpx.Response(200, json={"aceito": True, "eventoId": "evt"})

    backend2.routes["eventos"].mock(side_effect=responder)

    assert reenviar(config, relogio) == 1

    assert backend2.routes["eventos"].call_count == 3
    (restante,) = pendentes(db)
    linha_id, dados, tentativas, ultimo_erro, criado_em, atualizado_em = restante
    assert linha_id == tres_pendentes["terceiro"]
    assert dados == payload(3)
    assert tentativas == 2
    assert isinstance(ultimo_erro, str)
    assert ultimo_erro.strip()
    assert ultimo_erro != ERRO_ANTIGO
    assert atualizado_em == relogio.agora()
    assert criado_em == relogio.agora() - timedelta(hours=3) - timedelta(days=1)


# §8 · tentativas soma 1 a partir do valor atual (não volta para 2)
def test_tentativas_soma_ao_valor_atual(db, backend2, config, relogio, instante_base):
    semear_pendente(db, payload(5), instante_base, tentativas=4)
    backend2.routes["eventos"].respond(503)

    assert reenviar(config, relogio) == 1

    assert pendentes(db)[0][2] == 5


# §8 · tabela vazia: saída 0 e nenhuma chamada
def test_tabela_vazia(db, backend2, config, relogio):
    assert reenviar(config, relogio) == 0

    assert backend2.calls.call_count == 0


# §8 · BACKEND2_URL não configurado: nada apagado, tentativas +1, saída 1, nenhuma chamada
def test_sem_backend2_url(db, backend2, config, relogio, tres_pendentes):
    sem_url = dataclasses.replace(config, backend2_url=None)

    assert reenviar(sem_url, relogio) == 1

    assert backend2.calls.call_count == 0
    linhas = pendentes(db)
    assert len(linhas) == 3
    assert all(linha[2] == 2 for linha in linhas)
    assert all(linha[3].strip() and linha[3] != ERRO_ANTIGO for linha in linhas)
    assert all(linha[5] == relogio.agora() for linha in linhas)


# §8 · rodar de novo depois do sucesso não reenvia nada
def test_segunda_execucao_nao_reenvia(db, backend2, config, relogio, tres_pendentes):
    assert reenviar(config, relogio) == 0
    assert reenviar(config, relogio) == 0

    assert backend2.routes["eventos"].call_count == 3


# §8 · depois de uma falha, a próxima execução com o Backend 2 de volta envia e apaga
def test_reenvio_depois_que_o_backend2_volta(db, backend2, config, relogio, instante_base):
    semear_pendente(db, payload(4), instante_base)
    backend2.routes["eventos"].respond(503)
    assert reenviar(config, relogio) == 1

    backend2.routes["eventos"].respond(200, json={"aceito": True, "eventoId": "evt"})
    assert reenviar(config, relogio) == 0

    assert pendentes(db) == []
    assert enviados(backend2) == [payload(4), payload(4)]
