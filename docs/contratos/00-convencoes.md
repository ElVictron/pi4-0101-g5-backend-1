# Convenções comuns dos contratos do Backend 1

Este documento fecha as lacunas que os contratos CT1 a CT11 deixam em aberto (formato de erro, status HTTP, limites, normalização, datas, ordenação). Vale para todas as operações do Backend 1. Em caso de conflito, o contrato específico (CTn) prevalece sobre este arquivo.

Origem: decisões P1 a P14 e D10 do `agentes.md`, aprovadas em 06/11/2026.

## 1. Transporte

- **HTTPS** entre Frontend e Backend 1 e entre Backend 1 e Backend 2 (CT12). O Backend 2 entrega as atualizações ao Frontend por **WSS** (CT13).
- O TLS do servidor é ligado por configuração (`SSL_CERTFILE` e `SSL_KEYFILE` no Uvicorn). Os testes automatizados falam com a aplicação dentro do processo, sem TLS.
- Corpo de requisição e resposta em JSON UTF-8. Nomes de campo em camelCase na API e snake_case no banco.

## 2. Status HTTP de sucesso

| Operação | Status |
|---|---|
| `POST /livros`, `POST /usuarios`, `POST /emprestimos` | `201 Created` |
| `GET` (todas as consultas) | `200 OK` |
| `PATCH /emprestimos/{emprestimoId}/devolucao` | `200 OK` |

## 3. Formato de erro

Toda resposta de erro tem este corpo:

```json
{"erro": {"codigo": "ISBN_DUPLICADO", "mensagem": "Já existe um livro com este ISBN."}}
```

- `codigo` é exatamente o código da ficha. `mensagem` é texto livre em português, para exibição.
- Mapeamento de status HTTP:

| Status | Códigos |
|---|---|
| `400 Bad Request` | `CAMPOS_OBRIGATORIOS`, `DADOS_INVALIDOS`, `QUANTIDADE_INVALIDA`, `PAGINACAO_INVALIDA`, `BUSCA_INVALIDA`, `STATUS_INVALIDO` |
| `404 Not Found` | `USUARIO_NAO_ENCONTRADO`, `LIVRO_NAO_ENCONTRADO`, `EMPRESTIMO_NAO_ENCONTRADO`, `ROTA_NAO_ENCONTRADA` |
| `409 Conflict` | `ISBN_DUPLICADO`, `CPF_DUPLICADO`, `LIVRO_INDISPONIVEL`, `EMPRESTIMO_JA_DEVOLVIDO` |
| `500 Internal Server Error` | `ERRO_INTERNO` (falha não prevista; nunca expõe detalhes internos) |

- `ROTA_NAO_ENCONTRADA` (rota inexistente) e `ERRO_INTERNO` são códigos de infraestrutura, não de ficha.
- Método não permitido numa rota existente: `405`, mesmo formato de corpo, código `ROTA_NAO_ENCONTRADA`.

## 4. Validação de entrada (corpo JSON)

Ordem de verificação. A primeira regra que falhar define o erro:

1. Corpo ausente, que não é JSON, ou que não é um objeto JSON → `DADOS_INVALIDOS`.
2. Campo obrigatório ausente, `null`, ou texto vazio depois de remover espaços das pontas → `CAMPOS_OBRIGATORIOS`.
3. Tipo, formato ou tamanho inválido → o código específico da ficha (`QUANTIDADE_INVALIDA` para a quantidade de exemplares) ou, nos demais campos, `DADOS_INVALIDOS`.
4. Regras que dependem do banco (duplicidade, existência, disponibilidade) → código da ficha.

Regras gerais:

- Campos de texto: espaços nas pontas são removidos antes de validar e gravar. Um campo de texto que chega com outro tipo (número, booleano, lista) é `DADOS_INVALIDOS`.
- Campos inteiros: só número JSON inteiro. Booleano (`true`), decimal (`3.5`, `3.0`) ou texto (`"3"`) não são aceitos.
- Campos desconhecidos no corpo são ignorados.

## 5. Formatos e limites

| Campo | Regra | Erro |
|---|---|---|
| `titulo`, `autor` (CT1) | texto de 1 a 200 caracteres | `DADOS_INVALIDOS` |
| `isbn` (CT1) | hífens e espaços removidos; resultado só com dígitos, 10 ou 13 dígitos. Dígito verificador **não** é conferido. É gravado e devolvido normalizado | `DADOS_INVALIDOS` |
| `quantidadeExemplares` (CT1) | inteiro ≥ 1 | `QUANTIDADE_INVALIDA` |
| `nome` (CT3) | texto de 1 a 150 caracteres | `DADOS_INVALIDOS` |
| `cpf` (CT3) | pontos, traço e espaços removidos; resultado com exatamente 11 dígitos. Dígitos verificadores **não** são conferidos (o exemplo `12345678900` dos contratos não passaria). É gravado e devolvido normalizado | `DADOS_INVALIDOS` |
| `contato` (CT3) | até 120 caracteres; e-mail no formato `algo@dominio.ext` (sem espaços, um `@`, ao menos um ponto depois do `@`) **ou** telefone: depois de remover espaços, parênteses, hífens e um `+` inicial, só dígitos, com 10 a 13 dígitos. Gravado como recebido, sem os espaços das pontas | `DADOS_INVALIDOS` |
| `usuarioId`, `livroId` (CT5) | inteiro ≥ 1 | `DADOS_INVALIDOS` |
| `emprestimoId` (CT6, no caminho) | inteiro ≥ 1; qualquer outro valor é tratado como empréstimo inexistente | `EMPRESTIMO_NAO_ENCONTRADO` |

