@echo off
echo ========================================
echo   SEO-AD AutoPilot - Start Web Console
echo ========================================
echo.

REM Start web console
echo Starting web console at http://localhost:3000
echo Press Ctrl+C to stop
echo.
pnpm --dir apps/web dev
