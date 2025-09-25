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

- **Guild-aware Data Isolation** - The bot is multi-guild aware: most database operations and interactive flows are scoped to the guild where they were triggered. Unregistration, registrations, leaderboards, and challenge role configuration are implemented to respect per-guild data isolation while still allowing cross-guild user profiles where appropriate.

### 🏆 Community Features

PRIMARY_GUILD_ID=123456789012345678
 # 🎌 Lemegeton - Multi-Guild Discord Anime & Gaming Bot

A comprehensive Discord bot that combines anime/manga tracking with AI-powered recommendations, featuring interactive UIs, personalized suggestions, community challenges, and guild-aware multi-server deployment support.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Discord.py](https://img.shields.io/badge/discord.py-2.6.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-production--ready-success.svg)

## ✨ Key Features

### 📚 Anime & Manga Tracking

- **AniList Integration** — Connect your AniList profile for seamless tracking.
- **AI-Powered Recommendations** — Personalized suggestions based on your highly-rated titles (8.0+).
- **Interactive Browsing** — Browse anime, manga, light novels, and general novels with advanced filtering.
- **Profile Viewing** — Comprehensive user statistics and favorite series.
- **Watchlist Management** — Track your current and planned anime/manga.
- **Trending Lists** — Stay updated with the latest popular series.

- **Guild-aware Data Isolation** — The bot is multi-guild aware: most database operations and interactive flows are scoped to the guild where they were triggered. Unregistration, registrations, leaderboards, and challenge role configuration respect per-guild isolation while still allowing shared user profiles across guilds where appropriate.

### 🏆 Community Features

- **Global Challenges** — Participate in community-wide anime/manga challenges.
- **Leaderboards** — Compete with other users across various metrics.
- **User Comparison** — Compare profiles and statistics with friends.
- **Achievement System** — Unlock achievements for various milestones.

### 🌐 Multi-Guild Support & Configuration

- **Multi-Server Ready** — Deploy across multiple Discord servers with per-guild configuration and data isolation.
- **Guild-Specific Settings** — Each server maintains independent challenge roles and configurations.
- **Flexible Role Management** — Configure different challenge roles for each server.
- **Cross-Guild User Profiles** — Users keep a single profile shared across guilds; most actions (unregister, challenge progress, role assignments) are applied per-guild.

#### Guild Configuration Commands (Requires "Manage Roles" Permission)

- **`/setup_challenge_role`** — Configure challenge roles for your server.
  - Set roles for different challenge types and difficulty levels.
  - Assign multiple roles per challenge category.
- **`/list_challenge_roles`** — View current challenge roles configuration.
  - Display all configured roles for your server.
- **`/remove_challenge_role`** — Remove specific challenge role assignments.
  - Clean up outdated or incorrect role configurations.

### 🤖 Utility Commands

- **Timestamp Converter** — Convert timestamps between formats.
- **Random Recommendations** — Get surprise anime/manga suggestions.
- **Statistics Tracking** — Detailed user engagement analytics.
- **AniList Username Verification** — Check username validity before registration.
- **Feedback System** — Report issues and suggest improvements.

## 🚀 Deployment (Local or Railway)

**Deploy once, use everywhere!** Lemegeton supports multiple Discord servers with a single deployment.

### Railway (Recommended)

The easiest way to deploy Lemegeton for multiple guilds is using Railway's hosting:

1. Fork this repository to your GitHub account.
2. Create a Railway account at https://railway.app and connect your repo.
3. Set environment variables (see `config.py` and the `Environment Variables` section below).
4. Invite the bot to your servers — each server can configure independent challenge roles.
5. Deploy — the bot will run continuously.

Full guide: `docs/RAILWAY_DEPLOYMENT.md`.

### Manual / Local Development

#### Prerequisites

- Python 3.8+
- Discord Bot Token (from Discord Developer Portal)
- Git

#### Quick start (Windows)

```cmd
# Run the automated setup script (if present)
setup_user.bat
```

#### Manual setup

```bash
# Clone and enter repo
#### "Bot not responding to commands"
cd lemegeton-test

# Create virtual environment
python -m venv venv

# Activate venv (Windows)
venv\\Scripts\\activate

# Install deps
pip install -r requirements.txt
```

#### Run the bot (development)

From the project root:

```powershell
python bot.py
```

Visit `http://localhost:5000` for the monitoring dashboard if enabled.

## 🎯 Commands (summary)

> Multi-guild note: commands operate across multiple Discord servers. Server admins can configure per-guild settings via the guild configuration commands.

### Account Management

- `/login` — Register your AniList username.
- `/check_anilist` — Verify an AniList username exists.
- `/profile` — View your AniList profile and statistics.

### Recommendations & Discovery

- `/recommendations` — AI-powered recommendations.
- `/trending` — Current trending anime and manga.
- `/random` — Random anime/manga suggestions.
- `/search_similar` — Find anime similar to a specific title.

### Interactive Features

- `/browse` — Interactive category browsing (Anime/Manga/Light Novels/Novels).
- `/compare` — Compare your profile with another user.
- `/watchlist` — Manage your anime/manga watchlist.

### Challenges & Competition

- `/challenge_progress` — View your current challenge progress.
- `/challenge_leaderboard` — See challenge rankings.
- `/leaderboard` — View community leaderboards.

### Guild Configuration (Requires "Manage Roles")

- `/setup_challenge_role` — Configure challenge roles for your server.
- `/list_challenge_roles` — View configured roles.
- `/remove_challenge_role` — Remove configured roles.

### Utilities

- `/timestamp` — Convert and format timestamps.
- `/stats` — View bot usage statistics.
- `/feedback` — Send feedback to the developers.
- `/help` — Interactive help system.

## 📁 Project Structure

```
lemegeton-test/
├── bot.py
├── config.py
├── database.py
├── requirements.txt
├── start.bat
├── cogs/
└── ...
```

## ⚙️ Configuration

### Environment Variables

The bot uses `python-dotenv` to load environment variables from a `.env` file in the project root. Example:

```env
DISCORD_TOKEN=your_discord_bot_token_here
# PRIMARY_GUILD_ID is recommended for backward compatibility (legacy GUILD_ID is supported)
PRIMARY_GUILD_ID=123456789012345678
# Optional legacy variable
GUILD_ID=123456789012345678
BOT_ID=your_bot_user_id
CHANNEL_ID=your_main_channel_id
DATABASE_PATH=data/database.db
ENVIRONMENT=development
```

- `PRIMARY_GUILD_ID` — Used for backward compatibility (recommended).
- `GUILD_ID` — Legacy environment key (optional).
- `DATABASE_PATH` — Path to SQLite DB file; defaults to `data/database.db` if not set.

### `config.py` snippet

```python
PRIMARY_GUILD_ID = int(os.getenv("PRIMARY_GUILD_ID", os.getenv("GUILD_ID", 0)))
GUILD_ID = PRIMARY_GUILD_ID
DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data", "database.db"))
```

## 🐛 Troubleshooting & Developer Notes

- If `tools/analyze_db.py` or other maintenance scripts report "unable to open database file", run them from the repository root or set `DATABASE_PATH` explicitly.
- The codebase is async-first (uses `aiosqlite` and `aiohttp`). Prefer `aiohttp` for HTTP clients in cogs to avoid blocking the event loop.
- Logs are written to the `logs/` directory. Increase logging in `config.py` during development with `logging.basicConfig(level=logging.DEBUG)`.

## 🤝 Contributing

Contributions welcome. Fork, branch, commit, and open a PR.

## 📄 License

MIT — see `docs/LICENSE`.

---

Made with ❤️ for the anime community

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

### Developer notes

- Analyzer and small maintenance scripts (for example `tools/analyze_db.py`) assume they're executed from the project root and may use the `DATABASE_PATH` environment variable or the repo `data/database.db` default. If you get an "unable to open database file" error when running tools, make sure you're running them from the repository root or set `DATABASE_PATH` explicitly.

- The codebase is async-first and uses `aiosqlite` and `aiohttp` for non-blocking DB and HTTP operations. Prefer `aiohttp` when adding new API integrations rather than introducing sync HTTP libraries.

Enable detailed logging by modifying `config.py` or using environment variables. Example:

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

- **Guild-aware Data Isolation** - The bot is multi-guild aware: most database operations and interactive flows are scoped to the guild where they were triggered. Unregistration, registrations, leaderboards, and challenge role configuration are implemented to respect per-guild data isolation while still allowing cross-guild user profiles where appropriate.

### 🏆 Community Features

PRIMARY_GUILD_ID=123456789012345678
 # 🎌 Lemegeton - Multi-Guild Discord Anime & Gaming Bot

A comprehensive Discord bot that combines anime/manga tracking with AI-powered recommendations, featuring interactive UIs, personalized suggestions, community challenges, and guild-aware multi-server deployment support.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Discord.py](https://img.shields.io/badge/discord.py-2.6.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-production--ready-success.svg)

## ✨ Key Features

### 📚 Anime & Manga Tracking

- **AniList Integration** — Connect your AniList profile for seamless tracking.
- **AI-Powered Recommendations** — Personalized suggestions based on your highly-rated titles (8.0+).
- **Interactive Browsing** — Browse anime, manga, light novels, and general novels with advanced filtering.
- **Profile Viewing** — Comprehensive user statistics and favorite series.
- **Watchlist Management** — Track your current and planned anime/manga.
- **Trending Lists** — Stay updated with the latest popular series.

- **Guild-aware Data Isolation** — The bot is multi-guild aware: most database operations and interactive flows are scoped to the guild where they were triggered. Unregistration, registrations, leaderboards, and challenge role configuration respect per-guild isolation while still allowing shared user profiles across guilds where appropriate.

### 🏆 Community Features

- **Global Challenges** — Participate in community-wide anime/manga challenges.
- **Leaderboards** — Compete with other users across various metrics.
- **User Comparison** — Compare profiles and statistics with friends.
- **Achievement System** — Unlock achievements for various milestones.

### 🌐 Multi-Guild Support & Configuration

- **Multi-Server Ready** — Deploy across multiple Discord servers with per-guild configuration and data isolation.
- **Guild-Specific Settings** — Each server maintains independent challenge roles and configurations.
- **Flexible Role Management** — Configure different challenge roles for each server.
- **Cross-Guild User Profiles** — Users keep a single profile shared across guilds; most actions (unregister, challenge progress, role assignments) are applied per-guild.

#### Guild Configuration Commands (Requires "Manage Roles" Permission)

- **`/setup_challenge_role`** — Configure challenge roles for your server.
  - Set roles for different challenge types and difficulty levels.
  - Assign multiple roles per challenge category.
- **`/list_challenge_roles`** — View current challenge roles configuration.
  - Display all configured roles for your server.
- **`/remove_challenge_role`** — Remove specific challenge role assignments.
  - Clean up outdated or incorrect role configurations.

### 🤖 Utility Commands

- **Timestamp Converter** — Convert timestamps between formats.
- **Random Recommendations** — Get surprise anime/manga suggestions.
- **Statistics Tracking** — Detailed user engagement analytics.
- **AniList Username Verification** — Check username validity before registration.
- **Feedback System** — Report issues and suggest improvements.

## 🚀 Deployment (Local or Railway)

**Deploy once, use everywhere!** Lemegeton supports multiple Discord servers with a single deployment.

### Railway (Recommended)

The easiest way to deploy Lemegeton for multiple guilds is using Railway's hosting:

1. Fork this repository to your GitHub account.
2. Create a Railway account at https://railway.app and connect your repo.
3. Set environment variables (see `config.py` and the `Environment Variables` section below).
4. Invite the bot to your servers — each server can configure independent challenge roles.
5. Deploy — the bot will run continuously.

Full guide: `docs/RAILWAY_DEPLOYMENT.md`.

### Manual / Local Development

#### Prerequisites

- Python 3.8+
- Discord Bot Token (from Discord Developer Portal)
- Git

#### Quick start (Windows)

```cmd
# Run the automated setup script (if present)
setup_user.bat
```

#### Manual setup

```bash
# Clone and enter repo
#### "Bot not responding to commands"
cd lemegeton-test

# Create virtual environment
python -m venv venv

# Activate venv (Windows)
venv\\Scripts\\activate

# Install deps
pip install -r requirements.txt
```

#### Run the bot (development)

From the project root:

```powershell
python bot.py
```

Visit `http://localhost:5000` for the monitoring dashboard if enabled.

## 🎯 Commands (summary)

> Multi-guild note: commands operate across multiple Discord servers. Server admins can configure per-guild settings via the guild configuration commands.

### Account Management

- `/login` — Register your AniList username.
- `/check_anilist` — Verify an AniList username exists.
- `/profile` — View your AniList profile and statistics.

### Recommendations & Discovery

- `/recommendations` — AI-powered recommendations.
- `/trending` — Current trending anime and manga.
- `/random` — Random anime/manga suggestions.
- `/search_similar` — Find anime similar to a specific title.

### Interactive Features

- `/browse` — Interactive category browsing (Anime/Manga/Light Novels/Novels).
- `/compare` — Compare your profile with another user.
- `/watchlist` — Manage your anime/manga watchlist.

### Challenges & Competition

- `/challenge_progress` — View your current challenge progress.
- `/challenge_leaderboard` — See challenge rankings.
- `/leaderboard` — View community leaderboards.

### Guild Configuration (Requires "Manage Roles")

- `/setup_challenge_role` — Configure challenge roles for your server.
- `/list_challenge_roles` — View configured roles.
- `/remove_challenge_role` — Remove configured roles.

### Utilities

- `/timestamp` — Convert and format timestamps.
- `/stats` — View bot usage statistics.
- `/feedback` — Send feedback to the developers.
- `/help` — Interactive help system.

## 📁 Project Structure

```
lemegeton-test/
├── bot.py
├── config.py
├── database.py
├── requirements.txt
├── start.bat
├── cogs/
└── ...
```

## ⚙️ Configuration

### Environment Variables

The bot uses `python-dotenv` to load environment variables from a `.env` file in the project root. Example:

```env
DISCORD_TOKEN=your_discord_bot_token_here
# PRIMARY_GUILD_ID is recommended for backward compatibility (legacy GUILD_ID is supported)
PRIMARY_GUILD_ID=123456789012345678
# Optional legacy variable
GUILD_ID=123456789012345678
BOT_ID=your_bot_user_id
CHANNEL_ID=your_main_channel_id
DATABASE_PATH=data/database.db
ENVIRONMENT=development
```

- `PRIMARY_GUILD_ID` — Used for backward compatibility (recommended).
- `GUILD_ID` — Legacy environment key (optional).
- `DATABASE_PATH` — Path to SQLite DB file; defaults to `data/database.db` if not set.

### `config.py` snippet

```python
PRIMARY_GUILD_ID = int(os.getenv("PRIMARY_GUILD_ID", os.getenv("GUILD_ID", 0)))
GUILD_ID = PRIMARY_GUILD_ID
DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data", "database.db"))
```

## 🐛 Troubleshooting & Developer Notes

- If `tools/analyze_db.py` or other maintenance scripts report "unable to open database file", run them from the repository root or set `DATABASE_PATH` explicitly.
- The codebase is async-first (uses `aiosqlite` and `aiohttp`). Prefer `aiohttp` for HTTP clients in cogs to avoid blocking the event loop.
- Logs are written to the `logs/` directory. Increase logging in `config.py` during development with `logging.basicConfig(level=logging.DEBUG)`.

## 🤝 Contributing

Contributions welcome. Fork, branch, commit, and open a PR.

## 📄 License

MIT — see `docs/LICENSE`.

---

Made with ❤️ for the anime community

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

### Developer notes

- Analyzer and small maintenance scripts (for example `tools/analyze_db.py`) assume they're executed from the project root and may use the `DATABASE_PATH` environment variable or the repo `data/database.db` default. If you get an "unable to open database file" error when running tools, make sure you're running them from the repository root or set `DATABASE_PATH` explicitly.

- The codebase is async-first and uses `aiosqlite` and `aiohttp` for non-blocking DB and HTTP operations. Prefer `aiohttp` when adding new API integrations rather than introducing sync HTTP libraries.

Enable detailed logging by modifying `config.py` or using environment variables. Example:

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
