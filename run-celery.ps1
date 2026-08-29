$ErrorActionPreference = 'Stop'

Write-Host "Starting Celery worker for myuganda..."
& celery -A myuganda worker -l info --pool=solo
