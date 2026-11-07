#!/bin/sh
# Inicia o Backend 1 com Uvicorn. O TLS é ligado aqui (D14): com
# SSL_CERTFILE e SSL_KEYFILE definidos, o servidor fala HTTPS.
set -eu

PORTA="${PORTA:-8000}"

if [ -n "${SSL_CERTFILE:-}" ] && [ -n "${SSL_KEYFILE:-}" ]; then
  exec uvicorn --factory app.main:create_app --host 0.0.0.0 --port "$PORTA" \
    --ssl-certfile "$SSL_CERTFILE" --ssl-keyfile "$SSL_KEYFILE"
fi

if [ -n "${SSL_CERTFILE:-}${SSL_KEYFILE:-}" ]; then
  echo "SSL_CERTFILE e SSL_KEYFILE precisam ser definidos juntos." >&2
  exit 1
fi

exec uvicorn --factory app.main:create_app --host 0.0.0.0 --port "$PORTA"
