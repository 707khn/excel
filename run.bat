@echo off
REM ============================================================
REM  Excel Manager - start the server (manual launch)
REM ============================================================
cd /d "%~dp0"

if not exist .env (
  echo ERROR: .env missing. Run setup.bat first.
  pause
  exit /b 1
)
if not exist venv\Scripts\uvicorn.exe (
  echo ERROR: virtual environment missing. Run setup.bat first.
  pause
  exit /b 1
)

echo Excel Manager is starting on http://0.0.0.0:8000
echo Open from any office PC: http://THIS-PC-IP:8000
echo Press Ctrl+C to stop.
echo.
venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
