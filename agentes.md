# agentes.md — Plano de ação multi-agente (spec driven) do Backend 1

Projeto Integrador IV (PI IV 0101 — Grupo 5). Repositório: `pi4-0101-g5-backend-1`.
Status deste documento: **plano aprovado (3 agentes + PM). Nenhuma implementação começa antes da ordem explícita do Victor.**

---

## 1. Objetivo e escopo

Implementar o Backend 1 (API REST em Python + PostgreSQL) a partir da especificação que já existe no repositório (contratos CT1 a CT11, ADRs 0001 a 0004) e dos cards do OpenProject, de forma **spec driven**: a especificação manda, os testes são derivados dela por um agente independente, e o código só entra quando passa nesses testes.

### 1.1 Cards no escopo (fonte: OpenProject, 06/11/2026)

| Card | Título | Entra como |
|---|---|---|
| #779 H01.1 | Docs: decisões (Python, HTTPS/WSS, atraso, devolução) | E0 — só o que falta (o PR nº 1 já resolveu quase tudo) |
| #781 H01.3 | Banco: script das tabelas e restrições | E2 |
| #783 H01.5 | Infra: CI | E3 — **somente o repositório do Backend 1** |
| #784 H02.1 | `cadastrarLivro` | E4 |
| #786 H03.1 | `cadastrarUsuario` | E5 |
| #788 H04.1 | `consultarLivros` | E6 |
| #790 H05.1 | `listarDisponibilidade` | E7 |
| #792 H09.1 | `consultarUsuarios` | E8 |
| #793 H06.1 | `registrarEmprestimo` (+ publicação no Backend 2) | E9 |
| #796 H07.1 | `consultarEmprestimos` | E10 |
| #798 H08.1 | `registrarDevolucao` (+ publicação no Backend 2) | E11 |
| #780 H01.2 | Infra: Compose | E12 — **parcial** (Backend 1 + PostgreSQL) |
| #801 H10.1 | Docs: README e release | E13 — **parcial** (README do Backend 1) |

### 1.2 Fora do escopo

