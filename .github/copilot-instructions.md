Short, focused instructions to help an AI coding agent be immediately productive in this repo.

1) Big picture
- Entry point: `bot.py` — sets up logging, intents, command sync helpers, cog loader (`load_cogs` / `_load_cogs_impl`) and background tasks (streaming status + AniList fetch). Treat `bot.py` as orchestration, not business logic.
- Command modules: `cogs/` — each file is a Cog and exposes an async `setup(bot)` function. Cogs register themselves via `await bot.add_cog(...)` or with the modern `async def setup(bot)` convention. Example: `cogs/recommendations.py` and `cogs/finisher.py`.
- Helpers: `helpers/` — utility modules (AniList, media, profile, cache helpers). Prefer calling these rather than duplicating logic.
- Persistence & caches: `database.py` (aiosqlite) and `data/` (JSON caches). Use `execute_db_operation()` wrapper for DB queries; many modules use atomic file writes (write to `.tmp` then rename).
- Infra & runtime: `config.py` loads environment variables (DOTENV). The project assumes a `.env` with `DISCORD_TOKEN`, `GUILD_ID`, `BOT_ID`, `DATABASE_PATH`, etc. Rails/Railway deployment configs live under `config/` and `docs/`.

NOTE: During recent edits the repo had a few files containing accidental Markdown fenced code blocks (triple backticks) which produced SyntaxErrors when the bot loaded cogs. If you see a SyntaxError while importing a cog, first check for stray backticks at the top or bottom of the file.

2) Developer workflows the project expects
- Local dev (Windows): create & activate venv then `pip install -r requirements.txt`. Run `start.bat` or `python bot.py` to start. See `README.md` for Railway deployment notes.
- Environment: `.env` must contain `DISCORD_TOKEN`, `BOT_ID`, and `GUILD_ID` (legacy). `config.DB_PATH` defaults to `data/database.db`.
- Logs: per-module logs in `logs/` (e.g., `bot.log`, `database.log`, `recommendations.log`). Modules avoid duplicate handlers on reload — follow that pattern when adding loggers.

Practical dev steps I used while working here:
- Always run `python -m pip install -r requirements.txt` in the project root (PowerShell: `python -m venv .venv; . .venv\Scripts\Activate.ps1` then install). Without installing deps (`requests`, etc.) the language server will show unresolved imports and the bot may fail at runtime.
- If a cog imports `requests`, either ensure `requests` is in `requirements.txt` and installed, or convert that cog to `aiohttp` (preferred async approach) to avoid adding sync HTTP deps.

3) Project-specific conventions & idioms (important to follow)
- Cogs: implement `async def setup(bot)` at module bottom. The loader expects files under `cogs/*.py` and loads `cogs.<filename>`.
- Async-first: All IO is asynchronous (aiosqlite, aiohttp, discord.py). Use async functions and avoid blocking calls.
- DB: Use `database.execute_db_operation(name, query, params, fetch_type)` for most SQL. It handles PRAGMA foreign_keys, commit, and logging. For new DB helpers follow the same logging and retry philosophy.
- Multi-guild support: prefer `add_user_guild_aware(discord_id, guild_id, username, ...)` over deprecated `add_user`. There is a migration helper `migrate_to_multi_guild_schema()` — do not assume a single-unique `discord_id`.
- Caches: persistent caches are stored under `data/` and written atomically (tmp->replace). If you add caching follow the same `*.tmp` + `os.replace()` pattern.
-- Logging: modules create a logger with a name like "Recommendations" or "Database" and add a FileHandler writing to `logs/<module>.log`. Avoid adding duplicate handlers on reload.

  Logging preferences
  - One log file per module in `logs/` (e.g., `logs/recommendations.log`, `logs/database.log`).
  - Use a single FileHandler per logger and avoid re-adding handlers when cogs reload (check and skip if handlers already set).
  - Log format: include ISO8601 timestamp, level, logger name, and message. Example formatter: `%(asctime)s %(levelname)s [%(name)s] %(message)s` (use UTC timestamps if possible).
  - Levels: default to INFO in production, use DEBUG for local development. Guard expensive debug logging behind level checks.
  - Rotation: use RotatingFileHandler with sensible defaults (e.g., maxBytes=5_000_000, backupCount=5) to avoid unbounded log growth.
  - When logging exceptions, prefer `logger.exception()` inside except blocks to include stack traces.
  - Avoid printing logs to stdout in production; rely on the per-module files. During local development it's acceptable to also add a StreamHandler for the console.

