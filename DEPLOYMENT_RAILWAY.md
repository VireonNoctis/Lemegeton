Railway deployment notes for this repository

Minimal checklist to deploy on Railway (single-process bot):

1) Files to fix before deployment (already applied in this branch):
   - `requirements.txt` must be plain text (no fenced code blocks). Done.
   - `runtime.txt` should contain a supported Python runtime (e.g., `python-3.11.16`). Done.

2) Environment variables (set these in Railway -> Variables):
   - DISCORD_TOKEN (required)
   - BOT_ID (required)
   - GUILD_ID (required)
   - CHANNEL_ID (required by some cogs)
   - ADMIN_DISCORD_ID (required by admin flows)
   - DATABASE_PATH (optional) — path to SQLite DB. If unset, defaults to `data/database.db`.
   - ENABLE_DASHBOARD (optional) — set to `1` to enable the Flask monitoring dashboard as a separate service.
   - PORT (Railway provides this to web services automatically)

3) Filesystem / Database considerations:
   - By default this project uses SQLite at `data/database.db`. Railway containers have ephemeral filesystems. To persist the database across restarts you must configure a Railway persistent volume and set `DATABASE_PATH` to the mounted path.
   - Alternatively, migrate to a managed DB (Postgres) and adapt `database.py` to use it.

4) Starting command (railway.json already includes this):
   - `python bot.py`
   - If you want to host the optional monitoring dashboard on Railway and expose it to the web, create a second Railway service (or process) that runs:
       - `python utils/monitoring_dashboard.py`
     and set `ENABLE_DASHBOARD=1` for that service. Railway will inject `PORT` into the environment for binding.

5) Notes and gotchas:
   - `config.py` now parses numeric env vars defensively; missing env vars will evaluate to `None`. The bot's `main()` validates required values before starting the connection.
   - Logging is file-based by default (logs/). Ensure your Railway service either doesn't rely on writing logs to disk or configure an output logging strategy. Railway captures stdout; logs still go to `logs/` files in the container's filesystem.
   - If you plan to use the Flask dashboard in production, run it as a separate Railway service (web), not inside the bot process.

6) Quick deploy steps (UI):
   - Create a new Railway project and link your GitHub repo or push the branch.
   - In the project Variables page, add the required env vars (see above list).
   - Deploy. Monitor build logs for Python version compatibility. If Nixpacks fails for the requested runtime, try `python-3.11.16` or `python-3.12.x`.

7) Troubleshooting:
   - If the bot complains about missing env vars at startup, add them and re-deploy.
   - If the monitoring dashboard fails to bind, ensure `PORT` is set (Railway's `web` service provides this automatically) and that `ENABLE_DASHBOARD=1` is set for the dashboard service.

Procfile note:
   - A simple `Procfile` was added to this branch with `web: python bot.py`. If you prefer to run the monitoring dashboard as a separate web process, create a second Procfile or configure an additional Railway service.

If you want, I can:
 - Create a Railway `dockerfile` instead of relying on nixpacks.
 - Patch `database.py` to support Postgres via `asyncpg` behind an environment flag.
 - Add a small systemd-like startup file to run both bot and dashboard in one container (not recommended for Railway).
