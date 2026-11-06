"""Situação efetiva e EmprestimoResumo (CT8; 00-convencoes §7)."""

from datetime import datetime, timedelta

import pytest

from app.emprestimos import repositorio
from app.emprestimos.esquemas import (
    EmprestimoResumo,
    Situacao,
    data_hora_para_json,
    emprestimo_resumo_para_json,
    situacao_efetiva,
)

pytestmark = pytest.mark.unitario

T0 = datetime(2026, 10, 13, 19, 20, 0)
LIMITE = T0 + timedelta(days=15)


@pytest.mark.parametrize(
    ("agora", "esperada"),
    [
        (T0, Situacao.ATIVO),
        (LIMITE - timedelta(seconds=1), Situacao.ATIVO),
        (LIMITE, Situacao.ATIVO),
        (LIMITE + timedelta(seconds=1), Situacao.ATRASADO),
        (LIMITE + timedelta(days=300), Situacao.ATRASADO),
    ],
    ids=["emprestimo", "1s-antes", "no-limite", "1s-depois", "muito-depois"],
)
def test_situacao_sem_devolucao(agora, esperada):
    assert situacao_efetiva(None, LIMITE, agora) is esperada


@pytest.mark.parametrize("agora", [T0, LIMITE + timedelta(days=30)])
def test_devolvido_vale_mesmo_depois_do_prazo(agora):
    assert situacao_efetiva(LIMITE + timedelta(days=1), LIMITE, agora) is Situacao.DEVOLVIDO


def test_valores_da_situacao():
    assert [s.value for s in Situacao] == ["ativo", "devolvido", "atrasado"]


@pytest.mark.parametrize(
    ("instante", "esperado"),
    [
        (None, None),
        (T0, "2026-10-13T19:20:00"),
        (datetime(2026, 1, 2, 3, 4, 5, 999_999), "2026-01-02T03:04:05"),
        (datetime(2026, 1, 2), "2026-01-02T00:00:00"),
    ],
)
def test_data_hora_sem_fuso_nem_fracao(instante, esperado):
    assert data_hora_para_json(instante) == esperado


def test_resumo_tem_os_campos_do_ct8_com_devolvido_em_nulo():
    emprestimo = EmprestimoResumo(9, 5, "Lucas", 7, "Livro", T0, LIMITE, None)

    assert emprestimo_resumo_para_json(emprestimo, LIMITE + timedelta(seconds=1)) == {
        "emprestimoId": 9,
        "usuarioId": 5,
        "usuarioNome": "Lucas",
        "livroId": 7,
        "livroTitulo": "Livro",
        "status": "atrasado",
        "emprestadoEm": "2026-10-13T19:20:00",
        "dataLimiteDevolucao": "2026-10-28T19:20:00",
        "devolvidoEm": None,
    }


def test_resumo_devolvido():
    devolucao = T0 + timedelta(days=2)
    emprestimo = EmprestimoResumo(9, 5, "Lucas", 7, "Livro", T0, LIMITE, devolucao)

    dados = emprestimo_resumo_para_json(emprestimo, LIMITE + timedelta(days=9))

    assert dados["status"] == "devolvido"
    assert dados["devolvidoEm"] == "2026-10-15T19:20:00"


def test_lista_vazia_de_usuarios_nao_consulta_o_banco():
    class ConexaoQueNaoPodeSerUsada:
        def execute(self, *args, **kwargs):
            raise AssertionError("não deveria consultar")

    assert repositorio.resumos_dos_usuarios(ConexaoQueNaoPodeSerUsada(), []) == []


def test_sql_do_resumo_usa_any_e_a_ordem_do_ct8():
    texto = repositorio.ORDEM_RESUMO.as_string(None)

    assert texto == "ORDER BY e.emprestado_em DESC, e.id DESC"
    assert "JOIN usuarios" in repositorio.SELECAO_RESUMO.as_string(None)
    assert "JOIN livros" in repositorio.SELECAO_RESUMO.as_string(None)
