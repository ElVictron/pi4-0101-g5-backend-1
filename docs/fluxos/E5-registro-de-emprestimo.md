# Fluxo do E5: Registro de empréstimo

**Resultado esperado:** O responsável seleciona um usuário e um livro disponível, e o empréstimo é registrado no sistema.

## Passos

1. O responsável seleciona um usuário e um livro com exemplares disponíveis no Frontend.
2. O Frontend chama o Backend 1 com registrarEmprestimo (CT5).
3. O Backend 1 valida o usuário e o livro e confirma a disponibilidade.
4. O Backend 1 define dataLimiteDevolucao para 15 dias depois do empréstimo.
5. O Backend 1 grava o empréstimo na tabela emprestimos (CT11) e reduz quantidadeDisponivel na tabela livros (CT9).
6. O Backend 1 publica a atualização no Backend 2 (CT12).
7. O Backend 2 distribui bibliotecaAtualizada às telas abertas (CT13).
8. O Backend 1 responde ao Frontend com o empréstimo registrado (CT5).
9. O Frontend mostra o empréstimo e a nova disponibilidade.

## Diagrama de sequência

```mermaid
sequenceDiagram
    actor Responsavel as Responsável
    participant Frontend
    participant Backend1 as Backend 1 (Python)
    participant Banco as Banco (PostgreSQL)
    participant Backend2 as Backend 2 (Python/WebSocket)
    Responsavel->>Frontend: seleciona usuário e livro
    Frontend->>Backend1: CT5 registrarEmprestimo
    Backend1->>Banco: CT10 usuarios (verifica)
    Banco-->>Backend1: usuário válido
    Backend1->>Banco: CT9 livros (verifica e atualiza)
    Banco-->>Backend1: disponibilidade atualizada
    Backend1->>Banco: CT11 emprestimos (INSERT)
    Banco-->>Backend1: empréstimo gravado
    Backend1->>Backend2: CT12 publicarAtualizacao
    Backend2-->>Backend1: evento aceito
    Backend2->>Frontend: CT13 bibliotecaAtualizada
    Backend1-->>Frontend: resposta do CT5
    Frontend-->>Responsavel: empréstimo registrado
```

## Contratos usados

CT5 registrarEmprestimo, CT9 livros, CT10 usuarios, CT11 emprestimos, CT12 publicarAtualizacao, CT13 bibliotecaAtualizada.
