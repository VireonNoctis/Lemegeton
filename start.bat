@echo off

REM ==========================================
REM   Discord Bot Startup Script
REM   Lemegeton Bot
REM ==========================================

echo Starting Lemegeton Discord Bot...
echo.

REM Change directory to the bot's folder
cd /d "%~dp0"

REM Check if Python is available
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python and add it to your system PATH
    pause
    exit /b 1
)

REM Run the bot using system Python
echo Starting Lemegeton Bot with system Python...
python bot.py

REM Keep the console open if the bot crashes
echo.
echo The bot has stopped or crashed.
pause