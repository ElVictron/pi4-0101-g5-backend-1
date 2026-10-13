# CT7: listarDisponibilidade

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E7 |
| Como chamar | `GET /livros/disponibilidade?busca={busca}` |

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
| Termo de busca inválido | Erro `BUSCA_INVALIDA` |
