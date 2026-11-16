# ADR 0005: Compose único com TLS e CA local

**Status:** aceito
**Data:** 2026-11-11

**Contexto:**
O card #779 exige HTTPS entre os módulos e WSS do Backend 2 para o navegador, e só permite HTTP/WS no ambiente local com aprovação do professor. O Backend 2 só sobe com TLS (`SSL_CERTFILE` e `SSL_KEYFILE` obrigatórios). O sistema também precisa subir com um comando (card #780), em qualquer máquina com Docker, sem exigir que cada pessoa gere certificados à mão.

**Decisão:**
Manter HTTPS e WSS e subir o sistema inteiro por **um único `docker-compose.yml`, no repositório principal do grupo**, com os repositórios do Backend 2 e do frontend como pastas irmãs. Um serviço `certificados` (Alpine com OpenSSL) roda uma vez e gera, em `certs/`, uma **CA local** e o certificado do Backend 2, válido para `localhost` e `backend2`. O Backend 1 verifica o certificado do Backend 2 com a CA (`BACKEND2_CA_BUNDLE=/certs/ca.pem`). O navegador conecta direto no WSS do Backend 2 (`wss://localhost:8443/ws/biblioteca`), e quem demonstra confia em `certs/ca.pem` uma vez.

**Alternativas consideradas:**

* **HTTP e WS no Compose local:** não adotado porque o grupo decidiu manter HTTPS e WSS e porque exigiria aprovação do professor.
* **Passar o WebSocket pelo Nginx do frontend:** não adotado porque acrescenta um proxy de WebSocket a configurar e testar, sem ganho para a demonstração.
* **Desligar a verificação do certificado (`BACKEND2_VERIFY_TLS=false`):** mantido só como opção de emergência, nunca como padrão.
* **Um Compose por repositório:** não adotado porque o sistema só funciona com os quatro serviços juntos.

**Consequências:**

* **Positivas:** um comando sobe tudo; o TLS é verificado de verdade entre os módulos; o teste de ponta a ponta roda no mesmo ambiente da entrega.
* **Negativas:** os quatro repositórios precisam estar lado a lado; é preciso importar `certs/ca.pem` no navegador; a CA é de desenvolvimento e não serve para produção. Uma CA sem `basicConstraints` e `keyUsage` é recusada por versões recentes do Python e do OpenSSL, por isso o script de certificados os define.

**Referências:**

* [ADR 0004: Implementar o componente WebSocket em Python](0004-websocket-em-python.md)
* `docker-compose.yml` e `scripts/gerar-certificados.sh`, no [repositório principal](https://github.com/ElVictron/pi4-2026-2-0102-grupo05)
