# 🎌 Lemegeton - Multi-Guild Discord Anime & Gaming Bot# 🎌 Lemegeton - Multi-Guild Discord Anime & Gaming Bot



A comprehensive Discord bot that combines anime/manga tracking with AI-powered recommendations, featuring interactive UIs, personalized suggestions, community challenges, and **full multi-guild deployment support**.A comprehensive Discord bot that combines anime/manga tracking with AI-powered recommendations, featuring interactive UIs, personalized suggestions, community challenges, and **full multi-guild deployment support**.



![Python](https://img.shields.io/badge/python-3.13+-blue.svg)![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

![Discord.py](https://img.shields.io/badge/discord.py-2.6.0-blue.svg)![Discord.py](https://img.shields.io/badge/discord.py-2.6.0-blue.svg)

![License](https://img.shields.io/badge/license-MIT-green.svg)![License](https://img.shields.io/badge/license-MIT-green.svg)

![Status](https://img.shields.io/badge/status-production--ready-success.svg)![Status](https://img.shields.io/badge/status-production--ready-success.svg)

![Multi-Guild](https://img.shields.io/badge/multi--guild-ready-brightgreen.svg)![Multi-Guild](https://img.shields.io/badge/multi--guild-ready-brightgreen.svg)

![Railway](https://img.shields.io/badge/railway-deployable-purple.svg)![Railway](https://img.shields.io/badge/railway-deployable-purple.svg)



## ✨ Key Features## ✨ Key Features



### 📚 Anime & Manga Tracking### 📚 Anime & Manga Tracking

- **AniList Integration** - Connect your AniList profile for seamless tracking- **AniList Integration** - Connect your AniList profile for seamless tracking

- **AI-Powered Recommendations** - Get personalized suggestions based on your highly-rated titles (8.0+)- **AI-Powered Recommendations** - Get personalized suggestions based on your highly-rated titles (8.0+)

- **Interactive Browsing** - Browse anime, manga, light novels, and general novels with advanced filtering- **Interactive Browsing** - Browse anime, manga, light novels, and general novels with advanced filtering

- **Profile Viewing** - Comprehensive user statistics, achievements, and favorite series- **Profile Viewing** - Comprehensive user statistics and favorite series

- **Trending Lists** - Stay updated with the latest popular series- **Watchlist Management** - Track your current and planned anime/manga

- **Twitter/X News Monitoring** - Track anime/manga news from Twitter accounts- **Trending Lists** - Stay updated with the latest popular series



### 🎨 Customization & Themes- **Guild-aware Data Isolation** - The bot is multi-guild aware: most database operations and interactive flows are scoped to the guild where they were triggered. Unregistration, registrations, leaderboards, and challenge role configuration are implemented to respect per-guild data isolation while still allowing cross-guild user profiles where appropriate.

- **Theme System** - Browse and apply custom themes to personalize your bot experience

- **Guild Themes** - Server moderators can set server-wide default themes### 🏆 Community Features

- **Theme Preview** - Preview themes before applying them

- **Individual Preferences** - User themes override guild settingsPRIMARY_GUILD_ID=123456789012345678

 # 🎌 Lemegeton - Multi-Guild Discord Anime & Gaming Bot

### 🏆 Community Features

- **Reading Challenges** - Participate in community-wide anime/manga challengesA comprehensive Discord bot that combines anime/manga tracking with AI-powered recommendations, featuring interactive UIs, personalized suggestions, community challenges, and guild-aware multi-server deployment support.

- **Leaderboards** - Compete with other users across various metrics

- **Achievement System** - Unlock achievements for various milestones![Python](https://img.shields.io/badge/python-3.8+-blue.svg)

- **Challenge Role Management** - Automatic role assignment based on challenge progress![Discord.py](https://img.shields.io/badge/discord.py-2.6.0-blue.svg)

![License](https://img.shields.io/badge/license-MIT-green.svg)

### 🎮 Gaming Integration![Status](https://img.shields.io/badge/status-production--ready-success.svg)

- **Steam Profile Viewing** - Display Steam profiles and stats

- **Steam Recommendations** - Get personalized game recommendations based on your library## ✨ Key Features

- **Cross-Platform Discovery** - Connect your anime/manga and gaming interests

### 📚 Anime & Manga Tracking

### 🌐 Multi-Guild Support & Configuration

- **Multi-Server Ready** - Deploy across multiple Discord servers with per-guild configuration- **AniList Integration** — Connect your AniList profile for seamless tracking.

- **Guild-Specific Settings** - Each server maintains independent challenge roles and configurations- **AI-Powered Recommendations** — Personalized suggestions based on your highly-rated titles (8.0+).

- **Flexible Role Management** - Configure different challenge roles for each server- **Interactive Browsing** — Browse anime, manga, light novels, and general novels with advanced filtering.

- **Cross-Guild User Profiles** - Users keep a single profile shared across guilds- **Profile Viewing** — Comprehensive user statistics and favorite series.

- **Guild-Aware Data Isolation** - Most database operations are scoped to the guild where they were triggered- **Watchlist Management** — Track your current and planned anime/manga.

- **Trending Lists** — Stay updated with the latest popular series.

### ⚙️ Server Management

- **Centralized Configuration** - `/server-config` command for unified server management- **Guild-aware Data Isolation** — The bot is multi-guild aware: most database operations and interactive flows are scoped to the guild where they were triggered. Unregistration, registrations, leaderboards, and challenge role configuration respect per-guild isolation while still allowing shared user profiles across guilds where appropriate.

- **Bot Moderators** - Manage users with bot-wide elevated permissions

- **Channel Configuration** - Set channels for bot updates and anime/manga completion notifications### 🏆 Community Features

- **Role Management** - Configure challenge roles and moderator roles per server

- **Notification System** - Users can manage their update notification preferences- **Global Challenges** — Participate in community-wide anime/manga challenges.

- **Leaderboards** — Compete with other users across various metrics.

### 🛠️ Utility Commands- **User Comparison** — Compare profiles and statistics with friends.

- **Planned Features** - View upcoming bot features and updates- **Achievement System** — Unlock achievements for various milestones.

- **Feedback System** - Report issues and suggest improvements

- **Interactive Help** - Comprehensive help system with category browsing### 🌐 Multi-Guild Support & Configuration

- **Invite Link** - Share the bot with other servers

- **Multi-Server Ready** — Deploy across multiple Discord servers with per-guild configuration and data isolation.

## 🚀 Quick Start- **Guild-Specific Settings** — Each server maintains independent challenge roles and configurations.

- **Flexible Role Management** — Configure different challenge roles for each server.

### Prerequisites- **Cross-Guild User Profiles** — Users keep a single profile shared across guilds; most actions (unregister, challenge progress, role assignments) are applied per-guild.

- Python 3.13+

- Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))#### Guild Configuration Commands (Requires "Manage Roles" Permission)

- AniList Account (optional, but recommended)

- **`/setup_challenge_role`** — Configure challenge roles for your server.

### Installation  - Set roles for different challenge types and difficulty levels.

  - Assign multiple roles per challenge category.

**Windows:**- **`/list_challenge_roles`** — View current challenge roles configuration.

```powershell  - Display all configured roles for your server.

# Clone the repository- **`/remove_challenge_role`** — Remove specific challenge role assignments.

git clone https://github.com/Kyerstorm/Lemegeton.git  - Clean up outdated or incorrect role configurations.

cd Lemegeton

### 🤖 Utility Commands

# Create virtual environment

python -m venv venv- **Timestamp Converter** — Convert timestamps between formats.

.venv\Scripts\Activate.ps1- **Random Recommendations** — Get surprise anime/manga suggestions.

- **Statistics Tracking** — Detailed user engagement analytics.

# Install dependencies- **AniList Username Verification** — Check username validity before registration.

pip install -r requirements.txt- **Feedback System** — Report issues and suggest improvements.



# Create .env file with your configuration## 🚀 Deployment (Local or Railway)

copy .env.example .env

# Edit .env with your Discord token and other settings**Deploy once, use everywhere!** Lemegeton supports multiple Discord servers with a single deployment.



# Run the bot### Railway (Recommended)

python bot.py

```The easiest way to deploy Lemegeton for multiple guilds is using Railway's hosting:



**Linux/Mac:**1. Fork this repository to your GitHub account.

```bash2. Create a Railway account at https://railway.app and connect your repo.

# Clone the repository3. Set environment variables (see `config.py` and the `Environment Variables` section below).

git clone https://github.com/Kyerstorm/Lemegeton.git4. Invite the bot to your servers — each server can configure independent challenge roles.

cd Lemegeton5. Deploy — the bot will run continuously.



# Create virtual environmentFull guide: `docs/RAILWAY_DEPLOYMENT.md`.

python3 -m venv venv

source venv/bin/activate### Manual / Local Development



# Install dependencies#### Prerequisites

pip install -r requirements.txt

- Python 3.8+

# Create .env file with your configuration- Discord Bot Token (from Discord Developer Portal)

cp .env.example .env- Git

# Edit .env with your Discord token and other settings

#### Quick start (Windows)

# Run the bot

python bot.py```cmd

```# Run the automated setup script (if present)

setup_user.bat

### Configuration```



Create a `.env` file in the project root:#### Manual setup



```env```bash

DISCORD_TOKEN=your_discord_bot_token_here# Clone and enter repo

PRIMARY_GUILD_ID=123456789012345678#### "Bot not responding to commands"

BOT_ID=your_bot_user_idcd lemegeton-test

DATABASE_PATH=data/database.db

ENVIRONMENT=development# Create virtual environment

```python -m venv venv



**Environment Variables:**# Activate venv (Windows)

- `DISCORD_TOKEN` (required) - Your Discord bot tokenvenv\\Scripts\\activate

- `PRIMARY_GUILD_ID` (required) - Primary guild ID for backward compatibility

- `BOT_ID` (optional) - Your bot's user ID# Install deps

- `DATABASE_PATH` (optional) - Path to SQLite database (default: `data/database.db`)pip install -r requirements.txt

- `ENVIRONMENT` (optional) - `development` or `production````



## 🎯 Commands#### Run the bot (development)



> All commands are slash commands. Type `/` in Discord to see available commands.From the project root:



### 🔐 Account Management```powershell

- `/login` - Register or update your AniList account connectionpython bot.py

```

### 📊 Profile & Stats

- `/profile [user]` - View AniList profile with stats & achievementsVisit `http://localhost:5000` for the monitoring dashboard if enabled.



### 📺 Anime & Manga## 🎯 Commands (summary)

- `/browse` - Interactive browsing with filtering and sorting

- `/trending` - View currently trending anime and manga> Multi-guild note: commands operate across multiple Discord servers. Server admins can configure per-guild settings via the guild configuration commands.

- `/recommendations [member]` - AI-powered personalized recommendations

- `/random` - Get random anime/manga suggestions### Account Management

- `/news-manage` - Manage Twitter/X news monitoring (Moderator)

- `/login` — Register your AniList username.

### 🏆 Challenges & Competition- `/check_anilist` — Verify an AniList username exists.

- `/challenge_progress` - View your reading challenge progress- `/profile` — View your AniList profile and statistics.

- `/challenge_update` - Manually update challenge progress

- `/challenge_manage` - Create and manage challenges (Moderator)### Recommendations & Discovery

- `/challenge_leaderboard` - View challenge rankings

- `/leaderboard` - Server leaderboards for various metrics- `/recommendations` — AI-powered recommendations.

- `/trending` — Current trending anime and manga.

### 🎮 Gaming- `/random` — Random anime/manga suggestions.

- `/steam-profile <username>` - Show Steam profile and stats- `/search_similar` — Find anime similar to a specific title.

- `/steam-recommendation <username>` - Get game recommendations

### Interactive Features

### 🎨 Customization

- `/theme` - Browse, preview, and apply custom themes- `/browse` — Interactive category browsing (Anime/Manga/Light Novels/Novels).

- `/guild_theme` - Manage server-wide theme settings (Moderator)- `/compare` — Compare your profile with another user.

- `/watchlist` — Manage your anime/manga watchlist.

### ⚙️ Server Management (Admin/Moderator Only)

- `/server-config` - Centralized server configuration### Challenges & Competition

- `/moderators` - Manage bot moderators

- `/set_bot_updates_channel` - Configure bot update notifications- `/challenge_progress` — View your current challenge progress.

- `/set_animanga_completion_channel` - Configure completion notifications- `/challenge_leaderboard` — See challenge rankings.

- `/leaderboard` — View community leaderboards.

### 🛠️ Utilities

- `/notifications` - Manage your notification preferences### Guild Configuration (Requires "Manage Roles")

- `/planned` - View planned bot features

- `/feedback` - Submit ideas or report bugs- `/setup_challenge_role` — Configure challenge roles for your server.

- `/invite` - Get bot invite link- `/list_challenge_roles` — View configured roles.

- `/help [category]` - Interactive help system- `/remove_challenge_role` — Remove configured roles.



### 👑 Admin Commands (Bot Moderators Only)### Utilities

- `/changelog` - Create and publish changelogs

- `/forceupdate` - Force anime/manga completion update- `/timestamp` — Convert and format timestamps.

- `/show_manga_channel` - View configured manga channel- `/stats` — View bot usage statistics.

- `/feedback` — Send feedback to the developers.

## 🏗️ Project Structure- `/help` — Interactive help system.



```## 📁 Project Structure

Lemegeton/

├── bot.py                          # Main bot entry point```

├── config.py                       # Configuration managementlemegeton-test/

├── database.py                     # Database operations (SQLite)├── bot.py

├── requirements.txt                # Python dependencies├── config.py

├── .env.example                    # Environment template├── database.py

├── cogs/                          # Command modules├── requirements.txt

│   ├── account/                   # Account management (login, profile)├── start.bat

│   ├── admin/                     # Admin commands (changelog, guild config)├── cogs/

│   ├── bot_management/            # Bot moderators└── ...

│   ├── challenges/                # Reading challenges```

│   ├── customization/             # Themes

│   ├── gaming/                    # Steam integration## ⚙️ Configuration

│   ├── media/                     # Anime/manga (browse, recommendations, news)

│   ├── server_management/         # Server configuration### Environment Variables

│   ├── social/                    # Social features (leaderboards, affinity)

│   └── utilities/                 # Utility commands (help, feedback, planned)The bot uses `python-dotenv` to load environment variables from a `.env` file in the project root. Example:

├── helpers/                       # Shared utility functions

│   ├── anilist_helper.py         # AniList API integration```env

│   ├── cache_helper.py           # Caching systemDISCORD_TOKEN=your_discord_bot_token_here

│   ├── embed_helper.py           # Discord embed formatting# PRIMARY_GUILD_ID is recommended for backward compatibility (legacy GUILD_ID is supported)

│   └── ...PRIMARY_GUILD_ID=123456789012345678

├── data/                          # Data storage# Optional legacy variable

│   └── database.db               # SQLite databaseGUILD_ID=123456789012345678

├── logs/                          # Log filesBOT_ID=your_bot_user_id

└── docs/                          # DocumentationCHANNEL_ID=your_main_channel_id

    ├── DEPLOYMENT_CHECKLIST.mdDATABASE_PATH=data/database.db

    ├── RAILWAY_DEPLOYMENT.mdENVIRONMENT=development

    └── structured_changelog.txt```

```

- `PRIMARY_GUILD_ID` — Used for backward compatibility (recommended).

## 🚂 Railway Deployment- `GUILD_ID` — Legacy environment key (optional).

- `DATABASE_PATH` — Path to SQLite DB file; defaults to `data/database.db` if not set.

Deploy to Railway for 24/7 hosting:

### `config.py` snippet

1. Fork this repository

2. Create a [Railway](https://railway.app) account```python

3. Create a new project from your forked repoPRIMARY_GUILD_ID = int(os.getenv("PRIMARY_GUILD_ID", os.getenv("GUILD_ID", 0)))

4. Set environment variables in Railway dashboard:GUILD_ID = PRIMARY_GUILD_ID

   - `DISCORD_TOKEN`DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data", "database.db"))

   - `PRIMARY_GUILD_ID````

   - `BOT_ID`

5. Deploy!## 🐛 Troubleshooting & Developer Notes



**Railway automatically:**- If `tools/analyze_db.py` or other maintenance scripts report "unable to open database file", run them from the repository root or set `DATABASE_PATH` explicitly.

- Installs dependencies from `requirements.txt`- The codebase is async-first (uses `aiosqlite` and `aiohttp`). Prefer `aiohttp` for HTTP clients in cogs to avoid blocking the event loop.

- Uses `Procfile` to start the bot- Logs are written to the `logs/` directory. Increase logging in `config.py` during development with `logging.basicConfig(level=logging.DEBUG)`.

- Creates persistent volume for database

- Provides 24/7 uptime## 🤝 Contributing



For detailed instructions, see [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md)Contributions welcome. Fork, branch, commit, and open a PR.



## 🔧 Development## 📄 License



### Running TestsMIT — see `docs/LICENSE`.

```bash

# Run database analysis---

python tools/analyze_db.py

Made with ❤️ for the anime community

# Run multi-guild tests

python tools/test_multi_guild.py- **Permissions**: Check bot has necessary permissions in Discord

```- **Token**: Verify Discord bot token is correct

- **Guild ID**: Ensure PRIMARY_GUILD_ID matches your Discord server (for multi-guild deployments)

### Database Management- **Slash Commands**: Commands may take up to 1 hour to sync on new guilds

The bot uses SQLite with `aiosqlite` for async operations. All database functions are in `database.py` and use the `execute_db_operation()` wrapper for consistent logging and error handling.

#### "Multi-Guild Configuration Issues"

**Key principles:**

- Always use guild-aware functions (`*_guild_aware()` variants)- **Challenge Roles**: Use `/setup_challenge_role` in each server to configure server-specific roles

- Never use blocking `sqlite3` - always use `aiosqlite`- **Permissions**: Ensure users have "Manage Roles" permission to configure guild settings

- Run tools from project root for correct `DATABASE_PATH` resolution- **Data Isolation**: User data is shared across guilds, but guild configurations are independent

- **Environment Variables**: Ensure PRIMARY_GUILD_ID is set for backward compatibility

### Adding New Commands

1. Create a new file in the appropriate `cogs/` subdirectory#### "Database errors"

2. Use `@app_commands.command()` decorator for slash commands- **File permissions**: Ensure bot can write to database directory

3. Always pass `interaction.guild_id` to database functions- **Path**: Check DATABASE_PATH is correct

4. Add command to `help.py` command categories- **SQLite**: Ensure SQLite3 is available

5. Update `README.md` and changelog

#### "AniList API errors"

## 🐛 Troubleshooting- **Rate limits**: AniList API has rate limits

- **Network issues**: Check internet connectivity

### Bot not responding to commands- **Invalid usernames**: Ensure usernames exist on AniList

- Check Discord bot token is correct

- Verify bot has necessary permissions in Discord server### Developer notes

- Wait up to 1 hour for slash commands to sync on new guilds

- Check logs in `logs/bot.log`- Analyzer and small maintenance scripts (for example `tools/analyze_db.py`) assume they're executed from the project root and may use the `DATABASE_PATH` environment variable or the repo `data/database.db` default. If you get an "unable to open database file" error when running tools, make sure you're running them from the repository root or set `DATABASE_PATH` explicitly.



### Database errors- The codebase is async-first and uses `aiosqlite` and `aiohttp` for non-blocking DB and HTTP operations. Prefer `aiohttp` when adding new API integrations rather than introducing sync HTTP libraries.

- Ensure `data/` directory exists and is writable

- Check `DATABASE_PATH` environment variableEnable detailed logging by modifying `config.py` or using environment variables. Example:

- Run tools from project root

```python

### AniList API errorsimport logging

- AniList has rate limits - wait and retrylogging.basicConfig(level=logging.DEBUG)

- Check internet connectivity```

- Verify AniList username exists (use "Check AniList" button in `/login`)

### Log Files

### Multi-Guild configuration issues

- Use `/server-config` in each server to configure server-specific settingsThe bot creates detailed logs in the `logs/` directory:

- Ensure users have appropriate permissions (Admin/Moderator)- `bot.log` - Main bot operations

- User data is shared across guilds, but guild configurations are independent- `database.log` - Database operations

- `media_helper.log` - AniList API calls

## 📊 Database Schema- Command-specific logs for debugging



The bot uses a comprehensive SQLite database with the following key tables:## 🤝 Contributing

- `users` - User profiles with `(discord_id, guild_id)` composite key

- `user_stats` - User statistics per guildWe welcome contributions! Please see our contributing guidelines:

- `guild_challenges` - Challenge configurations per guild

- `guild_challenge_roles` - Role assignments per guild1. Fork the repository

- `guild_mod_roles` - Moderator roles per guild2. Create a feature branch (`git checkout -b feature/AmazingFeature`)

- `paginator_state` - UI state persistence3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)

- `planned_features` - Feature planning system4. Push to the branch (`git push origin feature/AmazingFeature`)

- `themes` - Theme customization data5. Open a Pull Request



All tables follow guild-aware design patterns for multi-server isolation.### Development Setup



## 🤝 Contributing```bash

# Clone your fork

Contributions are welcome! Please:git clone https://github.com/YourUsername/lemegeton-test.git

cd lemegeton-test

1. Fork the repository

2. Create a feature branch (`git checkout -b feature/AmazingFeature`)# Create development environment

3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)python -m venv venv

4. Push to the branch (`git push origin feature/AmazingFeature`)source venv/bin/activate  # or venv\Scripts\activate on Windows

5. Open a Pull Requestpip install -r requirements.txt



**Development guidelines:**# Run in development mode

- Follow existing code structure and patternspython bot.py

- Use async/await for all I/O operations```

- Always use guild-aware database functions

- Update help.py and README.md for new commands## 📄 License

- Add entries to `docs/structured_changelog.txt`

- Test with multiple guilds before submittingThis project is licensed under the MIT License - see the [LICENSE](docs/LICENSE) file for details.



## 📄 License## 🆘 Support



This project is licensed under the MIT License - see the [LICENSE](docs/LICENSE) file for details.- **Discord Server**: [https://discord.gg/xUGD7krzws](https://discord.gg/xUGD7krzws)

- **Documentation**: [docs/README.md](docs/README.md)

## 🆘 Support- **Issues**: [GitHub Issues](https://github.com/Kyerstorm/lemegeton-test/issues)

- **Feature Requests**: Use the `/feedback` command in Discord

- **Discord Server**: [Join our Support Server](https://discord.gg/xUGD7krzws)

- **Documentation**: [docs/README.md](docs/README.md)## 🙏 Acknowledgments

- **Issues**: [GitHub Issues](https://github.com/Kyerstorm/Lemegeton/issues)

- **Feature Requests**: Use the `/feedback` command in Discord- **AniList API** - For providing comprehensive anime/manga data

- **Discord.py** - Excellent Discord bot framework

## 🙏 Acknowledgments- **Railway** - Reliable hosting platform

- **Contributors** - Thank you to all who have contributed to this project

- **AniList API** - Comprehensive anime/manga data

- **Discord.py** - Excellent Discord bot framework---

- **Railway** - Reliable hosting platform

- **Community** - Thank you to all contributors and users!Made with ❤️ for the anime community


## 📈 Statistics

- **Commands**: 30+ slash commands
- **Cogs**: 40+ command modules
- **Database Tables**: 15+ tables with multi-guild support
- **Active Development**: Regular updates and bug fixes
- **Multi-Guild**: Fully tested across multiple Discord servers

---

Made with ❤️ for the anime community by [Kyerstorm](https://github.com/Kyerstorm)

**Deploy once, use everywhere!** 🚀
