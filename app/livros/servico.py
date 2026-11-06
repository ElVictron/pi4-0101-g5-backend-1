"""Regras de negócio de livros (CT1)."""

from __future__ import annotations

from types import MappingProxyType

from app.config import Config
from app.db import transacao, violacoes_como_erro
from app.erros import CodigoErro
from app.livros import repositorio
from app.livros.esquemas import Livro, NovoLivro
from app.relogio import Relogio

# D16 a: restrição do banco → código da ficha.
ERROS_POR_RESTRICAO = MappingProxyType({"livros_isbn_unico": CodigoErro.ISBN_DUPLICADO})


def cadastrar_livro(config: Config, relogio: Relogio, novo: NovoLivro) -> Livro:
    """Grava o livro; ISBN já cadastrado (após normalização) → `ISBN_DUPLICADO`."""
    with violacoes_como_erro(ERROS_POR_RESTRICAO), transacao(config) as conexao:
        return repositorio.inserir(conexao, novo, criado_em=relogio.agora())
