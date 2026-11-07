# CT4: consultarUsuarios

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E4 |
| Como chamar | `GET /usuarios?busca={busca}&pagina={pagina}&tamanho={tamanho}` |
| Convenções | Formato de erro, status HTTP, limites e datas em [00-convencoes.md](00-convencoes.md) |

## Entrada

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| busca | texto | não | Lucas |
| pagina | inteiro | não | 1 |
| tamanho | inteiro | não | 20 |

## Saída

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| usuarios | lista de objeto (UsuarioResumo) | sim | lista com 1 usuário |
| total | inteiro | sim | 1 |
| pagina | inteiro | sim | 1 |
| tamanho | inteiro | sim | 20 |

### Objeto UsuarioResumo

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| id | inteiro | sim | 55 |
| nome | texto | sim | Lucas Joaquim |
| cpf | texto | sim | 12345678900 |
| contato | texto | sim | lucas@email.com |
| emprestimos | lista de objeto (EmprestimoResumo) | sim | lista com 1 empréstimo |

## Erros

| Quando | O que volta |
|---|---|
| Página menor que 1, tamanho fora de 1 a 100, ou valor não inteiro | Erro `PAGINACAO_INVALIDA` |
| Busca com mais de 100 caracteres | Erro `BUSCA_INVALIDA` |
