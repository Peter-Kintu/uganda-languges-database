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

exec gunicorn myuganda.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-2}" \
  --max-requests "${GUNICORN_MAX_REQUESTS:-250}" \
  --max-requests-jitter "${GUNICORN_MAX_REQUESTS_JITTER:-50}" \
  --timeout "${GUNICORN_TIMEOUT:-30}" \
  --access-logfile - \
  --error-logfile -
