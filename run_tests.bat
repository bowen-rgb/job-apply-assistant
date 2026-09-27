@echo off
setlocal
cd /d %~dp0
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
  if errorlevel 1 exit /b 1
  .venv\Scripts\python.exe -m unittest discover -s tests -v
) else (
  py -3 -m pip install -r requirements-dev.txt
  if errorlevel 1 exit /b 1
  py -3 -m unittest discover -s tests -v
)
pause
endlocal
