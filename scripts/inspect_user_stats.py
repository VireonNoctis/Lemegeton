"""Utility: inspect user_stats table for debugging.

Usage:
    python scripts/inspect_user_stats.py --by chapters --limit 20
    python scripts/inspect_user_stats.py --by episodes --limit 50

This script reads the DB path from config.DB_PATH for consistency with the bot.
"""
import sqlite3
import argparse
from pathlib import Path

from config import DB_PATH


def top_by(db_path: str, by: str, limit: int = 20):
    if by == "chapters":
        col = "total_chapters"
    elif by == "episodes":
        col = "total_episodes"
    elif by == "manga_completed":
        col = "manga_completed"
    elif by == "anime_completed":
        col = "anime_completed"
    else:
        raise ValueError("by must be one of: 'chapters', 'episodes', 'manga_completed', 'anime_completed'")

    sql = f"SELECT discord_id, username, {col} FROM user_stats ORDER BY {col} DESC LIMIT ?"

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(sql, (limit,))
        rows = cur.fetchall()

    print(f"Top {limit} users by {by}:")
    for idx, row in enumerate(rows, start=1):
        discord_id, username, total = row
        print(f"{idx:2d}. {username} (discord_id={discord_id}) - {total}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--by', choices=['chapters', 'episodes', 'manga_completed', 'anime_completed'], default='chapters')
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()

    db_path = DB_PATH if DB_PATH else 'data/database.db'
    top_by(db_path, args.by, args.limit)
