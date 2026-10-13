# CT11: emprestimos

| Linha | Valor |
|---|---|
| Fronteira | Banco |
| Quem chama | Backend 1, único módulo que lê e grava a tabela |
| Quem responde | Banco PostgreSQL |
| Atende | E4, E5, E6 e E8 |
| Como chamar | Tabela `emprestimos`, chave `id` |

## Entrada e saída

Os campos gravados são os mesmos campos lidos.

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| id | inteiro | sim | 9001 |
| usuario_id | inteiro | sim | 55 |
| livro_id | inteiro | sim | 101 |
| status | um de: ativo, devolvido, atrasado | sim | ativo |
| emprestado_em | data e hora | sim | 2026-10-13T19:20:00 |
| data_limite_devolucao | data e hora | sim | 2026-10-28T19:20:00 |
| devolvido_em | data e hora | não | não tem |

## Erros

| Quando | O que volta |
|---|---|
| Usuário ou livro não existe | A operação é recusada por chave estrangeira |
| Empréstimo já devolvido | O Backend 1 não envia a atualização ao banco |
| Status fora da lista | O banco recusa a gravação por restrição de domínio |
