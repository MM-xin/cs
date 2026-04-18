@echo off
setlocal

set "PYTHON_EXE=C:\Users\Administrator\miniconda3\envs\cs\python.exe"

if not exist "%PYTHON_EXE%" (
  echo [ERROR] Python not found: %PYTHON_EXE%
  echo Please update PYTHON_EXE in start_backend.bat
  pause
  exit /b 1
)

cd /d "%~dp0"
echo Starting FastAPI at http://127.0.0.1:8000 ...
"%PYTHON_EXE%" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

endlocal
