"""SQL da tabela `eventos_pendentes` (§8, §11). Conexão já dentro de `transacao`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from app.db import Conexao

# §8 / D20: `ultimo_erro` curto, não vazio, sem o payload.
LIMITE_ULTIMO_ERRO = 200
_ERRO_SEM_DESCRICAO = "falha sem descrição"


def resumo_do_erro(motivo: str) -> str:
    """Motivo sem brancos nas pontas, cortado em 200 caracteres; nunca vazio."""
    return motivo.strip()[:LIMITE_ULTIMO_ERRO] or _ERRO_SEM_DESCRICAO


@dataclass(frozen=True)
class EventoPendente:
    id: int
    payload: dict[str, Any]
    tentativas: int


def inserir(conexao: Conexao, payload: Mapping[str, Any], ultimo_erro: str, agora: datetime) -> int:
    """Guarda o evento com `tentativas` = 1 e as datas do relógio da aplicação."""
    linha = conexao.execute(
        "INSERT INTO eventos_pendentes (payload, tentativas, ultimo_erro, criado_em, atualizado_em)"
        " VALUES (%s, 1, %s, %s, %s) RETURNING id",
        (Jsonb(dict(payload)), resumo_do_erro(ultimo_erro), agora, agora),
    ).fetchone()
    assert linha is not None
    return linha["id"]


def ids_em_ordem(conexao: Conexao) -> list[int]:
    """Pendentes na ordem de criação (§8): `criado_em`, depois `id`."""
    linhas = conexao.execute("SELECT id FROM eventos_pendentes ORDER BY criado_em, id")
    return [linha["id"] for linha in linhas]


def travar(conexao: Conexao, evento_id: int) -> EventoPendente | None:
    """Trava a linha para este reenvio; `None` se sumiu ou outro reenvio já a pegou."""
    linha = conexao.execute(
        "SELECT id, payload, tentativas FROM eventos_pendentes WHERE id = %s"
        " FOR UPDATE SKIP LOCKED",
        (evento_id,),
    ).fetchone()
    return None if linha is None else EventoPendente(**linha)


def apagar(conexao: Conexao, evento_id: int) -> None:
    conexao.execute("DELETE FROM eventos_pendentes WHERE id = %s", (evento_id,))


def registrar_falha(conexao: Conexao, evento_id: int, ultimo_erro: str, agora: datetime) -> None:
    conexao.execute(
        "UPDATE eventos_pendentes"
        " SET tentativas = tentativas + 1, ultimo_erro = %s, atualizado_em = %s WHERE id = %s",
        (resumo_do_erro(ultimo_erro), agora, evento_id),
    )
