# CT8: consultarEmprestimos

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E8 |
| Como chamar | `GET /emprestimos?status={status}&busca={busca}` |

## Entrada

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| status | um de: ativo, devolvido, atrasado | não | ativo |
| busca | texto | não | Lucas |

## Saída

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| emprestimos | lista de objeto (EmprestimoResumo) | sim | lista com 2 empréstimos |
| total | inteiro | sim | 2 |

### Objeto EmprestimoResumo

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| emprestimoId | inteiro | sim | 9001 |
| usuarioId | inteiro | sim | 55 |
| usuarioNome | texto | sim | Lucas Joaquim |
| livroId | inteiro | sim | 101 |
| livroTitulo | texto | sim | Fundamentos de Sistemas de Informação |
| status | um de: ativo, devolvido, atrasado | sim | ativo |
| emprestadoEm | data e hora | sim | 2026-10-13T19:20:00 |
| dataLimiteDevolucao | data e hora | sim | 2026-10-28T19:20:00 |
| devolvidoEm | data e hora | não | não tem |

## Erros

| Quando | O que volta |
|---|---|
| Status inválido | Erro `STATUS_INVALIDO` |
| Busca maior que o limite permitido | Erro `BUSCA_INVALIDA` |
