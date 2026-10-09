# ADR 0003: Implementar o WebSocket em Java

**Status:** aceito

**Contexto:**
O projeto possui a necessidade de implementar comunicação utilizando WebSocket. O backend principal do sistema será desenvolvido em Python, enquanto o WebSocket deverá ser implementado em Java. Essa separação exige que o componente responsável pela comunicação em tempo real seja desenvolvido como uma parte específica da arquitetura do sistema.

**Decisão:**
Implementar o **componente WebSocket em Java**, mantendo o backend principal da aplicação desenvolvido em Python.

**Alternativas consideradas:**

* **Implementar o WebSocket em Python:** descartado porque o projeto possui como requisito a implementação do WebSocket utilizando Java.
* **Implementar o WebSocket diretamente no frontend:** descartado porque a comunicação WebSocket deve ser realizada por um componente específico do sistema, mantendo a responsabilidade de comunicação em tempo real separada da interface.
* **Não utilizar WebSocket:** descartado porque a implementação dessa tecnologia faz parte dos requisitos do projeto.

**Consequências:**

* **Positivas:** o projeto atende ao requisito de implementação de WebSocket em Java e mantém o backend principal em Python. A separação também permite tratar a comunicação em tempo real como um componente específico da arquitetura.
* **Negativas:** o sistema precisará trabalhar com Python e Java simultaneamente, aumentando a complexidade da arquitetura. Também será necessário definir e implementar corretamente a comunicação entre o componente WebSocket e o restante do sistema.
