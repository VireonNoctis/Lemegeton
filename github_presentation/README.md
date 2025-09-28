# Lemegeton Discord Bot

![Discord](https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)

A comprehensive Discord bot built with discord.py featuring anime/manga tracking, Steam integration, timestamp conversion, news monitoring, and much more.

## ✨ Features

### 🎌 AniList Integration
- **Profile Management**: Link and display AniList profiles
- **Anime & Manga Tracking**: Browse, search, and track anime/manga
- **Statistics**: View detailed user statistics and leaderboards
- **Recommendations**: Get personalized anime/manga recommendations
- **Daily Updates**: Automatic manga/anime completion tracking
- **Watchlist Management**: Manage your anime watchlist
- **Trending Content**: Stay updated with trending anime/manga

### 🎮 Steam Integration
- **Profile Display**: Show Steam user profiles and game libraries
- **Game Information**: Detailed game statistics and information
- **Profile Comparison**: Compare Steam profiles between users
- **Game Recommendations**: Get game recommendations based on your library
- **Deals Tracking**: Monitor Steam deals and sales
- **Trending Games**: View trending games on Steam

### ⏰ Timestamp Conversion
- **Smart Detection**: Automatically detects time mentions in chat
- **Timezone Support**: Per-user timezone configuration
- **Universal Display**: Times display correctly for all users
- **Multiple Formats**: Supports various time formats (12h/24h, relative dates)

### 📰 News Monitoring (Guild-Only)
- **Twitter Integration**: Monitor Twitter accounts for updates
- **Custom Notifications**: Set up notifications in specific channels
- **Keyword Filtering**: Filter out unwanted content
- **Real-time Updates**: Background monitoring with instant notifications

### 🛠️ Server Management
- **User Cleanup**: Automatic cleanup of inactive users
- **Invite Tracking**: Track server invites and member recruitment
- **Feedback System**: Collect and manage user feedback
- **Server Configuration**: Comprehensive server settings management

### 🎯 Challenges & Gamification
- **Custom Challenges**: Create and manage server challenges
- **Progress Tracking**: Monitor challenge completion
- **Leaderboards**: Competitive ranking systems
- **Role Management**: Automatic role assignment based on achievements

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- AniList API access (automatic)
- Steam Web API Key (optional, for Steam features)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Kyerstorm/lemegeton-test.git
   cd lemegeton-test
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/Mac
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your bot token and other settings
   ```

5. **Run the bot**
   ```bash
   python bot.py
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```env
# Discord Bot Configuration
DISCORD_TOKEN=your_discord_bot_token_here
BOT_ID=your_bot_application_id
GUILD_ID=your_primary_guild_id

# API Keys (Optional)
STEAM_API_KEY=your_steam_api_key
ANILIST_CLIENT_ID=your_anilist_client_id

# Database Configuration
DATABASE_URL=sqlite:///data/database.db

# Logging
LOG_LEVEL=INFO
```

### Guild vs Global Commands

This bot uses a hybrid approach for command deployment:

- **Global Commands**: Available in all servers (most features)
- **Guild Commands**: Server-specific commands (news monitoring)

See `guild_sync.txt` for detailed command deployment information.

## 📚 Command Categories

### AniList Commands
- `/profile` - Display your AniList profile
- `/browse` - Browse anime/manga with filters
- `/random` - Get random anime/manga recommendations
- `/trending` - View trending content
- `/stats` - View detailed statistics
- `/leaderboard` - Server leaderboards
- `/watchlist` - Manage your watchlist

### Steam Commands
- `/steam profile` - Display Steam profile
- `/steam game` - Get game information
- `/steam compare` - Compare profiles
- `/steam recommendations` - Get game recommendations
- `/steam deals` - View current deals
- `/steam trending` - View trending games

### Utility Commands
- `/timestamp_watch` - Toggle automatic timestamp conversion
- `/set_timezone` - Set your timezone
- `/help` - Comprehensive help system
- `/feedback` - Submit feedback

### Guild-Only Commands
- `/news add` - Monitor Twitter accounts
- `/news remove` - Stop monitoring accounts
- `/news list` - List monitored accounts
- `/news status` - Check system status

## 🏗️ Architecture

### Project Structure
```
├── bot.py              # Main bot entry point
├── config.py           # Configuration management
├── database.py         # Database utilities
├── cogs/               # Command modules
│   ├── anilist/        # AniList integration
│   ├── gaming/         # Steam and gaming features
│   ├── utilities/      # Utility commands
│   ├── server_management/ # Server tools
│   └── challenges/     # Challenge system
├── helpers/            # Utility functions
├── data/               # Database files
├── logs/               # Log files (gitignored)
└── docs/               # Documentation
```

### Key Technologies
- **discord.py 2.6+**: Modern Discord API wrapper
- **aiohttp**: Asynchronous HTTP requests
- **aiosqlite**: Async SQLite database
- **snscrape**: Twitter scraping (optional)
- **Pillow**: Image processing
- **python-dotenv**: Environment management

## 🔧 Development

### Adding New Features

1. Create a new cog in the appropriate category folder
2. Follow the existing patterns for command structure
3. Add proper error handling and logging
4. Update documentation and help text
5. Consider guild vs global command placement

### Database Schema

The bot uses SQLite with the following main tables:
- `users`: User profiles and settings
- `guilds`: Server configurations
- `challenges`: Challenge tracking
- `accounts`: Twitter monitoring (news feature)
- `filters`: Content filtering rules

### Logging

Comprehensive logging system with:
- Rotating log files
- Per-cog log separation
- Error tracking and reporting
- Performance monitoring

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](docs/CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](docs/LICENSE) file for details.

## 🙏 Credits

**Created by**: [Vireon](https://github.com/Kyerstorm)

### Special Thanks
- discord.py community for excellent documentation
- AniList for providing a robust API
- Steam for the Web API
- All contributors and users who helped improve this bot

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Kyerstorm/lemegeton-test/issues)
- **Documentation**: Check the `docs/` folder
- **Discord**: Join our support server (link in bot status)

## 🚧 Roadmap

### Upcoming Features
- [ ] Web dashboard for server management
- [ ] Enhanced statistics and analytics
- [ ] Mobile app companion
- [ ] Plugin system for custom extensions
- [ ] Multi-language support
- [ ] Voice channel integration
- [ ] Advanced moderation tools

### Recent Updates
- ✅ Guild-specific news commands
- ✅ Enhanced timezone support
- ✅ Improved error handling
- ✅ Performance optimizations
- ✅ Better logging system

## 🛡️ Privacy & Security

This bot respects user privacy:
- Minimal data collection
- Secure API key handling
- Local database storage
- No data selling or sharing
- Transparent data usage

For more information, see our [Privacy Policy](docs/PRIVACY.md).

---

**Created by Kyerstom & Vireon | Powered by discord.py**