"""Validação de campos do corpo JSON, reutilizada pelos cadastros (00-convencoes §4 e §5).

Ordem do §4: primeiro `exigir_presentes` em todos os campos (item 2, `CAMPOS_OBRIGATORIOS`),
depois cada campo na ordem da tabela de Entrada do contrato (item 3).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from app.erros import CodigoErro, ErroDominio

# §4: espaços em branco das pontas = espaço, tabulação e quebra de linha.
BRANCOS = " \t\n\r"
# §4: maior inteiro de entrada (limite do `integer` do PostgreSQL).
INTEIRO_MAXIMO = 2_147_483_647

_SO_DIGITOS_ASCII = re.compile(r"[0-9]+")


def _invalido(campo: str, motivo: str, codigo: CodigoErro) -> ErroDominio:
    return ErroDominio(codigo, f"O campo '{campo}' {motivo}.")


def exigir_presentes(dados: Mapping[str, Any], campos: Sequence[str]) -> None:
    """Item 2 do §4: cada campo precisa existir, não ser `null` nem texto em branco."""
    for campo in campos:
        valor = dados.get(campo)
        if valor is None or (isinstance(valor, str) and not valor.strip(BRANCOS)):
            raise ErroDominio(CodigoErro.CAMPOS_OBRIGATORIOS, f"O campo '{campo}' é obrigatório.")


def texto(
    valor: Any,
    campo: str,
    *,
    maximo: int,
    codigo: CodigoErro = CodigoErro.DADOS_INVALIDOS,
) -> str:
    """Texto sem os brancos das pontas, com no máximo `maximo` caracteres."""
    if not isinstance(valor, str):
        raise _invalido(campo, "deve ser um texto", codigo)
    limpo = valor.strip(BRANCOS)
    if len(limpo) > maximo:
        raise _invalido(campo, f"deve ter no máximo {maximo} caracteres", codigo)
    return limpo


def inteiro(
    valor: Any,
    campo: str,
    *,
    minimo: int,
    maximo: int = INTEIRO_MAXIMO,
    codigo: CodigoErro = CodigoErro.DADOS_INVALIDOS,
) -> int:
    """Só número JSON inteiro (nem booleano, nem decimal, nem texto), entre os limites."""
    if type(valor) is not int:
        raise _invalido(campo, "deve ser um número inteiro", codigo)
    if not minimo <= valor <= maximo:
        raise _invalido(campo, f"deve estar entre {minimo} e {maximo}", codigo)
    return valor


def digitos(
    valor: Any,
    campo: str,
    *,
    separadores: str,
    tamanhos: Sequence[int],
    codigo: CodigoErro = CodigoErro.DADOS_INVALIDOS,
) -> str:
    """Texto que, sem brancos nas pontas e sem `separadores`, tem só dígitos 0-9.

    A quantidade de dígitos precisa ser uma das `tamanhos`. Devolve só os dígitos
    (forma normalizada, usada para gravar e para comparar duplicidade).
    """
    if not isinstance(valor, str):
        raise _invalido(campo, "deve ser um texto", codigo)
    normalizado = valor.strip(BRANCOS).translate(str.maketrans("", "", separadores))
    if not _SO_DIGITOS_ASCII.fullmatch(normalizado) or len(normalizado) not in tamanhos:
        quantos = " ou ".join(str(t) for t in tamanhos)
        raise _invalido(campo, f"deve ter {quantos} dígitos", codigo)
    return normalizado
