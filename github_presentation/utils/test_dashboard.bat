@echo off
echo Testing monitoring dashboard startup...
cd /d "%~dp0"

echo Current directory: %CD%

if exist ".venv\Scripts\python.exe" (
    echo Found virtual environment Python
    set PYTHON_CMD=.venv\Scripts\python.exe
) else (
    echo Using system Python
    set PYTHON_CMD=python
)

echo Testing Python command: %PYTHON_CMD%
%PYTHON_CMD% --version

echo.
echo Starting monitoring dashboard...
echo Command: start "Dashboard Test" /min %PYTHON_CMD% monitoring_dashboard.py
start "Dashboard Test" /min %PYTHON_CMD% monitoring_dashboard.py

echo.
echo Waiting 3 seconds...
timeout /t 3 /nobreak

echo.
echo Checking if port 5000 is in use...
netstat -an | findstr :5000

echo.
echo Test complete. Press any key to exit...
pause