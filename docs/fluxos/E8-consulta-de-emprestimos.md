# Fluxo do E8: Consulta de empréstimos

**Resultado esperado:** O responsável visualiza os empréstimos ativos, devolvidos e atrasados.

## Passos

1. O responsável abre a consulta de empréstimos e escolhe, opcionalmente, um status.
2. O Frontend chama o Backend 1 com consultarEmprestimos (CT8).
3. O Backend 1 consulta os empréstimos na tabela emprestimos (CT11).
4. O Backend 1 consulta usuários e livros relacionados nas tabelas usuarios e livros (CT10 e CT9).
5. O Backend 1 responde ao Frontend com a lista classificada por status (CT8).
6. O Frontend mostra empréstimos ativos, devolvidos e atrasados.

## Diagrama de sequência

```mermaid
sequenceDiagram
    actor Responsavel as Responsável
    participant Frontend
    participant Backend1 as Backend 1 (Python)
    participant Banco as Banco (PostgreSQL)
    Responsavel->>Frontend: seleciona status de empréstimo
    Frontend->>Backend1: CT8 consultarEmprestimos
    Backend1->>Banco: CT11 emprestimos (SELECT)
    Banco-->>Backend1: empréstimos encontrados
    Backend1->>Banco: CT10 usuarios e CT9 livros
    Banco-->>Backend1: dados relacionados
    Backend1-->>Frontend: resposta do CT8
    Frontend-->>Responsavel: mostra ativos, devolvidos e atrasados
```

## Contratos usados

CT8 consultarEmprestimos, CT9 livros, CT10 usuarios, CT11 emprestimos.
