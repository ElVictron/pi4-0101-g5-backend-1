# Sistema de Gerenciamento de Biblioteca

Projeto Integrador IV (PUC-Campinas, Sistemas de Informação, turma 102, grupo 05). Sistema web que substitui as planilhas de uma biblioteca: o responsável cadastra livros e usuários, registra empréstimos e devoluções, pesquisa o acervo e acompanha os atrasos. Um painel de disponibilidade se atualiza sozinho: um empréstimo registrado numa tela aparece nas outras telas abertas, sem recarregar a página.

## Integrantes

| Nome | RA | Responde por |
|---|---|---|
| Victor Hugo Gulino dos Santos | 22968572 | Backend 1 (API e banco), Compose, integração e testes de ponta a ponta |
| Lucas Joaquim de Souza | 24020901 | Backend 2 (eventos em tempo real) |
| Gabriel Gregorio Ribeiro Leite | 20060547 | Frontend |

## Repositórios

| Repositório | O que tem |
|---|---|
| [pi4-0101-g5-backend-1](https://github.com/ElVictron/pi4-0101-g5-backend-1) (este) | Backend 1 (API REST em Python/FastAPI), banco PostgreSQL, `docker-compose.yml`, documentos e scripts de integração |
| [pi4-0101-g5-backend-2](https://github.com/ElVictron/pi4-0101-g5-backend-2) | Backend 2: recebe eventos do Backend 1 e os envia às telas por WebSocket seguro |
| [pi4-0101-g5-frontend](https://github.com/ElVictron/pi4-0101-g5-frontend) | Frontend em React |

## Pré-requisitos

- Docker Engine com o plugin Docker Compose v2 (`docker compose version`); testado com o Docker Engine 29. Docker Desktop no Windows e no macOS (não testado).
- Git.
- Acesso à internet para baixar as imagens (`postgres`, `python`, `node`, `nginx`, `alpine`) do Docker Hub.
- Um navegador (Chrome, Edge ou Firefox).
- Portas livres: 5173, 8000 e 8443.
- Opcional, só para o teste automático: Python 3.12 ou superior (`python3`).

## Como subir

1. Clone os três repositórios na mesma pasta:
   ```bash
   mkdir biblioteca && cd biblioteca
   git clone https://github.com/ElVictron/pi4-0101-g5-backend-1.git
   git clone https://github.com/ElVictron/pi4-0101-g5-backend-2.git
   git clone https://github.com/ElVictron/pi4-0101-g5-frontend.git
   ```
2. Entre na pasta do repositório principal e suba o sistema (não é preciso criar `.env`; os padrões servem para a demonstração):
   ```bash
   cd pi4-0101-g5-backend-1
   docker compose up --build -d
   ```
   Na primeira vez leva alguns minutos. O serviço `certificados` gera, sozinho, a pasta `certs/`.
3. Confira que tudo subiu (quatro serviços em execução, `backend2` e `postgres` como `healthy`):
   ```bash
   docker compose ps
   ```
4. Carregue os dados de exemplo (4 livros, 3 usuários e 3 empréstimos, um deles atrasado; só insere se o banco estiver vazio):
   ```bash
   docker compose exec -T postgres psql -U biblioteca -d biblioteca < db/dados-demo.sql
   ```
5. Confie na autoridade certificadora local no navegador, para ele aceitar o HTTPS do Backend 1 e o WSS do Backend 2: importe o arquivo `certs/ca.pem` como "autoridade de certificação raiz confiável" (Windows: duplo clique, "Instalar certificado", "Autoridades de Certificação Raiz Confiáveis"; Firefox: Configurações, Certificados, Importar) e reinicie o navegador.
6. Abra <http://localhost:5173>. O indicador do canto superior direito deve mostrar **Tempo real: conectado**.

Para desligar: `docker compose down` (mantém os dados) ou `docker compose down -v` (apaga também o banco).

Para conferir tudo de uma vez, com um teste automático das duas abas: `python3 -m pip install playwright && python3 -m playwright install chromium && python3 scripts/integracao/verificar_docker.py`.

## Como usar

O sistema não tem login: quem abre a tela é o responsável da biblioteca. Menu lateral: Painel, Acervo, Usuários, Empréstimos.

| Entregável | Como fazer |
|---|---|
| E1 Cadastro de livros | Acervo, "Cadastrar livro": título, autor, ISBN e quantidade de exemplares, depois Cadastrar |
| E2 Consulta de livros | Acervo, "Pesquisar livros": digite parte do título, autor ou ISBN e clique em Buscar |
| E3 Cadastro de usuários | Usuários, "Novo usuário": nome, CPF e contato, depois Cadastrar |
| E4 Consulta de usuários | Usuários, "Usuários cadastrados": busque por nome ou CPF; cada cartão mostra os empréstimos |
| E5 Registro de empréstimo | Empréstimos, "Registrar empréstimo": busque e marque o usuário, escolha o livro e clique em Registrar empréstimo. O prazo é de 15 dias |
| E6 Registro de devolução | Empréstimos, lista de empréstimos: clique em Devolver na linha do empréstimo |
| E7 Controle de disponibilidade | Painel: mostra os livros com exemplares disponíveis e se atualiza sozinho. Abra duas abas, registre um empréstimo numa e veja a outra mudar |
| E8 Consulta de empréstimos | Empréstimos, "Empréstimos registrados": filtre por Ativos, Atrasados ou Devolvidos e busque por usuário ou livro |

Roteiro completo de demonstração: [`docs/roteiro-demonstracao.md`](docs/roteiro-demonstracao.md).

## Documentação

- [Documento de Projeto](docs/documento-de-projeto.md): visão geral, requisitos, arquitetura, banco, contratos, testes, telas e conclusão.
- [Fluxos](docs/fluxos/), [contratos](docs/contratos/) (comece por [`00-convencoes.md`](docs/contratos/00-convencoes.md)) e [decisões (ADR)](docs/adr/).
- [`agentes.md`](agentes.md): plano, decisões e processo de desenvolvimento.

---

# Referência técnica do Backend 1

## Rotas

| Método e caminho | Operação | Contrato | Card |
|---|---|---|---|
| `POST /livros` | cadastrarLivro | [CT1](docs/contratos/CT1-cadastrarLivro.md) | #784 |
| `GET /livros?busca&pagina&tamanho` | consultarLivros | [CT2](docs/contratos/CT2-consultarLivros.md) | #788 |
| `GET /livros/disponibilidade?busca` | listarDisponibilidade | [CT7](docs/contratos/CT7-listarDisponibilidade.md) | #790 |
| `POST /usuarios` | cadastrarUsuario | [CT3](docs/contratos/CT3-cadastrarUsuario.md) | #786 |
| `GET /usuarios?busca&pagina&tamanho` | consultarUsuarios | [CT4](docs/contratos/CT4-consultarUsuarios.md) | #792 |
| `POST /emprestimos` | registrarEmprestimo | [CT5](docs/contratos/CT5-registrarEmprestimo.md) | #793 |
| `GET /emprestimos?status&busca` | consultarEmprestimos | [CT8](docs/contratos/CT8-consultarEmprestimos.md) | #796 |
| `PATCH /emprestimos/{emprestimoId}/devolucao` | registrarDevolucao | [CT6](docs/contratos/CT6-registrarDevolucao.md) | #798 |
| `GET /saude` | verificação de saúde (não consulta o banco) | [convenções §9](docs/contratos/00-convencoes.md) | — |

Erros sempre no formato `{"erro": {"codigo": "...", "mensagem": "..."}}`; códigos e status HTTP em [`00-convencoes.md` §3](docs/contratos/00-convencoes.md). O banco (tabelas `livros`, `usuarios`, `emprestimos`, `eventos_pendentes`) está em [`db/schema.sql`](db/schema.sql) e nos contratos CT9 a CT11.

## Subir o sistema com Docker Compose

Sobe o frontend, o Backend 1, o Backend 2 e o PostgreSQL, cada um no seu contêiner (card #780).

Requisitos: Docker com o plugin Compose e os três repositórios lado a lado:

```text
pi4-0101-g5-backend-1/   (aqui)
pi4-0101-g5-backend-2/
pi4-0101-g5-frontend/
```

```bash
docker compose up --build
```

| Serviço | Endereço | Observação |
|---|---|---|
| Frontend | `http://localhost:5173` | imagem Nginx; o navegador chama os dois backends pelo host |
| Backend 1 | `https://localhost:8000` | HTTPS; `curl --cacert certs/ca.pem https://localhost:8000/saude` |
| Backend 2 | `https://localhost:8443` | HTTPS e WSS (`/ws/biblioteca`); só aceita TLS |
| PostgreSQL 16 | rede interna | dados no volume `dados-postgres` |

- **Certificados.** Na primeira subida, o serviço `certificados` gera em `./certs` uma CA local (`ca.pem`) e os certificados do Backend 1 e do Backend 2 (nomes `localhost`, o nome do serviço e `127.0.0.1`). Para gerar fora do Docker: `sh scripts/gerar-certificados.sh` (`FORCE=1` regera). A pasta `certs/` não é versionada.
- **Backend 1 → Backend 2.** Por HTTPS em `https://backend2:8443`, verificando a CA local (`BACKEND2_CA_BUNDLE=/certs/ca.pem`).
- **Navegador → Backends.** O frontend chama `https://localhost:8000` (Backend 1) e abre `wss://localhost:8443/ws/biblioteca` (Backend 2). Sem confiar na CA, o navegador recusa os dois: as telas mostram erro de conexão e o painel fica "desconectado". Importe `certs/ca.pem` como autoridade confiável (Windows: duplo clique, "Instalar certificado", "Autoridades de certificação raiz confiáveis"; Firefox: Configurações → Certificados → Importar). Reinicie o navegador depois.
- **Só o Backend 1.** `docker compose up --build postgres backend1` (sem Backend 2, os eventos ficam em `eventos_pendentes`).
- O schema é aplicado **só na primeira vez**, com o volume novo. Mudou o `db/schema.sql`? Recrie o banco (apaga os dados): `docker compose down -v && docker compose up --build`.
- Configuração por variáveis de ambiente (arquivo `.env` ao lado do `docker-compose.yml` ou exportadas no terminal); veja a tabela abaixo.

### Roteiro e teste de integração

Passo a passo da demonstração, com o empréstimo atrasado: [`docs/roteiro-demonstracao.md`](docs/roteiro-demonstracao.md). Com o sistema de pé, `python scripts/integracao/teste_duas_abas.py` confere (Playwright) que um empréstimo ou devolução feito numa aba muda o painel de outra aba sem recarregar (card #795).

### Dados de exemplo

Para a demonstração (card #802), com o sistema de pé:

```bash
docker compose exec -T postgres psql -U biblioteca -d biblioteca < db/dados-demo.sql
```

Insere 4 livros, 3 usuários e 3 empréstimos, **um deles atrasado** (prazo vencido há 5 dias). Só insere se o banco estiver vazio.

### HTTPS no Backend 1

No Compose o Backend 1 já sobe em HTTPS (D24), com `certs/backend1.pem`. Com `SSL_CERTFILE` e `SSL_KEYFILE`, o `scripts/iniciar.sh` sobe o Uvicorn com TLS; com só uma delas, o contêiner não sobe. Para voltar ao HTTP no Compose (por exemplo, sem importar a CA), defina `SSL_CERTFILE=` e `SSL_KEYFILE=` vazios e `VITE_API_URL=http://localhost:8000` no `.env`, e use `docker compose up --build`. Rodando sem Docker, o padrão continua HTTP.

## Rodar sem Docker

Requisitos: Python 3.12+ e um PostgreSQL 16 com codificação UTF8 e locale `C.UTF-8` ou `en_US.utf8`.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
export DATABASE_URL=postgresql://usuario:senha@localhost:5432/biblioteca
.venv/bin/python -c "from app.config import Config; from app.db import aplicar_schema; aplicar_schema(Config.from_env())"
.venv/bin/uvicorn --factory app.main:create_app --port 8000
```

## Configuração

| Variável | Padrão | Uso |
|---|---|---|
| `DATABASE_URL` | — (obrigatória) | conexão PostgreSQL |
| `BACKEND2_URL` | vazio (no Compose: `https://backend2:8443`) | base do Backend 2 (ex.: `https://backend2:8443`); vazio = todo evento fica pendente |
| `BACKEND2_TIMEOUT_SEGUNDOS` | `3` | tempo limite de conexão e de leitura da chamada ao Backend 2 |
| `BACKEND2_VERIFY_TLS` | `true` | verificar o certificado do Backend 2 |
| `BACKEND2_CA_BUNDLE` | vazio (no Compose: `/certs/ca.pem`) | certificado próprio do Backend 2 (mantém a verificação ligada) |
| `CORS_ORIGENS` | vazio (no Compose: `http://localhost:5173`) | origens do Frontend, separadas por vírgula; `*` não é aceito |
| `SSL_CERTFILE`, `SSL_KEYFILE` | vazio | HTTPS do próprio Backend 1 |

Valor inválido faz a aplicação não subir (`ValueError`).

## Integração com o Backend 2

Depois de cada empréstimo ou devolução confirmados, o Backend 1 chama `POST {BACKEND2_URL}/eventos/biblioteca` (contrato CT12, no repositório do Backend 2) com o evento `emprestimo_registrado` ou `devolucao_registrada`. Se o Backend 2 estiver fora, a operação do usuário continua dando certo e o evento vai para a tabela `eventos_pendentes`. Para reenviar:

```bash
.venv/bin/python -m app.reenviar_eventos          # sem Docker
docker compose exec backend1 python -m app.reenviar_eventos   # com Docker
```

Sai com código `0` quando não sobra pendente e `1` quando sobra. A entrega é "pelo menos uma vez" e sem ordem garantida: o Backend 2 deve tolerar evento repetido (`tipo` + `emprestimoId`) e fora de ordem.

## Testes

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
scripts/test-db.sh start && .venv/bin/pytest
```

`scripts/test-db.sh start` sobe um PostgreSQL descartável na porta 54329 (dados em `/tmp/pi4-backend1-pgdata`; precisa dos binários `initdb` e `pg_ctl` do PostgreSQL 16; fora do Debian/Ubuntu, indique a pasta deles em `PG_BIN`) e imprime a URL. Para usar outro banco, defina `TEST_DATABASE_URL`; o nome do banco precisa terminar em `_teste` — **os testes apagam e recriam o schema `public` desse banco**. `scripts/test-db.sh stop` para o servidor.

- `tests/contrato/`: testes de contrato, escritos a partir da especificação.
- `tests/unitarios/`: testes da lógica interna.
- Cobertura: `.venv/bin/pytest --cov=app`. Lint: `.venv/bin/ruff check . && .venv/bin/ruff format --check .`.
- O CI (GitHub Actions) roda tudo isso em todo push, com Python 3.12 e 3.13 e PostgreSQL 16.
