#!/usr/bin/env bash
# Sobe (ou para) um PostgreSQL 16 local e descartável para os testes.
# Uso: scripts/test-db.sh start | stop | url
# Variáveis: PG_BIN (pasta dos binários), PG_PORT (padrão 54329),
#            PG_DATA (padrão /tmp/pi4-backend1-pgdata), PG_OS_USER (usuário do
#            sistema que roda o servidor quando o script é executado como root).
set -euo pipefail

PG_BIN="${PG_BIN:-$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1)}"
PG_PORT="${PG_PORT:-54329}"
PG_DATA="${PG_DATA:-/tmp/pi4-backend1-pgdata}"
PG_OS_USER="${PG_OS_USER:-postgres}"
DB_NAME="${DB_NAME:-biblioteca_teste}"

run() {
  if [ "$(id -u)" = "0" ]; then runuser -u "$PG_OS_USER" -- "$@"; else "$@"; fi
}

case "${1:-start}" in
  start)
    if [ ! -s "$PG_DATA/PG_VERSION" ]; then
      mkdir -p "$PG_DATA"
      [ "$(id -u)" = "0" ] && chown "$PG_OS_USER" "$PG_DATA"
      run "$PG_BIN/initdb" -D "$PG_DATA" -U postgres -A trust --encoding=UTF8 --locale=C.UTF-8 >/dev/null
    fi
    if ! run "$PG_BIN/pg_ctl" -D "$PG_DATA" status >/dev/null 2>&1; then
      run "$PG_BIN/pg_ctl" -D "$PG_DATA" -o "-p $PG_PORT -k /tmp -c listen_addresses=localhost" -l "$PG_DATA/server.log" -w start >/dev/null
    fi
    run "$PG_BIN/psql" -h localhost -p "$PG_PORT" -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 \
      || run "$PG_BIN/createdb" -h localhost -p "$PG_PORT" -U postgres "$DB_NAME"
    echo "postgresql://postgres@localhost:$PG_PORT/$DB_NAME"
    ;;
  stop)
    run "$PG_BIN/pg_ctl" -D "$PG_DATA" -m fast stop >/dev/null && echo "parado"
    ;;
  url)
    echo "postgresql://postgres@localhost:$PG_PORT/$DB_NAME"
    ;;
  *) echo "uso: $0 start|stop|url" >&2; exit 2 ;;
esac
