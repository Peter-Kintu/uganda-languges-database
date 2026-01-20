# --- Stage 1: Build Dependencies ---
# Using Python 3.12 for stability and compatibility with Django 5.1+
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build-essential tools for packages like psycopg2 or Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a separate directory to keep the final image clean
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt

# --- Stage 2: Final Runtime Image ---
FROM python:3.12-slim

# Install only the runtime libraries needed for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the pre-installed packages from the builder stage
COPY --from=builder /install /usr/local
# Copy your actual project files
COPY . /app

# Set production environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV DEBUG="False"

# --- CRITICAL: Build-time Dummy Variables ---
# These allow 'collectstatic' to run without crashing for missing keys/DB
ENV SECRET_KEY="dummy-key-for-build-only"

# Run collectstatic. We use dummy vars to prevent DB connection attempts during build.
RUN DATABASE_URL=sqlite:///:memory: python manage.py collectstatic --noinput

# --- FINAL EXECUTION COMMAND ---
# 1. Migrates 'users' first (essential for CustomUser)
# 2. Migrates 'eshop' and others
# 3. Starts Gunicorn
CMD ["bash", "-c", "\
    python manage.py migrate users --noinput && \
    python manage.py migrate --noinput && \
    gunicorn myuganda.wsgi:application --bind 0.0.0.0:8000 --access-logfile - --error-logfile - \
"]