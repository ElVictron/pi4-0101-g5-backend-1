"""E12 — contêiner e Compose do Backend 1 (card #780, parte do Backend 1).

Fontes: `agentes.md` §7 E12, D14, D18 e D22; `00-convencoes.md` §9 e §10. Sem daemon
Docker neste ambiente: o Compose é validado por `docker compose config`; o `Dockerfile` e o
`.dockerignore`, pelo texto; o `scripts/iniciar.sh`, executado com um `uvicorn` falso.
"""

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INICIAR = RAIZ / "scripts" / "iniciar.sh"
DOCKERFILE = RAIZ / "Dockerfile"
DOCKERIGNORE = RAIZ / ".dockerignore"
COMPOSE = RAIZ / "docker-compose.yml"

VARIAVEIS_CONVENCOES = (
    "DATABASE_URL",
    "BACKEND2_URL",
    "BACKEND2_TIMEOUT_SEGUNDOS",
    "BACKEND2_VERIFY_TLS",
    "BACKEND2_CA_BUNDLE",
    "CORS_ORIGENS",
    "SSL_CERTFILE",
    "SSL_KEYFILE",
)
BASE = ["--factory", "app.main:create_app", "--host", "0.0.0.0"]


# --------------------------------------------------------------------------- iniciar.sh


@pytest.fixture
def uvicorn_falso(tmp_path):
    """Pasta com um `uvicorn` que grava os argumentos (um por linha) em `chamada.txt`."""
    pasta = tmp_path / "bin"
    pasta.mkdir()
    registro = tmp_path / "chamada.txt"
    falso = pasta / "uvicorn"
    falso.write_text(f'#!/bin/sh\nfor a in "$@"; do echo "$a"; done > "{registro}"\n')
    falso.chmod(falso.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return pasta, registro


def iniciar(uvicorn_falso, **variaveis):
    """Roda `sh scripts/iniciar.sh` com o uvicorn falso; devolve (processo, argumentos|None)."""
    pasta, registro = uvicorn_falso
    ambiente = {
        k: v for k, v in os.environ.items() if k not in ("SSL_CERTFILE", "SSL_KEYFILE", "PORTA")
    }
    ambiente["PATH"] = f"{pasta}{os.pathsep}{ambiente.get('PATH', '')}"
    ambiente.update(variaveis)
    processo = subprocess.run(
        ["sh", str(INICIAR)], cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=30
    )
    argumentos = registro.read_text().splitlines() if registro.exists() else None
    return processo, argumentos


# D22 / D14 · sem SSL_*: Uvicorn em HTTP, fábrica create_app, 0.0.0.0:8000, sem --ssl-*
def test_iniciar_sem_tls(uvicorn_falso):
    processo, argumentos = iniciar(uvicorn_falso)

    assert processo.returncode == 0, processo.stderr
    assert argumentos == [*BASE, "--port", "8000"]
    assert not any(a.startswith("--ssl") for a in argumentos)


# D22 / D14 · SSL_* vazios valem como não definidos (padrão do Compose é vazio)
def test_iniciar_com_ssl_vazios_e_http(uvicorn_falso):
    processo, argumentos = iniciar(uvicorn_falso, SSL_CERTFILE="", SSL_KEYFILE="")

    assert processo.returncode == 0, processo.stderr
    assert argumentos == [*BASE, "--port", "8000"]


# D22 / D14 · com SSL_CERTFILE e SSL_KEYFILE: Uvicorn com TLS
def test_iniciar_com_tls(uvicorn_falso):
    processo, argumentos = iniciar(
        uvicorn_falso, SSL_CERTFILE="/certs/servidor.crt", SSL_KEYFILE="/certs/servidor.key"
    )

    assert processo.returncode == 0, processo.stderr
    assert argumentos[: len(BASE)] == BASE
    assert argumentos[argumentos.index("--port") + 1] == "8000"
    assert argumentos[argumentos.index("--ssl-certfile") + 1] == "/certs/servidor.crt"
    assert argumentos[argumentos.index("--ssl-keyfile") + 1] == "/certs/servidor.key"


# D22 · só um dos dois SSL_*: sai com código 1, mensagem no stderr, Uvicorn não é chamado
@pytest.mark.parametrize(
    "variaveis",
    [
        {"SSL_CERTFILE": "/certs/servidor.crt"},
        {"SSL_KEYFILE": "/certs/servidor.key"},
        {"SSL_CERTFILE": "/certs/servidor.crt", "SSL_KEYFILE": ""},
    ],
    ids=["so-cert", "so-key", "key-vazio"],
)
def test_iniciar_com_um_so_ssl_falha(uvicorn_falso, variaveis):
    processo, argumentos = iniciar(uvicorn_falso, **variaveis)

    assert processo.returncode == 1
    assert processo.stderr.strip()
    assert argumentos is None


# D22 · PORTA altera a porta (com e sem TLS)
def test_iniciar_com_porta(uvicorn_falso):
    _, http = iniciar(uvicorn_falso, PORTA="9123")
    _, https = iniciar(uvicorn_falso, PORTA="9124", SSL_CERTFILE="/c.crt", SSL_KEYFILE="/c.key")

    assert http == [*BASE, "--port", "9123"]
    assert https[https.index("--port") + 1] == "9124"


# D22 · o script é executável (o Dockerfile também faz chmod) e começa com #!/bin/sh
def test_iniciar_e_script_sh_executavel():
    assert INICIAR.read_text().startswith("#!/bin/sh")
    assert INICIAR.stat().st_mode & stat.S_IXUSR


# --------------------------------------------------------------------------- docker compose


@pytest.fixture(scope="module")
def compose():
    """Saída de `docker compose config --format json`, com as variáveis da §10 ausentes."""
    if shutil.which("docker") is None:
        pytest.skip("CLI do docker não instalado")
    ambiente = {
        k: v
        for k, v in os.environ.items()
        if k not in VARIAVEIS_CONVENCOES and k != "POSTGRES_PASSWORD"
    }
    processo = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE),
            "--project-directory",
            str(RAIZ),
            "config",
            "--format",
            "json",
        ],
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if processo.returncode != 0 and "unknown" in processo.stderr.lower():
        pytest.skip(f"docker compose indisponível: {processo.stderr.strip()}")
    assert processo.returncode == 0, processo.stderr
    return json.loads(processo.stdout)


