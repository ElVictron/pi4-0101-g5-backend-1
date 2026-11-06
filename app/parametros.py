"""Parâmetros de consulta (00-convencoes §6; D13), reutilizados pelas consultas.

A query string é lida crua (`scope["query_string"]`), e não por `request.query_params`:
o Starlette decodifica `%FF` como U+FFFD e ficaria impossível distinguir UTF-8 inválido.

- nomes diferenciam maiúsculas; parâmetros desconhecidos são ignorados (nem decodificados);
- parâmetro repetido: vale o primeiro valor;
- vazio ou só com brancos (§4) = não informado;
- texto com UTF-8 inválido, NUL ou metade de par substituto → código do parâmetro;
- inteiros só `-?[0-9]+` (ASCII), até 2147483647.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from urllib.parse import unquote_to_bytes

from app.erros import CodigoErro, ErroDominio
from app.validacao import BRANCOS, INTEIRO_MAXIMO

TAMANHO_MAXIMO_BUSCA = 100
PAGINA_PADRAO = 1
TAMANHO_PADRAO = 20
TAMANHO_MAXIMO_PAGINA = 100

_INTEIRO = re.compile(r"-?[0-9]+")
_DIGITOS_MAXIMOS = len(str(INTEIRO_MAXIMO))


def primeiros_valores(query_string: bytes, nomes: Collection[str]) -> dict[str, bytes]:
    """Primeiro valor (bytes já sem `%xx` e `+`) de cada parâmetro de `nomes` presente."""
    procurados = {nome.encode("ascii"): nome for nome in nomes}
    encontrados: dict[str, bytes] = {}
    for par in query_string.split(b"&"):
        chave, _, valor = par.partition(b"=")
        nome = procurados.get(unquote_to_bytes(chave.replace(b"+", b" ")))
        if nome is not None and nome not in encontrados:
            encontrados[nome] = unquote_to_bytes(valor.replace(b"+", b" "))
    return encontrados


def texto_do_parametro(bruto: bytes | None, nome: str, codigo: CodigoErro) -> str | None:
    """Texto do parâmetro sem os brancos das pontas; `None` se ausente ou em branco."""
    if bruto is None:
        return None
    try:
        texto = bruto.decode("utf-8")  # estrito: recusa bytes inválidos e substitutos
    except UnicodeDecodeError:
        raise ErroDominio(codigo, f"O parâmetro '{nome}' não é um texto UTF-8 válido.") from None
    if "\x00" in texto:
        raise ErroDominio(codigo, f"O parâmetro '{nome}' tem caractere inválido.")
    return texto.strip(BRANCOS) or None


def ler_busca(bruto: bytes | None, *, codigo: CodigoErro = CodigoErro.BUSCA_INVALIDA) -> str | None:
    """`busca`: até 100 caracteres depois de cortar as pontas; vazio = sem filtro."""
    termo = texto_do_parametro(bruto, "busca", codigo)
    if termo is not None and len(termo) > TAMANHO_MAXIMO_BUSCA:
        raise ErroDominio(
            codigo, f"O parâmetro 'busca' deve ter no máximo {TAMANHO_MAXIMO_BUSCA} caracteres."
        )
    return termo


def ler_inteiro(
    bruto: bytes | None,
    nome: str,
    *,
    padrao: int,
    minimo: int,
    maximo: int = INTEIRO_MAXIMO,
    codigo: CodigoErro,
) -> int:
    """Inteiro `-?[0-9]+` entre `minimo` e `maximo`; ausente ou em branco = `padrao`."""
    texto = texto_do_parametro(bruto, nome, codigo)
    if texto is None:
        return padrao
    invalido = ErroDominio(
        codigo, f"O parâmetro '{nome}' deve ser um inteiro entre {minimo} e {maximo}."
    )
    # Zeros à esquerda não contam (`01` vale 1); mais dígitos que o máximo já é fora da faixa
    # (e evita converter números gigantes).
    if not _INTEIRO.fullmatch(texto) or len(texto.lstrip("-").lstrip("0")) > _DIGITOS_MAXIMOS:
        raise invalido
    valor = int(texto)
    if not minimo <= valor <= maximo:
        raise invalido
    return valor


@dataclass(frozen=True)
class ConsultaPaginada:
    busca: str | None
    pagina: int
    tamanho: int

    @property
    def deslocamento(self) -> int:
        """`OFFSET` da página; cabe em `bigint` (máximo ≈ 2,1 × 10¹¹)."""
        return (self.pagina - 1) * self.tamanho


def ler_consulta_paginada(valores: Mapping[str, bytes]) -> ConsultaPaginada:
    """CT2 e CT4: `busca`, `pagina`, `tamanho`, verificados nessa ordem."""
    busca = ler_busca(valores.get("busca"))
    pagina = ler_inteiro(
        valores.get("pagina"),
        "pagina",
        padrao=PAGINA_PADRAO,
        minimo=1,
        codigo=CodigoErro.PAGINACAO_INVALIDA,
    )
    tamanho = ler_inteiro(
        valores.get("tamanho"),
        "tamanho",
        padrao=TAMANHO_PADRAO,
        minimo=1,
        maximo=TAMANHO_MAXIMO_PAGINA,
        codigo=CodigoErro.PAGINACAO_INVALIDA,
    )
    return ConsultaPaginada(busca=busca, pagina=pagina, tamanho=tamanho)


PARAMETROS_PAGINADOS = ("busca", "pagina", "tamanho")
