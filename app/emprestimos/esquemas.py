"""Entrada do CT5, situação efetiva e EmprestimoResumo (CT5, CT8; 00-convencoes §4, §7)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from app import validacao

# D2 / §7: data limite = emprestado em + 15 dias, no mesmo horário.
PRAZO_DE_DEVOLUCAO = timedelta(days=15)

# Ordem da tabela de Entrada do CT5 (§4).
CAMPOS_ENTRADA = ("usuarioId", "livroId")

# CT6 · Detalhes: `emprestimoId` do caminho só em `[0-9]+` ASCII, de 1 a 2147483647.
_ID_DO_CAMINHO = re.compile(r"[0-9]+")
_DIGITOS_DO_MAXIMO = len(str(validacao.INTEIRO_MAXIMO))


class Situacao(StrEnum):
    """Situação efetiva (CT8). Só `ativo` e `devolvido` são gravados (D3)."""

    ATIVO = "ativo"
    DEVOLVIDO = "devolvido"
    ATRASADO = "atrasado"


@dataclass(frozen=True)
class EmprestimoResumo:
    id: int
    usuario_id: int
    usuario_nome: str
    livro_id: int
    livro_titulo: str
    emprestado_em: datetime
    data_limite_devolucao: datetime
    devolvido_em: datetime | None


@dataclass(frozen=True)
class NovoEmprestimo:
    usuario_id: int
    livro_id: int


@dataclass(frozen=True)
class Emprestimo:
    """Linha da tabela `emprestimos` (CT11)."""

    id: int
    usuario_id: int
    livro_id: int
    status: str
    emprestado_em: datetime
    data_limite_devolucao: datetime
    devolvido_em: datetime | None


def ler_novo_emprestimo(dados: Mapping[str, Any]) -> NovoEmprestimo:
    """Valida o corpo do CT5 na ordem do §4: inteiros ≥ 1, senão `DADOS_INVALIDOS`."""
    validacao.exigir_presentes(dados, CAMPOS_ENTRADA)
    return NovoEmprestimo(
        usuario_id=validacao.inteiro(dados["usuarioId"], "usuarioId", minimo=1),
        livro_id=validacao.inteiro(dados["livroId"], "livroId", minimo=1),
    )


def ler_id_do_caminho(texto: str) -> int | None:
    """Id do caminho (CT6); `None` se não for inteiro válido (vale como inexistente).

    Sem cortar brancos nem aceitar sinal; zeros à esquerda não contam no tamanho.
    """
    if not _ID_DO_CAMINHO.fullmatch(texto) or len(texto.lstrip("0")) > _DIGITOS_DO_MAXIMO:
        return None
    valor = int(texto)
    return valor if 1 <= valor <= validacao.INTEIRO_MAXIMO else None


@dataclass(frozen=True)
class Devolucao:
    """Resultado do CT6."""

    emprestimo_id: int
    livro_id: int
    usuario_id: int
    devolvido_em: datetime
    quantidade_disponivel: int


def data_limite_para(emprestado_em: datetime) -> datetime:
    return emprestado_em + PRAZO_DE_DEVOLUCAO


def situacao_efetiva(
    devolvido_em: datetime | None, data_limite_devolucao: datetime, agora: datetime
) -> Situacao:
    """§7: devolvido se `devolvido_em`; senão atrasado só **depois** do limite; senão ativo."""
    if devolvido_em is not None:
        return Situacao.DEVOLVIDO
    if agora > data_limite_devolucao:
        return Situacao.ATRASADO
    return Situacao.ATIVO


def data_hora_para_json(instante: datetime | None) -> str | None:
    """`AAAA-MM-DDTHH:MM:SS`, sem fuso nem frações de segundo (§7); `None` vira `null`."""
    if instante is None:
        return None
    return instante.replace(tzinfo=None, microsecond=0).isoformat(timespec="seconds")


def emprestimo_resumo_para_json(emprestimo: EmprestimoResumo, agora: datetime) -> dict[str, Any]:
    """Objeto EmprestimoResumo do CT8, com a situação efetiva no instante `agora`."""
    return {
        "emprestimoId": emprestimo.id,
        "usuarioId": emprestimo.usuario_id,
        "usuarioNome": emprestimo.usuario_nome,
        "livroId": emprestimo.livro_id,
        "livroTitulo": emprestimo.livro_titulo,
        "status": situacao_efetiva(
            emprestimo.devolvido_em, emprestimo.data_limite_devolucao, agora
        ).value,
        "emprestadoEm": data_hora_para_json(emprestimo.emprestado_em),
        "dataLimiteDevolucao": data_hora_para_json(emprestimo.data_limite_devolucao),
        "devolvidoEm": data_hora_para_json(emprestimo.devolvido_em),
    }


def emprestimo_para_json(emprestimo: Emprestimo) -> dict[str, Any]:
    """Saída do CT5 (e do CT6): o status gravado, sem nome de usuário nem título."""
    return {
        "emprestimoId": emprestimo.id,
        "usuarioId": emprestimo.usuario_id,
        "livroId": emprestimo.livro_id,
        "status": emprestimo.status,
        "emprestadoEm": data_hora_para_json(emprestimo.emprestado_em),
        "dataLimiteDevolucao": data_hora_para_json(emprestimo.data_limite_devolucao),
        "devolvidoEm": data_hora_para_json(emprestimo.devolvido_em),
    }


def devolucao_para_json(devolucao: Devolucao) -> dict[str, Any]:
    """Saída do CT6."""
    return {
        "emprestimoId": devolucao.emprestimo_id,
        "livroId": devolucao.livro_id,
        "status": Situacao.DEVOLVIDO.value,
        "devolvidoEm": data_hora_para_json(devolucao.devolvido_em),
        "quantidadeDisponivel": devolucao.quantidade_disponivel,
    }