# D22 · só postgres e backend1 (Backend 2 e Frontend só como comentário)
def test_compose_servicos(compose):
    assert set(compose["services"]) == {"postgres", "backend1"}


# D22 · postgres:16, volume persistente e healthcheck com pg_isready
def test_compose_postgres(compose):
    postgres = compose["services"]["postgres"]

    assert postgres["image"] == "postgres:16"
    dados = [v for v in postgres["volumes"] if v["target"] == "/var/lib/postgresql/data"]
    assert len(dados) == 1
    assert dados[0]["type"] == "volume"
    assert dados[0]["source"] in compose.get("volumes", {})
    teste = postgres["healthcheck"]["test"]
    assert any("pg_isready" in parte for parte in teste)


# D18 / D22 · db/schema.sql montado em docker-entrypoint-initdb.d, somente leitura
def test_compose_schema_no_initdb(compose):
    volumes = compose["services"]["postgres"]["volumes"]
    schema = [v for v in volumes if v["source"].endswith("/db/schema.sql")]

    assert len(schema) == 1
    assert schema[0]["type"] == "bind"
    assert schema[0]["target"].startswith("/docker-entrypoint-initdb.d/")
    assert schema[0]["target"].endswith(".sql")
    assert schema[0].get("read_only") is True


# D22 · backend1 depende do postgres saudável e publica a porta 8000
def test_compose_backend1_dependencia_e_porta(compose):
    backend1 = compose["services"]["backend1"]

    assert backend1["depends_on"]["postgres"]["condition"] == "service_healthy"
    portas = [p for p in backend1["ports"] if p["target"] == 8000]
    assert len(portas) == 1
    assert str(portas[0]["published"]) == "8000"
    assert "build" in backend1


