@echo off@echo off

echo Starting Lemegeton Discord Bot...REM ==========================================

echo.REM   Discord Bot Startup Script

REM   Lemegeton Bot

REM Activate virtual environmentREM ==========================================

call .venv\Scripts\activate

REM Change directory to the bot's folder

REM Start the botcd /d "%~dp0"

python bot.py

REM Activate the virtual environment

REM Keep window open if bot crashesecho Activating virtual environment...

echo.call .venv\Scripts\activate

echo Bot has stopped. Press any key to close...

pause > nulREM Run the bot
echo Starting Lemegeton Bot...
python bot.py

REM Keep the console open if the bot crashes
echo.
echo The bot has stopped or crashed.
pause
: