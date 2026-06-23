@echo off
echo ========================================
echo   SEO-AD AutoPilot - Start API Server
echo ========================================
echo.

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Start API server
echo Starting API server at http://127.0.0.1:8000
echo Press Ctrl+C to stop
echo.
uvicorn apps.api.seo_ad_autopilot.app:create_app --factory --reload --host 127.0.0.1 --port 8000
