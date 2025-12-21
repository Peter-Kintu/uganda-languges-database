# --- Stage 1: Build Dependencies ---
FROM python:3.11-slim AS builder

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
FROM python:3.11-slim

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
RUN DATABASE_URL=sqlite:///:memory: python manage.py collectstatic --noinput

# --- FINAL EXECUTION COMMAND ---
# 1. Migrates specific 'users' app first (due to CustomUser dependencies)
# 2. Migrates all other apps
# 3. Starts Gunicorn with logging enabled to help you see errors in the Render/Koyeb console
CMD ["bash", "-c", "\
    python manage.py migrate users --noinput && \
    python manage.py migrate --noinput && \
    gunicorn myuganda.wsgi:application --bind 0.0.0.0:$PORT --access-logfile - --error-logfile - \
"]