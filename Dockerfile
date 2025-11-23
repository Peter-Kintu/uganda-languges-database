FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies and collect static files
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && python manage.py collectstatic --noinput

# Run migrations in the correct order:
# 1. python manage.py migrate users: Ensures the custom user model migrates first.
# 2. python manage.py migrate: Runs all remaining migrations.
# 3. gunicorn: Starts the application server.
CMD bash -c "python manage.py migrate users --noinput && python manage.py migrate --noinput && gunicorn myuganda.wsgi:application --bind 0.0.0.0:$PORT"              