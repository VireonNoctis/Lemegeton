import aiosqlite
from pathlib import Path
import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime

# ------------------------------------------------------
# Logging Setup
# ------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger("Database")

# ------------------------------------------------------
# Database Configuration
# ------------------------------------------------------
DB_NAME = "database.db"
DB_PATH = Path(DB_NAME).resolve()
logger.info(f"Using database file at: {DB_PATH}")

# ------------------------------------------------------
# USERS TABLE FUNCTIONS
# ------------------------------------------------------
async def init_users_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER UNIQUE,
                username TEXT NOT NULL
            )
        """)
        await db.commit()
        logger.info("Users table is ready.")

async def add_user(discord_id: int, username: str, anilist_username: str = None, anilist_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (discord_id, username, anilist_username, anilist_id)
            VALUES (?, ?, ?, ?)
            """,
            (discord_id, username, anilist_username, anilist_id)
        )
        await db.commit()


async def get_user(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users WHERE discord_id = ?", (discord_id,))
        user = await cursor.fetchone()
        await cursor.close()
        return user

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM users")
        users = await cursor.fetchall()
        await cursor.close()
        return users

async def update_username(discord_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET username = ? WHERE discord_id = ?", (username, discord_id))
        await db.commit()
        logger.info(f"Updated username for {discord_id} to {username}")

async def remove_user(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM users WHERE discord_id = ?", (discord_id,))
        await db.commit()
        logger.info(f"Removed user {discord_id}")

async def update_anilist_info(discord_id: int, anilist_username: str, anilist_id: int):
    """Update the anilist_username and anilist_id for a user in the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET anilist_username = ?, anilist_id = ?
            WHERE discord_id = ?
            """,
            (anilist_username, anilist_id, discord_id)
        )
        await db.commit()

# ------------------------------------------------------
# CHALLENGE RULES TABLE FUNCTIONS
# ------------------------------------------------------
async def init_challenge_rules_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS challenge_rules (
                id INTEGER PRIMARY KEY,
                rules TEXT
            )
        """)
        await db.commit()
        logger.info("Challenge rules table is ready.")

async def set_challenge_rules(rules: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO challenge_rules (id, rules)
            VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET rules=excluded.rules
        """, (rules,))
        await db.commit()
        logger.info("Challenge rules updated.")

async def get_challenge_rules() -> Optional[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT rules FROM challenge_rules WHERE id = 1")
        row = await cursor.fetchone()
        await cursor.close()
        return row[0] if row else None

# ------------------------------------------------------
# MANGA RECOMMENDATION VOTES TABLE
# ------------------------------------------------------
async def init_recommendation_votes_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS manga_recommendations_votes (
                manga_id INTEGER NOT NULL,
                voter_id INTEGER NOT NULL,
                vote INTEGER NOT NULL,
                PRIMARY KEY (manga_id, voter_id)
            )
        """)
        await db.commit()
        logger.info("Manga recommendation votes table ready.")

# ------------------------------------------------------
# USER STATS TABLE
# ------------------------------------------------------
async def init_user_stats_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                discord_id INTEGER PRIMARY KEY,
                username TEXT,
                total_manga INTEGER DEFAULT 0,
                total_anime INTEGER DEFAULT 0,
                avg_manga_score REAL DEFAULT 0,
                avg_anime_score REAL DEFAULT 0
            )
        """)
        await db.commit()
        logger.info("User stats table ready.")

# ------------------------------------------------------
# ACHIEVEMENTS TABLE
# ------------------------------------------------------
async def init_achievements_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                discord_id INTEGER,
                achievement TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (discord_id, achievement)
            )
        """)
        await db.commit()
        logger.info("Achievements table ready.")


# ------------------------------------------------------
# USER MANGA PROGRESS TABLE
# ------------------------------------------------------
async def init_user_manga_progress_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_manga_progress (
                discord_id INTEGER NOT NULL,
                manga_id INTEGER NOT NULL,
                current_chapter INTEGER DEFAULT 0,
                rating REAL DEFAULT 0,
                PRIMARY KEY (discord_id, manga_id)
            )
        """)
        await db.commit()
        logger.info("User manga progress table ready.")

