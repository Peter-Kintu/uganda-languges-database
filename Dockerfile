FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app

# Install dependencies and collect static files
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && python manage.py collectstatic --noinput

# Run migrations and start gunicorn
CMD bash -c "python manage.py migrate --noinput && gunicorn myuganda.wsgi:application --bind 0.0.0.0:$PORT"