#!/usr/bin/env python3
"""Verifica o sistema inteiro com Docker (cards #780, #795, #801).

Sobe o Compose (frontend, Backend 1, Backend 2 e PostgreSQL), espera ficar de pé,
carrega os dados de exemplo, roda o teste das duas abas e confere que nenhum
evento ficou pendente. Mostra um resumo com o que passou e o que falhou.

Uso (da pasta do Backend 1, com os três repositórios lado a lado):
    pip install playwright && playwright install chromium
    python scripts/integracao/verificar_docker.py [--derrubar] [--sem-navegador]

Por padrão deixa o sistema rodando (http://localhost:5173); --derrubar faz
`docker compose down` no fim. --sem-navegador pula o teste das duas abas.
"""

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
RESULTADOS: list[tuple[str, bool, str]] = []


def registrar(nome, ok, detalhe=""):
    RESULTADOS.append((nome, ok, detalhe))
    print(f"[{'ok' if ok else 'FALHOU'}] {nome}" + (f": {detalhe}" if detalhe else ""), flush=True)
    return ok


def executar(comando, **kwargs):
    return subprocess.run(comando, cwd=RAIZ, text=True, **kwargs)


def compose(*args, **kwargs):
    return executar(["docker", "compose", *args], **kwargs)


def http_ok(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as resposta:
            return resposta.status == 200
    except (urllib.error.URLError, OSError):
        return False


def esperar(url, nome, limite=180):
    fim = time.time() + limite
    while time.time() < fim:
        if http_ok(url):
            return registrar(f"{nome} responde", True, url)
        time.sleep(3)
    return registrar(f"{nome} responde", False, f"sem resposta em {limite}s ({url})")


def resumo():
    print("\n=== Resumo ===")
    for nome, ok, detalhe in RESULTADOS:
        print(f"{'OK    ' if ok else 'FALHOU'} {nome}" + (f"  ({detalhe})" if detalhe else ""))
    falhas = [r for r in RESULTADOS if not r[1]]
    print("\nTudo certo." if not falhas else f"\n{len(falhas)} verificação(ões) falharam.")
    return 1 if falhas else 0


def main():
    analisador = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    analisador.add_argument("--derrubar", action="store_true", help="docker compose down no fim")
    analisador.add_argument(
        "--sem-navegador", action="store_true", help="pula o teste das duas abas"
    )
    args = analisador.parse_args()

    faltando = [
        p
        for p in ("../pi4-0101-g5-backend-2", "../pi4-0101-g5-frontend")
        if not (RAIZ / p).is_dir()
    ]
    if not registrar(
        "repositórios irmãos",
        not faltando,
        ", ".join(faltando) + " não encontrado(s)" if faltando else "",
    ):
        return resumo()

    versao = compose("version", capture_output=True)
    if not registrar(
        "docker compose disponível", versao.returncode == 0, (versao.stderr or "").strip()[:200]
    ):
        return resumo()

    subida = compose("up", "--build", "-d")
    if not registrar("docker compose up --build", subida.returncode == 0, "veja a saída acima"):
        compose("ps", "-a")
        compose("logs", "--tail", "40")
        return resumo()

    if esperar("http://localhost:8000/saude", "Backend 1") and esperar(
        "http://localhost:5173", "Frontend"
    ):
        estado = compose(
            "ps", "--format", "{{.Service}} {{.State}} {{.Health}}", capture_output=True
        )
        linhas = (estado.stdout or "").strip().splitlines()
        print("\n".join(linhas))
        # O Backend 1 só sobe com o Backend 2 saudável (depends_on).
        registrar(
            "Backend 2 saudável",
            any(x.startswith("backend2 running") and "healthy" in x for x in linhas),
            "healthcheck do Compose",
        )

        with open(RAIZ / "db" / "dados-demo.sql", "rb") as sql:
            carga = compose(
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "biblioteca",
                "-d",
                "biblioteca",
                stdin=sql,
                capture_output=True,
            )
        registrar(
            "dados de exemplo carregados", carga.returncode == 0, (carga.stderr or "").strip()[:200]
        )

        if not args.sem_navegador:
            teste = executar(
                [
                    sys.executable,
                    "scripts/integracao/teste_duas_abas.py",
                    "--prints",
                    "prints-docker",
                ]
            )
            registrar("teste das duas abas", teste.returncode == 0, "capturas em prints-docker/")

        pendentes = compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "biblioteca",
            "-d",
            "biblioteca",
            "-Atc",
            "select count(*) from eventos_pendentes",
            capture_output=True,
        )
        quantos = (pendentes.stdout or "").strip()
        registrar(
            "nenhum evento pendente (Backend 1 → Backend 2 por HTTPS)",
            pendentes.returncode == 0 and quantos == "0",
            f"pendentes: {quantos or '?'}",
        )
    if args.derrubar:
        compose("down")
    return resumo()


if __name__ == "__main__":
    sys.exit(main())
