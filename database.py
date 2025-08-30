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

async def add_user(discord_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (discord_id, username) VALUES (?, ?)",
            (discord_id, username)
        )
        await db.commit()
        logger.info(f"Added user: {username} ({discord_id})")

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


# Upsert user stats
async def upsert_user_stats(discord_id: int, username: str,
                            total_manga: int, total_anime: int,
                            avg_manga_score: float, avg_anime_score: float):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_stats (discord_id, username, total_manga, total_anime, avg_manga_score, avg_anime_score)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                username=excluded.username,
                total_manga=excluded.total_manga,
                total_anime=excluded.total_anime,
                avg_manga_score=excluded.avg_manga_score,
                avg_anime_score=excluded.avg_anime_score
        """, (discord_id, username, total_manga, total_anime, avg_manga_score, avg_anime_score))
        await db.commit()
        logger.info(f"Upserted stats for {discord_id} ({username})")

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
# INITIALIZE ALL DATABASE TABLES
# ------------------------------------------------------
async def init_db():
    await init_users_table()
    await init_challenge_rules_table()
    await init_recommendation_votes_table()
    await init_user_stats_table()
    await init_achievements_table()
    logger.info("All database tables initialized.")
