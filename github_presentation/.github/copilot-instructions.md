# Lemegeton Discord Bot - AI Coding Agent Guide

## Architecture Overview

This is a multi-guild Discord bot built with discord.py 2.6+ featuring AniList integration, Steam gaming features, challenges system, and optional Twitter news monitoring. The architecture follows a modular cog-based design with comprehensive logging and monitoring.

### Core Components
- **`bot.py`**: Main entry point with command sync optimization and trending anime status rotation
- **`config.py`**: Environment-based configuration with defensive parsing for numeric IDs
- **`database.py`**: Centralized async SQLite operations with connection pooling and retries
- **`cogs/`**: Feature modules organized by domain (anilist, gaming, challenges, utilities)
- **`helpers/`**: Shared utility functions for API calls and data processing
- **`utils/`**: Monitoring, deployment, and operational tools

## Command Deployment Strategy

**CRITICAL**: This bot uses a hybrid global/guild command approach documented in `guild_sync.txt`:
- **Global commands**: Most features (AniList, Steam, utilities) - available in all servers
- **Guild-only commands**: News monitoring (`cogs/*/news.py`) - uses `@app_commands.guild_only()`
- Command sync optimization uses command signatures hashing to avoid unnecessary Discord API calls

## Data Architecture

### Database Patterns
- All database operations use `aiosqlite` with `DB_TIMEOUT = 30.0` and retry logic
- Connection management through context managers: `async with aiosqlite.connect(DB_PATH)`
- Schema migrations handled automatically with version tracking
- Key tables: `users`, `guilds`, `challenges`, `accounts` (news), `filters`

### Configuration Inheritance
- Primary guild settings in `config.CHALLENGE_ROLE_IDS` migrate to multi-guild database storage
- Environment variables use defensive parsing via `_int_env()` helper
- Challenge roles support threshold-based progression (see config.py structure)

## Cog Patterns

### Standard Cog Structure
```python
class ExampleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()  # For API calls
        
    async def cog_unload(self):
        await self.session.close()  # Always cleanup sessions
```

### AniList Integration
- Central API helper in `helpers/anilist_helper.py` with retry logic and rate limiting
- GraphQL queries with timeout `API_TIMEOUT = 30`
- Progress tracking integrates with user database profiles
- Media embeds use consistent color schemes and formatting

### Challenge System
- Multi-guild challenge management with role-based progression
- Progress tracking through AniList API integration
- Interactive Discord UI components for management
- Automatic role assignment based on completion thresholds

## Logging Architecture

**Every module implements file-based logging** with this pattern:
```python
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "module_name.log"
LOG_MAX_SIZE = 50 * 1024 * 1024  # Auto-clear at 50MB

logger = logging.getLogger("ModuleName")
# File handler with detailed formatting including function names and line numbers
```

Key log files: `bot.log`, `database.log`, `anilist_helper.log`, `monitoring.log`

## Development Workflow

### Adding New Features
1. Create cog in appropriate category folder (`cogs/domain/`)
2. Implement helper functions in `helpers/` if reusable
3. Add database schema updates to `database.py` init functions
4. Decide global vs guild-only deployment (update `guild_sync.txt`)
5. Add comprehensive logging following project patterns

### API Integration Patterns
- Use `aiohttp.ClientSession()` in cog `__init__` with proper cleanup
- Implement timeout handling and retry logic (see `anilist_helper.py`)
- Use centralized helper functions for common API operations
- Cache results when appropriate to reduce API calls

### Multi-Guild Considerations
- All guild-specific data stored in database, not config files
- Challenge roles and settings per-guild with fallback to defaults
- News monitoring is guild-specific with separate channel configurations
- User data shared across guilds (AniList profiles, Steam accounts)

## Monitoring & Deployment

- **Monitoring**: Optional `utils/bot_monitoring.py` integration with health checks
- **Error tracking**: Comprehensive logging with error context and user information
- **Performance**: Database query optimization and connection pooling
- **Deployment**: Railway-compatible with `Procfile` and `runtime.txt`

## Key File Relationships

- `bot.py` → loads cogs → use `helpers/` → query `database.py`
- `config.py` → environment setup → default values → database migration
- `cogs/anilist/` → `helpers/anilist_helper.py` → AniList API → user progress tracking
- `cogs/challenges/` → multi-guild database → role management → AniList integration