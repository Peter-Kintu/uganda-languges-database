FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies if needed (e.g., for psycopg2 or pillow)
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a separate prefix
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt

FROM python:3.11-slim

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local
# Copy project files
COPY . /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations and start gunicorn
# Use --chdir to ensure gunicorn is in the correct directory
CMD ["bash", "-c", "python manage.py migrate --noinput && gunicorn --chdir /app myuganda.wsgi:application --bind 0.0.0.0:$PORT"]