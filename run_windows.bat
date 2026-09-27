@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PIP_PREFER_BINARY=1"

echo ==================================================
echo Job Apply Assistant V8.3 - Windows setup
echo ==================================================

echo [1/8] Checking virtual environment...
set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if exist ".venv" if not exist "%VENV_PY%" (
  echo Found an incomplete .venv. Recreating it...
  rmdir /s /q ".venv"
)

if not exist "%VENV_PY%" (
  echo Creating .venv...
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3.12 -m venv ".venv" >nul 2>&1
    if not exist "%VENV_PY%" py -3 -m venv ".venv"
  ) else (
    where python >nul 2>&1
    if errorlevel 1 goto :no_python
    python -m venv ".venv"
  )
)

if not exist "%VENV_PY%" goto :venv_failed
echo Using: "%VENV_PY%"

echo [2/8] Updating pip/setuptools/wheel...
"%VENV_PY%" -m pip install --upgrade "pip>=26.0,<27" setuptools wheel
if errorlevel 1 goto :failed

echo [3/8] Installing small core runtime...
"%VENV_PY%" -m pip install --prefer-binary -r requirements.txt
if errorlevel 1 goto :failed

echo [4/8] Installing JobSpy separately...
"%VENV_PY%" -m pip install --prefer-binary -r requirements-jobspy.txt
if errorlevel 1 goto :failed

echo [5/8] Installing Scrapling fetchers only...
"%VENV_PY%" -m pip install --prefer-binary -r requirements-scrapling.txt
if errorlevel 1 goto :failed

echo [6/8] Installing Playwright Chromium...
"%VENV_PY%" -m playwright install chromium
if errorlevel 1 goto :failed

echo [7/8] Installing Scrapling browser components...
"%VENV_PY%" -c "from scrapling.cli import install; install(['--force'], standalone_mode=False)"
if errorlevel 1 (
  echo WARNING: Scrapling browser component setup failed.
  echo The app can still start with JobSpy, normal HTTP fetching, and Chrome/CDP.
)

echo [8/8] Preparing profile and starting...
if not exist "profile.json" copy /Y "profile.example.json" "profile.json" >nul

call start_chrome_debug.bat
if errorlevel 1 (
  echo WARNING: Chrome/Edge debug browser did not start. The local dashboard can still start.
)
timeout /t 2 /nobreak >nul
start "JAA Server" "%VENV_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:8765"

echo.
echo Setup complete. Dashboard: http://127.0.0.1:8765
echo For later launches, use start.bat.
exit /b 0

:no_python
echo.
echo ERROR: Python was not found. Install Python 3.11+ and rerun this file.
pause
exit /b 1

:venv_failed
echo.
echo ERROR: Could not create .venv.
echo If a .venv folder remains, delete it and rerun run_windows.bat.
pause
exit /b 1

:failed
echo.
echo ERROR: Setup failed at the step shown above.
echo The window will remain open so you can copy the error message.
pause
exit /b 1
