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
- Caminho com barra no fim (ex.: `/saude/`, `/livros/`) é rota inexistente: `404` `ROTA_NAO_ENCONTRADA`, sem redirecionamento.
- Não existem rotas de documentação automática (`/docs`, `/redoc`, `/openapi.json`): respondem como rota inexistente.
- Método não permitido numa rota existente: `405`, mesmo formato de corpo, código `ROTA_NAO_ENCONTRADA`.

## 4. Validação de entrada (corpo JSON)

Ordem de verificação. A primeira regra que falhar define o erro:

1. Corpo ausente, que não é JSON, ou que não é um objeto JSON → `DADOS_INVALIDOS`. Também `DADOS_INVALIDOS`: `Content-Type` diferente de `application/json` (parâmetros como `charset=utf-8` são aceitos); corpo que não é UTF-8 válido; corpo acima de 64 KiB; JSON aninhado a ponto de não poder ser lido; texto com caractere Unicode inválido (ex.: o escape `\ud800`, metade de um par substituto) ou com o caractere NUL (`\u0000`) em qualquer chave ou valor.
2. Campo obrigatório ausente, `null`, ou texto vazio depois de remover espaços das pontas → `CAMPOS_OBRIGATORIOS`. Vale para qualquer campo, inclusive os inteiros (`"quantidadeExemplares": ""` → `CAMPOS_OBRIGATORIOS`).
3. Tipo, formato ou tamanho inválido → o código específico da ficha (`QUANTIDADE_INVALIDA` para a quantidade de exemplares) ou, nos demais campos, `DADOS_INVALIDOS`.
4. Regras que dependem do banco (duplicidade, existência, disponibilidade) → código da ficha.

Dentro dos itens 2 e 3, os campos são verificados na ordem da tabela de Entrada do contrato (ex.: no CT1, `titulo`, `autor`, `isbn`, `quantidadeExemplares`); o primeiro campo com problema define o erro.

Regras gerais:

- Campos de texto: espaços em branco nas pontas (espaço, tabulação, quebra de linha) são removidos antes de validar e gravar. Tamanhos contam caracteres, não bytes, depois dessa remoção. Um campo de texto que chega com outro tipo (número, booleano, lista) é `DADOS_INVALIDOS`.
- Campos inteiros: só número JSON inteiro. Booleano (`true`), decimal (`3.5`, `3.0`), texto (`"3"`), lista ou objeto não são aceitos. O valor máximo de qualquer inteiro de entrada é 2147483647 (limite do `integer` do banco); acima disso vale como inválido, com o mesmo código do campo.
- Campos desconhecidos no corpo são ignorados.

## 5. Formatos e limites

| Campo | Regra | Erro |
|---|---|---|
| `titulo`, `autor` (CT1) | texto de 1 a 200 caracteres | `DADOS_INVALIDOS` |
| `isbn` (CT1) | hífens e espaços removidos; resultado só com dígitos, 10 ou 13 dígitos. Dígito verificador **não** é conferido. É gravado e devolvido normalizado | `DADOS_INVALIDOS` |
| `quantidadeExemplares` (CT1) | inteiro ≥ 1 | `QUANTIDADE_INVALIDA` |
| `nome` (CT3) | texto de 1 a 150 caracteres | `DADOS_INVALIDOS` |
| `cpf` (CT3) | pontos, traço e espaços removidos; resultado com exatamente 11 dígitos. Dígitos verificadores **não** são conferidos (o exemplo `12345678900` dos contratos não passaria). É gravado e devolvido normalizado | `DADOS_INVALIDOS` |
| `contato` (CT3) | até 120 caracteres; e-mail no formato `algo@dominio.ext` (nenhum caractere branco — espaço, tabulação, quebra de linha; exatamente um `@`; parte antes do `@` não vazia; depois do `@`, ao menos um ponto, sem começar nem terminar com ponto) **ou** telefone: depois de remover espaços (U+0020), parênteses e hífens e, em seguida, um `+` inicial (então `(+55) 19 99999-0000` é aceito), só dígitos, com 10 a 13 dígitos (tabulação ou quebra de linha no meio é inválida). Gravado como recebido, sem os espaços das pontas | `DADOS_INVALIDOS` |
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

