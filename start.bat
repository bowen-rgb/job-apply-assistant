@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "VENV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
  echo .venv is missing or incomplete. Run run_windows.bat first.
  pause
  exit /b 1
)
call start_chrome_debug.bat
timeout /t 2 /nobreak >nul
start "JAA Server" "%VENV_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8765"
endlocal
