"""Regras de negócio de livros (CT1, CT2)."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from app.config import Config
from app.db import transacao, violacoes_como_erro
from app.erros import CodigoErro
from app.livros import repositorio
from app.livros.esquemas import Livro, NovoLivro
from app.parametros import ConsultaPaginada
from app.relogio import Relogio

# D16 a: restrição do banco → código da ficha.
ERROS_POR_RESTRICAO = MappingProxyType({"livros_isbn_unico": CodigoErro.ISBN_DUPLICADO})


@dataclass(frozen=True)
class PaginaDeLivros:
    livros: list[Livro]
    total: int


def cadastrar_livro(config: Config, relogio: Relogio, novo: NovoLivro) -> Livro:
    """Grava o livro; ISBN já cadastrado (após normalização) → `ISBN_DUPLICADO`."""
    with violacoes_como_erro(ERROS_POR_RESTRICAO), transacao(config) as conexao:
        return repositorio.inserir(conexao, novo, criado_em=relogio.agora())


def consultar_livros(config: Config, consulta: ConsultaPaginada) -> PaginaDeLivros:
    """Página de livros e `total` do filtro, lidos no mesmo retrato do banco."""
    with transacao(config, somente_leitura=True) as conexao:
        return PaginaDeLivros(
            livros=repositorio.buscar(
                conexao, consulta.busca, limite=consulta.tamanho, deslocamento=consulta.deslocamento
            ),
            total=repositorio.contar(conexao, consulta.busca),
        )
