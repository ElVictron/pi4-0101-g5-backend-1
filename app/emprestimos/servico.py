"""Regras de negócio de empréstimos (CT5)."""

from __future__ import annotations

from types import MappingProxyType

from app.config import Config
from app.db import transacao, violacoes_como_erro
from app.emprestimos import repositorio
from app.emprestimos.esquemas import Emprestimo, NovoEmprestimo, Situacao, data_limite_para
from app.erros import CodigoErro, ErroDominio
from app.eventos.publicador import EMPRESTIMO_REGISTRADO, PublicadorDeEventos, montar_payload
from app.eventos.servico import publicar_ou_guardar
from app.livros import repositorio as repositorio_livros
from app.relogio import Relogio
from app.usuarios import repositorio as repositorio_usuarios

# D16 b: a chave estrangeira é só a rede de segurança (ex.: exclusão no meio da operação).
ERROS_POR_RESTRICAO = MappingProxyType(
    {
        "emprestimos_usuario_existe": CodigoErro.USUARIO_NAO_ENCONTRADO,
        "emprestimos_livro_existe": CodigoErro.LIVRO_NAO_ENCONTRADO,
    }
)


def registrar_emprestimo(
    config: Config,
    relogio: Relogio,
    publicador: PublicadorDeEventos,
    novo: NovoEmprestimo,
) -> Emprestimo:
    """CT5: grava o empréstimo e baixa um exemplar numa transação; depois publica (D6).

    Ordem dos erros de negócio: usuário, livro, exemplar disponível.
    """
    emprestado_em = relogio.agora()
    with violacoes_como_erro(ERROS_POR_RESTRICAO), transacao(config) as conexao:
        if not repositorio_usuarios.existe(conexao, novo.usuario_id):
            raise ErroDominio(CodigoErro.USUARIO_NAO_ENCONTRADO)
        if not repositorio_livros.existe(conexao, novo.livro_id):
            raise ErroDominio(CodigoErro.LIVRO_NAO_ENCONTRADO)
        disponivel = repositorio_livros.baixar_exemplar(conexao, novo.livro_id)
        if disponivel is None:
            # Sem linha no UPDATE: sem exemplar, ou o livro foi excluído no meio do caminho.
            if not repositorio_livros.existe(conexao, novo.livro_id):
                raise ErroDominio(CodigoErro.LIVRO_NAO_ENCONTRADO)
            raise ErroDominio(CodigoErro.LIVRO_INDISPONIVEL)
        emprestimo = repositorio.inserir(
            conexao,
            usuario_id=novo.usuario_id,
            livro_id=novo.livro_id,
            emprestado_em=emprestado_em,
            data_limite_devolucao=data_limite_para(emprestado_em),
        )

    # Só depois do commit (§8): falha na publicação não desfaz o empréstimo.
    publicar_ou_guardar(
        config,
        relogio,
        publicador,
        montar_payload(
            tipo=EMPRESTIMO_REGISTRADO,
            livro_id=emprestimo.livro_id,
            usuario_id=emprestimo.usuario_id,
            emprestimo_id=emprestimo.id,
            status=Situacao.ATIVO.value,
            quantidade_disponivel=disponivel,
            atualizada_em=emprestimo.emprestado_em,
        ),
    )
    return emprestimo
