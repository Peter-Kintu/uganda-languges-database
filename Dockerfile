# --- Stage 1: Build Python Dependencies ---
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt


# --- Stage 2: Final Runtime Image ---
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    nodejs \
    npm \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libgbm1 \
    fonts-liberation \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . /app

RUN playwright install --with-deps chromium

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DEBUG="False"
ENV SECRET_KEY="build-time-dummy-key"

RUN which npm && node -v && npm -v
RUN python manage.py tailwind install
RUN python manage.py tailwind build
RUN python manage.py collectstatic --noinput

ENV GUNICORN_WORKERS=2
ENV GUNICORN_THREADS=2
ENV GUNICORN_MAX_REQUESTS=250
ENV GUNICORN_MAX_REQUESTS_JITTER=50
ENV GUNICORN_TIMEOUT=30

CMD ["bash", "-c", "set -e; \
    python - <<'PY'
import os
import sys
import time
from urllib.parse import urlparse

try:
    import psycopg
except Exception as exc:
    print(f'[startup] psycopg unavailable: {exc}')
    raise

database_url = os.getenv('DATABASE_URL')
if database_url:
    parsed = urlparse(database_url)
    host = parsed.hostname or 'localhost'
    port = parsed.port or 5432
    dbname = (parsed.path or '/postgres').lstrip('/')
    user = parsed.username or 'postgres'
    password = parsed.password or ''
    deadline = time.time() + 90
    last_error = None
    while time.time() < deadline:
        try:
            conn = psycopg.connect(host=host, port=port, dbname=dbname, user=user, password=password, connect_timeout=2)
            conn.close()
            print('[startup] Postgres ready')
            break
        except Exception as exc:
            last_error = exc
            print(f'[startup] Waiting for Postgres... {exc}')
            time.sleep(2)
    else:
        print(f'[startup] Postgres not ready after 90s: {last_error}')
        raise SystemExit(1)
else:
    print('[startup] No DATABASE_URL set; skipping Postgres wait check.')

redis_url = os.getenv('REDIS_URL')
if redis_url:
    try:
        import redis
        client = redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        print('[startup] Redis ready')
    except Exception as exc:
        print(f'[startup] Redis unavailable; app will continue with graceful fallback: {exc}')
else:
    print('[startup] No REDIS_URL set; app will continue with graceful fallback.')
PY
    python manage.py migrate --noinput
    exec gunicorn myuganda.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers ${GUNICORN_WORKERS:-2} \
        --threads ${GUNICORN_THREADS:-2} \
        --max-requests ${GUNICORN_MAX_REQUESTS:-250} \
        --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-50} \
        --timeout ${GUNICORN_TIMEOUT:-30} \
        --access-logfile - \
        --error-logfile -"]
