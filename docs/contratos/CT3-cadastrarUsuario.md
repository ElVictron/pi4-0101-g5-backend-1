# CT3: cadastrarUsuario

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E3 |
| Como chamar | `POST /usuarios` |

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
| CPF ou contato inválido | Erro `DADOS_INVALIDOS` |
| Campo obrigatório ausente | Erro `CAMPOS_OBRIGATORIOS` |
