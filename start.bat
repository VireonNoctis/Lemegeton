@echo off
REM Activate virtual environment
call .venv\Scripts\activate

REM Optional: display which Python is used
where python

REM Set log file path
set LOG_FILE=bot_log.txt

:loop
echo ------------------------------ >> %LOG_FILE%
echo Bot starting at %date% %time% >> %LOG_FILE%
python bot.py >> %LOG_FILE% 2>&1
echo Bot crashed or exited at %date% %time%. Restarting in 5 seconds... >> %LOG_FILE%
timeout /t 5
goto loop
