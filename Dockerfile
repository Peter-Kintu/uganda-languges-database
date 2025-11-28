FROM python:3.11-slim AS builder

WORKDIR /app
COPY . /app

# Install dependencies into a separate prefix
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt

FROM python:3.11-slim
WORKDIR /app

# Copy installed packages and project files
COPY --from=builder /install /usr/local
COPY . /app

# [cite_start]Collect static files [cite: 1, 2]
[cite_start]RUN python manage.py collectstatic --noinput [cite: 1, 2]

# NEW STEP: Create Superuser using Environment Variables
# This requires you to set DJANGO_SUPERUSER_USERNAME, DJANGO_SUPERUSER_EMAIL, and DJANGO_SUPERUSER_PASSWORD
# in your deployment environment (Render/Koyeb).
# We use the '|| true' trick to prevent the build from failing if the user already exists.
# RUN bash -c "python manage.py createsuperuser --noinput || true"

# [cite_start]Run migrations and start gunicorn [cite: 1, 2]
[cite_start]CMD ["bash", "-c", "python manage.py migrate --noinput && gunicorn myuganda.wsgi:application --bind 0.0.0.0:$PORT"] [cite: 1, 2]






