# Fluxo do E7: Controle de disponibilidade

**Resultado esperado:** O sistema apresenta quais livros possuem exemplares disponíveis para empréstimo.

## Passos

1. O responsável abre o painel de disponibilidade no Frontend.
2. O Frontend chama o Backend 1 com listarDisponibilidade (CT7).
3. O Backend 1 consulta a tabela livros (CT9) filtrando quantidadeDisponivel maior que zero.
4. O Banco devolve os livros e as quantidades disponíveis.
5. O Backend 1 responde ao Frontend com a lista de disponibilidade (CT7).
6. O Frontend marca quais livros podem ser emprestados.

## Diagrama de sequência

```mermaid
sequenceDiagram
    actor Responsavel as Responsável
    participant Frontend
    participant Backend1 as Backend 1 (Python)
    participant Banco as Banco (PostgreSQL)
    Responsavel->>Frontend: abre painel de disponibilidade
    Frontend->>Backend1: CT7 listarDisponibilidade
    Backend1->>Banco: CT9 livros (SELECT disponíveis)
    Banco-->>Backend1: livros e quantidades
    Backend1-->>Frontend: resposta do CT7
    Frontend-->>Responsavel: mostra livros disponíveis
```

## Contratos usados

CT7 listarDisponibilidade, CT9 livros.
