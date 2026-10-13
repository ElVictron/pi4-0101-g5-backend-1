# CT5: registrarEmprestimo

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E5 |
| Como chamar | `POST /emprestimos` |

## Entrada

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| usuarioId | inteiro | sim | 55 |
| livroId | inteiro | sim | 101 |

## Saída

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| emprestimoId | inteiro | sim | 9001 |
| usuarioId | inteiro | sim | 55 |
| livroId | inteiro | sim | 101 |
| status | um de: ativo, devolvido, atrasado | sim | ativo |
| emprestadoEm | data e hora | sim | 2026-10-13T19:20:00 |
| dataLimiteDevolucao | data e hora | sim | 2026-10-28T19:20:00 |
| devolvidoEm | data e hora | não | não tem |

## Erros

| Quando | O que volta |
|---|---|
| Usuário não existe | Erro `USUARIO_NAO_ENCONTRADO` |
| Livro não existe | Erro `LIVRO_NAO_ENCONTRADO` |
| Livro sem exemplar disponível | Erro `LIVRO_INDISPONIVEL` |
