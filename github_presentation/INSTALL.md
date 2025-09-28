# Installation and Setup Guide

This guide will help you set up the Lemegeton Discord Bot for development or production use.

## 🚀 Quick Start (Recommended)

### Windows Users
```bash
# Run the automated setup script
setup.bat
```

### Linux/Mac Users
```bash
# Make the script executable and run it
chmod +x setup.sh
./setup.sh
```

## 📋 Manual Installation

If you prefer to set up the bot manually, follow these steps:

### Prerequisites
- Python 3.9 or higher
- Git (for cloning the repository)
- A Discord Bot Token ([Create one here](https://discord.com/developers/applications))

### Step 1: Clone and Navigate
```bash
git clone https://github.com/Kyerstorm/lemegeton-test.git
cd lemegeton-test
```

### Step 2: Set up Virtual Environment
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment
```bash
# Copy the example configuration
cp .env.example .env

# Edit .env with your actual values
# You'll need at minimum:
# - DISCORD_TOKEN (your bot token)
# - GUILD_ID (your Discord server ID)
```

### Step 5: Create Necessary Directories
```bash
mkdir -p data logs
```

### Step 6: Run the Bot
```bash
python bot.py
```

## ⚙️ Configuration

### Required Environment Variables

Edit your `.env` file with these essential variables:

```env
# Discord Configuration (Required)
DISCORD_TOKEN=your_discord_bot_token_here
BOT_ID=your_bot_application_id
GUILD_ID=your_primary_guild_id

# Optional API Keys
STEAM_API_KEY=your_steam_api_key_here
```

### Getting Your Discord Bot Token

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section
4. Create a bot and copy the token
5. Enable necessary bot permissions and intents

### Setting Up Bot Permissions

Your bot needs these permissions:
- Send Messages
- Use Slash Commands
- Embed Links
- Attach Files
- Read Message History
- Manage Messages (for timestamp conversion)
- Manage Webhooks (for timestamp conversion)

## 🎯 Features Setup

### AniList Integration
- No additional setup required
- Features work out of the box

### Steam Integration
1. Get a Steam Web API Key from [Steam](https://steamcommunity.com/dev/apikey)
2. Add it to your `.env` file as `STEAM_API_KEY`

### News Monitoring (Twitter)
1. Install snscrape: `pip install snscrape`
2. Note: Twitter/X may block scraping attempts

### Timestamp Conversion
- No additional setup required
- Users can set their timezone with `/set_timezone`

## 🛠️ Development Setup

### For Contributors

1. Fork the repository
2. Clone your fork
3. Follow the installation steps above
4. Create a new branch for your feature
5. Make changes and test thoroughly
6. Submit a pull request

### Running Tests
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/
```

### Code Style
```bash
# Format code with black
black .

# Lint with flake8
flake8 .

# Type checking with mypy
mypy .
```

## 📊 Database

The bot uses SQLite for data storage. Databases are automatically created in the `data/` directory:

- `database.db` - Main bot database
- `news_cog.db` - Twitter monitoring data
- Various JSON files for caching

## 🔧 Troubleshooting

### Common Issues

**Bot not responding to commands:**
- Check that the bot is online in your Discord server
- Verify slash commands are synced (restart the bot)
- Check bot permissions

**Database errors:**
- Ensure the `data/` directory exists
- Check file permissions
- Delete corrupted database files (they'll be recreated)

**Import errors:**
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Verify you're using Python 3.9 or higher

**API key errors:**
- Double-check your `.env` file configuration
- Ensure no extra spaces or quotes around values

### Getting Help

- Check the [Issues](https://github.com/Kyerstorm/lemegeton-test/issues) page
- Read the documentation in the `docs/` folder
- Join our Discord server for community support

## 🚀 Production Deployment

### Railway (Recommended)
1. Fork the repository
2. Connect Railway to your GitHub
3. Set environment variables in Railway dashboard
4. Deploy automatically

### Docker (Advanced)
```bash
# Build image
docker build -t lemegeton-bot .

# Run container
docker run -d --name lemegeton -v $(pwd)/data:/app/data lemegeton-bot
```

### Linux Server
```bash
# Use systemd for process management
sudo cp lemegeton.service /etc/systemd/system/
sudo systemctl enable lemegeton
sudo systemctl start lemegeton
```

## 📈 Monitoring

The bot includes built-in monitoring:
- Log files in `logs/` directory
- Performance metrics
- Health check endpoints

Monitor logs with:
```bash
tail -f logs/bot.log
```

## 🔄 Updates

To update the bot:
```bash
git pull origin main
pip install -r requirements.txt
python bot.py
```

## 🔐 Security

- Never commit `.env` files or tokens to version control
- Regularly rotate API keys
- Use proper file permissions on production servers
- Monitor logs for suspicious activity

---

For more detailed information, see the [README.md](README.md) and documentation in the `docs/` folder.