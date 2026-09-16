@echo off
title SEO-AD AutoPilot Unified Launcher
echo ==================================================
echo   SEO-AD AutoPilot - Unified Launcher (Windows)
echo   Starting API Server (8000) and Web Console (3000)
echo ==================================================
echo.

REM Check for .env file
if not exist ".env" (
    echo [WARNING] .env file not found. Running setup first...
    call setup.bat
)

REM Activate Virtual Environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Start API Server in a new window
echo [1/2] Starting API Server on http://127.0.0.1:8000 in background...
start "SEO-AD API Server" cmd /k "python -m uvicorn apps.api.seo_ad_autopilot.app:create_app --factory --host 127.0.0.1 --port 8000"

REM Wait 2 seconds for API to spin up
timeout /t 2 /nobreak >nul

REM Start Web Console in a new window
echo [2/2] Starting Web Console on http://localhost:3000 in background...
start "SEO-AD Web Console" cmd /k "pnpm --dir apps/web dev"

echo.
echo ==================================================
echo   [SUCCESS] Both servers are starting up!
echo   - API: http://127.0.0.1:8000
echo   - Web Console: http://localhost:3000
echo   - API Docs: http://127.0.0.1:8000/docs
echo ==================================================
echo.
echo Press any key to exit this launcher (the service windows will remain open).
pause >nul
