import aiosqlite
from pathlib import Path
import aiohttp
import asyncio
import logging
import os
import time
from typing import List, Dict, Optional
from datetime import datetime

# ------------------------------------------------------
# Logging Setup with File-based System
# ------------------------------------------------------
# Configuration constants
LOG_DIR = "logs"
LOG_FILE = "database.log"
LOG_MAX_SIZE = 50 * 1024 * 1024  # 50MB max log file size
DB_TIMEOUT = 30.0  # Database operation timeout in seconds
CONNECTION_RETRIES = 3  # Number of retry attempts for database connections
RETRY_DELAY = 1.0  # Delay between retries in seconds

# Ensure logs directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Configure comprehensive file-based logging
log_file_path = os.path.join(LOG_DIR, LOG_FILE)

# Clear existing log file if it's too large
if os.path.exists(log_file_path) and os.path.getsize(log_file_path) > LOG_MAX_SIZE:
    open(log_file_path, 'w').close()

# Setup file handler with detailed formatting
file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# Setup console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] [%(name)s] %(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Configure logger
logger = logging.getLogger("Database")
logger.setLevel(logging.DEBUG)
logger.handlers.clear()  # Remove any existing handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Prevent propagation to avoid duplicate logs
logger.propagate = False

logger.info("="*50)
logger.info("Database logging system initialized")
logger.info(f"Log file: {log_file_path}")
logger.info("="*50)

# ------------------------------------------------------
# Database Configuration with Enhanced Connection Management
# ------------------------------------------------------
DB_NAME = "database.db"
DB_PATH = Path(DB_NAME).resolve()

logger.info(f"Database configuration initialized")
logger.info(f"Database file path: {DB_PATH}")
logger.info(f"Database file exists: {DB_PATH.exists()}")
if DB_PATH.exists():
    file_size = DB_PATH.stat().st_size
    logger.info(f"Database file size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")

