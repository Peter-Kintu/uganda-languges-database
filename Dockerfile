# --- Stage 1: Build Python Dependencies ---
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build tools for C-extensions (psycopg, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into /install
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt


# --- Stage 2: Final Runtime Image ---
FROM python:3.12-slim

# 1. Install System Dependencies:
# - libpq5 for Postgres runtime
# - nodejs/npm for Tailwind compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copy installed Python packages from builder
COPY --from=builder /install /usr/local
COPY . /app

# 3. Production environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DEBUG="False"
ENV SECRET_KEY="build-time-dummy-key"

# 4. Compile Tailwind CSS
# Use 'tailwind' as the command (the library maps this to your 'theme' app internally)
# We run 'install' first to generate the local node_modules inside the 'theme' directory
RUN which npm && node -v && npm -v
RUN python manage.py tailwind install
RUN python manage.py tailwind build

# 5. Collect static files
RUN python manage.py collectstatic --noinput

# 5. Run collectstatic with dummy DB
RUN DATABASE_URL=sqlite:///:memory: python manage.py collectstatic --noinput

# --- FINAL EXECUTION COMMAND ---
CMD ["bash", "-c", "\
    python manage.py migrate users --noinput && \
    python manage.py migrate --noinput && \
    gunicorn myuganda.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 4 \
    --worker-class gthread \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
"]
