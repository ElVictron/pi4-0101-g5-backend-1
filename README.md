# pi4-0101-g5-backend-1

Backend 1 do sistema de gerenciamento de biblioteca (Projeto Integrador IV — PI IV 0101, Grupo 5): API REST em Python (FastAPI) com PostgreSQL. Cuida do cadastro e da consulta de livros e usuários, dos empréstimos e das devoluções, e avisa o Backend 2 (atualizações em tempo real) a cada empréstimo ou devolução.

Especificação: [`docs/contratos/`](docs/contratos/) — comece por [`00-convencoes.md`](docs/contratos/00-convencoes.md) —, [`docs/adr/`](docs/adr/) e [`agentes.md`](agentes.md) (plano, decisões e processo de desenvolvimento).

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
| Backend 1 | `http://localhost:8000` | `curl http://localhost:8000/saude` |
| Backend 2 | `https://localhost:8443` | HTTPS e WSS (`/ws/biblioteca`); só aceita TLS |
| PostgreSQL 16 | rede interna | dados no volume `dados-postgres` |

- **Certificados.** Na primeira subida, o serviço `certificados` gera em `./certs` uma CA local (`ca.pem`) e o certificado do Backend 2 (nomes `localhost`, `backend2`, `127.0.0.1`). Para gerar fora do Docker: `sh scripts/gerar-certificados.sh` (`FORCE=1` regera). A pasta `certs/` não é versionada.
- **Backend 1 → Backend 2.** Por HTTPS em `https://backend2:8443`, verificando a CA local (`BACKEND2_CA_BUNDLE=/certs/ca.pem`).
- **Navegador → Backend 2.** O frontend abre `wss://localhost:8443/ws/biblioteca`. Sem confiar na CA, o navegador recusa o WSS e a tela mostra "desconectado". Importe `certs/ca.pem` como autoridade confiável (Windows: duplo clique, "Instalar certificado", "Autoridades de certificação raiz confiáveis"; Firefox: Configurações → Certificados → Importar). Reinicie o navegador depois.
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

### HTTPS no Backend 1 (opcional)

O Backend 1 sobe em HTTP por padrão. Para HTTPS, defina `SSL_CERTFILE` e `SSL_KEYFILE` apontando para arquivos montados em `/certs`. Com as duas variáveis, o `scripts/iniciar.sh` sobe o Uvicorn com TLS; com só uma delas, o contêiner não sobe. A chave precisa ser legível pelo usuário do contêiner (uid 10001), por exemplo `chmod 644` ou `chown 10001` no arquivo. Se mudar o Backend 1 para HTTPS, ajuste `VITE_API_URL` do frontend para `https://...`.

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
