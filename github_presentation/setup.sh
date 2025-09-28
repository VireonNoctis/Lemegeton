#!/bin/bash
# Lemegeton Discord Bot - Setup Script
# This script helps you set up the bot for development or production

set -e  # Exit on any error

echo "🤖 Lemegeton Discord Bot Setup"
echo "=============================="
echo

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>/dev/null | cut -d" " -f2)
if [ -z "$python_version" ]; then
    echo "❌ Python 3 is required but not found. Please install Python 3.9 or higher."
    exit 1
fi

major_version=$(echo $python_version | cut -d"." -f1)
minor_version=$(echo $python_version | cut -d"." -f2)

if [ "$major_version" -lt 3 ] || ([ "$major_version" -eq 3 ] && [ "$minor_version" -lt 9 ]); then
    echo "❌ Python 3.9 or higher is required. Found: Python $python_version"
    exit 1
fi

echo "✅ Python $python_version found"

# Create virtual environment
echo
echo "🔧 Setting up virtual environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo
echo "🔄 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Dependencies installed"

# Set up configuration
echo
echo "⚙️ Setting up configuration..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ Created .env file from template"
    echo "⚠️  Please edit .env with your Discord bot token and other settings"
else
    echo "✅ .env file already exists"
fi

# Create necessary directories
echo
echo "📁 Creating directories..."
mkdir -p data logs
echo "✅ Created data and logs directories"

# Initialize database
echo
echo "💾 Initializing database..."
python3 -c "
import asyncio
from database import create_tables
asyncio.run(create_tables())
print('✅ Database tables created')
" 2>/dev/null || echo "ℹ️  Database will be initialized on first run"

echo
echo "🎉 Setup complete!"
echo
echo "Next steps:"
echo "1. Edit the .env file with your bot token and settings"
echo "2. Run the bot with: python3 bot.py"
echo
echo "For more information, see README.md"