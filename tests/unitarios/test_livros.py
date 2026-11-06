"""Livros: leitura do corpo do CT1 (ordem do §4), saída e serviço (sem banco)."""

import json
from contextlib import contextmanager
from datetime import datetime

import pytest

from app.config import Config
from app.erros import CodigoErro, ErroDominio
from app.livros import servico
from app.livros.esquemas import CAMPOS_ENTRADA, Livro, NovoLivro, ler_novo_livro, livro_para_json
from app.relogio import RelogioFixo

pytestmark = pytest.mark.unitario

VALIDO = {"titulo": "T", "autor": "A", "isbn": "9780000000001", "quantidadeExemplares": 3}
INSTANTE = datetime(2026, 10, 13, 19, 20)


def _erro(**alteracoes) -> CodigoErro:
    dados = {**VALIDO, **alteracoes}
    with pytest.raises(ErroDominio) as erro:
        ler_novo_livro({k: v for k, v in dados.items() if v is not ...})
    return erro.value.codigo


def test_campos_na_ordem_do_ct1():
    assert CAMPOS_ENTRADA == ("titulo", "autor", "isbn", "quantidadeExemplares")


def test_le_e_normaliza():
    novo = ler_novo_livro(
        {"titulo": " T ", "autor": "\tA\n", "isbn": "978-0-00-000000-1", "quantidadeExemplares": 2}
    )

    assert novo == NovoLivro(titulo="T", autor="A", isbn="9780000000001", quantidade_exemplares=2)


@pytest.mark.parametrize(
    ("alteracoes", "codigo"),
    [
        ({"titulo": ..., "quantidadeExemplares": 0}, CodigoErro.CAMPOS_OBRIGATORIOS),
        ({"titulo": "a" * 201, "quantidadeExemplares": None}, CodigoErro.CAMPOS_OBRIGATORIOS),
        ({"isbn": "123", "quantidadeExemplares": 0}, CodigoErro.DADOS_INVALIDOS),
        ({"autor": 1, "quantidadeExemplares": True}, CodigoErro.DADOS_INVALIDOS),
        ({"quantidadeExemplares": 0}, CodigoErro.QUANTIDADE_INVALIDA),
        ({"quantidadeExemplares": "3"}, CodigoErro.QUANTIDADE_INVALIDA),
        ({"quantidadeExemplares": ""}, CodigoErro.CAMPOS_OBRIGATORIOS),
    ],
)
def test_ordem_do_paragrafo_4(alteracoes, codigo):
    assert _erro(**alteracoes) is codigo


def test_saida_tem_os_campos_do_ct1_sem_criado_em():
    livro = Livro(1, "T", "A", "9780000000001", 3, 2, INSTANTE)

    assert livro_para_json(livro) == {
        "id": 1,
        "titulo": "T",
        "autor": "A",
        "isbn": "9780000000001",
        "quantidadeExemplares": 3,
        "quantidadeDisponivel": 2,
    }


def test_servico_grava_com_o_instante_do_relogio_dentro_da_transacao(monkeypatch):
    chamadas = []

    @contextmanager
    def transacao_falsa(config):
        chamadas.append(("abre", config))
        yield "conexao"
        chamadas.append(("confirma",))

    def inserir_falso(conexao, novo, criado_em):
        chamadas.append(("inserir", conexao, novo, criado_em))
        return "livro"

    monkeypatch.setattr(servico, "transacao", transacao_falsa)
    monkeypatch.setattr(servico.repositorio, "inserir", inserir_falso)
    config = Config(database_url="postgresql://x/y_teste")
    novo = NovoLivro("T", "A", "9780000000001", 1)

    assert servico.cadastrar_livro(config, RelogioFixo(INSTANTE), novo) == "livro"
    assert chamadas == [("abre", config), ("inserir", "conexao", novo, INSTANTE), ("confirma",)]


def test_servico_mapeia_so_a_restricao_de_isbn():
    assert dict(servico.ERROS_POR_RESTRICAO) == {"livros_isbn_unico": CodigoErro.ISBN_DUPLICADO}


@pytest.mark.parametrize("campo", ["titulo", "autor", "isbn"])
def test_rota_recusa_nul_antes_de_chegar_ao_banco(campo):
    from fastapi.testclient import TestClient

    from app.main import create_app

    # Banco inexistente: se a validação deixasse passar, o teste daria erro de conexão (500).
    app = create_app(config=Config(database_url="postgresql://ninguem@127.0.0.1:1/nada_teste"))
    corpo = json.dumps({**VALIDO, campo: "97800\u000000001"})

    with TestClient(app, raise_server_exceptions=False) as cliente:
        resposta = cliente.post(
            "/livros", content=corpo, headers={"Content-Type": "application/json"}
        )

    assert resposta.status_code == 400
    assert resposta.json()["erro"]["codigo"] == "DADOS_INVALIDOS"


