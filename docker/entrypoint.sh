#!/usr/bin/env bash
set -e

python - <<'PY'
import os
import time
from urllib.parse import urlparse


def wait_for_postgres():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print('[startup] No DATABASE_URL set; skipping Postgres wait check.')
        return

    try:
        import psycopg
    except Exception as exc:
        print(f'[startup] psycopg unavailable: {exc}')
        raise

    parsed = urlparse(database_url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 5432
    dbname = (parsed.path or '/postgres').lstrip('/')
    user = parsed.username or 'postgres'
    password = parsed.password or ''
    deadline = time.time() + 90

    while time.time() < deadline:
        try:
            conn = psycopg.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=2,
            )
            conn.close()
            print('[startup] Postgres ready')
            return
        except Exception as exc:
            print(f'[startup] Waiting for Postgres... {exc}')
            time.sleep(2)

    raise SystemExit('[startup] Postgres not ready after 90s')


def check_redis():
    redis_url = os.getenv('REDIS_URL')
    if not redis_url:
        print('[startup] No REDIS_URL set; app will continue with graceful fallback.')
        return

    try:
        import redis
        client = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        print('[startup] Redis ready')
    except Exception as exc:
        print(f'[startup] Redis unavailable; app will continue with graceful fallback: {exc}')


wait_for_postgres()
check_redis()
PY

python manage.py migrate --noinput

DB_CONNECTION_BUDGET="${WEB_DB_CONNECTION_BUDGET:-8}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
GUNICORN_THREADS="${GUNICORN_THREADS:-2}"
DB_ALIAS_COUNT=1
if [ -n "${READ_REPLICA_URL:-}" ]; then
    DB_ALIAS_COUNT=2
fi

if ! [[ "$DB_CONNECTION_BUDGET" =~ ^[1-9][0-9]*$ && "$GUNICORN_WORKERS" =~ ^[1-9][0-9]*$ && "$GUNICORN_THREADS" =~ ^[1-9][0-9]*$ ]]; then
    echo '[startup] WEB_DB_CONNECTION_BUDGET, GUNICORN_WORKERS, and GUNICORN_THREADS must be positive integers.' >&2
    exit 1
fi

PER_ALIAS_BUDGET=$((DB_CONNECTION_BUDGET / DB_ALIAS_COUNT))
if [ "$PER_ALIAS_BUDGET" -lt 1 ]; then
    echo '[startup] WEB_DB_CONNECTION_BUDGET must allow at least one connection per configured database.' >&2
    exit 1
fi

MAX_GUNICORN_PROCESSES=$((PER_ALIAS_BUDGET / GUNICORN_THREADS))
if [ "$MAX_GUNICORN_PROCESSES" -lt 1 ]; then
    echo '[startup] GUNICORN_THREADS exceeds the per-database connection budget.' >&2
    exit 1
fi
if [ "$GUNICORN_WORKERS" -gt "$MAX_GUNICORN_PROCESSES" ]; then
    echo "[startup] Clamping GUNICORN_WORKERS from $GUNICORN_WORKERS to $MAX_GUNICORN_PROCESSES for the database connection budget."
    GUNICORN_WORKERS="$MAX_GUNICORN_PROCESSES"
fi

echo "[startup] Web DB connection ceiling: $((GUNICORN_WORKERS * GUNICORN_THREADS * DB_ALIAS_COUNT)) across $DB_ALIAS_COUNT database(s)."

exec gunicorn myuganda.wsgi:application \
  --bind 0.0.0.0:8000 \
    --workers "$GUNICORN_WORKERS" \
    --threads "$GUNICORN_THREADS" \
  --max-requests "${GUNICORN_MAX_REQUESTS:-250}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-50}" \
  --timeout "${GUNICORN_TIMEOUT:-30}" \
  --access-logfile - \
  --error-logfile -
