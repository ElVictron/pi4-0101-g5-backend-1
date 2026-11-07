"""Entrada e saída da API de usuários (CT3; 00-convencoes §4 e §5)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app import validacao
from app.erros import CodigoErro, ErroDominio

TAMANHO_MAXIMO_NOME = 150
TAMANHO_MAXIMO_CONTATO = 120
SEPARADORES_CPF = ". -"
TAMANHOS_CPF = (11,)
# Telefone (§5): removidos só U+0020, parênteses e hífens; depois, um `+` inicial.
SEPARADORES_TELEFONE = " ()-"
DIGITOS_TELEFONE = (10, 13)

# Ordem da tabela de Entrada do CT3 (§4: define qual erro aparece primeiro).
CAMPOS_ENTRADA = ("nome", "cpf", "contato")

_DIGITOS_ASCII = re.compile(r"[0-9]+")
_REMOVER_DO_TELEFONE = str.maketrans("", "", SEPARADORES_TELEFONE)


@dataclass(frozen=True)
class NovoUsuario:
    nome: str
    cpf: str
    contato: str


@dataclass(frozen=True)
class Usuario:
    id: int
    nome: str
    cpf: str
    contato: str
    criado_em: datetime


def e_email(contato: str) -> bool:
    """`algo@dominio.ext`: sem brancos, um `@`, parte local não vazia e domínio com ponto
    que não começa nem termina com ponto (§5)."""
    if any(branco in contato for branco in validacao.BRANCOS) or contato.count("@") != 1:
        return False
    local, dominio = contato.split("@")
    return (
        bool(local) and "." in dominio and not dominio.startswith(".") and not dominio.endswith(".")
    )


def e_telefone(contato: str) -> bool:
    """Sem espaços (U+0020), parênteses, hífens e um `+` inicial: 10 a 13 dígitos (§5)."""
    numero = contato.translate(_REMOVER_DO_TELEFONE).removeprefix("+")
    minimo, maximo = DIGITOS_TELEFONE
    return bool(_DIGITOS_ASCII.fullmatch(numero)) and minimo <= len(numero) <= maximo


def contato(valor: Any, campo: str = "contato") -> str:
    """E-mail ou telefone, até 120 caracteres; devolvido sem os brancos das pontas."""
    limpo = validacao.texto(valor, campo, maximo=TAMANHO_MAXIMO_CONTATO)
    if not (e_email(limpo) or e_telefone(limpo)):
        raise ErroDominio(
            CodigoErro.DADOS_INVALIDOS, f"O campo '{campo}' deve ser um e-mail ou um telefone."
        )
    return limpo


def ler_novo_usuario(dados: Mapping[str, Any]) -> NovoUsuario:
    """Valida o corpo do CT3 na ordem do §4 e devolve os valores normalizados."""
    validacao.exigir_presentes(dados, CAMPOS_ENTRADA)
    return NovoUsuario(
        nome=validacao.texto(dados["nome"], "nome", maximo=TAMANHO_MAXIMO_NOME),
        cpf=validacao.digitos(
            dados["cpf"], "cpf", separadores=SEPARADORES_CPF, tamanhos=TAMANHOS_CPF
        ),
        contato=contato(dados["contato"]),
    )


def usuario_para_json(usuario: Usuario) -> dict[str, Any]:
    """Saída do CT3."""
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "cpf": usuario.cpf,
        "contato": usuario.contato,
    }
