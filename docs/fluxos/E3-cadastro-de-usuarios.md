# Fluxo do E3: Cadastro de usuários

**Resultado esperado:** O responsável cadastra um usuário com nome, CPF e contato, e ele aparece na lista.

## Passos

1. O responsável preenche nome, CPF e contato no Frontend.
2. O Frontend chama o Backend 1 com cadastrarUsuario (CT3).
3. O Backend 1 valida os campos e verifica se o CPF ainda não existe.
4. O Backend 1 grava o usuário na tabela usuarios (CT10).
5. O Backend 1 responde ao Frontend com o usuário criado (CT3).
6. O Frontend mostra o usuário na lista.

## Diagrama de sequência

```mermaid
sequenceDiagram
    actor Responsavel as Responsável
    participant Frontend
    participant Backend1 as Backend 1 (Python)
    participant Banco as Banco (PostgreSQL)
    Responsavel->>Frontend: informa dados do usuário
    Frontend->>Backend1: CT3 cadastrarUsuario
    Backend1->>Backend1: valida campos e CPF
    Backend1->>Banco: CT10 usuarios (INSERT)
    Banco-->>Backend1: usuário gravado
    Backend1-->>Frontend: resposta do CT3
    Frontend-->>Responsavel: usuário aparece na lista
```

## Contratos usados

CT3 cadastrarUsuario, CT10 usuarios.
