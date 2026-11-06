"""Regras de negócio de usuários (CT3, CT4)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from app.config import Config
from app.db import transacao, violacoes_como_erro
from app.emprestimos import repositorio as repositorio_emprestimos
from app.emprestimos.esquemas import EmprestimoResumo
from app.erros import CodigoErro
from app.parametros import ConsultaPaginada
from app.relogio import Relogio
from app.usuarios import repositorio
from app.usuarios.esquemas import NovoUsuario, Usuario

# D16 a: restrição do banco → código da ficha.
ERROS_POR_RESTRICAO = MappingProxyType({"usuarios_cpf_unico": CodigoErro.CPF_DUPLICADO})


def cadastrar_usuario(config: Config, relogio: Relogio, novo: NovoUsuario) -> Usuario:
    """Grava o usuário; CPF já cadastrado (após normalização) → `CPF_DUPLICADO`."""
    with violacoes_como_erro(ERROS_POR_RESTRICAO), transacao(config) as conexao:
        return repositorio.inserir(conexao, novo, criado_em=relogio.agora())


_NAO_DIGITO_ASCII = re.compile(r"[^0-9]")


@dataclass(frozen=True)
class UsuarioComEmprestimos:
    usuario: Usuario
    emprestimos: list[EmprestimoResumo]


@dataclass(frozen=True)
class PaginaDeUsuarios:
    usuarios: list[UsuarioComEmprestimos]
    total: int
    agora: datetime


def digitos_do_termo(termo: str | None) -> str | None:
    """Dígitos ASCII do termo, para a busca no CPF (§6, CT4); `None` se não houver."""
    if termo is None:
        return None
    return _NAO_DIGITO_ASCII.sub("", termo) or None


def consultar_usuarios(
    config: Config, relogio: Relogio, consulta: ConsultaPaginada
) -> PaginaDeUsuarios:
    """Página de usuários, `total` e os empréstimos deles: três consultas, um só retrato."""
    digitos = digitos_do_termo(consulta.busca)
    agora = relogio.agora()
    with transacao(config, somente_leitura=True) as conexao:
        usuarios = repositorio.buscar(
            conexao,
            consulta.busca,
            digitos,
            limite=consulta.tamanho,
            deslocamento=consulta.deslocamento,
        )
        total = repositorio.contar(conexao, consulta.busca, digitos)
        emprestimos = repositorio_emprestimos.resumos_dos_usuarios(
            conexao, [usuario.id for usuario in usuarios]
        )

    por_usuario: dict[int, list[EmprestimoResumo]] = {usuario.id: [] for usuario in usuarios}
    for emprestimo in emprestimos:  # já na ordem do CT8
        por_usuario[emprestimo.usuario_id].append(emprestimo)
    return PaginaDeUsuarios(
        usuarios=[UsuarioComEmprestimos(u, por_usuario[u.id]) for u in usuarios],
        total=total,
        agora=agora,
    )
