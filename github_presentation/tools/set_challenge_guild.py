"""One-off script to set guild_id for challenge tables.

Usage: python tools\set_challenge_guild.py

This script will:
- Check that the DB file exists at data/database.db
- Confirm the target tables exist and contain a 'guild_id' column
- Update rows where guild_id IS NULL OR guild_id = 0 to the supplied GUILD_ID
- Print a summary of changes

It's safe to run multiple times (idempotent).
"""
import sqlite3
from pathlib import Path
import config

# Use configured DB path when available to avoid creating repo-root database
DB_PATH = Path(getattr(config, 'DB_PATH', Path('data') / 'database.db'))
GUILD_ID = 897814031346319382

if not DB_PATH.exists():
    print(f"Database not found at {DB_PATH}. Run from repo root.")
    raise SystemExit(1)

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

def table_exists(tbl):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
    return cur.fetchone() is not None

def has_guild_column(tbl):
    cur.execute(f"PRAGMA table_info({tbl})")
    cols = [r[1] for r in cur.fetchall()]
    return 'guild_id' in cols

for tbl in ('global_challenges', 'challenge_manga'):
    print(f"-- Checking table: {tbl}")
    if not table_exists(tbl):
        print(f"Table {tbl} not found, skipping.")
        continue
    if not has_guild_column(tbl):
        print(f"Table {tbl} does not have 'guild_id' column, skipping.")
        continue

    cur.execute(f"SELECT COUNT(*) FROM {tbl} WHERE guild_id IS NULL OR guild_id = 0")
    count = cur.fetchone()[0]
    print(f"Rows to update in {tbl}: {count}")
    if count > 0:
        cur.execute(f"UPDATE {tbl} SET guild_id = ? WHERE guild_id IS NULL OR guild_id = 0", (GUILD_ID,))
        conn.commit()
        print(f"Updated {cur.rowcount} rows in {tbl} to guild_id={GUILD_ID}")
    else:
        print(f"No rows require updating in {tbl}.")

conn.close()
print("Done.")
