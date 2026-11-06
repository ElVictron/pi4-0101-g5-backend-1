"""Situação efetiva e objeto EmprestimoResumo (CT8; 00-convencoes §7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


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