def test_consulta_le_pagina_e_total_na_mesma_transacao_somente_leitura(monkeypatch):
    from app.parametros import ConsultaPaginada

    chamadas = []

    @contextmanager
    def transacao_falsa(config, *, somente_leitura=False):
        chamadas.append(("abre", somente_leitura))
        yield "conexao"
        chamadas.append(("fecha",))

    def buscar_falso(conexao, termo, *, limite, deslocamento):
        chamadas.append(("buscar", conexao, termo, limite, deslocamento))
        return ["livro"]

    def contar_falso(conexao, termo):
        chamadas.append(("contar", conexao, termo))
        return 42

    monkeypatch.setattr(servico, "transacao", transacao_falsa)
    monkeypatch.setattr(servico.repositorio, "buscar", buscar_falso)
    monkeypatch.setattr(servico.repositorio, "contar", contar_falso)

    pagina = servico.consultar_livros(
        Config(database_url="postgresql://x/y_teste"), ConsultaPaginada("dados", 3, 10)
    )

    assert pagina == servico.PaginaDeLivros(livros=["livro"], total=42)
    assert chamadas == [
        ("abre", True),
        ("buscar", "conexao", "dados", 10, 20),
        ("contar", "conexao", "dados"),
        ("fecha",),
    ]


def test_ordem_da_consulta_usa_collation_deterministica():
    from app.livros import repositorio

    assert repositorio._ORDEM.as_string(None) == (
        'ORDER BY lower(unaccent("titulo")) COLLATE "C", "titulo" COLLATE "C", "id"'
    )
    assert repositorio.COLUNAS_DA_BUSCA == ("titulo", "autor", "isbn")


# ----------------------------------------------- CT7 listarDisponibilidade (sem banco)


def test_saida_livro_disponibilidade_tem_so_os_campos_do_ct7():
    from app.livros.esquemas import livro_disponibilidade_para_json

    livro = Livro(1, "T", "A", "9780000000001", 3, 2, INSTANTE)

    assert livro_disponibilidade_para_json(livro) == {
        "id": 1,
        "titulo": "T",
        "quantidadeExemplares": 3,
        "quantidadeDisponivel": 2,
        "disponivel": True,
    }


def test_where_da_disponibilidade_combina_estoque_e_busca_com_and():
    from app.livros import repositorio

    sem_busca = repositorio._onde(None, repositorio._SO_DISPONIVEIS).as_string(None)
    com_busca = repositorio._onde("x", repositorio._SO_DISPONIVEIS).as_string(None)

    assert sem_busca == "WHERE quantidade_disponivel > 0"
    assert com_busca.startswith("WHERE quantidade_disponivel > 0 AND (")
    assert com_busca.count("LIKE") == 3
    assert repositorio._onde(None).as_string(None) == ""


def test_servico_de_disponibilidade_usa_transacao_somente_leitura(monkeypatch):
    chamadas = []

    @contextmanager
    def transacao_falsa(config, *, somente_leitura=False):
        chamadas.append(("abre", somente_leitura))
        yield "conexao"

    def listar_falso(conexao, termo):
        chamadas.append(("listar", conexao, termo))
        return ["livro"]

    monkeypatch.setattr(servico, "transacao", transacao_falsa)
    monkeypatch.setattr(servico.repositorio, "listar_disponiveis", listar_falso)

    resultado = servico.listar_disponibilidade(Config(database_url="postgresql://x/y_teste"), "a")

    assert resultado == ["livro"]
    assert chamadas == [("abre", True), ("listar", "conexao", "a")]


@pytest.fixture
def cliente_disponibilidade(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import create_app

    recebidos = []

    def listar_falso(config, busca):
        recebidos.append(busca)
        return [Livro(5, "Livro", "Autor", "9780000000001", 2, 1, INSTANTE)]

    monkeypatch.setattr(servico, "listar_disponibilidade", listar_falso)
    app = create_app(config=Config(database_url="postgresql://x/y_teste"))
    with TestClient(app) as cliente:
        yield cliente, recebidos


def test_rota_de_disponibilidade_le_so_a_busca_e_ignora_paginacao(cliente_disponibilidade):
    cliente, recebidos = cliente_disponibilidade

    resposta = cliente.get("/livros/disponibilidade?pagina=0&tamanho=abc&busca=+a+&busca=b")

    assert resposta.status_code == 200
    assert resposta.json() == {
        "livros": [
            {
                "id": 5,
                "titulo": "Livro",
                "quantidadeExemplares": 2,
                "quantidadeDisponivel": 1,
                "disponivel": True,
            }
        ]
    }
    assert recebidos == ["a"]


@pytest.mark.parametrize("consulta", ["busca=" + "a" * 101, "busca=%00", "busca=%FF"])
def test_rota_de_disponibilidade_com_busca_invalida(cliente_disponibilidade, consulta):
    cliente, recebidos = cliente_disponibilidade

    resposta = cliente.get(f"/livros/disponibilidade?{consulta}")

    assert resposta.status_code == 400
    assert resposta.json()["erro"]["codigo"] == "BUSCA_INVALIDA"
    assert recebidos == []