async def get_db_connection():
    """
    Get database connection with comprehensive logging and retry logic.
    """
    for attempt in range(CONNECTION_RETRIES):
        try:
            logger.debug(f"Attempting database connection (attempt {attempt + 1}/{CONNECTION_RETRIES})")
            
            connection = await aiosqlite.connect(
                DB_PATH, 
                timeout=DB_TIMEOUT,
                check_same_thread=False
            )
            
            # Enable foreign key constraints
            await connection.execute("PRAGMA foreign_keys = ON")
            
            logger.debug(f"Database connection established successfully")
            return connection
            
        except aiosqlite.Error as db_error:
            logger.warning(f"Database connection attempt {attempt + 1} failed: {db_error}")
            if attempt < CONNECTION_RETRIES - 1:
                logger.debug(f"Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"All database connection attempts failed")
                raise
        except Exception as e:
            logger.error(f"Unexpected error during database connection: {e}", exc_info=True)
            raise

async def execute_db_operation(operation_name: str, query: str, params=None, fetch_type=None):
    """
    Execute database operation with comprehensive logging and error handling.
    
    Args:
        operation_name: Human-readable name for the operation
        query: SQL query to execute
        params: Query parameters
        fetch_type: 'one', 'all', or None for no fetch
    """
    logger.debug(f"Executing {operation_name}")
    logger.debug(f"Query: {query}")
    if params:
        logger.debug(f"Parameters: {params}")
    
    start_time = time.time()
    
    try:
        async with await get_db_connection() as db:
            cursor = await db.execute(query, params or ())
            
            result = None
            if fetch_type == 'one':
                result = await cursor.fetchone()
            elif fetch_type == 'all':
                result = await cursor.fetchall()
            elif fetch_type == 'lastrowid':
                result = cursor.lastrowid
            
            await cursor.close()
            await db.commit()
            
            execution_time = time.time() - start_time
            logger.debug(f"{operation_name} completed in {execution_time:.3f}s")
            
            if result is not None:
                if fetch_type == 'one':
                    logger.debug(f"Query returned 1 row")
                elif fetch_type == 'all':
                    logger.debug(f"Query returned {len(result)} rows")
                elif fetch_type == 'lastrowid':
                    logger.debug(f"Last inserted row ID: {result}")
            
            return result
            
    except aiosqlite.Error as db_error:
        execution_time = time.time() - start_time
        logger.error(f"{operation_name} failed after {execution_time:.3f}s: {db_error}")
        raise
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Unexpected error in {operation_name} after {execution_time:.3f}s: {e}", exc_info=True)
        raise

# ------------------------------------------------------
# USERS TABLE FUNCTIONS with Enhanced Logging
# ------------------------------------------------------
async def init_users_table():
    """Initialize users table with comprehensive logging and error handling."""
    logger.info("Initializing users table")
    
    try:
        create_query = """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER UNIQUE NOT NULL,
                username TEXT NOT NULL,
                anilist_username TEXT,
                anilist_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        
        await execute_db_operation("users table creation", create_query)
        
        # Add missing columns if they don't exist
        columns_to_add = [
            ("anilist_username", "TEXT"),
            ("anilist_id", "INTEGER"),
            ("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                alter_query = f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
                await execute_db_operation(f"add {column_name} column to users", alter_query)
                logger.debug(f"Added missing column '{column_name}' to users table")
            except aiosqlite.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.debug(f"Column '{column_name}' already exists in users table")
                else:
                    logger.warning(f"Error adding column '{column_name}' to users table: {e}")
        
        # Verify table structure
        schema_query = "PRAGMA table_info(users)"
        schema = await execute_db_operation("users table schema check", schema_query, fetch_type='all')
        logger.debug(f"Users table schema: {len(schema)} columns")
        for column in schema:
            logger.debug(f"  Column: {column[1]} ({column[2]})")
        
        logger.info("✅ Users table initialization completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize users table: {e}", exc_info=True)
        raise

async def add_user(discord_id: int, username: str, anilist_username: str = None, anilist_id: int = None):
    """Add new user with comprehensive logging and validation."""
    logger.info(f"Adding new user: {username} (Discord ID: {discord_id})")
    
    try:
        # Validate input
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(username, str) or not username.strip():
            raise ValueError(f"Invalid username: {username}")
        
        logger.debug(f"User data - Discord ID: {discord_id}, Username: {username}")
        if anilist_username:
            logger.debug(f"AniList data - Username: {anilist_username}, ID: {anilist_id}")
        
        query = """
            INSERT INTO users (discord_id, username, anilist_username, anilist_id)
            VALUES (?, ?, ?, ?)
        """
        
        await execute_db_operation(
            f"add user {username}",
            query,
            (discord_id, username.strip(), anilist_username, anilist_id)
        )
        
        logger.info(f"✅ Successfully added user {username} (Discord ID: {discord_id})")
        
    except aiosqlite.IntegrityError as integrity_error:
        if "UNIQUE constraint failed" in str(integrity_error):
            logger.warning(f"User {discord_id} already exists, cannot add duplicate")
        else:
            logger.error(f"Database integrity error adding user {discord_id}: {integrity_error}")
        raise
    except ValueError as validation_error:
        logger.error(f"Validation error adding user: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error adding user {discord_id}: {e}", exc_info=True)
        raise


async def get_user(discord_id: int):
    """Get user by Discord ID with comprehensive logging."""
    logger.debug(f"Retrieving user data for Discord ID: {discord_id}")
    
    try:
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        
        query = "SELECT * FROM users WHERE discord_id = ?"
        user = await execute_db_operation(
            f"get user {discord_id}",
            query,
            (discord_id,),
            fetch_type='one'
        )
        
        if user:
            logger.debug(f"✅ Found user: {user[2]} (ID: {user[0]})")  # username at index 2, id at index 0
        else:
            logger.debug(f"No user found for Discord ID: {discord_id}")
        
        return user
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting user: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving user {discord_id}: {e}", exc_info=True)
        raise

async def get_all_users():
    """Get all users with comprehensive logging."""
    logger.debug("Retrieving all users from database")
    
    try:
        query = "SELECT * FROM users ORDER BY username"
        users = await execute_db_operation(
            "get all users",
            query,
            fetch_type='all'
        )
        
        logger.info(f"✅ Retrieved {len(users)} users from database")
        return users
        
    except Exception as e:
        logger.error(f"❌ Error retrieving all users: {e}", exc_info=True)
        raise

async def update_username(discord_id: int, username: str):
    """Update username with comprehensive logging and validation."""
    logger.info(f"Updating username for Discord ID {discord_id} to '{username}'")
    
    try:
        # Validate input
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(username, str) or not username.strip():
            raise ValueError(f"Invalid username: {username}")
        
        # Check if user exists first
        existing_user = await get_user(discord_id)
        if not existing_user:
            logger.warning(f"Cannot update username - user {discord_id} not found")
            return False
        
        old_username = existing_user[2]  # username at index 2
        
        query = "UPDATE users SET username = ?, updated_at = CURRENT_TIMESTAMP WHERE discord_id = ?"
        await execute_db_operation(
            f"update username for {discord_id}",
            query,
            (username.strip(), discord_id)
        )
        
        logger.info(f"✅ Updated username for {discord_id}: '{old_username}' → '{username}'")
        return True
        
    except ValueError as validation_error:
        logger.error(f"Validation error updating username: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error updating username for {discord_id}: {e}", exc_info=True)
        raise

async def remove_user(discord_id: int):
    """Remove user with comprehensive logging and validation."""
    logger.info(f"Removing user with Discord ID: {discord_id}")
    
    try:
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        
        # Check if user exists first
        existing_user = await get_user(discord_id)
        if not existing_user:
            logger.warning(f"Cannot remove user - user {discord_id} not found")
            return False
        
        username = existing_user[2]  # username at index 2
        
        query = "DELETE FROM users WHERE discord_id = ?"
        await execute_db_operation(
            f"remove user {discord_id}",
            query,
            (discord_id,)
        )
        
        logger.info(f"✅ Successfully removed user: {username} (Discord ID: {discord_id})")
        return True
        
    except ValueError as validation_error:
        logger.error(f"Validation error removing user: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error removing user {discord_id}: {e}", exc_info=True)
        raise

async def update_anilist_info(discord_id: int, anilist_username: str, anilist_id: int):
    """Update AniList information with comprehensive logging and validation."""
    logger.info(f"Updating AniList info for Discord ID {discord_id}")
    logger.debug(f"AniList data - Username: {anilist_username}, ID: {anilist_id}")
    
    try:
        # Validate input
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(anilist_username, str) or not anilist_username.strip():
            raise ValueError(f"Invalid anilist_username: {anilist_username}")
        if not isinstance(anilist_id, int) or anilist_id <= 0:
            raise ValueError(f"Invalid anilist_id: {anilist_id}")
        
        # Check if user exists
        existing_user = await get_user(discord_id)
        if not existing_user:
            logger.error(f"Cannot update AniList info - user {discord_id} not found")
            return False
        
        query = """
            UPDATE users
            SET anilist_username = ?, anilist_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE discord_id = ?
        """
        
        await execute_db_operation(
            f"update AniList info for {discord_id}",
            query,
            (anilist_username.strip(), anilist_id, discord_id)
        )
        
        logger.info(f"✅ Updated AniList info for {discord_id}: {anilist_username} (ID: {anilist_id})")
        return True
        
    except ValueError as validation_error:
        logger.error(f"Validation error updating AniList info: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error updating AniList info for {discord_id}: {e}", exc_info=True)
        raise

# ------------------------------------------------------
# CHALLENGE RULES TABLE FUNCTIONS with Enhanced Logging
# ------------------------------------------------------
async def init_challenge_rules_table():
    """Initialize challenge rules table with comprehensive logging."""
    logger.info("Initializing challenge rules table")
    
    try:
        create_query = """
            CREATE TABLE IF NOT EXISTS challenge_rules (
                id INTEGER PRIMARY KEY,
                rules TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        
        await execute_db_operation("challenge rules table creation", create_query)
        
        # Add missing timestamp columns if they don't exist
        for column_name, column_type in [("created_at", "DATETIME DEFAULT CURRENT_TIMESTAMP"), ("updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")]:
            try:
                alter_query = f"ALTER TABLE challenge_rules ADD COLUMN {column_name} {column_type}"
                await execute_db_operation(f"add {column_name} to challenge_rules", alter_query)
                logger.debug(f"Added missing column '{column_name}' to challenge_rules table")
            except aiosqlite.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.debug(f"Column '{column_name}' already exists in challenge_rules table")
        
        logger.info("✅ Challenge rules table initialization completed")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize challenge rules table: {e}", exc_info=True)
        raise

async def set_challenge_rules(rules: str):
    """Set challenge rules with comprehensive logging and validation."""
    logger.info("Setting challenge rules")
    
    try:
        if not isinstance(rules, str) or not rules.strip():
            raise ValueError("Rules must be a non-empty string")
        
        logger.debug(f"Rules length: {len(rules)} characters")
        
        query = """
            INSERT INTO challenge_rules (id, rules, updated_at)
            VALUES (1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET 
                rules=excluded.rules,
                updated_at=CURRENT_TIMESTAMP
        """
        
        await execute_db_operation("set challenge rules", query, (rules.strip(),))
        logger.info("✅ Challenge rules updated successfully")
        
    except ValueError as validation_error:
        logger.error(f"Validation error setting challenge rules: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error setting challenge rules: {e}", exc_info=True)
        raise

async def get_challenge_rules() -> Optional[str]:
    """Get challenge rules with comprehensive logging."""
    logger.debug("Retrieving challenge rules")
    
    try:
        query = "SELECT rules FROM challenge_rules WHERE id = 1"
        result = await execute_db_operation("get challenge rules", query, fetch_type='one')
        
        if result:
            rules = result[0]
            logger.debug(f"Retrieved challenge rules ({len(rules)} characters)")
            return rules
        else:
            logger.debug("No challenge rules found")
            return None
            
    except Exception as e:
        logger.error(f"❌ Error retrieving challenge rules: {e}", exc_info=True)
        raise

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
        # Create table if not exists
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_manga_progress (
                discord_id INTEGER NOT NULL,
                manga_id INTEGER NOT NULL,
                title TEXT DEFAULT '',
                current_chapter INTEGER DEFAULT 0,
                rating REAL DEFAULT 0,
                status TEXT DEFAULT 'Not Started',
                points INTEGER DEFAULT 0,
                repeat INTEGER DEFAULT 0,
                started_at TEXT DEFAULT NULL,
                updated_at TEXT DEFAULT NULL,   -- NEW COLUMN
                PRIMARY KEY (discord_id, manga_id)
            )
        """)
        # Add 'repeat' column if missing
        try:
            await db.execute("ALTER TABLE user_manga_progress ADD COLUMN repeat INTEGER DEFAULT 0")
        except aiosqlite.OperationalError:
            pass
        # Add 'updated_at' column if missing
        try:
            await db.execute("ALTER TABLE user_manga_progress ADD COLUMN updated_at TEXT DEFAULT NULL")
        except aiosqlite.OperationalError:
            pass

        await db.commit()
        logger.info("User manga progress table ready (with started_at, repeat, and updated_at).")



async def set_user_manga_progress(discord_id: int, manga_id: int, chapter: int, rating: float):
    """Set user manga progress with comprehensive logging and validation."""
    logger.info(f"Setting manga progress for user {discord_id}, manga {manga_id}")
    
    try:
        # Validate input
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(manga_id, int) or manga_id <= 0:
            raise ValueError(f"Invalid manga_id: {manga_id}")
        if not isinstance(chapter, int) or chapter < 0:
            raise ValueError(f"Invalid chapter: {chapter}")
        if not isinstance(rating, (int, float)) or not (0 <= rating <= 10):
            logger.warning(f"Invalid rating {rating}, clamping to 0-10 range")
            rating = max(0, min(10, float(rating)))
        
        logger.debug(f"Progress data - Chapter: {chapter}, Rating: {rating}")
        
        query = """
            INSERT INTO user_manga_progress (discord_id, manga_id, current_chapter, rating, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(discord_id, manga_id) DO UPDATE SET
                current_chapter=excluded.current_chapter,
                rating=excluded.rating,
                updated_at=CURRENT_TIMESTAMP
        """
        
        await execute_db_operation(
            f"set manga progress for user {discord_id}",
            query,
            (discord_id, manga_id, chapter, rating)
        )
        
        logger.info(f"✅ Set manga {manga_id} progress for user {discord_id}: Chapter {chapter}, Rating {rating}")
        
    except ValueError as validation_error:
        logger.error(f"Validation error setting manga progress: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error setting manga progress for user {discord_id}: {e}", exc_info=True)
        raise

async def get_user_manga_progress(discord_id: int, manga_id: int):
    """Get user manga progress with comprehensive logging and validation."""
    logger.debug(f"Getting manga progress for user {discord_id}, manga {manga_id}")
    
    try:
        # Validate input
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(manga_id, int) or manga_id <= 0:
            raise ValueError(f"Invalid manga_id: {manga_id}")
        
        query = """
            SELECT current_chapter, rating, status, repeat FROM user_manga_progress
            WHERE discord_id = ? AND manga_id = ?
        """
        
        result = await execute_db_operation(
            f"get manga progress for user {discord_id}",
            query,
            (discord_id, manga_id),
            fetch_type='one'
        )
        
        if result:
            progress_data = {
                "current_chapter": result[0],
                "rating": result[1],
                "status": result[2],
                "repeat": result[3]
            }
            logger.debug(f"✅ Retrieved manga progress: {progress_data}")
            return progress_data
        else:
            logger.debug(f"No progress found for user {discord_id}, manga {manga_id}")
            return None
            
    except ValueError as validation_error:
        logger.error(f"Validation error getting manga progress: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error getting manga progress for user {discord_id}: {e}", exc_info=True)
        raise

async def upsert_user_manga_progress(discord_id, manga_id, title, chapters, points, status, repeat=0, started_at=None):
    """Upsert user manga progress with comprehensive logging and validation."""
    logger.info(f"Upserting manga progress for user {discord_id}: {title}")
    
    try:
        # Validate input
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(manga_id, int) or manga_id <= 0:
            raise ValueError(f"Invalid manga_id: {manga_id}")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Invalid title: {title}")
        if not isinstance(chapters, int) or chapters < 0:
            logger.warning(f"Invalid chapters {chapters}, setting to 0")
            chapters = 0
        if not isinstance(points, int) or points < 0:
            logger.warning(f"Invalid points {points}, setting to 0")
            points = 0
        if not isinstance(repeat, int) or repeat < 0:
            logger.warning(f"Invalid repeat {repeat}, setting to 0")
            repeat = 0
        
        logger.debug(f"Manga progress - Title: {title}, Chapters: {chapters}, Points: {points}, Status: {status}, Repeat: {repeat}")
        
        now = datetime.utcnow().isoformat()
        
        query = """
            INSERT INTO user_manga_progress(
                discord_id, manga_id, title, current_chapter, points, status, repeat, started_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id, manga_id) DO UPDATE SET
                title=excluded.title,
                current_chapter=excluded.current_chapter,
                points=excluded.points,
                status=excluded.status,
                repeat=excluded.repeat,
                started_at=excluded.started_at,
                updated_at=excluded.updated_at
        """
        
        await execute_db_operation(
            f"upsert manga progress for user {discord_id}",
            query,
            (discord_id, manga_id, title.strip(), chapters, points, status, repeat, started_at, now)
        )
        
        logger.info(f"✅ Upserted manga progress for user {discord_id}: {title} ({status})")
        
    except ValueError as validation_error:
        logger.error(f"Validation error upserting manga progress: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error upserting manga progress for user {discord_id}: {e}", exc_info=True)
        raise
        
async def upsert_user_stats(
    discord_id: int,
    username: str,
    total_manga: int,
    total_anime: int,
    avg_manga_score: float,
    avg_anime_score: float,
    total_chapters: int = 0,
    total_episodes: int = 0 
):
    """Upsert user stats with comprehensive logging and validation."""
    logger.info(f"Upserting stats for user {username} (Discord ID: {discord_id})")
    
    try:
        # Validate input data
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(username, str) or not username.strip():
            raise ValueError(f"Invalid username: {username}")
        
        # Validate numeric fields
        numeric_fields = {
            'total_manga': total_manga,
            'total_anime': total_anime,
            'avg_manga_score': avg_manga_score,
            'avg_anime_score': avg_anime_score,
            'total_chapters': total_chapters,
            'total_episodes': total_episodes
        }
        
        for field_name, value in numeric_fields.items():
            if not isinstance(value, (int, float)) or value < 0:
                logger.warning(f"Invalid {field_name}: {value}, setting to 0")
                numeric_fields[field_name] = 0
        
        logger.debug(f"User stats - Manga: {total_manga}, Anime: {total_anime}, Chapters: {total_chapters}, Episodes: {total_episodes}")
        logger.debug(f"Average scores - Manga: {avg_manga_score:.2f}, Anime: {avg_anime_score:.2f}")
        
        query = """
            INSERT INTO user_stats (
                discord_id, username, total_manga, total_anime,
                avg_manga_score, avg_anime_score, total_chapters, total_episodes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                username=excluded.username,
                total_manga=excluded.total_manga,
                total_anime=excluded.total_anime,
                avg_manga_score=excluded.avg_manga_score,
                avg_anime_score=excluded.avg_anime_score,
                total_chapters=excluded.total_chapters,
                total_episodes=excluded.total_episodes
        """
        
        await execute_db_operation(
            f"upsert user stats for {username}",
            query,
            (discord_id, username.strip(), numeric_fields['total_manga'], numeric_fields['total_anime'],
             numeric_fields['avg_manga_score'], numeric_fields['avg_anime_score'], 
             numeric_fields['total_chapters'], numeric_fields['total_episodes'])
        )
        
        logger.info(f"✅ Successfully upserted stats for {username}")
        
    except ValueError as validation_error:
        logger.error(f"Validation error upserting user stats: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error upserting stats for {discord_id}: {e}", exc_info=True)
        raise

# Save or update a user with comprehensive logging
async def save_user(discord_id: int, username: str):
    """Save or update user with comprehensive logging and validation."""
    logger.info(f"Saving user: {username} (Discord ID: {discord_id})")
    
    try:
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(username, str) or not username.strip():
            raise ValueError(f"Invalid username: {username}")
        
        # Check if user already exists
        existing_user = await get_user(discord_id)
        operation_type = "update" if existing_user else "insert"
        
        query = """
            INSERT INTO users (discord_id, username, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(discord_id) DO UPDATE SET 
                username=excluded.username,
                updated_at=CURRENT_TIMESTAMP
        """
        
        await execute_db_operation(
            f"save user {username} ({operation_type})",
            query,
            (discord_id, username.strip())
        )
        
        logger.info(f"✅ Successfully saved user: {username} ({operation_type})")
        
    except ValueError as validation_error:
        logger.error(f"Validation error saving user: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error saving user {discord_id}: {e}", exc_info=True)
        raise


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
        # Create table if it doesn't exist (without the difficulty column first)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS global_challenges (
                challenge_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                total_chapters INTEGER DEFAULT 0
            )
        """)
        # Try adding the column (if it doesn't exist yet)
        try:
            await db.execute("ALTER TABLE global_challenges ADD COLUMN difficulty TEXT DEFAULT 'Medium'")
        except aiosqlite.OperationalError:
            # Column already exists
            pass

        # Optional: Add a start_date column too if you need it
        try:
            await db.execute("ALTER TABLE global_challenges ADD COLUMN start_date TEXT DEFAULT NULL")
        except aiosqlite.OperationalError:
            pass

        await db.commit()
        logger.info("Global challenges table ready with difficulty column.")

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

async def add_global_challenge(manga_id: int, title: str, total_chapters: int, start_date: datetime = None):
    if start_date is None:
        start_date = datetime.utcnow()  # Use UTC for consistency

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO global_challenges (manga_id, title, total_chapters, start_date)
            VALUES (?, ?, ?, ?)
            """,
            (manga_id, title, total_chapters, start_date)
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
                medium_type TEXT DEFAULT 'manga',
                FOREIGN KEY(challenge_id) REFERENCES global_challenges(challenge_id)
            )
        """)
        # Ensure medium_type exists if the table already existed
        try:
            await db.execute("ALTER TABLE challenge_manga ADD COLUMN medium_type TEXT DEFAULT 'manga'")
        except aiosqlite.OperationalError:
            # Column already exists, ignore
            pass
        await db.commit()

from datetime import datetime

async def upsert_user_manga_progress(discord_id, manga_id, title, chapters, points, status, repeat=0, started_at=None):
    """Upsert user manga progress including repeat, started_at, and updated_at"""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_manga_progress(discord_id, manga_id, title, current_chapter, points, status, repeat, started_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id, manga_id) DO UPDATE SET
                title=excluded.title,
                current_chapter=excluded.current_chapter,
                points=excluded.points,
                status=excluded.status,
                repeat=excluded.repeat,
                started_at=excluded.started_at,
                updated_at=excluded.updated_at
            """,
            (discord_id, manga_id, title, chapters, points, status, repeat, started_at, now)
        )
        await db.commit()

# ------------------------------------------------------
# STEAM USERS TABLE
# ------------------------------------------------------
async def init_steam_users_table():
    """Create a table to store Discord -> Steam account mapping"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS steam_users (
                discord_id INTEGER PRIMARY KEY,
                steam_id TEXT NOT NULL,
                vanity_name TEXT
            )
        """)
        await db.commit()
        logger.info("Steam users table ready.")




# ------------------------------------------------------
# INITIALIZE ALL DATABASE TABLES with Enhanced Logging
# ------------------------------------------------------
async def init_db():
    """Initialize all database tables with comprehensive logging and error handling."""
    logger.info("="*60)
    logger.info("STARTING DATABASE INITIALIZATION")
    logger.info("="*60)
    
    # List of table initialization functions and their names
    table_init_functions = [
        ("Users", init_users_table),
        ("Challenge Rules", init_challenge_rules_table),
        ("Recommendation Votes", init_recommendation_votes_table),
        ("User Stats", init_user_stats_table),
        ("Achievements", init_achievements_table),
        ("User Manga Progress", init_user_manga_progress_table),
        ("Manga Challenges", init_manga_challenges_table),
        ("User Progress", init_user_progress_table),
        ("Global Challenges", init_global_challenges_table),
        ("Steam Users", init_steam_users_table),
        ("Challenge Manga", init_challenge_manga_table),
    ]
    
    start_time = time.time()
    success_count = 0
    failure_count = 0
    
    try:
        # Verify database connectivity first
        logger.info("Verifying database connectivity...")
        async with await get_db_connection() as test_db:
            await test_db.execute("SELECT 1")
        logger.info("✅ Database connectivity verified")
        
        # Initialize each table
        for table_name, init_function in table_init_functions:
            try:
                logger.debug(f"Initializing {table_name} table...")
                await init_function()
                success_count += 1
                logger.debug(f"✅ {table_name} table initialized successfully")
                
            except Exception as table_error:
                failure_count += 1
                logger.error(f"❌ Failed to initialize {table_name} table: {table_error}", exc_info=True)
                # Continue with other tables instead of failing completely
        
        # Log final statistics
        total_time = time.time() - start_time
        total_tables = len(table_init_functions)
        
        logger.info("="*60)
        logger.info("DATABASE INITIALIZATION SUMMARY")
        logger.info(f"Total tables: {total_tables}")
        logger.info(f"Successfully initialized: {success_count}")
        logger.info(f"Failed to initialize: {failure_count}")
        logger.info(f"Total time: {total_time:.2f} seconds")
        
        if failure_count > 0:
            logger.warning(f"⚠️  {failure_count} tables failed to initialize - some functionality may be limited")
        else:
            logger.info("✅ All database tables initialized successfully")
        
        logger.info("="*60)
        
        # Log database file statistics
        if DB_PATH.exists():
            file_size = DB_PATH.stat().st_size
            logger.info(f"Final database file size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")
        
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(f"❌ Fatal error during database initialization after {total_time:.2f}s: {e}", exc_info=True)
        raise
