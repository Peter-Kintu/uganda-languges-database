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

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations safely and start gunicorn
CMD ["bash", "-c", "python manage.py migrate users 0001_initial --fake --noinput && python manage.py migrate --noinput && gunicorn myuganda.wsgi:application --bind 0.0.0.0:$PORT"]