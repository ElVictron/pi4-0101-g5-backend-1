#!/usr/bin/env python3
"""Teste de integração do card #795 (duas abas, sistema real).

Com frontend, Backend 1, Backend 2 e PostgreSQL de pé, confere que um empréstimo
feito numa aba muda a quantidade no painel de disponibilidade aberto em outra
aba, sem recarregar, e que a devolução faz o caminho inverso (CT5, CT6, CT12, CT13).

Uso:
    pip install playwright && playwright install chromium
    python scripts/integracao/teste_duas_abas.py \
        [--frontend http://localhost:5173] [--api http://localhost:8000] \
        [--prints pasta] [--mostrar]

O certificado do Backend 2 é da CA local do Compose; o navegador do teste ignora
erros de certificado (equivale a confiar na CA). Cria um livro e um usuário novos
a cada execução, sem mexer nos dados existentes. Código de saída 0 = passou.
"""

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

TEMPO_MS = 10_000


def chamar_api(base, metodo, caminho, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    pedido = urllib.request.Request(
        base + caminho, data=dados, method=metodo, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(pedido, timeout=10) as resposta:
            return json.loads(resposta.read())
    except urllib.error.HTTPError as erro:
        raise SystemExit(f"{metodo} {caminho} falhou: {erro.code} {erro.read().decode()}") from erro


def passo(texto):
    print(f"[ok] {texto}", flush=True)


def quantidade(pagina, titulo):
    linha = pagina.locator("table[aria-label='Livros disponíveis'] tr", has_text=titulo)
    return linha.locator("td").nth(1)


def main():
    analisador = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    analisador.add_argument("--frontend", default="http://localhost:5173")
    analisador.add_argument("--api", default="http://localhost:8000")
    analisador.add_argument("--prints", help="pasta para salvar capturas de tela")
    analisador.add_argument("--mostrar", action="store_true", help="abre o navegador visível")
    args = analisador.parse_args()

    sufixo = str(int(time.time()))
    titulo = f"Livro de integração {sufixo}"
    nome = f"Leitor de integração {sufixo}"
    isbn = "978" + sufixo.rjust(10, "0")[-10:]
    cpf = "".join(str(random.randint(0, 9)) for _ in range(11))
    pasta = Path(args.prints) if args.prints else None
    if pasta:
        pasta.mkdir(parents=True, exist_ok=True)

    chamar_api(args.api, "GET", "/saude")
    chamar_api(
        args.api,
        "POST",
        "/livros",
        {"titulo": titulo, "autor": "Teste", "isbn": isbn, "quantidadeExemplares": 2},
    )
    chamar_api(
        args.api,
        "POST",
        "/usuarios",
        {"nome": nome, "cpf": cpf, "contato": f"leitor{sufixo}@exemplo.com"},
    )
    passo(f"dados criados: {titulo} (2 exemplares) e {nome}")

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=not args.mostrar)
        contexto = navegador.new_context(
            ignore_https_errors=True, viewport={"width": 1280, "height": 800}
        )
        aba_painel = contexto.new_page()
        aba_emprestimo = contexto.new_page()
        try:
            aba_painel.goto(args.frontend)
            aba_painel.evaluate("window.__marcador = 'sem-recarregar'")
            expect(aba_painel.get_by_role("status")).to_contain_text(
                "Tempo real: conectado", timeout=TEMPO_MS
            )
            passo("aba do painel conectada ao WSS do Backend 2")
            expect(quantidade(aba_painel, titulo)).to_have_text("2", timeout=TEMPO_MS)
            passo("painel mostra 2 exemplares disponíveis")
            if pasta:
                aba_painel.screenshot(path=str(pasta / "1-painel-antes.png"))

            aba_emprestimo.goto(args.frontend)
            aba_emprestimo.get_by_role("button", name="Empréstimos", exact=True).click()
            aba_emprestimo.get_by_label("Buscar usuário").fill(nome)
            aba_emprestimo.get_by_role("button", name="Buscar usuário").click()
            aba_emprestimo.get_by_label(f"{nome} (CPF {cpf})").check()
            aba_emprestimo.get_by_label("Livro").select_option(label=f"{titulo} (disponíveis: 2)")
            aba_emprestimo.get_by_role("button", name="Registrar empréstimo").click()
            expect(aba_emprestimo.get_by_text("Empréstimo registrado.")).to_be_visible(
                timeout=TEMPO_MS
            )
            passo("empréstimo registrado na outra aba")

            expect(quantidade(aba_painel, titulo)).to_have_text("1", timeout=TEMPO_MS)
            assert aba_painel.evaluate("window.__marcador") == "sem-recarregar", "a aba recarregou"
            passo("painel passou de 2 para 1 sem recarregar (CT12 + CT13)")
            if pasta:
                aba_painel.screenshot(path=str(pasta / "2-painel-depois-do-emprestimo.png"))

            linha = aba_emprestimo.locator("table[aria-label='Empréstimos'] tr", has_text=titulo)
            linha.get_by_role("button", name="Devolver").first.click()
            expect(linha.first).to_contain_text("Devolvido", timeout=TEMPO_MS)
            passo("devolução registrada na outra aba")

            expect(quantidade(aba_painel, titulo)).to_have_text("2", timeout=TEMPO_MS)
            assert aba_painel.evaluate("window.__marcador") == "sem-recarregar", "a aba recarregou"
            passo("painel voltou para 2 sem recarregar")
            if pasta:
                aba_painel.screenshot(path=str(pasta / "3-painel-depois-da-devolucao.png"))
        except Exception as erro:
            if pasta:
                aba_painel.screenshot(path=str(pasta / "falha-painel.png"))
                aba_emprestimo.screenshot(path=str(pasta / "falha-emprestimo.png"))
            print(f"[FALHOU] {erro}", file=sys.stderr)
            return 1
        finally:
            navegador.close()
    print("Integração OK: duas abas, sistema real.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
