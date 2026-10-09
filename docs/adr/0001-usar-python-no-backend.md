# ADR 0001: Usar Python no backend

**Status:** aceito

**Contexto:**
O sistema de gerenciamento de biblioteca necessita de um backend responsável pelo processamento das regras de negócio, gerenciamento dos usuários, livros, empréstimos e devoluções e comunicação com o banco de dados. O grupo precisa utilizar uma tecnologia que permita desenvolver essas funcionalidades de forma organizada e adequada ao escopo do projeto. Python foi escolhido como linguagem para implementação do backend.

**Decisão:**
Utilizar **Python como linguagem de desenvolvimento do backend** do sistema de gerenciamento de biblioteca.

**Alternativas consideradas:**

* **Java:** descartado para o backend principal porque o grupo definiu Python como a tecnologia do backend, enquanto Java será utilizado especificamente para a implementação do WebSocket.
* **JavaScript/Node.js:** descartado porque o grupo optou por utilizar Python para concentrar a implementação das regras de negócio do backend.

**Consequências:**

* **Positivas:** o backend será desenvolvido utilizando uma única linguagem principal, facilitando a organização das regras de negócio e a manutenção do código. A separação entre Python no backend e Java no WebSocket também permite atender ao requisito de utilização das duas tecnologias.
* **Negativas:** a utilização de Java para o WebSocket e Python para o backend introduz duas linguagens diferentes no projeto, aumentando a necessidade de integração, configuração e conhecimento de tecnologias distintas.
