# ADR 0003: Implementar o WebSocket em Java

**Status:** substituído por [ADR 0004: Implementar o WebSocket em Python](0004-websocket-em-python.md)

> Este documento é mantido como registro histórico. A decisão vigente está no ADR 0004 e segue a arquitetura Python documentada na visão geral do sistema.

**Contexto original:**
O projeto possui a necessidade de implementar comunicação utilizando WebSocket. O backend principal do sistema será desenvolvido em Python, enquanto o WebSocket deverá ser implementado em Java. Essa separação exige que o componente responsável pela comunicação em tempo real seja desenvolvido como uma parte específica da arquitetura do sistema.

**Decisão original (substituída):**
Implementar o **componente WebSocket em Java**, mantendo o backend principal da aplicação desenvolvido em Python.

**Alternativas consideradas na decisão original:**

* **Implementar o WebSocket em Python:** descartado naquela decisão porque o projeto parecia exigir Java para o WebSocket. Essa decisão foi substituída pelo ADR 0004, que alinha o componente à escolha atual do grupo.
* **Implementar o WebSocket diretamente no frontend:** descartado naquela decisão porque a comunicação WebSocket deve ser realizada por um componente específico do sistema, mantendo a responsabilidade de comunicação em tempo real separada da interface.
