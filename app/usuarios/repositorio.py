"""SQL da tabela `usuarios` (CT10). Recebe uma conexão já dentro de `transacao`."""

from __future__ import annotations

from datetime import datetime

from psycopg import sql

from app.db import Conexao, filtro_de_busca, ordem_alfabetica
from app.usuarios.esquemas import NovoUsuario, Usuario

_COLUNAS = sql.SQL("id, nome, cpf, contato, criado_em")
# Ordem do §6: por nome (sem caixa nem acento, depois texto exato) e depois id.
_ORDEM = sql.SQL("ORDER BY {}").format(ordem_alfabetica("nome"))
# CT4 em detalhe (§6): nome contém o termo, ou CPF contém os dígitos do termo.
_FILTRO_NOME = filtro_de_busca(["nome"])
_FILTRO_CPF = sql.SQL("cpf LIKE %(padrao_cpf)s")


def _onde(termo: str | None, digitos: str | None) -> sql.Composable:
    if termo is None:
        return sql.SQL("")
    if not digitos:
        return sql.SQL("WHERE {}").format(_FILTRO_NOME)
    return sql.SQL("WHERE ({}) OR {}").format(_FILTRO_NOME, _FILTRO_CPF)


def _parametros(termo: str | None, digitos: str | None) -> dict[str, object]:
    # Só dígitos ASCII: nenhum caractere especial do LIKE precisa de escape.
    return {"termo": termo, "padrao_cpf": f"%{digitos}%" if digitos else None}


def inserir(conexao: Conexao, novo: NovoUsuario, criado_em: datetime) -> Usuario:
    linha = conexao.execute(
        "INSERT INTO usuarios (nome, cpf, contato, criado_em) VALUES (%s, %s, %s, %s)"
        " RETURNING id, nome, cpf, contato, criado_em",
        (novo.nome, novo.cpf, novo.contato, criado_em),
    ).fetchone()
    assert linha is not None
    return Usuario(**linha)


def buscar(
    conexao: Conexao,
    termo: str | None,
    digitos: str | None,
    *,
    limite: int,
    deslocamento: int,
) -> list[Usuario]:
    """Página de usuários do filtro, na ordem do §6."""
    consulta = sql.SQL(
        "SELECT {} FROM usuarios {} {} LIMIT %(limite)s OFFSET %(deslocamento)s"
    ).format(_COLUNAS, _onde(termo, digitos), _ORDEM)
    parametros = _parametros(termo, digitos) | {"limite": limite, "deslocamento": deslocamento}
    return [Usuario(**linha) for linha in conexao.execute(consulta, parametros).fetchall()]


def contar(conexao: Conexao, termo: str | None, digitos: str | None) -> int:
    """Quantos usuários o filtro encontra (o `total` do CT4)."""
    consulta = sql.SQL("SELECT count(*) AS total FROM usuarios {}").format(_onde(termo, digitos))
    linha = conexao.execute(consulta, _parametros(termo, digitos)).fetchone()
    assert linha is not None
    return linha["total"]