Additional agent-friendly rules (from hands-on fixes in this repo):
- Avoid adding Postgres or DATABASE_URL routing without explicit instruction. A Postgres fallback (asyncpg) was prototyped during earlier work but reverted—do not change `database.py` to add `asyncpg` unless the repo owner requests it. If Postgres is required, centralize changes so all direct `aiosqlite.connect(...)` calls use the same abstraction.
- When editing cogs, prefer non-blocking `aiohttp` over `requests`. If you must use `requests`, add an entry to `requirements.txt` and mention why.
- If you create or change files that the cog loader imports, run a quick smoke test: `python bot.py` in the venv to detect import/syntax errors early.

4) Integration points & external dependencies
- AniList: `ANILIST_API_URL` usage in `bot.py` and cogs like `recommendations.py` and `anilist.py`. Use `aiohttp.ClientSession` with timeouts and robust JSON parsing (see existing code for status handling and fallbacks).
- Discord: `discord.py` v2.x — slash commands and app commands are used. Intents include `message_content` and `members`.
- Hosting: Railway-friendly; `config/railway.json`, `start.bat` and `utils/monitoring` are referenced by deployment docs in `docs/`.

Dependency checklist for edits made here:
- If you touch a file using `requests`, ensure `requests==2.31.0` (or compatible) is present in `requirements.txt` and instruct the developer to run `python -m pip install -r requirements.txt`.
- Prefer `aiohttp` (already present in requirements) for API calls to keep everything async and avoid blocking the event loop.

Short, focused instructions to help an AI coding agent be immediately productive in this repo.

1) Big picture
- Entry point: `bot.py` — sets up logging, intents, command sync helpers, cog loader (`load_cogs` / `_load_cogs_impl`) and background tasks (streaming status + AniList fetch). Treat `bot.py` as orchestration, not business logic.
- Command modules: `cogs/` — each file is a Cog and exposes an async `setup(bot)` function. Cogs register themselves via `await bot.add_cog(...)` or with the modern `async def setup(bot)` convention. Example: `cogs/recommendations.py` and `cogs/finisher.py`.
- Helpers: `helpers/` — utility modules (AniList, media, profile, cache helpers). Prefer calling these rather than duplicating logic.
- Persistence & caches: `database.py` (aiosqlite) and `data/` (JSON caches). Use `execute_db_operation()` wrapper for DB queries; many modules use atomic file writes (write to `.tmp` then rename).
- Infra & runtime: `config.py` loads environment variables (DOTENV). The project assumes a `.env` with `DISCORD_TOKEN`, `GUILD_ID`, `BOT_ID`, `DATABASE_PATH`, etc. Rails/Railway deployment configs live under `config/` and `docs/`.

NOTE: During recent edits the repo had a few files containing accidental Markdown fenced code blocks (triple backticks) which produced SyntaxErrors when the bot loaded cogs. If you see a SyntaxError while importing a cog, first check for stray backticks at the top or bottom of the file.

2) Developer workflows the project expects
- Local dev (Windows): create & activate venv then `pip install -r requirements.txt`. Run `start.bat` or `python bot.py` to start. See `README.md` for Railway deployment notes.
- Environment: `.env` must contain `DISCORD_TOKEN`, `BOT_ID`, and `GUILD_ID` (legacy). `config.DB_PATH` defaults to `data/database.db`.
- Logs: per-module logs in `logs/` (e.g., `bot.log`, `database.log`, `recommendations.log`). Modules avoid duplicate handlers on reload — follow that pattern when adding loggers.

Practical dev steps I used while working here:
- Always run `python -m pip install -r requirements.txt` in the project root (PowerShell: `python -m venv .venv; . .venv\Scripts\Activate.ps1` then install). Without installing deps (`requests`, etc.) the language server will show unresolved imports and the bot may fail at runtime.
- If a cog imports `requests`, either ensure `requests` is in `requirements.txt` and installed, or convert that cog to `aiohttp` (preferred async approach) to avoid adding sync HTTP deps.

