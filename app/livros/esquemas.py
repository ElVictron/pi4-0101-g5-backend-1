"""Entrada e saída da API de livros (CT1; 00-convencoes §4 e §5)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app import validacao
from app.erros import CodigoErro

TAMANHO_MAXIMO_TEXTO = 200
SEPARADORES_ISBN = "- "
TAMANHOS_ISBN = (10, 13)

# Ordem da tabela de Entrada do CT1 (§4: define qual erro aparece primeiro).
CAMPOS_ENTRADA = ("titulo", "autor", "isbn", "quantidadeExemplares")


@dataclass(frozen=True)
class NovoLivro:
    titulo: str
    autor: str
    isbn: str
    quantidade_exemplares: int


@dataclass(frozen=True)
class Livro:
    id: int
    titulo: str
    autor: str
    isbn: str
    quantidade_exemplares: int
    quantidade_disponivel: int
    criado_em: datetime


def ler_novo_livro(dados: Mapping[str, Any]) -> NovoLivro:
    """Valida o corpo do CT1 na ordem do §4 e devolve os valores normalizados."""
    validacao.exigir_presentes(dados, CAMPOS_ENTRADA)
    return NovoLivro(
        titulo=validacao.texto(dados["titulo"], "titulo", maximo=TAMANHO_MAXIMO_TEXTO),
        autor=validacao.texto(dados["autor"], "autor", maximo=TAMANHO_MAXIMO_TEXTO),
        isbn=validacao.digitos(
            dados["isbn"], "isbn", separadores=SEPARADORES_ISBN, tamanhos=TAMANHOS_ISBN
        ),
        quantidade_exemplares=validacao.inteiro(
            dados["quantidadeExemplares"],
            "quantidadeExemplares",
            minimo=1,
            codigo=CodigoErro.QUANTIDADE_INVALIDA,
        ),
    )


def livro_para_json(livro: Livro) -> dict[str, Any]:
    """Saída do CT1."""
    return {
        "id": livro.id,
        "titulo": livro.titulo,
        "autor": livro.autor,
        "isbn": livro.isbn,
        "quantidadeExemplares": livro.quantidade_exemplares,
        "quantidadeDisponivel": livro.quantidade_disponivel,
    }
