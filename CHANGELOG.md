# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Cada versão reúne os três repositórios (Backend 1, Backend 2 e frontend). E é o entregável, CT é o contrato, TE é o teste e #número é o card do OpenProject.

## [1.0.0] - 2026-11-23
### Adicionado
- Documento de Projeto (`docs/documento-de-projeto.md`) com os 11 capítulos, e o README como capítulo 9 (#801, #802).
- Análise no SonarQube Cloud nos dois backends, a cada PR (#783).
- ADR 0005 (Compose único com TLS e CA local) e ADR 0006 (entrega de eventos "pelo menos uma vez").
- Medição do tempo do painel no teste das duas abas: 85 a 169 ms (RNF-04, TE-04).
### Alterado
- O Backend 1 sobe em HTTPS no Compose, como pedem as fichas CT1 a CT8 (D24).
- Fluxos E1 a E8 movidos para o repositório principal, em `docs/fluxos/`.

## [0.3.0] - 2026-11-11
### Adicionado
- Compose único com frontend, Backend 1, Backend 2 e PostgreSQL, e o serviço `certificados` que gera a CA local (#780).
- Teste de integração das duas abas com navegador real e script que verifica o sistema com Docker (#795).
- Roteiro de demonstração e dados de exemplo com um empréstimo atrasado (#802).
- Backend 2 completo: publicação de eventos (CT12), WebSocket (CT13), fila de 32 por painel e só TLS (#782).
### Corrigido
- CA local sem `keyUsage`, recusada pelo Python 3.13.
- Painel podia voltar a um valor antigo com evento fora de ordem; o frontend agora ignora o evento mais antigo (TE-08).

## [0.2.0] - 2026-11-07
### Adicionado
- Backend 1 completo: cadastro e consulta de livros e usuários, empréstimo, devolução, disponibilidade e consulta de empréstimos com `atrasado` calculado (E1 a E8; CT1 a CT8; #784 a #798).
- Reenvio dos eventos que o Backend 2 não aceitou (`eventos_pendentes`).
- Frontend com Painel, Acervo, Usuários e Empréstimos (#785 a #800).
### Removido
- ADR 0003 (WebSocket em Java), substituído pelo ADR 0004 (Python).

## [0.1.0] - 2026-10-13
### Adicionado
- Escopo da Entrega 1 (E1 a E8), ADRs 0001 a 0003 e contratos CT1 a CT11 (Entrega 2).
