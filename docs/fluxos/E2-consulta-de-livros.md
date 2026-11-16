# Fluxo do E2: Consulta de livros

**Resultado esperado:** O responsável pesquisa um livro e visualiza seus dados e a quantidade disponível.

## Passos

1. O responsável informa um termo de pesquisa no Frontend.
2. O Frontend chama o Backend 1 com consultarLivros (CT2).
3. O Backend 1 consulta a tabela livros usando o termo informado (CT9).
4. O Banco devolve os livros encontrados e suas quantidades.
5. O Backend 1 responde ao Frontend com a lista paginada (CT2).
6. O Frontend mostra título, autor, ISBN e quantidade disponível.

## Diagrama de sequência

```mermaid
sequenceDiagram
    actor Responsavel as Responsável
    participant Frontend
    participant Backend1 as Backend 1 (Python)
    participant Banco as Banco (PostgreSQL)
    Responsavel->>Frontend: pesquisa um livro
    Frontend->>Backend1: CT2 consultarLivros
    Backend1->>Banco: CT9 livros (SELECT)
    Banco-->>Backend1: livros encontrados
    Backend1-->>Frontend: resposta do CT2
    Frontend-->>Responsavel: mostra dados e quantidade disponível
```

## Contratos usados

CT2 consultarLivros, CT9 livros.