async def set_user_manga_progress(discord_id: int, manga_id: int, chapter: int, rating: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_manga_progress (discord_id, manga_id, current_chapter, rating)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discord_id, manga_id) DO UPDATE SET
                current_chapter=excluded.current_chapter,
                rating=excluded.rating
        """, (discord_id, manga_id, chapter, rating))
        await db.commit()

async def get_user_manga_progress(discord_id: int, manga_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT current_chapter, rating FROM user_manga_progress
            WHERE discord_id = ? AND manga_id = ?
        """, (discord_id, manga_id))
        row = await cursor.fetchone()
        await cursor.close()
        return {"current_chapter": row[0], "rating": row[1]} if row else None

        
        
async def upsert_user_stats(
    discord_id: int,
    username: str,
    total_manga: int,
    total_anime: int,
    avg_manga_score: float,
    avg_anime_score: float,
    total_chapters: int = 0  # new column for total chapters
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_stats (
                discord_id, username, total_manga, total_anime,
                avg_manga_score, avg_anime_score, total_chapters
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                username=excluded.username,
                total_manga=excluded.total_manga,
                total_anime=excluded.total_anime,
                avg_manga_score=excluded.avg_manga_score,
                avg_anime_score=excluded.avg_anime_score,
                total_chapters=excluded.total_chapters
        """, (discord_id, username, total_manga, total_anime, avg_manga_score, avg_anime_score, total_chapters))
        await db.commit()
        logger.info(f"Upserted stats for {discord_id} ({username}) with {total_chapters} total chapters")


# Save or update a user
async def save_user(discord_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (discord_id, username)
            VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET username=excluded.username
        """, (discord_id, username))
        await db.commit()
        logger.info(f"Saved user: {username} ({discord_id})")


# ------------------------------------------------------
# MANGA CHALLENGES TABLE
# ------------------------------------------------------
async def init_manga_challenges_table():
    async with aiosqlite.connect("database.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS manga_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                manga_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                total_chapters INTEGER NOT NULL,
                chapters_read INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'in_progress',
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
        """)
        await db.commit()

async def init_global_challenges_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS global_challenges (
                challenge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                total_chapters INTEGER DEFAULT 0
            )
        """)
        await db.commit()


async def init_user_progress_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                challenge_manga_id INTEGER NOT NULL,
                chapters_read INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'in_progress',
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(challenge_manga_id) REFERENCES challenge_manga(id)
            )
        """)
        await db.commit()

async def add_global_challenge(manga_id: int, title: str, total_chapters: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO global_challenges (manga_id, title, total_chapters) VALUES (?, ?, ?)",
            (manga_id, title, total_chapters)
        )
        challenge_id = cursor.lastrowid
        users = await db.execute_fetchall("SELECT id FROM users")
        for (user_id,) in users:
            await db.execute(
                "INSERT INTO user_progress (user_id, challenge_id) VALUES (?, ?)",
                (user_id, challenge_id)
            )
        await db.commit()
        return challenge_id
    
async def init_challenge_manga_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS challenge_manga (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                challenge_id INTEGER NOT NULL,
                manga_id INTEGER NOT NULL UNIQUE,
                title TEXT NOT NULL,
                total_chapters INTEGER NOT NULL,
                FOREIGN KEY(challenge_id) REFERENCES global_challenges(challenge_id)
            )
        """)
        await db.commit()

async def upsert_user_anilist_progress(user_id: int, manga_id: int, chapters_read: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_progress (user_id, challenge_manga_id, chapters_read, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, challenge_manga_id) DO UPDATE SET
                chapters_read=excluded.chapters_read,
                status=excluded.status
        """, (user_id, manga_id, chapters_read, status))
        await db.commit()

async def upsert_user_manga_progress(discord_id: int, manga_id: int, current_chapter: int, rating: float):
    """
    Insert or update a user's manga progress.
    If a record for (discord_id, manga_id) exists, update current_chapter and rating.
    Otherwise, insert a new record.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_manga_progress (discord_id, manga_id, current_chapter, rating)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discord_id, manga_id) DO UPDATE SET
                current_chapter = excluded.current_chapter,
                rating = excluded.rating
        """, (discord_id, manga_id, current_chapter, rating))
        await db.commit()




# ------------------------------------------------------
# INITIALIZE ALL DATABASE TABLES
# ------------------------------------------------------
async def init_db():
    await init_users_table()
    await init_challenge_rules_table()
    await init_recommendation_votes_table()
    await init_user_stats_table()
    await init_achievements_table()
    await init_user_manga_progress_table()
    await init_manga_challenges_table()
    await init_user_progress_table()
    await init_global_challenges_table()
    await init_challenge_manga_table()
    logger.info("All database tables initialized.")
