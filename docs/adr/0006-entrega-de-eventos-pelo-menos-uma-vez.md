# ADR 0006: Entrega de eventos "pelo menos uma vez", com reenvio

**Status:** aceito
**Data:** 2026-11-11

**Contexto:**
Depois de gravar um empréstimo ou uma devolução, o Backend 1 publica um evento no Backend 2 (CT12), que o repassa às telas (CT13). O empréstimo já foi gravado no banco; a falha do Backend 2 não pode desfazê-lo nem travar a tela de quem registrou. Ao mesmo tempo, o painel não pode ficar permanentemente desatualizado depois que o Backend 2 volta.

**Decisão:**
Se o Backend 2 não aceitar o evento, o Backend 1 o guarda na tabela `eventos_pendentes` e segue respondendo normalmente. O reenvio é feito por `python -m app.reenviar_eventos`. A entrega é, portanto, **"pelo menos uma vez" e sem ordem garantida**. O Backend 2 não deduplica nem reordena: repassa o que recebe. Quem exibe o dado se protege: o painel do frontend ignora o evento cujo `atualizadaEm` seja mais antigo que o último mostrado para o mesmo livro, e a lista de empréstimos recarrega do servidor a cada evento.

**Alternativas consideradas:**

* **Falhar o empréstimo se o Backend 2 estiver fora do ar:** não adotado porque a operação de negócio não depende do tempo real.
* **Fila com confirmação e ordem garantida (por exemplo, um broker de mensagens):** não adotado por ser mais infraestrutura do que o escopo pede.
* **Deduplicar e ordenar no Backend 2:** não adotado; ele ficaria com estado, e o frontend já resolve com o `atualizadaEm`.

**Consequências:**

* **Positivas:** o sistema continua funcionando com o Backend 2 fora do ar; nenhum evento é perdido enquanto estiver em `eventos_pendentes`.
* **Negativas:** o reenvio é manual (comando) e um evento reenviado pode chegar depois de um mais novo; as telas precisam tolerar duplicatas e ordem trocada. Fica sem ser tratado, por decisão do grupo, quem pode publicar no Backend 2: o `POST /eventos/biblioteca` não tem autenticação e o WebSocket não confere a origem (limite conhecido, capítulo 7 do Documento de Projeto).

**Referências:**

* [CT12 publicarAtualizacao](https://github.com/ElVictron/pi4-0101-g5-backend-2/blob/main/docs/contratos/CT12-publicarAtualizacao.md) e [CT13 bibliotecaAtualizada](https://github.com/ElVictron/pi4-0101-g5-backend-2/blob/main/docs/contratos/CT13-bibliotecaAtualizada.md)
* [ADR 0004: Implementar o componente WebSocket em Python](0004-websocket-em-python.md)
