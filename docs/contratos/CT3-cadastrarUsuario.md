# CT3: cadastrarUsuario

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E3 |
| Como chamar | `POST /usuarios` |
| Convenções | Formato de erro, status HTTP, limites e datas em [00-convencoes.md](00-convencoes.md) |

## Entrada

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| nome | texto | sim | Lucas Joaquim |
| cpf | texto | sim | 12345678900 |
| contato | texto | sim | lucas@email.com |

## Saída

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| id | inteiro | sim | 55 |
| nome | texto | sim | Lucas Joaquim |
| cpf | texto | sim | 12345678900 |
| contato | texto | sim | lucas@email.com |

## Erros

| Quando | O que volta |
|---|---|
| CPF já cadastrado | Erro `CPF_DUPLICADO` |
| CPF sem 11 dígitos, contato que não é e-mail nem telefone, nome acima de 150 caracteres, ou campo com tipo errado | Erro `DADOS_INVALIDOS` |
| Campo obrigatório ausente | Erro `CAMPOS_OBRIGATORIOS` |