- Parâmetro presente mas vazio ou só com brancos (ex.: `pagina=`) vale como não informado e recebe o padrão. Parâmetro repetido: vale o primeiro valor.
- Os parâmetros são verificados na ordem da tabela de Entrada do contrato (ex.: no CT2, `busca`, `pagina`, `tamanho`); o primeiro com problema define o erro.
- Os caracteres `%`, `_` e `\` na busca são texto literal (não funcionam como curinga nem como escape).
- Brancos das pontas, em qualquer parâmetro: os mesmos do §4 (espaço, tabulação, quebra de linha).
- As regras valem para o valor já decodificado da URL: `+` na URL é espaço (`?pagina=+1` vale 1); o caractere `+` de fato é `%2B`.
- Inteiros (`pagina`, `tamanho`): depois de cortar os brancos das pontas, só `-?[0-9]+` (dígitos ASCII; `01` vale 1). Qualquer outra forma — `+1`, `1.0`, `1e1`, `1_0`, dígitos não ASCII — é inválida, com o código do parâmetro. Mesmo limite máximo do §4 (2147483647).
- Texto de parâmetro com NUL, metade de par substituto ou bytes que não formam UTF-8 válido → inválido, com o código do parâmetro (`BUSCA_INVALIDA` para `busca`).
- Parâmetros desconhecidos são ignorados.
- A busca compara o termo como foi digitado (sem os brancos das pontas); hífens não são removidos ao buscar ISBN (`978-0` não acha `9780...`). Exceção: CT4, que compara os dígitos do termo com o CPF.
- A busca de texto não diferencia maiúsculas de minúsculas nem acentos (`sistemas` encontra `Sistemas de Informação`; `informacao` encontra `Informação`), e procura o termo em qualquer posição do campo.
- Página além da última: lista vazia, com `total` correto. Não é erro.

| Operação | Onde a busca procura | Ordem do resultado |
|---|---|---|
| CT2 consultarLivros | título, autor ou ISBN | título, depois `id` (crescente) |
| CT4 consultarUsuarios | nome; ou CPF, comparando só os dígitos do termo, quando o termo tem algum dígito | nome, depois `id` |
| CT7 listarDisponibilidade | título, autor ou ISBN | título, depois `id` |
| CT8 consultarEmprestimos | nome do usuário ou título do livro | `emprestadoEm` mais recente primeiro, depois `id` decrescente |

- "Ordem por título" (e "por nome") é alfabética sem diferenciar maiúsculas nem acentos (`álgebra`, `Banco`, `cálculo`, `Zoologia`); empate nesse critério → o texto exato por código de caractere; depois `id`. A ordem é a mesma em qualquer locale do servidor.
- Os empréstimos dentro de cada usuário (CT4) seguem a ordem do CT8 e incluem todas as situações.
- CT4 em detalhe: o usuário entra no resultado se o nome contém o termo (sem caixa nem acento, com `%`, `_` e `\` literais) **ou** se o termo tem ao menos um dígito e o CPF gravado contém a sequência de dígitos do termo (ex.: `123.456` → `123456`; `Lucas 1` procura `Lucas 1` no nome ou `1` no CPF). `total`, `pagina` e `tamanho` contam usuários, não empréstimos. `emprestimos` vem sempre presente (lista vazia se não houver), com objetos `EmprestimoResumo` iguais aos do CT8 e a situação efetiva do §7 calculada com o relógio da aplicação.
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
- Detalhes da chamada: `Content-Type: application/json`; `BACKEND2_URL` sem a barra final (se vier com barra, ela é removida); `atualizadaEm` = o mesmo instante gravado na operação (`emprestadoEm` ou `devolvidoEm`); `quantidadeDisponivel` = o valor do livro **depois** da operação; `usuarioId` e `emprestimoId` sempre enviados.
- Em `eventos_pendentes`, `criado_em` e `atualizado_em` vêm do relógio da aplicação; `ultimo_erro` é um texto curto, não vazio, que descreve a falha (ex.: `timeout`, `falha de conexão`, `HTTP 503`, `resposta inválida`, `BACKEND2_URL não configurado`) sem dados pessoais nem segredos.
- Se a gravação em `eventos_pendentes` também falhar, a resposta ao cliente continua de sucesso (a operação já foi confirmada) e a falha é registrada no log sem dados pessoais.
- Uma única tentativa por operação; não há nova tentativa automática dentro da requisição.
- TLS com o Backend 2: verificação sempre ligada por padrão (`BACKEND2_VERIFY_TLS=true`); certificado próprio por `BACKEND2_CA_BUNDLE`.

## 9. Rotas de infraestrutura

- `GET /saude` → `200` com `{"status": "ok"}`. Não consulta o banco.
- CORS: origens permitidas em `CORS_ORIGENS`, separadas por vírgula; vazio = nenhuma origem externa. O curinga `*` não é aceito (a configuração é recusada ao iniciar).
- Preflight CORS recusado (origem ou método não permitido) não ganha cabeçalhos CORS e segue o formato de erro do §3.

## 10. Configuração (variáveis de ambiente)

Valor vazio ou só com espaços vale como não configurado. Valor inválido (timeout que não é número positivo, `BACKEND2_VERIFY_TLS` fora de `true/false/1/0`, `*` em `CORS_ORIGENS`) faz `Config.from_env` levantar `ValueError`, e a aplicação não sobe.


| Variável | Padrão | Uso |
|---|---|---|
| `DATABASE_URL` | — (obrigatória) | conexão PostgreSQL |
| `BACKEND2_URL` | vazio | base do Backend 2 (ex.: `https://backend2:8443`) |
| `BACKEND2_TIMEOUT_SEGUNDOS` | `3` | timeout da publicação |
| `BACKEND2_VERIFY_TLS` | `true` | verificar o certificado do Backend 2 |
| `BACKEND2_CA_BUNDLE` | vazio | certificado próprio do Backend 2 |
| `CORS_ORIGENS` | vazio | origens do Frontend |
| `SSL_CERTFILE`, `SSL_KEYFILE` | vazio | TLS do servidor (Uvicorn) |

