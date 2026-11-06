# ADR 0004: Implementar o componente WebSocket em Python

**Status:** aceito
**Data:** 2026-10-31

**Contexto:**
O grupo decidiu desenvolver os serviços de backend em Python, conforme a visão geral do sistema. O ADR 0003 registrou uma decisão anterior de usar Java no componente WebSocket, mas essa escolha não corresponde à tecnologia adotada pelo grupo. A aplicação precisa manter comunicação em tempo real entre os serviços e a interface, conforme os contratos e fluxos documentados.

**Decisão:**
Implementar em **Python** o componente responsável pela comunicação WebSocket. A conexão entre cliente e servidor seguirá o transporte seguro definido na arquitetura (WSS em ambientes com TLS), e o componente atenderá aos contratos de publicação/atualização. Este ADR define a linguagem, mas não impõe uma biblioteca ou framework que ainda não foi escolhido.

**Alternativas consideradas:**

* **Implementar o WebSocket em Java:** não adotado porque a arquitetura e a decisão atual do grupo padronizam os backends em Python. A decisão histórica do ADR 0003 fica substituída por este registro.
* **Implementar a comunicação diretamente no frontend:** não adotado porque a publicação dos eventos e a integração com os contratos pertencem ao componente de backend.
* **Não utilizar WebSocket:** não adotado porque os fluxos de atualização em tempo real dependem desse canal.

**Consequências:**

* **Positivas:** a tecnologia do componente fica consistente com os demais serviços Python, com a visão geral e com a decisão comunicada pelo grupo.
* **Negativas:** a equipe deve selecionar e documentar a biblioteca Python durante a implementação e validar a integração WSS e os eventos descritos nos contratos.

**Referências:**

* [ADR 0001: Usar Python no backend](0001-usar-python-no-backend.md)
* [ADR 0003: decisão histórica substituída](0003-implementar-websocket-em-java.md)
* [Visão geral do sistema](https://github.com/ELVictron/pi4-0101-g5-frontend/blob/main/docs/fluxos/visao-geral.md)
* Contratos CT12 e CT13 dos repositórios de backend.
