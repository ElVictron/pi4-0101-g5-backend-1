"""Regras de negócio de usuários (CT3)."""

from __future__ import annotations

from types import MappingProxyType

from app.config import Config
from app.db import transacao, violacoes_como_erro
from app.erros import CodigoErro
from app.relogio import Relogio
from app.usuarios import repositorio
from app.usuarios.esquemas import NovoUsuario, Usuario

# D16 a: restrição do banco → código da ficha.
ERROS_POR_RESTRICAO = MappingProxyType({"usuarios_cpf_unico": CodigoErro.CPF_DUPLICADO})


def cadastrar_usuario(config: Config, relogio: Relogio, novo: NovoUsuario) -> Usuario:
    """Grava o usuário; CPF já cadastrado (após normalização) → `CPF_DUPLICADO`."""
    with violacoes_como_erro(ERROS_POR_RESTRICAO), transacao(config) as conexao:
        return repositorio.inserir(conexao, novo, criado_em=relogio.agora())
