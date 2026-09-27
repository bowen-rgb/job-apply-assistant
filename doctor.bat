@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe doctor.py
) else (
  py -3 doctor.py
)
pause
