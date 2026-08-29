# Redis startup instructions

## Windows (local development)

Option 1: Docker

```powershell
docker run -d --name uganda-redis -p 6379:6379 redis:latest
```

Option 2: Installed Redis service

```powershell
redis-server
```

## Linux / macOS

```bash
redis-server
```

## Verify Redis is running

```bash
redis-cli ping
```

Expected response:

```text
PONG
```

## Django worker commands

Start Celery worker:

```bash
celery -A myuganda worker -l info
```

Start Celery beat (if you later add scheduled tasks):

```bash
celery -A myuganda beat -l info
```

## Important note

The app is set up to fall back gracefully when Redis is unavailable, but the cache and background worker features will work only when Redis is running.
