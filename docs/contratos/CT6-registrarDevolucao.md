# CT6: registrarDevolucao

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E6 |
| Como chamar | `PATCH /emprestimos/{emprestimoId}/devolucao` |
| Convenções | Formato de erro, status HTTP, limites e datas em [00-convencoes.md](00-convencoes.md) |

## Entrada

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| emprestimoId | inteiro | sim | 9001 |

## Pré-condições e regras

- O empréstimo identificado por `emprestimoId` deve existir.
- A devolução é permitida para um empréstimo com status efetivo `ativo` ou `atrasado`, desde que ainda não tenha sido devolvido.
- Ao concluir, o Backend 1 registra `devolvidoEm`, grava o status `devolvido` e atualiza a quantidade disponível do livro.
- Um empréstimo já devolvido não pode ser devolvido novamente.
- Depois de gravar, publica `devolucao_registrada` no Backend 2 (CT12), com a mesma regra de falha do CT5.

## Detalhes

- `emprestimoId` vem só do caminho. A rota não exige corpo; se vier corpo (de qualquer tipo), ele é ignorado.
- `emprestimoId` que não é inteiro ≥ 1 no formato `[0-9]+` (dígitos ASCII, até 2147483647) é tratado como empréstimo inexistente → `EMPRESTIMO_NAO_ENCONTRADO`.
- Ordem: empréstimo inexistente → `EMPRESTIMO_NAO_ENCONTRADO`; já devolvido → `EMPRESTIMO_JA_DEVOLVIDO`.
- `devolvidoEm` = agora do relógio da aplicação; a quantidade disponível do livro sobe exatamente 1, e `quantidadeDisponivel` na resposta é o valor depois dessa alta.
- Duas devoluções simultâneas do mesmo empréstimo: exatamente uma tem sucesso; a outra recebe `EMPRESTIMO_JA_DEVOLVIDO`, e a quantidade sobe uma vez só.
- Depois de gravar, publica no Backend 2 (CT12) `tipo` `devolucao_registrada`, `status` `devolvido`, `livroId`, `usuarioId`, `emprestimoId`, `quantidadeDisponivel` (depois da alta) e `atualizadaEm` = `devolvidoEm`, com a mesma regra de falha do CT5 (00-convencoes §8).
- Erros não publicam nada.

## Saída

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| emprestimoId | inteiro | sim | 9001 |
| livroId | inteiro | sim | 101 |
| status | constante: devolvido | sim | devolvido |
| devolvidoEm | data e hora | sim | 2026-10-15T16:30:00 |
| quantidadeDisponivel | inteiro | sim | 3 |

## Erros

| Quando | O que volta |
|---|---|
| Empréstimo não existe | Erro `EMPRESTIMO_NAO_ENCONTRADO` |
| Empréstimo já devolvido | Erro `EMPRESTIMO_JA_DEVOLVIDO` |
