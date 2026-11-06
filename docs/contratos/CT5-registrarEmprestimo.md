# CT5: registrarEmprestimo

| Linha | Valor |
|---|---|
| Fronteira | HTTPS |
| Quem chama | Frontend |
| Quem responde | Backend 1 |
| Atende | E5 |
| Como chamar | `POST /emprestimos` |
| Convenções | Formato de erro, status HTTP, limites e datas em [00-convencoes.md](00-convencoes.md) |

## Entrada

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| usuarioId | inteiro | sim | 55 |
| livroId | inteiro | sim | 101 |

## Saída

| Campo | Tipo | Obrigatório | Exemplo |
|---|---|---|---|
| emprestimoId | inteiro | sim | 9001 |
| usuarioId | inteiro | sim | 55 |
| livroId | inteiro | sim | 101 |
| status | constante: ativo | sim | ativo |
| emprestadoEm | data e hora | sim | 2026-10-13T19:20:00 |
| dataLimiteDevolucao | data e hora | sim | 2026-10-28T19:20:00 |
| devolvidoEm | data e hora | não | não tem |

## Erros

| Quando | O que volta |
|---|---|
| Usuário não existe | Erro `USUARIO_NAO_ENCONTRADO` |
| Livro não existe | Erro `LIVRO_NAO_ENCONTRADO` |
| Livro sem exemplar disponível | Erro `LIVRO_INDISPONIVEL` |
| Campo obrigatório ausente | Erro `CAMPOS_OBRIGATORIOS` |
| `usuarioId` ou `livroId` não é inteiro maior que zero | Erro `DADOS_INVALIDOS` |

## Ordem dos erros de negócio

Depois das validações de entrada (00-convencoes §4), nesta ordem: usuário inexistente → `USUARIO_NAO_ENCONTRADO`; livro inexistente → `LIVRO_NAO_ENCONTRADO`; livro sem exemplar disponível → `LIVRO_INDISPONIVEL`.

## Efeitos

- Grava o empréstimo com status `ativo` e `dataLimiteDevolucao` = `emprestadoEm` + 15 dias.
- Diminui em um a quantidade disponível do livro, na mesma transação.
- Depois de gravar, publica `emprestimo_registrado` no Backend 2 (CT12). Se a publicação falhar, o empréstimo continua registrado e o evento vai para `eventos_pendentes` ([00-convencoes.md](00-convencoes.md), seção 8).
