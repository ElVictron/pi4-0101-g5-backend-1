# CT10: usuarios

| Linha | Valor |
|---|---|
| Fronteira | Banco |
| Quem chama | Backend 1, único módulo que lê e grava a tabela |
| Quem responde | Banco PostgreSQL |
| Atende | E3, E4 e E5 |
| Como chamar | Tabela `usuarios`, chave `id` |

## Entrada e saída

Os campos gravados são os mesmos campos lidos.

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| id | inteiro | sim | 55 |
| nome | texto | sim | Lucas Joaquim |
| cpf | texto | sim | 12345678900 |
| contato | texto | sim | lucas@email.com |
| criado_em | data e hora | sim | 2026-10-13T19:20:00 |

## Erros

| Quando | O que volta |
|---|---|
| CPF duplicado | O banco recusa a gravação por restrição única |
| Usuário referenciado não existe | A operação é recusada por chave estrangeira |