- **#782 H01.4 Backend 2** e tudo que for código do Backend 2 (pedido explícito).
- **#795 H06.3 Integração** (precisa do Backend 2 e do Frontend de pé) e **#802 H10.2 Roteiro** (demonstração do sistema inteiro).
- Todos os cards de Frontend (#785, #787, #789, #791, #794, #797, #799, #800).
- Autenticação/autorização: não existe em nenhuma ficha.

O Backend 2 é **simulado nos testes** (servidor HTTP falso que responde como o CT12). A integração real fica para depois, fora deste plano.

---

## 2. Fontes da verdade (ordem de precedência)

1. **Contratos** `docs/contratos/CT1` a `CT11` (e o CT12 do repositório do Backend 2, só leitura, para o cliente de publicação).
2. **ADRs** `docs/adr/0001` a `0004` (Python, PostgreSQL, WebSocket em Python; o 0003 está substituído).
3. **Decisões registradas neste arquivo** (seção 4), que preenchem as lacunas da especificação.
4. **Cards do OpenProject** (texto de "O que precisa existir").
5. Fluxos E1 a E8 e visão geral (repositório do Frontend), só leitura.

Se duas fontes divergirem, vale a de menor número, e o PM registra a divergência na seção 4 e corrige o documento de menor precedência. **Nenhum agente decide sozinho uma divergência.**

---

## 3. Agentes

### 3.1 PM (orquestrador) — Claude, esta sessão

- Mantém este arquivo, a lista de tarefas e o registro de decisões.
- Escreve o **briefing** de cada entregável: trecho do contrato, regras, decisões da seção 4, casos de teste obrigatórios.
- Aciona os agentes, **congela** os testes do agente de teste (hash), confere que eles falham pelo motivo certo antes da implementação, roda a suíte completa e **faz o commit**.
- Arbitra disputas entre agentes **com base na especificação**. Se a especificação não responde, pergunta ao Victor.
- Não escreve código de produção nem testes de contrato (para não corrigir o próprio trabalho).

### 3.2 Agente de Teste

- Entrada: **somente** o briefing, os contratos/ADRs/decisões e o `tests/conftest.py` com as fixtures de banco. **Não lê `app/`** (a regra é imposta no prompt e conferida pelo PM).
- Saída: testes de contrato/aceitação em `tests/contrato/`, que chamam a API HTTP real contra um PostgreSQL real e semeiam dados por SQL (nunca pela própria API sob teste).
- Cada teste cita o contrato e a regra que cobre (ex.: `# CT1 · Erros · ISBN_DUPLICADO`).
- Cobre: caminho feliz, **cada erro da ficha**, campos obrigatórios, limites, tipos, formato do JSON de saída, efeitos no banco.
- Entrega primeiro os testes **vermelhos**; depois do congelamento só o PM autoriza alterá-los.

### 3.3 Agente de Backend

- Entrada: briefing, especificação, testes congelados (pode **ler** `tests/contrato/`).
- Saída: código em `app/`, e **testes unitários próprios** em `tests/unitarios/` (validadores, serviços, relógio, cliente do Backend 2), sem banco quando possível.
- **Proibido** editar `tests/contrato/`. Se achar um teste errado, abre uma **disputa** para o PM (qual teste, qual trecho da especificação contradiz).
- Implementa o mínimo para passar nos testes e cumprir o contrato; nada de funcionalidade fora da ficha.

### 3.4 Agente Revisor de Conformidade — **ativo** (decisão do Victor)

- Somente leitura: não edita código nem testes; entrega um relatório ao PM.
- Entrada: contratos, ADRs, decisões, briefing do entregável, `tests/contrato/`, `app/` e `tests/unitarios/`.
- Confere, para o entregável: rota, campos, tipos, obrigatoriedade e **cada erro da ficha** contra o que o código faz; se existe teste de contrato para cada linha da tabela de erros; se há comportamento no código que nenhuma ficha pede; se o texto do card foi atendido.
- Saída: lista de achados (`bloqueia` / `não bloqueia`) com o trecho da especificação e o arquivo/linha. Achado que bloqueia volta ao passo 4 do ciclo; o PM decide se é erro do código, do teste ou da especificação.
- Roda **depois** da suíte verde e **antes** do commit.

### 3.5 Sobre mais agentes

Decisão do Victor: **3 agentes** (Teste, Backend, Revisor) além do PM. Não haverá mais de um agente de Backend nem de Teste, para evitar conflito na mesma branch e commits misturados.

---

## 4. Decisões

### 4.1 Já decididas (conversa e especificação)

| # | Decisão | Origem |
|---|---|---|
| D1 | Backend em Python; banco PostgreSQL; WebSocket é responsabilidade do Backend 2 em Python (ADR 0004) | ADRs 0001, 0002, 0004 |
| D2 | Prazo de empréstimo: **15 dias**; vencido e sem devolução = **atrasado** | Revisão da Entrega 2, cards #793/#796 |
| D3 | `atrasado` **não é gravado**: a tabela `emprestimos` guarda só `ativo` e `devolvido`; `atrasado` é calculado na consulta (CT8, CT11) | CT8, CT11 (PR nº 1) |
| D4 | Devolução aceita empréstimo `ativo` ou efetivamente `atrasado`; grava `devolvido` + `devolvido_em`; devolver de novo → `EMPRESTIMO_JA_DEVOLVIDO` | CT6 |
| D5 | Backend 1 é o único que acessa as tabelas `livros`, `usuarios`, `emprestimos` | CT9–CT11 |
| D6 | Backend 1 publica eventos no Backend 2 por HTTPS (`POST /eventos/biblioteca`, CT12) depois de gravar; se o Backend 2 estiver fora, a operação **não falha**: o dado fica gravado e o evento falho é guardado para nova tentativa | Cards #793, #798; CT12 |
| D7 | Uma **branch separada** para toda a implementação; **cada entregável = 1 commit**; todo entregável tem testes unitários **e** passa nos testes do agente de teste | Pedido do Victor |
| D8 | Backend 2 é simulado nos testes; nada deste plano altera o repositório do Backend 2 ou do Frontend | Pedido do Victor |
| D9 | PM orquestra; mínimo de 2 agentes (Teste e Backend) | Pedido do Victor |

### 4.2 Decisões P1 a P14 — **aprovadas pelo Victor em 06/11/2026**

Lacunas da especificação fechadas por esta tabela. Valem como decisões, e a E0 as leva para os contratos.

| # | Lacuna | Proposta |
|---|---|---|
| P1 | **Framework** (o ADR 0004 não escolhe) | FastAPI + Uvicorn, psycopg 3 com SQL explícito (sem ORM, o schema é pequeno e o CT9–11 descreve tabelas), Pydantic v2 para validação |
| P2 | **Ferramentas de teste** | pytest, httpx (cliente de teste), pytest-cov, ruff, `respx`/servidor falso para o Backend 2 |
| P3 | **Banco nos testes** | PostgreSQL 16 real, subido por `scripts/test-db.sh` (binários já existem neste ambiente, sem Docker); no CI, `services: postgres`. Banco recriado do script `db/schema.sql` a cada sessão de teste, tabelas limpas entre testes |
| P4 | **Formato de erro** (as fichas só dizem "Erro `CODIGO`") | HTTP + corpo `{"erro": {"codigo": "ISBN_DUPLICADO", "mensagem": "..."}}`. Status: 400 validação/entrada inválida, 404 não encontrado, 409 conflito (`*_DUPLICADO`, `LIVRO_INDISPONIVEL`, `EMPRESTIMO_JA_DEVOLVIDO`), 503 não aplicável (Backend 2 fora não gera erro ao cliente, ver D6) |
| P5 | **Limites numéricos** ("limite permitido") | `busca`: até 100 caracteres; `pagina` ≥ 1 (padrão 1); `tamanho` de 1 a 100 (padrão 20); `quantidadeExemplares` inteiro ≥ 1 |
| P6 | **ISBN** | Só dígitos, 10 ou 13 (hífens e espaços removidos antes de validar e gravar). **Sem** conferir dígito verificador |
| P7 | **CPF** | 11 dígitos numéricos (pontos e traço removidos). **Sem** conferir dígitos verificadores: o CPF de exemplo dos contratos (`12345678900`) é inválido pelo cálculo e quebraria os próprios exemplos |
| P8 | **Contato** | E-mail válido (regra simples) **ou** telefone com 10 ou 11 dígitos; até 120 caracteres |
| P9 | **Datas e fuso** (exemplos sem fuso) | Datas sem fuso, no horário de `America/Sao_Paulo`; o "agora" vem de um relógio injetável (`Clock`) para testar atraso sem esperar 15 dias |
| P10 | **Guardar evento que falhou** (ficha: "guarda o evento"; CT12: "retry manual"; nenhum define onde) | Tabela nova `eventos_pendentes` (id, payload JSON, tentativas, criado_em, ultimo_erro) criada em `db/schema.sql`, mais um comando `python -m app.reenviar_eventos`. Sem endpoint HTTP novo, então nenhum contrato novo |
| P11 | **Atomicidade** de estoque | `UPDATE livros SET quantidade_disponivel = quantidade_disponivel - 1 WHERE id = ? AND quantidade_disponivel > 0` dentro da transação do empréstimo; teste de concorrência obrigatório |
| P12 | **HTTPS do Backend 1** | Aplicação fala HTTP puro; TLS ligado por variáveis de ambiente (certificado/chave) no Uvicorn. Testes usam HTTP. O que for "só HTTPS" no Compose depende da aprovação do professor citada no card #779 |
| P13 | **CORS** (Frontend em outra origem) | Origens permitidas por variável de ambiente `CORS_ORIGENS` |
| P14 | **Inconsistências a corrigir na E0** | CT5 ainda lista `atrasado` como status possível na saída; deve ficar `ativo, devolvido` como o CT11. O card #781 (texto do OpenProject) ainda pede `atrasado` na restrição de `status`: o schema segue o CT11, e o card precisa ser atualizado pelo grupo (fora deste repositório) |

---

## 5. Fluxo de cada entregável (ciclo do PM)

```
 1. PM        Briefing: contrato + decisões + casos obrigatórios
 2. Agente de Teste   Escreve tests/contrato/ (vermelhos)
 3. PM        Confere: cobre cada erro da ficha? falha pelo motivo certo
              (rota inexistente / comportamento ausente, nunca erro de import
              ou de fixture)? Congela (sha256 de tests/contrato/)
 4. Agente de Backend Implementa app/ + tests/unitarios/
 5. PM        Roda: ruff + unitários + contrato + cobertura
              Confere: tests/contrato/ não mudou desde o congelamento
 6. Revisor   Relatório de conformidade (contrato × código × testes)
 7. PM        Verde e sem achado bloqueante? Commit único do entregável
              + push da branch
              Vermelho ou achado bloqueante? volta ao passo 4 (máx. 3
              voltas); disputa de teste vai ao passo 3 com decisão
              registrada; sem solução → Victor
```

Regras do ciclo:

- Tudo roda **em sequência**, um entregável por vez (sem paralelismo entre agentes).
- O agente de teste não vê `app/`; o de backend não altera `tests/contrato/`.
- Toda decisão nova tomada num ciclo é anexada à seção 4 e entra no commit do entregável.
- O PM anota no commit qual card e quais contratos o entregável atende.

---

## 6. Branch, commits e Definition of Done

### 6.1 Branch

- Criada a partir da `main` atualizada: **`feat/backend-1-implementacao`**.
- Nenhum commit direto na `main`. Ao fim, o PM abre um pull request para a `main` **somente quando o Victor pedir**.
- Antes de cada push: `git fetch origin main` (o proxy de git rejeita push a partir de clone raso desatualizado).

### 6.2 Commits

- **Um commit por entregável**, na ordem da seção 7, mensagem em português no padrão:
  `feat(livros): cadastra livro com ISBN único (E4, card #784, CT1/CT9)`
  - tipos: `docs`, `feat`, `test`, `ci`, `chore`.
  - corpo curto: o que entrou, o que os testes cobrem.
  - rodapé com os trailers de coautoria exigidos pela sessão.
- Autor dos commits: Victor Hugo Gulino Dos Santos.
- O commit contém, no mesmo pacote, código, `tests/unitarios/` e `tests/contrato/` do entregável. Nunca se faz commit com teste falhando.

### 6.3 Definition of Done (vale para todo entregável com código)

- [ ] Cumpre o contrato: rota, campos, tipos, obrigatoriedade e **todos** os erros da ficha.
- [ ] Testes unitários do agente de Backend passando.
- [ ] Testes de contrato do agente de Teste passando, **sem alteração** desde o congelamento.
- [ ] Suíte completa (entregáveis anteriores incluídos) verde.
- [ ] Relatório do Revisor sem achado bloqueante.
- [ ] `ruff check` e `ruff format --check` sem erros.
- [ ] Cobertura de `app/` ≥ 85% no entregável (medido, não declarado).
- [ ] Sem segredo no código; configuração por variável de ambiente.
- [ ] Decisões novas registradas neste arquivo.
- [ ] Um commit, na branch, com push feito.

---

## 7. Entregáveis

Ordem de execução. Cada um é um commit.

### E0 — Fechar a especificação (card #779) · `docs`
- Corrigir CT5 (status de saída), conferir CT6/CT8/CT11/CT12 contra a regra D3/D4.
- Gravar as decisões P1 a P14 aprovadas neste arquivo (ou em `docs/decisoes.md`, se o Victor preferir separar) e atualizar os contratos que mencionam limites (CT1–CT4, CT7, CT8) com os números de P5 a P8.
- **Sem código, sem teste de código.** Critério: o agente de teste consegue escrever qualquer teste seguinte sem inventar número, formato ou status HTTP.

### E1 — Esqueleto do projeto · `chore`
- `pyproject.toml`, estrutura `app/` e `tests/`, configuração por ambiente, relógio injetável, tratamento de erro no formato P4, rota `GET /saude`, `scripts/test-db.sh`, `.gitignore`, `ruff`.
- Testes: unitários de configuração, relógio e formato de erro; contrato: `GET /saude` e formato do corpo de erro.
- Critério: `pytest` roda do zero em máquina limpa com um comando documentado.

### E2 — Banco (card #781, CT9/CT10/CT11) · `feat`
- `db/schema.sql`: `livros`, `usuarios`, `emprestimos`, `eventos_pendentes` (P10).
- Restrições: ISBN único, CPF único, `quantidade_disponivel >= 0` e `<= quantidade_exemplares`, `status IN ('ativo','devolvido')`, chaves estrangeiras.
- Teste (contrato, SQL direto): cada restrição recusa a gravação inválida; banco vazio sobe só pelo script; script é idempotente em banco novo.
- Unitário: carregamento do schema e fixtures.

### E3 — CI do Backend 1 (card #783) · `ci`
- GitHub Actions: PostgreSQL 16 como serviço, instala dependências, ruff, pytest com cobertura, resultado visível no GitHub.
- Critério: o workflow roda a suíte existente e falha quando um teste falha (provado por um commit de verificação descartado, não deixado na branch).
- Limite: o CI do Backend 2 (metade do card) não é tocado.

### E4 — `cadastrarLivro` (card #784, CT1, CT9) · `feat`
- `POST /livros`. Quantidade disponível = quantidade de exemplares. Erros: `ISBN_DUPLICADO`, `QUANTIDADE_INVALIDA`, `CAMPOS_OBRIGATORIOS`.
- Teste de contrato: sucesso e estado do banco; ISBN duplicado (inclusive com hífens, após normalização); quantidade 0 e negativa; cada campo ausente; tipos errados; saída com todos os campos do CT1.

### E5 — `cadastrarUsuario` (card #786, CT3, CT10) · `feat`
- `POST /usuarios`. Erros: `CPF_DUPLICADO`, `DADOS_INVALIDOS`, `CAMPOS_OBRIGATORIOS`.
- Teste: sucesso; CPF duplicado (com e sem pontuação); CPF e contato inválidos; campos ausentes.

### E6 — `consultarLivros` (card #788, CT2, CT9) · `feat`
- `GET /livros?busca&pagina&tamanho`. Busca por título, autor ou ISBN; lista paginada com quantidade disponível. Erros: `PAGINACAO_INVALIDA`, `BUSCA_INVALIDA`.
- Teste: sem busca; com busca (acento e maiúscula); paginação (primeira, última, fora do intervalo); `total`; limites de P5; ordem estável.

### E7 — `listarDisponibilidade` (card #790, CT7, CT9) · `feat`
- `GET /livros/disponibilidade?busca`. Só `quantidade_disponivel > 0`; campo `disponivel`. Erro: `BUSCA_INVALIDA`.
- Teste: livro com zero exemplares livres **não aparece**; busca; campos do objeto `LivroDisponibilidade`.

### E8 — `consultarUsuarios` (card #792, CT4, CT10, CT11) · `feat`
- `GET /usuarios?busca&pagina&tamanho`. Busca por nome ou CPF; cada usuário vem com seus empréstimos (`EmprestimoResumo`), com a **situação efetiva** (D3). Erros: `PAGINACAO_INVALIDA`, `BUSCA_INVALIDA`.
- Teste: usuário sem empréstimos (lista vazia); com ativo, devolvido e atrasado (empréstimos semeados por SQL com datas relativas ao relógio fixo); busca por CPF com e sem pontuação; paginação.
- Observação: não depende de `registrarEmprestimo` (dados semeados por SQL), por isso fica pronta na S2, como pede o card.

### E9 — `registrarEmprestimo` + publicação (card #793, CT5, CT9–CT12) · `feat`
- `POST /emprestimos`. Valida usuário, livro e exemplar livre; grava `ativo` com data limite = emprestado em + 15 dias; baixa a quantidade disponível de forma atômica (P11); publica o evento `emprestimo_registrado` no Backend 2 (cliente HTTP, P10 se falhar).
- Erros: `USUARIO_NAO_ENCONTRADO`, `LIVRO_NAO_ENCONTRADO`, `LIVRO_INDISPONIVEL`.
- Teste de contrato: sucesso (empréstimo, quantidade −1, evento recebido com o payload do CT12); cada erro; último exemplar; **concorrência** (2 pedidos pelo último exemplar: um passa, outro `LIVRO_INDISPONIVEL`); **Backend 2 fora ou com erro** → 201 ao cliente, empréstimo gravado, linha em `eventos_pendentes`; Backend 2 lento (timeout) tratado igual.
- Unitário: cliente do Backend 2, montagem do payload, regra dos 15 dias, `reenviar_eventos` (reenvia, apaga ao ter sucesso, conta tentativas).

### E10 — `consultarEmprestimos` (card #796, CT8, CT9–CT11) · `feat`
- `GET /emprestimos?status&busca`. Situação efetiva pela regra do CT8 (ordem: devolvido → atrasado → ativo). Filtro `status` usa a mesma regra. Busca por usuário ou livro. Erros: `STATUS_INVALIDO`, `BUSCA_INVALIDA`.
- Teste: borda exata do prazo (no instante da data limite e um segundo depois, com relógio fixo); ativo gravado mas vencido sai como `atrasado`; filtro por cada status; devolvido vencido continua `devolvido`; campos de `EmprestimoResumo`.

### E11 — `registrarDevolucao` + publicação (card #798, CT6, CT9, CT11, CT12) · `feat`
- `PATCH /emprestimos/{emprestimoId}/devolucao`. Aceita ativo ou atrasado; grava `devolvido` e `devolvido_em`; sobe a quantidade disponível; resposta com `quantidadeDisponivel` (CT6); publica `devolucao_registrada`; mesma regra de falha do E9.
- Erros: `EMPRESTIMO_NAO_ENCONTRADO`, `EMPRESTIMO_JA_DEVOLVIDO`.
- Teste: devolução de ativo e de **atrasado**; devolver duas vezes; id inexistente; quantidade nunca passa de `quantidade_exemplares`; Backend 2 fora; evento com o payload correto.

### E12 — Contêiner do Backend 1 e Compose parcial (card #780) · `chore`
- `Dockerfile` do Backend 1 e `docker-compose.yml` com `backend1` + `postgres` (volume, healthcheck, schema aplicado no primeiro start). Serviços do Backend 2 e do Frontend ficam como comentários/placeholders.
- **Verificação limitada:** este ambiente não tem Docker em execução. Valida-se com `docker compose config`, build do Dockerfile **só se houver daemon**, e subida real fica registrada como "não verificada aqui". O PM avisa o Victor disso no commit.
- Critério: configuração sintaticamente válida e `GET /saude` coberto por teste local equivalente.

### E13 — README do Backend 1 (card #801, parte do repositório) · `docs`
- Como subir (com e sem Compose), variáveis de ambiente, como rodar testes, como reenviar eventos, tabela rota ↔ contrato ↔ card.
- A release v1.0 e os dados de exemplo do sistema inteiro ficam para o grupo.

---

## 8. Estrutura de pastas prevista

```
app/
  main.py            criação da aplicação, CORS, tratamento de erro
  config.py          variáveis de ambiente
  clock.py           relógio injetável
  db.py              conexão e transação
  erros.py           códigos e formato de erro (P4)
  livros/            rotas, serviço, repositório, schemas
  usuarios/
  emprestimos/
  eventos/           cliente do Backend 2 e reenviar_eventos
db/schema.sql
scripts/test-db.sh
tests/
  conftest.py        fixtures de banco, cliente, relógio, Backend 2 falso
  contrato/          agente de Teste (congelado por entregável)
  unitarios/         agente de Backend
docs/                contratos, ADRs (já existem)
```

---

## 8A. Preparação para a integração com o Backend 2 (sem implementá-lo)

**Quem fala o quê.** O WebSocket não passa pelo Backend 1.

```
Frontend ──HTTPS──► Backend 1 ──SQL──► PostgreSQL
                       │
                       └──HTTPS (CT12: POST /eventos/biblioteca)──► Backend 2 ──WSS (CT13)──► Frontend
```

- **Backend 1 → Backend 2:** requisição **HTTPS** comum, `POST /eventos/biblioteca` (CT12).
- **Backend 2 → Frontend:** **WebSocket seguro (WSS)** com o evento `bibliotecaAtualizada` (CT13). Isso é do Backend 2 e fica fora deste plano.
- Logo, o Backend 1 não abre, não aceita e não mantém conexão WebSocket. O que ele precisa deixar pronto é um **cliente HTTP fiel ao CT12**.

**O que o Backend 1 deixa "no jeito" para a integração:**

| Item | Como fica |
|---|---|
| Endereço do Backend 2 | Variável `BACKEND2_URL` (ex.: `https://backend2:8443`), sem valor fixo no código |
| TLS | `BACKEND2_CA_BUNDLE` (certificado próprio do Compose) e `BACKEND2_VERIFY_TLS`; nunca desligar a verificação por padrão |
| Timeout | `BACKEND2_TIMEOUT_SEGUNDOS` (padrão 3), para o empréstimo não ficar preso se o Backend 2 travar |
| Payload | Exatamente os campos do CT12: `tipo` (`emprestimo_registrado` ou `devolucao_registrada`), `livroId`, `usuarioId`, `emprestimoId`, `status`, `quantidadeDisponivel`, `atualizadaEm` |
| Resposta esperada | `{"aceito": true, "eventoId": "..."}`; qualquer outra coisa (erro HTTP, timeout, conexão recusada, `aceito` falso) conta como falha |
| Falha | A operação do cliente **continua com sucesso**; o evento vai para `eventos_pendentes` (P10) e pode ser reenviado com `python -m app.reenviar_eventos` |
| Fronteira isolada | Todo o código que fala com o Backend 2 fica em um único módulo (`app/eventos/`), atrás de uma interface (`PublicadorDeEventos`). Trocar o servidor falso pelo real não muda regra de negócio |
| Teste de fidelidade ao CT12 | Os testes validam o payload enviado campo a campo contra o CT12 (tipos, obrigatoriedade, valores permitidos); se o CT12 mudar, o teste quebra |
| Servidor falso | Nos testes, um servidor HTTP local responde como o CT12 (sucesso, `EVENTO_INVALIDO`, `EVENTO_NAO_PUBLICADO`, lento, fora do ar) |

**Fica para depois (card #795, fora do plano):** subir Backend 1, Backend 2, Frontend e PostgreSQL juntos e conferir que um empréstimo numa aba muda a quantidade no painel de outra aba. A única mudança esperada no Backend 1 nessa hora é apontar `BACKEND2_URL` e o certificado para o contêiner real.

**Ponto de atenção para o Victor:** o CT12 define o retorno do Backend 2 como `aceito` + `eventoId`, e `status` aceita `atrasado` no evento. Como `atrasado` não é gravado (D3) e os dois eventos do Backend 1 são de empréstimo e devolução, o Backend 1 só enviará `ativo` ou `devolvido`. Se o Backend 2 quiser tratar `atrasado`, é decisão do lado dele.

---

## 9. Riscos e como o plano os trata

| Risco | Tratamento |
|---|---|
| Os dois agentes leem a mesma ficha ambígua e erram juntos | Lacunas fechadas na E0; PM confere conformidade; Revisor (3.4) |
| Teste vermelho "por engano" (erro de fixture, não de comportamento) | Passo 3 do ciclo: PM exige falha pelo motivo certo |
| Agente de backend "ajusta" o teste para passar | Hash congelado de `tests/contrato/`, conferido no passo 5 |
| Cobertura alta com teste fraco | Casos obrigatórios listados por entregável; contrato testa efeito no banco, não só status HTTP |
| Corrida no último exemplar | Atualização condicional (P11) + teste de concorrência |
| Atraso difícil de testar | Relógio injetável (P9) e testes de borda do prazo |
| Backend 2 inexistente | Servidor falso nos testes (D8); integração real fica fora do plano |
| Sem Docker neste ambiente | PostgreSQL local para testes (P3); E12 declarada com verificação parcial |
| `initdb` recusa rodar como root | `scripts/test-db.sh` roda o cluster com usuário não-root; validado na E1 antes de seguir |
| Push com proxy instável | `fetch` antes do push; um push por entregável |

---

## 10. Estado

| Item | Situação |
|---|---|
| Plano | Aprovado com 3 agentes; aguardando ordem de início |
| Decisões P1–P14 | **Aprovadas** |
| Revisor (3.4) | **Ativo** (aprovado) |
| Branch `feat/backend-1-implementacao` | Criada só para guardar este plano; **nenhum código nela ainda** |
| Implementação | **Não iniciada** |

Quando o Victor liberar: começar pela E0 nesta mesma branch e seguir a ordem da seção 7.