# §10 · todas as variáveis das convenções no ambiente do backend1; DATABASE_URL → postgres
def test_compose_backend1_ambiente(compose):
    ambiente = compose["services"]["backend1"]["environment"]

    assert set(VARIAVEIS_CONVENCOES) <= set(ambiente)
    url = urlsplit(ambiente["DATABASE_URL"])
    assert url.scheme in ("postgresql", "postgres")
    assert url.hostname == "postgres"
    assert (url.port or 5432) == 5432
    assert url.path.lstrip("/")


# §10 / D22 · padrões vazios de BACKEND2_URL e SSL_* (HTTP sem TLS e eventos pendentes)
@pytest.mark.parametrize("variavel", ["BACKEND2_URL", "SSL_CERTFILE", "SSL_KEYFILE"])
def test_compose_padroes_vazios(compose, variavel):
    assert compose["services"]["backend1"]["environment"][variavel] in ("", None)


# --------------------------------------------------------------------------- Dockerfile


def instrucoes() -> list[tuple[str, str]]:
    """Instruções do Dockerfile (continuações de linha unidas, comentários fora)."""
    linhas, atual = [], ""
    for linha in DOCKERFILE.read_text().splitlines():
        limpa = linha.strip()
        if not atual and (not limpa or limpa.startswith("#")):
            continue
        if limpa.endswith("\\"):
            atual += limpa[:-1].strip() + " "
            continue
        linhas.append(atual + limpa)
        atual = ""
    resultado = []
    for linha in linhas:
        comando, _, resto = linha.partition(" ")
        resultado.append((comando.upper(), resto.strip()))
    return resultado


def valores(comando: str) -> list[str]:
    return [resto for nome, resto in instrucoes() if nome == comando]


# D22 · imagem base python:3.12-slim
def test_dockerfile_base():
    assert valores("FROM") == ["python:3.12-slim"]


# D22 · roda com usuário sem privilégios (último USER não é root nem 0)
def test_dockerfile_usuario_sem_privilegios():
    usuarios = valores("USER")
    assert usuarios
    ultimo = usuarios[-1].split(":")[0]
    assert ultimo not in ("root", "0")


# D22 · porta 8000
def test_dockerfile_expoe_8000():
    assert any("8000" in v.split() for v in valores("EXPOSE"))


# D22 / §9 · HEALTHCHECK faz GET em /saude na porta 8000
def test_dockerfile_healthcheck_em_saude():
    (healthcheck,) = valores("HEALTHCHECK")
    assert "CMD" in healthcheck
    assert "/saude" in healthcheck
    assert "8000" in healthcheck


# D22 · início por scripts/iniciar.sh
def test_dockerfile_cmd_iniciar():
    comandos = valores("CMD") + valores("ENTRYPOINT")
    assert any("scripts/iniciar.sh" in c for c in comandos)


# D22 · instala o pacote (pip install .) e copia o que o início precisa
def test_dockerfile_instala_o_pacote():
    assert any(v.split()[:3] == ["pip", "install", "."] for v in valores("RUN"))
    copiados = " ".join(valores("COPY"))
    for caminho in ("pyproject.toml", "app", "scripts/iniciar.sh"):
        assert caminho in copiados, caminho


# --------------------------------------------------------------------------- .dockerignore


# D22 · a imagem não leva ambiente virtual, git, testes nem segredos
@pytest.mark.parametrize("entrada", [".venv", ".git", "tests", ".env"])
def test_dockerignore_exclui(entrada):
    linhas = {
        linha.strip().rstrip("/").removeprefix("/")
        for linha in DOCKERIGNORE.read_text().splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    }
    assert entrada in linhas


# D22 · .dockerignore não exclui o que a imagem precisa
@pytest.mark.parametrize("necessario", ["app", "db", "scripts", "pyproject.toml"])
def test_dockerignore_nao_exclui_o_necessario(necessario):
    linhas = {
        linha.strip().rstrip("/").removeprefix("/")
        for linha in DOCKERIGNORE.read_text().splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    }
    assert necessario not in linhas
