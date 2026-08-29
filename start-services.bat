@echo off
setlocal

cd /d "%~dp0"

where docker >nul 2>nul
if not errorlevel 1 (
    echo Starting Redis with Docker...
    docker ps -a --format "{{.Names}}" | findstr /I "uganda-redis" >nul
    if errorlevel 1 (
        docker run -d --name uganda-redis -p 6379:6379 redis:latest
    ) else (
        echo Redis container already exists; starting it if needed...
        docker start uganda-redis
    )
    echo.
    echo Starting Celery worker...
    start "Celery Worker" cmd /k "celery -A myuganda worker -l info --pool=solo"
    echo.
    echo Services started. Redis is on port 6379.
    echo Use Ctrl+C in the Celery window to stop it.
    exit /b 0
)

where redis-server >nul 2>nul
if not errorlevel 1 (
    echo Starting Redis directly...
    start "Redis Server" cmd /k "redis-server"
    echo.
    echo Starting Celery worker...
    start "Celery Worker" cmd /k "celery -A myuganda worker -l info --pool=solo"
    echo.
    echo Services started. Redis is on port 6379.
    echo Use the terminal windows to stop each service.
    exit /b 0
)

echo Neither Docker nor redis-server was found on PATH.
echo Install Redis or Docker, then re-run this script.
exit /b 1
