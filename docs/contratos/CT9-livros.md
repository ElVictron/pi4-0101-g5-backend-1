# CT9: livros

| Linha | Valor |
|---|---|
| Fronteira | Banco |
| Quem chama | Backend 1, único módulo que lê e grava a tabela |
| Quem responde | Banco PostgreSQL |
| Atende | E1, E2, E5, E6, E7 e E8 |
| Como chamar | Tabela `livros`, chave `id` |

## Entrada e saída

Os campos gravados são os mesmos campos lidos.

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| id | inteiro | sim | 101 |
| titulo | texto | sim | Fundamentos de Sistemas de Informação |
| autor | texto | sim | Ana Silva |
| isbn | texto | sim | 9780000000001 |
| quantidade_exemplares | inteiro | sim | 3 |
| quantidade_disponivel | inteiro | sim | 2 |
| criado_em | data e hora | sim | 2026-10-13T19:20:00 |

## Erros

| Quando | O que volta |
|---|---|
| ISBN duplicado | O banco recusa a gravação por restrição única |
| Quantidade disponível ficaria menor que zero | O banco recusa a alteração por restrição de integridade |
| Livro referenciado não existe | A operação é recusada por chave estrangeira |
