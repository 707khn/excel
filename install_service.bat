@echo off
REM ============================================================
REM  Excel Manager - install as a Windows Service (autostart)
REM  Requires NSSM (https://nssm.cc/download) - put nssm.exe
REM  next to this script. RUN THIS AS ADMINISTRATOR.
REM ============================================================
cd /d "%~dp0"

if not exist nssm.exe (
  echo ERROR: nssm.exe not found in this folder.
  echo Download it from https://nssm.cc/download and place nssm.exe here.
  pause
  exit /b 1
)
if not exist venv\Scripts\uvicorn.exe (
  echo ERROR: virtual environment missing. Run setup.bat first.
  pause
  exit /b 1
)

if not exist logs mkdir logs

nssm install ExcelManager "%~dp0venv\Scripts\uvicorn.exe" "app.main:app --host 0.0.0.0 --port 8000"
nssm set ExcelManager AppDirectory "%~dp0"
nssm set ExcelManager Start SERVICE_AUTO_START
nssm set ExcelManager AppStdout "%~dp0logs\service.log"
nssm set ExcelManager AppStderr "%~dp0logs\service.log"
nssm start ExcelManager

echo.
echo ============================================================
echo  Service "ExcelManager" installed and started.
echo  It will now start automatically when this PC powers on,
echo  with no login required.
echo  Access from any office PC: http://THIS-PC-IP:8000
echo ============================================================
pause
