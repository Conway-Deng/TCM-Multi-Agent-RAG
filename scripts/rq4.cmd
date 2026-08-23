@echo off
setlocal
set "REPO=%~dp0.."
set "PYTHON=%REPO%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo RQ4 Python environment not found: %PYTHON%
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0rq4.ps1" %*
exit /b %ERRORLEVEL%
