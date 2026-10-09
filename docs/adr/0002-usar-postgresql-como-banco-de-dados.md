# ADR 0002: Usar PostgreSQL como banco de dados

**Status:** aceito

**Contexto:**
O sistema precisa armazenar informações relacionadas aos usuários, livros, empréstimos, devoluções e disponibilidade dos exemplares. Como essas informações possuem relações entre si e precisam ser mantidas de forma estruturada, é necessário utilizar um banco de dados relacional. O grupo decidiu utilizar PostgreSQL para armazenar os dados do sistema.

**Decisão:**
Utilizar o **PostgreSQL como banco de dados relacional** do sistema de gerenciamento de biblioteca.

**Alternativas consideradas:**

* **MySQL:** descartado porque o grupo optou pelo PostgreSQL como banco de dados do projeto.
* **SQLite:** descartado porque é mais adequado para cenários menores e locais, enquanto o projeto necessita de um banco de dados relacional para centralizar os dados da aplicação.
* **MongoDB:** descartado porque o projeto trabalha com informações estruturadas e relacionadas, como usuários, livros, empréstimos e devoluções, favorecendo o uso de um banco relacional.

**Consequências:**

* **Positivas:** os dados do sistema serão armazenados de forma estruturada, permitindo representar os relacionamentos entre usuários, livros e empréstimos. O PostgreSQL também permite utilizar recursos de um banco de dados relacional para manter a consistência dos registros.
* **Negativas:** será necessário configurar, administrar e manter um servidor PostgreSQL, além de definir corretamente as tabelas, relacionamentos e regras de integridade do banco.
