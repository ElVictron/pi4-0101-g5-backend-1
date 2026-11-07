# CT7: listarDisponibilidade

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E7 |
| Como chamar | `GET /livros/disponibilidade?busca={busca}` |
| Convenções | Formato de erro, status HTTP, limites e datas em [00-convencoes.md](00-convencoes.md) |

## Entrada

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| busca | texto | não | sistemas |

## Saída

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| livros | lista de objeto (LivroDisponibilidade) | sim | lista com 2 livros |

### Objeto LivroDisponibilidade

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| id | inteiro | sim | 101 |
| titulo | texto | sim | Fundamentos de Sistemas de Informação |
| quantidadeExemplares | inteiro | sim | 3 |
| quantidadeDisponivel | inteiro | sim | 2 |
| disponivel | booleano | sim | true |

## Erros

| Quando | O que volta |
|---|---|
| Termo de busca com mais de 100 caracteres | Erro `BUSCA_INVALIDA` |
