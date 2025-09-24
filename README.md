# 🎌 Lemegeton - Multi-Guild Discord Anime & Gaming Bot

A comprehensive Discord bot that combines anime/manga tracking with AI-powered recommendations, featuring interactive UIs, personalized suggestions, community challenges, and **full multi-guild deployment support**.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Discord.py](https://img.shields.io/badge/discord.py-2.6.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-production--ready-success.svg)
![Multi-Guild](https://img.shields.io/badge/multi--guild-ready-brightgreen.svg)
![Railway](https://img.shields.io/badge/railway-deployable-purple.svg)

## ✨ Key Features

### 📚 Anime & Manga Tracking
- **AniList Integration** - Connect your AniList profile for seamless tracking
- **AI-Powered Recommendations** - Get personalized suggestions based on your highly-rated titles (8.0+)
- **Interactive Browsing** - Browse anime, manga, light novels, and general novels with advanced filtering
- **Profile Viewing** - Comprehensive user statistics and favorite series
- **Watchlist Management** - Track your current and planned anime/manga
- **Trending Lists** - Stay updated with the latest popular series

### 🏆 Community Features

- **Global Challenges** - Participate in community-wide anime/manga challenges
- **Leaderboards** - Compete with other users across various metrics
- **User Comparison** - Compare profiles and statistics with friends
- **Achievement System** - Unlock achievements for various milestones

### 🌐 Multi-Guild Support & Configuration

- **Multi-Server Ready** - Deploy across unlimited Discord servers with complete data isolation
- **Guild-Specific Settings** - Each server maintains independent challenge roles and configurations
- **Flexible Role Management** - Configure different challenge roles for each server
- **Cross-Guild User Data** - Users maintain their profiles across all servers while respecting server-specific settings

#### Guild Configuration Commands (Requires "Manage Roles" Permission)

- **`/setup_challenge_role`** - Configure challenge roles for your server
  - Set roles for different challenge types and difficulty levels
  - Assign multiple roles per challenge category
- **`/list_challenge_roles`** - View current challenge roles configuration
  - Display all configured roles for your server
- **`/remove_challenge_role`** - Remove specific challenge role assignments
  - Clean up outdated or incorrect role configurations

### 🤖 Utility Commands
- **Timestamp Converter** - Convert timestamps between formats
- **Random Recommendations** - Get surprise anime/manga suggestions
- **Statistics Tracking** - Detailed user engagement analytics
- **AniList Username Verification** - Check username validity before registration
- **Feedback System** - Report issues and suggest improvements

## 🚀 Multi-Guild Deployment (Railway - Recommended)

**✨ Deploy once, use everywhere!** Lemegeton now supports multiple Discord servers with a single deployment.

The easiest way to deploy Lemegeton for multiple guilds is using Railway's free hosting:

1. **Fork this repository** to your GitHub account
2. **Create a Railway account** at [railway.app](https://railway.app)
3. **Deploy from GitHub** - Select your forked repository
4. **Set environment variables** (see [Railway Deployment Guide](docs/RAILWAY_DEPLOYMENT.md))
   - Set `PRIMARY_GUILD_ID` for backward compatibility with existing setups
   - The bot will automatically work across all servers it's invited to
5. **Invite the bot** to multiple servers - Each server can configure independent challenge roles
5. **Deploy!** Your bot will be online 24/7

📖 **Full Railway Guide**: [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md)

## 🛠️ Manual Installation

### Prerequisites
- **Python 3.8+** - [Download Python](https://python.org/downloads/)
- **Discord Bot Token** - [Discord Developer Portal](https://discord.com/developers/applications)
- **Git** - [Download Git](https://git-scm.com/downloads)

### Step 1: Clone Repository

```bash
git clone https://github.com/Kyerstorm/lemegeton-test.git
cd lemegeton-test
```

### Step 2: Install Dependencies

#### Option A: Quick Setup (Windows)
```cmd
# Run the automated setup script
setup_user.bat
```

#### Option B: Manual Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment

Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your_discord_bot_token_here
GUILD_ID=your_discord_server_id
BOT_ID=your_bot_user_id
CHANNEL_ID=your_main_channel_id
DATABASE_PATH=data/database.db
ENVIRONMENT=development
```

### Step 4: Run the Bot

#### Local Development
1. Run `start.bat` to start the bot with monitoring
2. Visit `http://localhost:5000` for monitoring dashboard
3. Bot supports unlimited Discord servers simultaneously

#### Production Deployment
1. See `docs/RAILWAY_DEPLOYMENT.md` for web-based deployment
2. See `docs/RAILWAY_CLI_DEPLOYMENT.md` for CLI deployment
3. All configuration files are in the `config/` folder

## 🎯 Commands

> **💡 Multi-Guild Note:** All commands work across multiple Discord servers. Server administrators can use guild configuration commands to customize challenge roles for their specific server.

### Account Management
- `/login` - Register your AniList username
- `/check_anilist` - Verify if an AniList username exists
- `/profile` - View your AniList profile and statistics

### Recommendations & Discovery
- `/recommendations` - Get AI-powered recommendations based on your 8.0+ rated titles
- `/trending` - View current trending anime and manga
- `/random` - Get random anime/manga suggestions
- `/search_similar` - Find anime similar to a specific title

### Interactive Features
- `/browse` - Interactive category browsing (Anime/Manga/Light Novels/Novels)
- `/compare` - Compare your profile with another user
- `/watchlist` - Manage your anime/manga watchlist

### Challenges & Competition
- `/challenge_progress` - View your current challenge progress
- `/challenge_leaderboard` - See challenge rankings
- `/leaderboard` - View various community leaderboards

### Guild Configuration (Requires "Manage Roles" Permission)

- `/setup_challenge_role` - Configure challenge roles for your server
- `/list_challenge_roles` - View current challenge roles configuration  
- `/remove_challenge_role` - Remove specific challenge role assignments

### Utilities
- `/timestamp` - Convert and format timestamps
- `/stats` - View bot usage statistics
- `/feedback` - Send feedback to the developers
- `/help` - Interactive help system with command categories

## 📁 Project Structure

```
lemegeton-test/
├── 📂 bot.py                 # Main bot entry point
├── 📂 config.py              # Configuration management
├── 📂 database.py            # Database operations
├── 📂 requirements.txt       # Python dependencies
├── 📂 start.bat              # Windows startup script
├── 📂 cogs/                  # Bot command modules
│   ├── anilist.py           # AniList integration
│   ├── recommendations.py   # AI recommendation system
│   ├── browse.py            # Interactive browsing
│   ├── challenge_*.py       # Challenge system
│   ├── help.py              # Interactive help system
│   └── ...                  # Other command modules
├── 📂 helpers/               # Utility functions
│   ├── media_helper.py      # AniList API helpers
│   └── challenge_helper.py  # Challenge management
├── 📂 data/                  # Database and cache files
├── 📂 docs/                  # Documentation
├── 📂 logs/                  # Application logs
└── 📂 scripts/               # Maintenance scripts
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `DISCORD_TOKEN` | Discord bot token | ✅ | `MTk4NjIyNDgzNDcxOTI1MjQ4...` |
| `PRIMARY_GUILD_ID` | Primary Discord server ID (for backward compatibility) | ✅ | `123456789012345678` |
| `GUILD_ID` | Legacy guild ID (maintained for compatibility) | ❌ | `123456789012345678` |
| `BOT_ID` | Discord bot user ID | ✅ | `987654321098765432` |
| `CHANNEL_ID` | Main channel ID (for primary guild) | ✅ | `555666777888999000` |
| `DATABASE_PATH` | Database file path | ❌ | `/app/database.db` |
| `ENVIRONMENT` | Runtime environment | ❌ | `production` |

**Multi-Guild Notes:**
- The bot now supports deployment across multiple Discord servers
- `PRIMARY_GUILD_ID` is used for backward compatibility with existing single-guild configurations
- Each guild maintains independent challenge role configurations
- User data is shared across guilds while respecting server-specific settings

### Bot Configuration (`config.py`)

```python
# Multi-Guild Discord settings
PRIMARY_GUILD_ID = int(os.getenv("PRIMARY_GUILD_ID", os.getenv("GUILD_ID", 0)))
GUILD_ID = PRIMARY_GUILD_ID  # Backward compatibility
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# Database
DB_PATH = os.getenv("DATABASE_PATH", "database.db")
```

## 🐛 Troubleshooting

### Common Issues

#### "Command failed with exit code 1"
- **Check Python version**: Ensure Python 3.8+
- **Dependencies**: Run `pip install -r requirements.txt`
- **Permissions**: Ensure proper file permissions

#### "Bot not responding to commands"

- **Permissions**: Check bot has necessary permissions in Discord
- **Token**: Verify Discord bot token is correct
- **Guild ID**: Ensure PRIMARY_GUILD_ID matches your Discord server (for multi-guild deployments)
- **Slash Commands**: Commands may take up to 1 hour to sync on new guilds

#### "Multi-Guild Configuration Issues"

- **Challenge Roles**: Use `/setup_challenge_role` in each server to configure server-specific roles
- **Permissions**: Ensure users have "Manage Roles" permission to configure guild settings
- **Data Isolation**: User data is shared across guilds, but guild configurations are independent
- **Environment Variables**: Ensure PRIMARY_GUILD_ID is set for backward compatibility

#### "Database errors"
- **File permissions**: Ensure bot can write to database directory
- **Path**: Check DATABASE_PATH is correct
- **SQLite**: Ensure SQLite3 is available

#### "AniList API errors"
- **Rate limits**: AniList API has rate limits
- **Network issues**: Check internet connectivity
- **Invalid usernames**: Ensure usernames exist on AniList

### Debug Mode

Enable detailed logging by modifying `config.py`:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Log Files

The bot creates detailed logs in the `logs/` directory:
- `bot.log` - Main bot operations
- `database.log` - Database operations
- `media_helper.log` - AniList API calls
- Command-specific logs for debugging

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/YourUsername/lemegeton-test.git
cd lemegeton-test

# Create development environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Run in development mode
python bot.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](docs/LICENSE) file for details.

## 🆘 Support

- **Discord Server**: [https://discord.gg/xUGD7krzws](https://discord.gg/xUGD7krzws)
- **Documentation**: [docs/README.md](docs/README.md)
- **Issues**: [GitHub Issues](https://github.com/Kyerstorm/lemegeton-test/issues)
- **Feature Requests**: Use the `/feedback` command in Discord

## 🙏 Acknowledgments

- **AniList API** - For providing comprehensive anime/manga data
- **Discord.py** - Excellent Discord bot framework
- **Railway** - Reliable hosting platform
- **Contributors** - Thank you to all who have contributed to this project

---

Made with ❤️ for the anime community
 
 