"""Reenvio dos eventos pendentes ao Backend 2 (P10, §8; agentes.md §8B).

Uso: `python -m app.reenviar_eventos`. Código de saída 0 se nenhum evento continuou
pendente, 1 se algum continuou.
"""

from __future__ import annotations

import logging
import sys

from app.config import Config
from app.db import transacao
from app.eventos import repositorio
from app.eventos.publicador import PublicadorDeEventos, PublicadorHttp
from app.relogio import Relogio, RelogioSistema

logger = logging.getLogger(__name__)


def reenviar(config: Config, relogio: Relogio, publicador: PublicadorDeEventos) -> int:
    """Tenta cada pendente uma vez, na ordem de criação; devolve quantos continuaram.

    Evento travado por outro reenvio em andamento é pulado e conta como pendente (D20).
    """
    with transacao(config, somente_leitura=True) as conexao:
        ids = repositorio.ids_em_ordem(conexao)

    enviados = falhas = pulados = 0
    for evento_id in ids:
        # Uma transação por evento, com a linha travada: dois reenvios ao mesmo tempo não
        # mandam o mesmo evento duas vezes (o segundo pula a linha travada).
        with transacao(config) as conexao:
            evento = repositorio.travar(conexao, evento_id)
            if evento is None:
                pulados += 1
                continue
            motivo = publicador.publicar(evento.payload)
            if motivo is None:
                repositorio.apagar(conexao, evento.id)
                enviados += 1
            else:
                repositorio.registrar_falha(conexao, evento.id, motivo, relogio.agora())
                falhas += 1
                logger.warning("Evento pendente %s continua pendente: %s", evento.id, motivo)
    logger.info(
        "Reenvio: %s enviado(s), %s com falha, %s pulado(s) por estar(em) em outro reenvio",
        enviados,
        falhas,
        pulados,
    )
    return falhas + pulados


def main(config: Config | None = None, relogio: Relogio | None = None) -> int:
    """Reenvia os pendentes com o mesmo cliente `httpx` da aplicação."""
    config = config if config is not None else Config.from_env()
    relogio = relogio if relogio is not None else RelogioSistema()
    return 1 if reenviar(config, relogio, PublicadorHttp(config)) else 0


if __name__ == "__main__":  # pragma: no cover - ponto de entrada do comando
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.exit(main())
