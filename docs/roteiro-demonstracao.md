# Roteiro de demonstração (card #802)

Mostra o sistema inteiro numa máquina limpa, com um empréstimo atrasado nos dados de exemplo. Tempo estimado: 10 minutos.

## 0. Antes de começar

Requisitos: Git, Docker com o plugin Compose e um navegador. Nada mais.

```bash
mkdir pi4 && cd pi4
git clone https://github.com/ElVictron/pi4-0101-g5-backend-1
git clone https://github.com/ElVictron/pi4-0101-g5-backend-2
git clone https://github.com/ElVictron/pi4-0101-g5-frontend
cd pi4-0101-g5-backend-1
docker compose up --build
```

Espere os quatro serviços ficarem de pé (o Backend 1 só sobe depois que o Backend 2 está saudável). Em outro terminal, na mesma pasta:

```bash
docker compose exec -T postgres psql -U biblioteca -d biblioteca < db/dados-demo.sql
```

**Certificado.** O Backend 2 usa uma CA local gerada em `certs/ca.pem`. Importe esse arquivo como autoridade confiável no navegador (veja o README) e reinicie o navegador. Sem isso, o indicador do canto superior direito fica "Tempo real: desconectado".

Confira: `http://localhost:5173` abre o painel e o indicador mostra **Tempo real: conectado**.

## 1. Painel de disponibilidade (CT7)

1. Abra **Painel**. Aparecem os livros com exemplar disponível. *Dom Casmurro* mostra 1 de 3.
2. **Deixe esta aba aberta.** Ela será a "aba A".

## 2. Acervo e usuários (CT1, CT2, CT3, CT4)

1. Em **Acervo**, cadastre um livro (título, autor, ISBN de 10 ou 13 dígitos, exemplares) e pesquise por título, autor ou ISBN.
2. Em **Usuários**, cadastre um usuário (nome, CPF de 11 dígitos, e-mail ou telefone) e pesquise por nome ou CPF. Cada usuário lista seus empréstimos.
3. Tente repetir o ISBN ou o CPF: a tela mostra a mensagem do erro, sem dados falsos.

## 3. Empréstimo em tempo real (CT5, CT12, CT13)

1. Abra uma **nova aba** (a "aba B") em `http://localhost:5173` e vá em **Empréstimos**.
2. Busque o usuário *Carla Dias*, escolha o livro *O Cortiço* e clique em **Registrar empréstimo**.
3. Volte à **aba A**, sem recarregar: *O Cortiço* passou de 2 para 1 disponível.

## 4. Empréstimo atrasado (CT8)

1. Na aba B, em **Empréstimos**, abra a aba **Atrasados**: aparece o empréstimo de *Ana Souza* (*Dom Casmurro*), com o selo vermelho **Atrasado** e a data limite em vermelho (venceu há 5 dias).
2. Mostre também as abas **Ativos** e **Devolvidos**.

## 5. Devolução (CT6)

1. Na aba B, clique em **Devolver** no empréstimo atrasado de Ana Souza.
2. Na aba A: *Dom Casmurro* passou de 1 para 2 disponíveis, sem recarregar. O empréstimo vai para **Devolvidos**.

## 6. Backend 2 fora do ar (CT12, plano B)

1. `docker compose stop backend2`. O indicador mostra **Tempo real: desconectado**.
2. Registre um empréstimo na aba B: continua funcionando. O Backend 1 guarda o evento em `eventos_pendentes`.
3. `docker compose start backend2` e, depois que ele estiver saudável, reenvie:

```bash
docker compose exec backend1 python -m app.reenviar_eventos
```

4. O indicador volta para **conectado** e as listas recarregam sozinhas (a tela que já estava aberta recupera os dados na reconexão, CT13). Se abrir a tela com o Backend 2 ainda fora do ar, atualize a página depois que ele voltar.

## Verificação automática com Docker

Para conferir tudo de uma vez (Compose, dados de exemplo, teste das duas abas e nenhum evento pendente), com os três repositórios lado a lado:

```bash
pip install playwright && playwright install chromium
python scripts/integracao/verificar_docker.py
```

O script mostra um resumo com o que passou e o que falhou; `--derrubar` desliga o sistema no fim.

## Teste automático equivalente

Com o sistema de pé, o mesmo fluxo das seções 3 e 5 roda sozinho:

```bash
pip install playwright && playwright install chromium
python scripts/integracao/teste_duas_abas.py
```

Cria um livro e um usuário novos, faz o empréstimo e a devolução numa aba e confere o painel da outra. Passa com código de saída 0.

## Se algo não funcionar

| Sintoma | Causa provável |
|---|---|
| "Tempo real: desconectado" | O navegador não confia em `certs/ca.pem`, ou o Backend 2 não subiu (`docker compose ps`) |
| Telas com mensagem de erro de conexão | Backend 1 fora do ar ou `VITE_API_URL` diferente de `http://localhost:8000` |
| Dados de exemplo "não inseridos" | O banco já tinha dados; recrie com `docker compose down -v && docker compose up --build` |
