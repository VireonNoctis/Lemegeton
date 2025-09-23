@echo off

REM ==========================================
REM   Discord Bot Setup Script
REM   Lemegeton Bot - User Installation
REM ==========================================

echo Setting up Lemegeton Discord Bot (User Installation)...
echo.

REM Change directory to the bot's folder
cd /d "%~dp0"

REM Check if Python is available
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org and add it to your system PATH
    pause
    exit /b 1
)

REM Display Python version
echo Found Python:
python --version

REM Check if pip is available
echo.
echo Checking pip installation...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: pip is not available
    echo Please ensure pip is installed with Python
    pause
    exit /b 1
)

REM Install required packages to user directory
echo.
echo Installing required packages to user directory...
echo This will install packages to your user Python directory (~/.local on Linux, %APPDATA% on Windows).
echo This doesn't require administrator privileges and won't affect system Python.
echo.

echo Installing packages from requirements.txt...
pip install --user -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Package installation failed
    echo Please check your internet connection and try again
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Setup complete!
echo You can now run the bot using start.bat
echo ==========================================
echo.
pause