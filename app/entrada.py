"""Leitura do corpo JSON das requisições (00-convencoes §4, item 1; agentes.md D12, D13).

As rotas que recebem corpo usam `corpo_json` como dependência. Vira `DADOS_INVALIDOS`,
antes de qualquer outra regra, o corpo:
- com `Content-Type` diferente de `application/json` (parâmetros como `charset` são aceitos);
- acima de 64 KiB;
- ausente, que não é UTF-8 válido, que não é JSON, aninhado demais para ser lido,
  que não é um objeto JSON, ou com caractere inválido em chave ou valor de texto: metade
  de um par substituto (ex.: `\\ud800` sozinho) ou NUL (`\\u0000`, que o PostgreSQL
  não grava em texto).
"""

from __future__ import annotations

import json
from typing import Any, NoReturn

from fastapi import Request

from app.erros import CodigoErro, ErroDominio
from app.validacao import INTEIRO_MAXIMO

LIMITE_CORPO_BYTES = 64 * 1024
TIPO_JSON = "application/json"

# Inteiro com mais dígitos que isto já passa de qualquer limite da API (§4: máximo
# 2147483647). Em vez de ser convertido, vira `INTEIRO_MAXIMO + 1` com o mesmo sinal:
# o campo recebe o seu próprio código de erro (qualquer `validacao.inteiro` o recusa) e o
# Python não converte números gigantes.
_DIGITOS_MAXIMOS = 18
_FORA_DA_FAIXA = INTEIRO_MAXIMO + 1
_NUL = "\x00"


def _dados_invalidos(mensagem: str) -> ErroDominio:
    return ErroDominio(CodigoErro.DADOS_INVALIDOS, mensagem)


def _recusar_constante(_nome: str) -> NoReturn:
    # `NaN`, `Infinity` e `-Infinity` não são JSON válido.
    raise ValueError("constante não permitida em JSON")


def _ler_inteiro(texto: str) -> int:
    if len(texto.lstrip("-")) > _DIGITOS_MAXIMOS:
        return -_FORA_DA_FAIXA if texto.startswith("-") else _FORA_DA_FAIXA
    return int(texto)


def _texto_invalido(texto: str) -> bool:
    if _NUL in texto:
        return True
    try:
        texto.encode("utf-8")
    except UnicodeEncodeError:  # par substituto incompleto
        return True
    return False


def _tem_caractere_invalido(dados: object) -> bool:
    """Procura, sem recursão, NUL ou par substituto incompleto em chaves e valores."""
    pendentes = [dados]
    while pendentes:
        atual = pendentes.pop()
        if isinstance(atual, str):
            if _texto_invalido(atual):
                return True
        elif isinstance(atual, dict):
            pendentes.extend(atual.keys())
            pendentes.extend(atual.values())
        elif isinstance(atual, list):
            pendentes.extend(atual)
    return False


def verificar_content_type(valor: str | None) -> None:
    """Exige `application/json` (sem diferenciar maiúsculas; parâmetros ignorados)."""
    tipo = (valor or "").split(";", 1)[0].strip().lower()
    if tipo != TIPO_JSON:
        raise _dados_invalidos("O corpo da requisição deve ser enviado como application/json.")


def _corpo_grande_demais() -> ErroDominio:
    return _dados_invalidos(f"O corpo da requisição passa do limite de {LIMITE_CORPO_BYTES} bytes.")


async def ler_corpo_limitado(request: Request, limite: int = LIMITE_CORPO_BYTES) -> bytes:
    """Lê o corpo em partes e para assim que passar de `limite` bytes."""
    tamanho_declarado = request.headers.get("content-length", "").strip()
    if tamanho_declarado.isdigit() and int(tamanho_declarado) > limite:
        raise _corpo_grande_demais()

    partes: list[bytes] = []
    total = 0
    async for parte in request.stream():
        total += len(parte)
        if total > limite:
            raise _corpo_grande_demais()
        partes.append(parte)
    return b"".join(partes)


def interpretar_corpo_json(conteudo: bytes) -> dict[str, Any]:
    """Interpreta o corpo bruto (UTF-8 estrito) como um objeto JSON."""
    try:
        texto = conteudo.decode("utf-8")
    except UnicodeDecodeError:
        raise _dados_invalidos("O corpo da requisição deve estar em UTF-8.") from None
    if not texto.strip():
        raise _dados_invalidos("O corpo da requisição é obrigatório.")
    try:
        dados = json.loads(texto, parse_constant=_recusar_constante, parse_int=_ler_inteiro)
    except (ValueError, RecursionError):
        raise _dados_invalidos("O corpo da requisição não é um JSON válido.") from None
    if not isinstance(dados, dict):
        raise _dados_invalidos("O corpo da requisição deve ser um objeto JSON.")
    if _tem_caractere_invalido(dados):
        raise _dados_invalidos("O corpo da requisição tem caractere inválido em um texto.")
    return dados


async def corpo_json(request: Request) -> dict[str, Any]:
    """Dependência FastAPI: devolve o corpo da requisição como objeto JSON."""
    verificar_content_type(request.headers.get("content-type"))
    return interpretar_corpo_json(await ler_corpo_limitado(request))
