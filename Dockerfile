# --- Stage 1: Build Dependencies ---
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build-essential tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt

# --- Stage 2: Final Runtime Image ---
FROM python:3.12-slim

# Install PostgreSQL runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages and project files
COPY --from=builder /install /usr/local
COPY . /app

# Production environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DEBUG="False"
ENV SECRET_KEY="dummy-key-for-build-only"

# Run collectstatic with dummy DB
RUN DATABASE_URL=sqlite:///:memory: python manage.py collectstatic --noinput

# --- FINAL EXECUTION COMMAND ---
# IMPROVEMENTS:
# 1. Added --timeout 120: Gives AliExpress API time to respond (Default is only 30s).
# 2. Added --workers 2: Better handling of concurrent requests on low-RAM instances.
# 3. Added --worker-class gthread: Better for I/O bound tasks like API syncing.
# 4. Added --threads 4: Allows workers to handle the sync without blocking the whole app.
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