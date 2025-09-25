import asyncio
import os
import sys
from pathlib import Path

# Ensure project root is importable when running directly
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

import config
import database

async def main():
    # Use an existing discord_id from inspect output
    discord_id = 331164413623009281
    username = 'Kyerstorm'
    total_manga = 1455
    total_anime = 473
    avg_manga_score = 5.5
    avg_anime_score = 6.1
    total_chapters = 10000
    total_episodes = 8000
    manga_completed = 42
    anime_completed = 128

    print("Running upsert_user_stats for test user...")
    await database.upsert_user_stats(
        discord_id=discord_id,
        username=username,
        total_manga=total_manga,
        total_anime=total_anime,
        avg_manga_score=avg_manga_score,
        avg_anime_score=avg_anime_score,
        total_chapters=total_chapters,
        total_episodes=total_episodes,
        manga_completed=manga_completed,
        anime_completed=anime_completed
    )
    print("Upsert completed.")

if __name__ == '__main__':
    asyncio.run(main())