Duplicidade de ISBN e CPF é avaliada **depois** da normalização: `978-0-00-000000-1` e `9780000000001` são o mesmo ISBN.

## 6. Parâmetros de consulta

| Parâmetro | Regra | Erro |
|---|---|---|
| `busca` | opcional; espaços das pontas removidos; vazio = sem filtro; até 100 caracteres | `BUSCA_INVALIDA` |
| `pagina` | opcional, padrão `1`; inteiro ≥ 1 | `PAGINACAO_INVALIDA` |
| `tamanho` | opcional, padrão `20`; inteiro de 1 a 100 | `PAGINACAO_INVALIDA` |
| `status` (CT8) | opcional; um de `ativo`, `devolvido`, `atrasado` | `STATUS_INVALIDO` |

- A busca de texto não diferencia maiúsculas de minúsculas nem acentos (`sistemas` encontra `Sistemas de Informação`; `informacao` encontra `Informação`), e procura o termo em qualquer posição do campo.
- Página além da última: lista vazia, com `total` correto. Não é erro.

| Operação | Onde a busca procura | Ordem do resultado |
|---|---|---|
| CT2 consultarLivros | título, autor ou ISBN | título, depois `id` (crescente) |
| CT4 consultarUsuarios | nome; ou CPF, comparando só os dígitos do termo, quando o termo tem algum dígito | nome, depois `id` |
| CT7 listarDisponibilidade | título, autor ou ISBN | título, depois `id` |
| CT8 consultarEmprestimos | nome do usuário ou título do livro | `emprestadoEm` mais recente primeiro, depois `id` decrescente |

- Os empréstimos dentro de cada usuário (CT4) seguem a ordem do CT8 e incluem todas as situações.
- CT7 e CT8 não são paginados.

## 7. Datas e situação do empréstimo

- Datas e horas no formato `AAAA-MM-DDTHH:MM:SS`, sem fuso e sem frações de segundo, no horário de `America/Sao_Paulo`.
- O banco usa `timestamp without time zone` com o mesmo horário.
- O "agora" da aplicação vem de um relógio injetável, para que os testes fixem o instante.
- `dataLimiteDevolucao` = `emprestadoEm` + 15 dias, no mesmo horário.
- Situação efetiva (CT8): `devolvido` se `devolvidoEm` estiver preenchido; senão `atrasado` se o agora for **depois** de `dataLimiteDevolucao`; senão `ativo`. No instante exato da data limite, o empréstimo ainda é `ativo`.
- Campo opcional sem valor (ex.: `devolvidoEm` de um empréstimo não devolvido) vem presente e com `null`.

## 8. Publicação de eventos no Backend 2 (CT12)

- O Backend 1 chama `POST {BACKEND2_URL}/eventos/biblioteca` **depois** de confirmar a gravação no banco.
- Payload: `tipo`, `livroId`, `usuarioId`, `emprestimoId`, `status`, `quantidadeDisponivel`, `atualizadaEm`, como no CT12. O Backend 1 só envia `status` `ativo` (empréstimo) ou `devolvido` (devolução).
- Conta como falha: erro de conexão, timeout (`BACKEND2_TIMEOUT_SEGUNDOS`, padrão 3), resposta fora de 2xx, corpo que não é JSON, ou `aceito` diferente de `true`. Com `BACKEND2_URL` não configurado, todo evento conta como falha.
- Em caso de falha, a operação do cliente **não** falha: a resposta continua de sucesso e o evento é gravado em `eventos_pendentes`.
- `eventos_pendentes`: `id`, `payload` (JSON do CT12), `tentativas` (começa em 1), `ultimo_erro` (texto), `criado_em`, `atualizado_em`.
- `python -m app.reenviar_eventos` tenta reenviar cada pendente na ordem de criação; apaga a linha em caso de sucesso; em caso de falha, soma 1 em `tentativas` e atualiza `ultimo_erro`. Termina com código de saída 0 se todos foram enviados, 1 se algum continuou pendente.
- TLS com o Backend 2: verificação sempre ligada por padrão (`BACKEND2_VERIFY_TLS=true`); certificado próprio por `BACKEND2_CA_BUNDLE`.

## 9. Rotas de infraestrutura

- `GET /saude` → `200` com `{"status": "ok"}`. Não consulta o banco.
- CORS: origens permitidas em `CORS_ORIGENS`, separadas por vírgula; vazio = nenhuma origem externa.

## 10. Configuração (variáveis de ambiente)

| Variável | Padrão | Uso |
|---|---|---|
| `DATABASE_URL` | — (obrigatória) | conexão PostgreSQL |
| `BACKEND2_URL` | vazio | base do Backend 2 (ex.: `https://backend2:8443`) |
| `BACKEND2_TIMEOUT_SEGUNDOS` | `3` | timeout da publicação |
| `BACKEND2_VERIFY_TLS` | `true` | verificar o certificado do Backend 2 |
| `BACKEND2_CA_BUNDLE` | vazio | certificado próprio do Backend 2 |
| `CORS_ORIGENS` | vazio | origens do Frontend |
| `SSL_CERTFILE`, `SSL_KEYFILE` | vazio | TLS do servidor (Uvicorn) |
