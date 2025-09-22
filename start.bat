@echo off

REM ==========================================
REM   Discord Bot Startup Script
REM   Lemegeton Bot
REM ==========================================

echo Starting Lemegeton Discord Bot...
echo.

REM Change directory to the bot's folder
cd /d "%~dp0"

REM Activate the virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate

REM Run the bot
echo Starting Lemegeton Bot...
python bot.py

REM Keep the console open if the bot crashes
echo.
echo The bot has stopped or crashed.
pause