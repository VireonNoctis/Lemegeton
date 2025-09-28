@echo off
REM Lemegeton Discord Bot - Windows Setup Script
REM This script helps you set up the bot for development or production on Windows

echo 🤖 Lemegeton Discord Bot Setup
echo ==============================
echo.

REM Check if Python is installed
echo 📋 Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is required but not found. Please install Python 3.9 or higher.
    echo Download from: https://python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set python_version=%%v
echo ✅ Python %python_version% found

REM Create virtual environment
echo.
echo 🔧 Setting up virtual environment...
if not exist ".venv" (
    python -m venv .venv
    echo ✅ Virtual environment created
) else (
    echo ✅ Virtual environment already exists
)

REM Activate virtual environment
echo.
echo 🔄 Activating virtual environment...
call .venv\Scripts\activate.bat

REM Upgrade pip and install dependencies
echo.
echo 📦 Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo ✅ Dependencies installed

REM Set up configuration
echo.
echo ⚙️ Setting up configuration...
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo ✅ Created .env file from template
    echo ⚠️  Please edit .env with your Discord bot token and other settings
) else (
    echo ✅ .env file already exists
)

REM Create necessary directories
echo.
echo 📁 Creating directories...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
echo ✅ Created data and logs directories

echo.
echo 🎉 Setup complete!
echo.
echo Next steps:
echo 1. Edit the .env file with your bot token and settings
echo 2. Run the bot with: python bot.py
echo.
echo For more information, see README.md
echo.
pause