3) Project-specific conventions & idioms (important to follow)
- Cogs: implement `async def setup(bot)` at module bottom. The loader expects files under `cogs/*.py` and loads `cogs.<filename>`.
- Async-first: All IO is asynchronous (aiosqlite, aiohttp, discord.py). Use async functions and avoid blocking calls.
- DB: Use `database.execute_db_operation(name, query, params, fetch_type)` for most SQL. It handles PRAGMA foreign_keys, commit, and logging. For new DB helpers follow the same logging and retry philosophy.
- Multi-guild support: prefer `add_user_guild_aware(discord_id, guild_id, username, ...)` over deprecated `add_user`. There is a migration helper `migrate_to_multi_guild_schema()` — do not assume a single-unique `discord_id`.
- Caches: persistent caches are stored under `data/` and written atomically (tmp->replace). If you add caching follow the same `*.tmp` + `os.replace()` pattern.
- Logging: modules create a logger with a name like "Recommendations" or "Database" and add a FileHandler writing to `logs/<module>.log`. Avoid adding duplicate handlers on reload.

Additional agent-friendly rules (from hands-on fixes in this repo):
- Avoid adding Postgres or DATABASE_URL routing without explicit instruction. A Postgres fallback (asyncpg) was prototyped during earlier work but reverted—do not change `database.py` to add `asyncpg` unless the repo owner requests it. If Postgres is required, centralize changes so all direct `aiosqlite.connect(...)` calls use the same abstraction.
- When editing cogs, prefer non-blocking `aiohttp` over `requests`. If you must use `requests`, add an entry to `requirements.txt` and mention why.
- If you create or change files that the cog loader imports, run a quick smoke test: `python bot.py` in the venv to detect import/syntax errors early.

4) Integration points & external dependencies
- AniList: `ANILIST_API_URL` usage in `bot.py` and cogs like `recommendations.py` and `anilist.py`. Use `aiohttp.ClientSession` with timeouts and robust JSON parsing (see existing code for status handling and fallbacks).
- Discord: `discord.py` v2.x — slash commands and app commands are used. Intents include `message_content` and `members`.
- Hosting: Railway-friendly; `config/railway.json`, `start.bat` and `utils/monitoring` are referenced by deployment docs in `docs/`.

Dependency checklist for edits made here:
- If you touch a file using `requests`, ensure `requests==2.31.0` (or compatible) is present in `requirements.txt` and instruct the developer to run `python -m pip install -r requirements.txt`.
- Prefer `aiohttp` (already present in requirements) for API calls to keep everything async and avoid blocking the event loop.

5) Where to make common edits
- New commands / features: add a new file in `cogs/` with `class X(commands.Cog)` and `async def setup(bot)` at bottom.
- Shared logic: add helpers in `helpers/` and import them in cogs. Keep database logic in `database.py`.
- Configuration: add environment keys in `config.py` and document them in `README.md` or `docs/`.

6) Quick examples to copy-paste
- Cog skeleton (follow async setup):
  - Implement a Cog class and expose `async def setup(bot): await bot.add_cog(MyCog(bot))`
- DB operation (use wrapper):
  - `await database.execute_db_operation("my op", "SELECT ...", params, fetch_type='one')`

When editing files with the automated agent:
- Use the provided `apply_patch` format for edits and preserve whitespace and style.
- If a file contains triple-backticks, remove them — they break imports. I encountered this with `cogs/embed.py` and `cogs/finisher.py` while working here.
- After edits, run the project's static error checker or start the bot to validate changes (`python bot.py`).

7) Safety notes for automated changes
- Don’t change `config.py` semantics (env variable names) or the DB path default without updating `docs/` and `start.bat`.
- Avoid making blocking calls in cogs (no sync HTTP/file I/O). Follow the module patterns (async + aiohttp + atomic writes).

Extra safety and verification gates I followed here:
- Always run `python -m pip install -r requirements.txt` before running the bot to avoid "Import could not be resolved" diagnostics.
- After any cog edits, run `python bot.py` to catch SyntaxError / import-time exceptions early. If the edit affects DB behavior, add a small unit or smoke test that exercises the changed logic.
- Don't assume you can run network calls during automated edits — gather info and mock network if needed for tests.

If anything here is unclear or you'd like more detail on a section (cog lifecycle, DB helpers, or deployment), tell me which part to expand and I will iterate.
