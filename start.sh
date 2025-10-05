#!/bin/bash
# Railway startup script with volume initialization

# Check if volume needs initialization
if [ ! -f "/app/data/database.db" ]; then
    echo "🔧 First run detected - initializing volume..."
    python init_volume.py
else
    echo "✅ Volume already initialized"
fi

# Start the bot
echo "🚀 Starting Discord bot..."
python bot.py
