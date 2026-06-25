@echo off
REM ============================================================
REM  Excel Manager - remove the Windows Service
REM  RUN THIS AS ADMINISTRATOR.
REM ============================================================
cd /d "%~dp0"

if not exist nssm.exe (
  echo ERROR: nssm.exe not found in this folder.
  pause
  exit /b 1
)

nssm stop ExcelManager
nssm remove ExcelManager confirm

echo.
echo Service "ExcelManager" removed.
pause
