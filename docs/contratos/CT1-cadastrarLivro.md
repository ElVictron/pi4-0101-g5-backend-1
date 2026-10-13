# CT1: cadastrarLivro

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E1 |
| Como chamar | `POST /livros` |

## Entrada

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| titulo | texto | sim | Fundamentos de Sistemas de Informação |
| autor | texto | sim | Ana Silva |
| isbn | texto | sim | 9780000000001 |
| quantidadeExemplares | inteiro | sim | 3 |

## Saída

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| id | inteiro | sim | 101 |
| titulo | texto | sim | Fundamentos de Sistemas de Informação |
| autor | texto | sim | Ana Silva |
| isbn | texto | sim | 9780000000001 |
| quantidadeExemplares | inteiro | sim | 3 |
| quantidadeDisponivel | inteiro | sim | 3 |

## Erros

| Quando | O que volta |
|---|---|
| ISBN já cadastrado | Erro `ISBN_DUPLICADO` |
| Quantidade menor que zero ou igual a zero | Erro `QUANTIDADE_INVALIDA` |
| Campo obrigatório ausente | Erro `CAMPOS_OBRIGATORIOS` |
