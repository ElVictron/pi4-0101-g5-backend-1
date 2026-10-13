# CT2: consultarLivros

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E2 |
| Como chamar | `GET /livros?busca={busca}&pagina={pagina}&tamanho={tamanho}` |

## Entrada

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| busca | texto | não | sistemas |
| pagina | inteiro | não | 1 |
| tamanho | inteiro | não | 20 |

## Saída

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| livros | lista de objeto (LivroResumo) | sim | lista com 2 livros |
| total | inteiro | sim | 2 |
| pagina | inteiro | sim | 1 |
| tamanho | inteiro | sim | 20 |

### Objeto LivroResumo

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| id | inteiro | sim | 101 |
| titulo | texto | sim | Fundamentos de Sistemas de Informação |
| autor | texto | sim | Ana Silva |
| isbn | texto | sim | 9780000000001 |
| quantidadeExemplares | inteiro | sim | 3 |
| quantidadeDisponivel | inteiro | sim | 2 |

## Erros

| Quando | O que volta |
|---|---|
| Página ou tamanho inválidos | Erro `PAGINACAO_INVALIDA` |
| Busca maior que o limite permitido | Erro `BUSCA_INVALIDA` |