## 11. Banco (complementa CT9, CT10 e CT11)

- O banco usa codificação UTF8 com `LC_CTYPE` Unicode (`C.UTF-8` ou `en_US.utf8`); com locale `C` puro, a busca e a ordem de letras não latinas mudariam.
- O arquivo `db/schema.sql` cria tudo a partir de um schema `public` vazio, inclusive a extensão `unaccent` (usada pela busca do §6).
- Chaves `id`: inteiro gerado pelo banco (`GENERATED BY DEFAULT AS IDENTITY`).
- `criado_em` (e `atualizado_em` em `eventos_pendentes`): `timestamp(0) without time zone`, obrigatório, com valor padrão do horário atual de `America/Sao_Paulo`. A aplicação pode informar o valor explicitamente.
- Demais datas (`emprestado_em`, `data_limite_devolucao`, `devolvido_em`): `timestamp(0) without time zone`.

Restrições, além das que as fichas já citam:

| Tabela | Restrição |
|---|---|
| `livros` | `isbn` único; `quantidade_exemplares >= 1`; `quantidade_disponivel >= 0`; `quantidade_disponivel <= quantidade_exemplares`; `titulo`, `autor`, `isbn` não nulos |
| `usuarios` | `cpf` único; `nome`, `cpf`, `contato` não nulos |
| `emprestimos` | `usuario_id` → `usuarios.id` e `livro_id` → `livros.id` (chave estrangeira, sem exclusão em cascata); `status` só `ativo` ou `devolvido`; `status = 'devolvido'` se e somente se `devolvido_em` não é nulo; `data_limite_devolucao > emprestado_em`; `devolvido_em`, quando preenchido, `>= emprestado_em` |
| `eventos_pendentes` | `payload` `jsonb` não nulo; `tentativas >= 1`, padrão 1; `ultimo_erro` texto, pode ser nulo |

Excluir um livro ou usuário que tenha empréstimo é recusado pela chave estrangeira.
