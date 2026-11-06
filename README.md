# pi4-0101-g5-backend-1

Backend 1 do sistema de gerenciamento de biblioteca (PI IV 0101 — Grupo 5): API REST em Python (FastAPI) com PostgreSQL.

Especificação: [`docs/contratos/`](docs/contratos/) (comece por `00-convencoes.md`), [`docs/adr/`](docs/adr/) e [`agentes.md`](agentes.md).

## Rodar os testes (do zero)

Requisitos: Python 3.12+ e os binários do PostgreSQL 16 (`initdb`, `pg_ctl`) instalados.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
scripts/test-db.sh start && .venv/bin/pytest
```

`scripts/test-db.sh start` sobe um PostgreSQL descartável na porta 54329 (dados em `/tmp/pi4-backend1-pgdata`) e imprime a URL. Para usar outro banco, defina `TEST_DATABASE_URL`; o nome do banco precisa terminar em `_teste` — **os testes apagam e recriam o schema `public` desse banco**. `scripts/test-db.sh stop` para o servidor.

Cobertura: `.venv/bin/pytest --cov=app`.
