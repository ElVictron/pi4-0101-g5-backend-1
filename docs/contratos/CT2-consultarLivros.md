# CT2: consultarLivros

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E2 |
| Como chamar | `GET /livros?busca={busca}&pagina={pagina}&tamanho={tamanho}` |
| Convenções | Formato de erro, status HTTP, limites e datas em [00-convencoes.md](00-convencoes.md) |

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
| Página menor que 1, tamanho fora de 1 a 100, ou valor não inteiro | Erro `PAGINACAO_INVALIDA` |
| Busca com mais de 100 caracteres | Erro `BUSCA_INVALIDA` |
