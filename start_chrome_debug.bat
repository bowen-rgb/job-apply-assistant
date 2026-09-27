@echo off
setlocal
REM Dedicated browser profile. CDP is bound to localhost only.
set "BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%BROWSER%" set "BROWSER=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%BROWSER%" set "BROWSER=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist "%BROWSER%" set "BROWSER=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%BROWSER%" set "BROWSER=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not exist "%BROWSER%" (
  echo Chrome or Edge not found.
  exit /b 1
)
start "JAA Browser" "%BROWSER%" --remote-debugging-address=127.0.0.1 --remote-debugging-port=9222 --user-data-dir="%~dp0data\chrome-profile" https://chatgpt.com/
endlocal
