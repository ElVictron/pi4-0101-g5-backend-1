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

## Regra da situação efetiva

O Backend 1 determina a situação usada na resposta e no filtro `status` com estas regras, nesta ordem:

1. Se `devolvidoEm` estiver preenchido, a situação efetiva é `devolvido`.
2. Se `devolvidoEm` estiver vazio e `dataLimiteDevolucao` já tiver passado, a situação efetiva é `atrasado`.
3. Nos demais casos, a situação efetiva é `ativo`.

Assim, um empréstimo vencido e ainda não devolvido aparece como `atrasado`, mesmo que seu status armazenado ainda seja `ativo`. O filtro `status=atrasado` usa essa mesma regra.

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
