# --- Stage 1: Builder ---
# Uses a separate stage to build and install dependencies
FROM python:3.11-slim AS builder

# Set environment variables for non-interactive dependency installation
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app
COPY . /app

# Install dependencies into the default site-packages directory
# We install dependencies first so this layer can be cached if requirements.txt doesn't change
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# --- Stage 2: Production Image ---
# Uses the slim base image for the final, smaller production container
FROM python:3.11-slim
WORKDIR /app

# Copy only the necessary project files
# Dependencies are not copied from the builder stage in this revised method,
# they are installed directly in the builder and remain in the default location.
# COPY --from=builder /usr/local /usr/local # <--- This line is NOT needed with the above change
COPY . /app

# Ensure Gunicorn is available and running from the correct path
# The dependencies (including Django and Gunicorn) are already in the base image's site-packages

# CRITICAL FIX: Add a step to wait for the database, especially important for
# services like Koyeb/Render where the DB might initialize after the app starts.
# You will need to install a simple wait-for-it script or use a Python equivalent.
# For simplicity, we'll keep the original CMD but recommend using a startup script (see below).

# Collect static files
# Since your settings use Cloudinary for media, this step is just for admin/CSS/JS.
RUN python manage.py collectstatic --noinput

# Define the command to run the application
# Use shell form for easier command chaining
# The default $PORT variable in many platforms is crucial.
CMD python manage.py migrate --noinput && gunicorn myuganda.wsgi:application --bind 0.0.0.0:$PORT