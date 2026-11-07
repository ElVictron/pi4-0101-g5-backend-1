# Backend 1 — API REST (FastAPI) do sistema de biblioteca.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv/backend1

# Dependências primeiro, para aproveitar o cache de camadas.
COPY pyproject.toml ./
COPY app ./app
RUN pip install .

COPY db ./db
COPY scripts/iniciar.sh ./scripts/iniciar.sh

RUN useradd --system --uid 10001 --home-dir /srv/backend1 backend1 \
    && chmod 0755 scripts/iniciar.sh
USER backend1

EXPOSE 8000

# GET /saude não consulta o banco (00-convencoes §9). Com TLS ligado, o
# healthcheck fala HTTPS sem conferir o certificado, só dentro do contêiner.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD ["python", "-c", "import os,ssl,urllib.request as u; tls=bool(os.environ.get('SSL_CERTFILE')); url=('https' if tls else 'http')+'://127.0.0.1:'+os.environ.get('PORTA','8000')+'/saude'; ctx=ssl._create_unverified_context() if tls else None; u.urlopen(url, timeout=2, context=ctx).read()"]

CMD ["./scripts/iniciar.sh"]
