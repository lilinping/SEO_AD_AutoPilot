@echo off
echo ========================================
echo   SEO-AD AutoPilot - Windows Startup
echo ========================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)

REM Check pnpm
pnpm --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing pnpm...
    npm install -g pnpm
)

REM Create virtual environment if not exists
if not exist ".venv" (
    echo [INFO] Creating Python virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install Python dependencies
echo [INFO] Installing Python dependencies...
pip install -r requirements.txt

REM Install Node.js dependencies
echo [INFO] Installing Node.js dependencies...
pnpm install

REM Copy .env if not exists
if not exist ".env" (
    echo [INFO] Creating .env from .env.example...
    copy .env.example .env
    echo [INFO] Please edit .env with your settings before running.
)

echo.
echo ========================================
echo   Setup complete!
echo ========================================
echo.
echo To start the application:
echo   1. API Server:   .venv\Scripts\uvicorn.exe apps.api.seo_ad_autopilot.app:create_app --factory --reload --host 127.0.0.1 --port 8000
echo   2. Web Console:  pnpm --dir apps/web dev
echo.
echo Or run this script again after editing .env
echo.
pause
