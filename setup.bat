@echo off
REM ============================================================
REM  Excel Manager - one-time setup (run once on the server PC)
REM ============================================================
cd /d "%~dp0"

echo [1/3] Creating Python virtual environment...
py -3 -m venv venv 2>nul || python -m venv venv
if not exist venv\Scripts\python.exe (
  echo ERROR: failed to create virtual environment.
  echo Make sure Python 3 is installed and on PATH.
  pause
  exit /b 1
)

echo [2/3] Installing dependencies...
venv\Scripts\python -m pip install --upgrade pip
venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: dependency installation failed. See messages above.
  pause
  exit /b 1
)

echo [3/3] Preparing .env...
if not exist .env copy .env.example .env

echo.
echo ============================================================
echo  Done. Now:
echo   1) Edit .env  -  set ADMIN_EMAIL, ADMIN_PASSWORD, SECRET_KEY
echo   2) Run run.bat to start the server
echo ============================================================
pause
