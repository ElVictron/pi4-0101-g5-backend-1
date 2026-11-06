"""Leitura do corpo JSON (00-convencoes §4 item 1; agentes.md D12, D13)."""

import asyncio

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient

from app.config import Config
from app.entrada import (
    LIMITE_CORPO_BYTES,
    corpo_json,
    interpretar_corpo_json,
    ler_corpo_limitado,
    verificar_content_type,
)
from app.erros import CodigoErro, ErroDominio
from app.main import create_app

pytestmark = pytest.mark.unitario

JSON = {"Content-Type": "application/json"}


@pytest.fixture
def cliente():
    app = create_app(config=Config(database_url="postgresql://x/y"))

    @app.post("/teste/corpo")
    async def corpo(dados: dict = Depends(corpo_json)):  # noqa: B008
        return dados

    with TestClient(app) as cliente:
        yield cliente


def _assert_dados_invalidos(resposta) -> None:
    assert resposta.status_code == 400
    corpo = resposta.json()
    assert set(corpo) == {"erro"}
    assert corpo["erro"]["codigo"] == "DADOS_INVALIDOS"
    assert corpo["erro"]["mensagem"].strip()


def _json_de_tamanho(tamanho: int) -> bytes:
    """Objeto JSON `{"a":"xxx..."}` com exatamente `tamanho` bytes."""
    return b'{"a":"' + b"x" * (tamanho - 8) + b'"}'


# --------------------------------------------------------------------------- Content-Type


@pytest.mark.parametrize(
    "content_type",
    [
        "application/json",
        "application/json; charset=utf-8",
        "Application/JSON",
        " application/json ",
    ],
)
def test_content_type_json_e_aceito(cliente, content_type):
    resposta = cliente.post(
        "/teste/corpo", content=b'{"a": 1}', headers={"Content-Type": content_type}
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"a": 1}


@pytest.mark.parametrize(
    "content_type",
    ["text/plain", "application/jsonx", "application/x-www-form-urlencoded", "multipart/form-data"],
)
def test_content_type_diferente_de_json_e_dados_invalidos(cliente, content_type):
    resposta = cliente.post(
        "/teste/corpo", content=b'{"a": 1}', headers={"Content-Type": content_type}
    )

    _assert_dados_invalidos(resposta)


def test_sem_content_type_e_dados_invalidos(cliente):
    _assert_dados_invalidos(cliente.post("/teste/corpo", content=b'{"a": 1}'))


@pytest.mark.parametrize("valor", [None, "", ";charset=utf-8"])
def test_verificar_content_type_recusa_ausente_ou_vazio(valor):
    with pytest.raises(ErroDominio) as erro:
        verificar_content_type(valor)

    assert erro.value.codigo is CodigoErro.DADOS_INVALIDOS


# --------------------------------------------------------------------------- conteúdo


@pytest.mark.parametrize(
    "conteudo",
    [b"", b"   ", b"{", b"nao e json", b"[1, 2]", b'"texto"', b"42", b"null", b"\xff\xfe"],
    ids=["vazio", "espacos", "truncado", "texto", "lista", "string", "numero", "null", "binario"],
)
def test_corpo_que_nao_e_objeto_json_e_dados_invalidos(cliente, conteudo):
    _assert_dados_invalidos(cliente.post("/teste/corpo", content=conteudo, headers=JSON))


@pytest.mark.parametrize("codificacao", ["utf-16", "utf-16-le", "utf-32", "utf-8-sig"])
def test_corpo_fora_de_utf8_estrito_e_dados_invalidos(cliente, codificacao):
    conteudo = '{"titulo": "Informação"}'.encode(codificacao)

    _assert_dados_invalidos(cliente.post("/teste/corpo", content=conteudo, headers=JSON))


def test_corpo_utf8_com_acentos_e_lido(cliente):
    resposta = cliente.post(
        "/teste/corpo", content='{"titulo": "Informação"}'.encode(), headers=JSON
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"titulo": "Informação"}


@pytest.mark.parametrize("constante", ["NaN", "Infinity", "-Infinity"])
def test_constantes_fora_do_json_sao_recusadas(constante):
    with pytest.raises(ErroDominio) as erro:
        interpretar_corpo_json(f'{{"quantidade": {constante}}}'.encode())

    assert erro.value.codigo is CodigoErro.DADOS_INVALIDOS


def test_json_aninhado_demais_e_dados_invalidos_e_nao_500(cliente):
    conteudo = b'{"a":' + b"[" * 60_000

    assert len(conteudo) <= LIMITE_CORPO_BYTES
    _assert_dados_invalidos(cliente.post("/teste/corpo", content=conteudo, headers=JSON))


def test_corpo_objeto_json_e_devolvido(cliente):
    resposta = cliente.post("/teste/corpo", json={"titulo": "Dom Casmurro", "extra": [1]})

    assert resposta.status_code == 200
    assert resposta.json() == {"titulo": "Dom Casmurro", "extra": [1]}


# --------------------------------------------------------------------------- limite de 64 KiB


def test_limite_e_64_kib():
    assert LIMITE_CORPO_BYTES == 65_536


def test_corpo_no_limite_e_aceito(cliente):
    conteudo = _json_de_tamanho(LIMITE_CORPO_BYTES)

    resposta = cliente.post("/teste/corpo", content=conteudo, headers=JSON)

    assert len(conteudo) == LIMITE_CORPO_BYTES
    assert resposta.status_code == 200


def test_corpo_um_byte_acima_do_limite_e_dados_invalidos(cliente):
    conteudo = _json_de_tamanho(LIMITE_CORPO_BYTES + 1)

    _assert_dados_invalidos(cliente.post("/teste/corpo", content=conteudo, headers=JSON))


def test_corpo_acima_do_limite_sem_content_length_e_dados_invalidos(cliente):
    def partes():
        for _ in range(10):
            yield b" " * 10_000
        yield b"{}"

    _assert_dados_invalidos(cliente.post("/teste/corpo", content=partes(), headers=JSON))


def _requisicao(partes: list[bytes], headers: dict[str, str] | None = None):
    """Request ASGI falsa que conta quantas partes do corpo foram lidas."""
    lidas: list[int] = []

    async def receive():
        indice = len(lidas)
        lidas.append(indice)
        return {
            "type": "http.request",
            "body": partes[indice],
            "more_body": indice < len(partes) - 1,
        }

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    return Request(scope, receive), lidas


def test_leitura_para_assim_que_passa_do_limite():
    requisicao, lidas = _requisicao([b"a" * 600, b"b" * 600, b"c" * 600, b"d" * 600])

    with pytest.raises(ErroDominio):
        asyncio.run(ler_corpo_limitado(requisicao, limite=1000))

    assert len(lidas) == 2


def test_content_length_acima_do_limite_recusa_sem_ler_o_corpo():
    requisicao, lidas = _requisicao([b"{}"], headers={"Content-Length": "999999"})

    with pytest.raises(ErroDominio):
        asyncio.run(ler_corpo_limitado(requisicao))

    assert lidas == []


def test_leitura_dentro_do_limite_junta_as_partes():
    requisicao, _ = _requisicao([b'{"a":', b" 1}"], headers={"Content-Length": "lixo"})

    assert asyncio.run(ler_corpo_limitado(requisicao)) == b'{"a": 1}'
