# update_difficulty.py
import asyncio
import logging
import os
import aiosqlite

from challenge_helper import get_manga_difficulty, get_challenge_difficulty
from database import DB_PATH

# -----------------------------
# Logging setup
# -----------------------------
os.makedirs("logs", exist_ok=True)  # ✅ Ensure logs/ exists

log_file = os.path.join("logs", "update_difficulty.log")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),  # Console
        logging.FileHandler(log_file, "a", encoding="utf-8")  # File
    ]
)
logger = logging.getLogger("UpdateDifficulty")


async def update_manga_difficulties():
    """Update manga difficulties in the challenge_manga table."""
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            "SELECT challenge_id, manga_id, total_chapters FROM challenge_manga"
        )

        updated = 0
        for challenge_id, manga_id, total_chapters in rows:
            difficulty = await get_manga_difficulty(total_chapters)

            await db.execute(
                """
                UPDATE challenge_manga
                SET manga_difficulty = ?
                WHERE challenge_id = ? AND manga_id = ?
                """,
                (difficulty, challenge_id, manga_id)
            )
            logger.info(
                f"📖 Manga Update → Challenge {challenge_id}, Manga {manga_id}, "
                f"Chapters={total_chapters}, Difficulty={difficulty}"
            )
            updated += 1

        await db.commit()
        logger.info(f"✅ Finished updating manga_difficulty for {updated} titles.")


async def update_challenge_difficulties():
    """Update challenge difficulties in the global_challenges table."""
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute_fetchall(
            "SELECT challenge_id FROM global_challenges"
        )

        updated = 0
        for (challenge_id,) in rows:
            difficulty = await get_challenge_difficulty(db, challenge_id)

            await db.execute(
                """
                UPDATE global_challenges
                SET challenge_difficulty = ?
                WHERE challenge_id = ?
                """,
                (difficulty, challenge_id)
            )
            logger.info(
                f"🏆 Challenge Update → Challenge {challenge_id}, Difficulty={difficulty}"
            )
            updated += 1

        await db.commit()
        logger.info(f"✅ Finished updating challenge_difficulty for {updated} challenges.")


async def main():
    logger.info("🚀 Starting difficulty update...")
    await update_manga_difficulties()
    await update_challenge_difficulties()
    logger.info("🏁 Update completed.")


if __name__ == "__main__":
    asyncio.run(main())
