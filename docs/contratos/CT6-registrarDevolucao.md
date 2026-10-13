# CT6: registrarDevolucao

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E6 |
| Como chamar | `PATCH /emprestimos/{emprestimoId}/devolucao` |

## Entrada

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| emprestimoId | inteiro | sim | 9001 |

## Saída

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| emprestimoId | inteiro | sim | 9001 |
| livroId | inteiro | sim | 101 |
| status | um de: ativo, devolvido, atrasado | sim | devolvido |
| devolvidoEm | data e hora | sim | 2026-10-15T16:30:00 |
| quantidadeDisponivel | inteiro | sim | 3 |

## Erros

| Quando | O que volta |
|---|---|
| Empréstimo não existe | Erro `EMPRESTIMO_NAO_ENCONTRADO` |
| Empréstimo já devolvido | Erro `EMPRESTIMO_JA_DEVOLVIDO` |
