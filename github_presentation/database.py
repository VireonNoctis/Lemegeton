import aiosqlite
from pathlib import Path
import aiohttp
import asyncio
import logging
import os
import time
from typing import List, Dict, Optional
from datetime import datetime
import config

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
DB_PATH = Path(config.DB_PATH).resolve()

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
            
            # Create a new connection each time to avoid thread reuse issues
            connection = aiosqlite.connect(
                DB_PATH, 
                timeout=DB_TIMEOUT,
                check_same_thread=False
            )
            
            # Don't await here - let the caller handle the async context
            logger.debug(f"Database connection object created successfully")
            return connection
            
        except Exception as e:
            logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < CONNECTION_RETRIES - 1:
                logger.debug(f"Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error(f"All database connection attempts failed")
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
        # Use direct aiosqlite.connect instead of the helper to avoid connection reuse issues
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
            # Enable foreign key constraints
            await db.execute("PRAGMA foreign_keys = ON")
            
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

async def migrate_to_multi_guild_schema():
    """Migrate the users table to support multi-guild by removing UNIQUE constraint on discord_id."""
    logger.info("🔄 Starting migration to multi-guild schema")
    
    try:
        # SQLite doesn't support dropping constraints, so we need to recreate the table
        # 1. Create new table with correct schema
        new_table_query = """
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                anilist_username TEXT,
                anilist_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(discord_id, guild_id)
            )
        """
        await execute_db_operation("create new users table", new_table_query)
        
        # 2. Copy data from old table to new table
        copy_query = """
            INSERT INTO users_new (id, discord_id, guild_id, username, anilist_username, anilist_id, created_at, updated_at)
            SELECT id, discord_id, COALESCE(guild_id, 897814031346319382), username, anilist_username, anilist_id, created_at, updated_at
            FROM users
        """
        await execute_db_operation("copy data to new users table", copy_query)
        
        # 3. Drop old table
        await execute_db_operation("drop old users table", "DROP TABLE users")
        
        # 4. Rename new table to original name
        await execute_db_operation("rename new users table", "ALTER TABLE users_new RENAME TO users")
        
        logger.info("✅ Successfully migrated to multi-guild schema")
        
    except Exception as e:
        logger.error(f"❌ Failed to migrate to multi-guild schema: {e}", exc_info=True)
        # Try to clean up any partial migration
        try:
            await execute_db_operation("cleanup failed migration", "DROP TABLE IF EXISTS users_new")
        except:
            pass
        raise

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
            ("guild_id", "INTEGER"),
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
        
        # Check if we need to migrate to multi-guild support
        # The original table has UNIQUE constraint on discord_id, but for multi-guild we need to allow duplicates
        try:
            # Check if guild_id column exists and if we have multi-guild data
            has_guild_id = any(col[1] == 'guild_id' for col in schema)
            if has_guild_id:
                # Check if we have any users with guild_id (new schema)
                check_query = "SELECT COUNT(*) FROM users WHERE guild_id IS NOT NULL"
                count_result = await execute_db_operation("check guild_id usage", check_query, fetch_type='one')
                has_guild_data = count_result[0] > 0 if count_result else False
                
                if not has_guild_data:
                    # Migrate existing users to use default guild_id
                    default_guild_id = 897814031346319382  # Your server ID
                    migrate_query = "UPDATE users SET guild_id = ? WHERE guild_id IS NULL"
                    await execute_db_operation("migrate existing users to default guild", migrate_query, (default_guild_id,))
                    logger.info(f"✅ Migrated existing users to default guild ID: {default_guild_id}")
                
                # Remove the UNIQUE constraint on discord_id to allow multi-guild support
                # SQLite doesn't support dropping constraints directly, so we need to recreate the table
                # But only if we still have the old constraint
                try:
                    # Test if we can insert duplicate discord_id (different guild_id)
                    test_discord_id = 999999999999999999  # Unlikely to exist
                    test_guild_id_1 = 1
                    test_guild_id_2 = 2
                    
                    # Try to insert two records with same discord_id but different guild_id
                    test_query = "INSERT INTO users (discord_id, guild_id, username) VALUES (?, ?, ?)"
                    await execute_db_operation("test multi-guild insert 1", test_query, (test_discord_id, test_guild_id_1, "test1"))
                    await execute_db_operation("test multi-guild insert 2", test_query, (test_discord_id, test_guild_id_2, "test2"))
                    
                    # Clean up test data
                    cleanup_query = "DELETE FROM users WHERE discord_id = ?"
                    await execute_db_operation("cleanup test data", cleanup_query, (test_discord_id,))
                    
                    logger.info("✅ Multi-guild support confirmed - table supports multiple guilds per user")
                    
                except aiosqlite.IntegrityError as e:
                    if "UNIQUE constraint failed" in str(e):
                        logger.warning("🔄 Table still has UNIQUE constraint on discord_id - migration needed")
                        await migrate_to_multi_guild_schema()
                    else:
                        logger.error(f"Unexpected integrity error during multi-guild test: {e}")
                except Exception as e:
                    logger.debug(f"Multi-guild test failed (may be normal): {e}")
                    
        except Exception as e:
            logger.error(f"Error during multi-guild migration check: {e}", exc_info=True)
        
        logger.info("✅ Users table initialization completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize users table: {e}", exc_info=True)
        raise

async def add_user(discord_id: int, username: str, anilist_username: str = None, anilist_id: int = None):
    """Add new user with comprehensive logging and validation. (DEPRECATED: Use add_user_guild_aware instead)"""
    logger.warning("Using deprecated add_user function. Consider using add_user_guild_aware for multi-guild support")
    
    try:
        # Validate input
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(username, str) or not username.strip():
            raise ValueError(f"Invalid username: {username}")
        
        logger.debug(f"User data - Discord ID: {discord_id}, Username: {username}")
        if anilist_username:
            logger.debug(f"AniList data - Username: {anilist_username}, ID: {anilist_id}")
        
        # For backwards compatibility, use a default guild_id (your current server)
        # This should be updated to use actual guild_id in all calling code
        default_guild_id = 897814031346319382
        
        query = """
            INSERT OR REPLACE INTO users (discord_id, guild_id, username, anilist_username, anilist_id, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        
        await execute_db_operation(
            f"add user {username}",
            query,
            (discord_id, default_guild_id, username.strip(), anilist_username, anilist_id)
        )
        
        logger.info(f"✅ Successfully added user {username} (Discord ID: {discord_id}) to default guild")
        
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


async def add_user_guild_aware(discord_id: int, guild_id: int, username: str, anilist_username: str = None, anilist_id: int = None):
    """Add new user with guild context for multi-server support."""
    logger.info(f"Adding new user: {username} (Discord ID: {discord_id}) to guild {guild_id}")
    
    try:
        # Validate input
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        if not isinstance(username, str) or not username.strip():
            raise ValueError(f"Invalid username: {username}")
        
        logger.debug(f"User data - Discord ID: {discord_id}, Guild ID: {guild_id}, Username: {username}")
        if anilist_username:
            logger.debug(f"AniList data - Username: {anilist_username}, ID: {anilist_id}")
        
        query = """
            INSERT OR REPLACE INTO users (discord_id, guild_id, username, anilist_username, anilist_id, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        
        await execute_db_operation(
            f"add user {username} to guild {guild_id}",
            query,
            (discord_id, guild_id, username.strip(), anilist_username, anilist_id)
        )
        
        logger.info(f"✅ Successfully added user {username} (Discord ID: {discord_id}) to guild {guild_id}")
        
    except aiosqlite.IntegrityError as integrity_error:
        if "UNIQUE constraint failed" in str(integrity_error):
            logger.warning(f"User {discord_id} already exists in guild {guild_id}, updating instead")
            # The INSERT OR REPLACE should handle this, but log it anyway
        else:
            logger.error(f"Database integrity error adding user {discord_id} to guild {guild_id}: {integrity_error}")
        raise
    except ValueError as validation_error:
        logger.error(f"Validation error adding user: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error adding user {discord_id} to guild {guild_id}: {e}", exc_info=True)
        raise


async def get_user(discord_id: int):
    """Get user by Discord ID with comprehensive logging. (DEPRECATED: Use get_user_guild_aware instead)"""
    logger.warning("Using deprecated get_user function. Consider using get_user_guild_aware for multi-guild support")
    logger.debug(f"Retrieving user data for Discord ID: {discord_id}")
    
    try:
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        
        # For backwards compatibility, try to get user from default guild first
        default_guild_id = 897814031346319382
        query = "SELECT * FROM users WHERE discord_id = ? AND guild_id = ?"
        user = await execute_db_operation(
            f"get user {discord_id} from default guild",
            query,
            (discord_id, default_guild_id),
            fetch_type='one'
        )
        
        if user:
            logger.debug(f"✅ Found user: {user[3]} (ID: {user[0]}) in default guild")  # username at index 3
        else:
            logger.debug(f"No user found for Discord ID: {discord_id} in default guild")
        
        return user
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting user: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting user {discord_id}: {e}", exc_info=True)
        raise


async def get_user_guild_aware(discord_id: int, guild_id: int):
    """Get user by Discord ID and Guild ID for multi-server support."""
    logger.debug(f"Retrieving user data for Discord ID: {discord_id} in guild: {guild_id}")
    
    try:
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        
        query = "SELECT * FROM users WHERE discord_id = ? AND guild_id = ?"
        user = await execute_db_operation(
            f"get user {discord_id} from guild {guild_id}",
            query,
            (discord_id, guild_id),
            fetch_type='one'
        )
        
        if user:
            logger.debug(f"✅ Found user: {user[3]} (ID: {user[0]}) in guild {guild_id}")  # username at index 3
        else:
            logger.debug(f"No user found for Discord ID: {discord_id} in guild {guild_id}")
        
        return user
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting user: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting user {discord_id} from guild {guild_id}: {e}", exc_info=True)
        raise
        
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
        
        query = "UPDATE users SET username = ? WHERE discord_id = ?"
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
    """Remove user with comprehensive logging and validation, including all related data."""
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
        logger.info(f"Beginning cascading deletion for user: {username} (Discord ID: {discord_id})")
        
        # Check related records for debugging
        related_records = await check_user_related_records(discord_id)
        if any(count > 0 for count in related_records.values() if isinstance(count, int)):
            logger.info(f"Found related records to delete: {related_records}")
        
        # Use direct connection to ensure all operations are in a single transaction
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
            db.row_factory = aiosqlite.Row
            
            # Begin transaction for atomic deletion
            await db.execute("BEGIN TRANSACTION")
            
            try:
                # Delete from all related tables first (in order to avoid foreign key conflicts)
                
                # 1. Delete user manga progress
                result = await db.execute("DELETE FROM user_manga_progress WHERE discord_id = ?", (discord_id,))
                progress_deleted = result.rowcount
                logger.debug(f"Deleted {progress_deleted} manga progress records for user {discord_id}")
                
                # 2. Delete user stats
                result = await db.execute("DELETE FROM user_stats WHERE discord_id = ?", (discord_id,))
                stats_deleted = result.rowcount
                logger.debug(f"Deleted {stats_deleted} user stats records for user {discord_id}")
                
                # 3. Delete cached stats
                try:
                    result = await db.execute("DELETE FROM cached_stats WHERE discord_id = ?", (discord_id,))
                    cached_deleted = result.rowcount
                    logger.debug(f"Deleted {cached_deleted} cached stats records for user {discord_id}")
                except Exception as e:
                    logger.debug(f"Cached stats deletion failed (table may not exist): {e}")
                    cached_deleted = 0
                
                # 4. Delete manga recommendation votes (voter_id column)
                try:
                    result = await db.execute("DELETE FROM manga_recommendations_votes WHERE voter_id = ?", (discord_id,))
                    votes_deleted = result.rowcount
                    logger.debug(f"Deleted {votes_deleted} recommendation votes for user {discord_id}")
                except Exception as e:
                    logger.debug(f"Manga recommendations votes deletion failed (table may not exist): {e}")
                    votes_deleted = 0
                
                # 5. Delete achievements
                try:
                    result = await db.execute("DELETE FROM achievements WHERE discord_id = ?", (discord_id,))
                    achievements_deleted = result.rowcount
                    logger.debug(f"Deleted {achievements_deleted} achievements for user {discord_id}")
                except Exception as e:
                    logger.debug(f"Achievements table deletion failed (table may not exist): {e}")
                    achievements_deleted = 0
                
                # 6. Delete steam user mapping
                try:
                    result = await db.execute("DELETE FROM steam_users WHERE discord_id = ?", (discord_id,))
                    steam_deleted = result.rowcount
                    logger.debug(f"Deleted {steam_deleted} steam user mappings for user {discord_id}")
                except Exception as e:
                    logger.debug(f"Steam users table deletion failed (table may not exist): {e}")
                    steam_deleted = 0
                
                # 7. Delete user progress checkpoint
                try:
                    result = await db.execute("DELETE FROM user_progress_checkpoint WHERE discord_id = ?", (discord_id,))
                    checkpoint_deleted = result.rowcount
                    logger.debug(f"Deleted {checkpoint_deleted} progress checkpoint records for user {discord_id}")
                except Exception as e:
                    logger.debug(f"Progress checkpoint deletion failed (table may not exist): {e}")
                    checkpoint_deleted = 0
                
                # 8. Delete manga challenges (user_id column)
                try:
                    result = await db.execute("DELETE FROM manga_challenges WHERE user_id = ?", (discord_id,))
                    manga_challenges_deleted = result.rowcount
                    logger.debug(f"Deleted {manga_challenges_deleted} manga challenges for user {discord_id}")
                except Exception as e:
                    logger.debug(f"Manga challenges deletion failed (table may not exist): {e}")
                    manga_challenges_deleted = 0
                
                # 9. Delete user progress (user_id column)
                try:
                    result = await db.execute("DELETE FROM user_progress WHERE user_id = ?", (discord_id,))
                    user_progress_deleted = result.rowcount
                    logger.debug(f"Deleted {user_progress_deleted} user progress records for user {discord_id}")
                except Exception as e:
                    logger.debug(f"User progress deletion failed (table may not exist): {e}")
                    user_progress_deleted = 0
                
                # 6. Finally, delete from users table
                result = await db.execute("DELETE FROM users WHERE discord_id = ?", (discord_id,))
                user_deleted = result.rowcount
                
                if user_deleted == 0:
                    logger.error(f"Failed to delete user {discord_id} from users table")
                    await db.execute("ROLLBACK")
                    return False
                
                # Commit the transaction
                await db.commit()
                
                # Log summary of deletion
                logger.info(f"✅ Successfully removed user: {username} (Discord ID: {discord_id})")
                logger.info(f"   Deleted records: manga_progress={progress_deleted}, stats={stats_deleted}, "
                           f"cached_stats={cached_deleted}, votes={votes_deleted}, achievements={achievements_deleted}, "
                           f"steam={steam_deleted}, checkpoint={checkpoint_deleted}, "
                           f"manga_challenges={manga_challenges_deleted}, user_progress={user_progress_deleted}")
                
                return True
                
            except Exception as e:
                # Rollback on any error
                await db.execute("ROLLBACK")
                logger.error(f"Failed to delete user data, transaction rolled back: {e}")
                raise
        
    except ValueError as validation_error:
        logger.error(f"Validation error removing user: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error removing user {discord_id}: {e}", exc_info=True)
        raise

async def check_user_related_records(discord_id: int):
    """Check for related records before user deletion (for debugging)."""
    logger.debug(f"Checking related records for user {discord_id}")
    
    try:
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as db:
            related_counts = {}
            
            # Check each table that might reference the user
            tables_to_check = [
                ("user_manga_progress", "discord_id"),
                ("user_stats", "discord_id"),
                ("cached_stats", "discord_id"),
                ("manga_recommendations_votes", "voter_id"),
                ("achievements", "discord_id"),
                ("steam_users", "discord_id"),
                ("user_progress_checkpoint", "discord_id"),
                ("manga_challenges", "user_id"),
                ("user_progress", "user_id")
            ]
            
            for table_name, column_name in tables_to_check:
                try:
                    cursor = await db.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = ?", (discord_id,))
                    count = await cursor.fetchone()
                    related_counts[table_name] = count[0] if count else 0
                    await cursor.close()
                except Exception as e:
                    logger.debug(f"Could not check table {table_name}: {e}")
                    related_counts[table_name] = "ERROR"
            
            logger.debug(f"Related records for user {discord_id}: {related_counts}")
            return related_counts
            
    except Exception as e:
        logger.error(f"Error checking related records for user {discord_id}: {e}")
        return {}

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
    async with aiosqlite.connect(DB_PATH) as db:
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
# INVITE TRACKER TABLES
# ------------------------------------------------------
async def init_invite_tracker_tables():
    """Initialize all invite tracker tables in the main database"""
    logger.info("Initializing invite tracker tables")
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Invites table - tracks all invites
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invites (
                    invite_code TEXT PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    inviter_id INTEGER NOT NULL,
                    inviter_name TEXT NOT NULL,
                    channel_id INTEGER,
                    max_uses INTEGER,
                    uses INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Invite uses table - tracks who used which invite
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invite_uses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    invite_code TEXT NOT NULL,
                    inviter_id INTEGER NOT NULL,
                    inviter_name TEXT NOT NULL,
                    joiner_id INTEGER NOT NULL,
                    joiner_name TEXT NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (invite_code) REFERENCES invites (invite_code)
                )
            """)
            
            # Recruitment stats table - tracks total recruits per user
            await db.execute("""
                CREATE TABLE IF NOT EXISTS recruitment_stats (
                    user_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    total_recruits INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Leave tracking table - tracks when users leave
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_leaves (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    left_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    was_invited_by INTEGER,
                    days_in_server INTEGER DEFAULT 0
                )
            """)
            
            # Invite tracker settings - stores channel configuration
            await db.execute("""
                CREATE TABLE IF NOT EXISTS invite_tracker_settings (
                    guild_id INTEGER PRIMARY KEY,
                    announcement_channel_id INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info("✅ Invite tracker tables initialized successfully")
    
    except Exception as e:
        logger.error(f"❌ Failed to initialize invite tracker tables: {e}", exc_info=True)
        raise

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
        ("Invite Tracker", init_invite_tracker_tables),
        ("Steam Users", init_steam_users_table),
        ("Challenge Manga", init_challenge_manga_table),
    ]
    
    start_time = time.time()
    success_count = 0
    failure_count = 0
    
    try:
        # Verify database connectivity first
        logger.info("Verifying database connectivity...")
        async with aiosqlite.connect(DB_PATH, timeout=DB_TIMEOUT) as test_db:
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


# ------------------------------------------------------
# MULTI-GUILD HELPER FUNCTIONS
# ------------------------------------------------------

async def get_user_progress_guild_aware(discord_id: int, guild_id: int):
    """Get user challenge progress for a specific guild."""
    logger.debug(f"Getting progress for user {discord_id} in guild {guild_id}")
    
    try:
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        
        query = """
            SELECT up.*, gc.title as challenge_title
            FROM user_progress up
            LEFT JOIN global_challenges gc ON up.challenge_manga_id = gc.challenge_id
            WHERE up.user_id = ? AND up.guild_id = ?
        """
        
        progress = await execute_db_operation(
            f"get user progress for {discord_id} in guild {guild_id}",
            query,
            (discord_id, guild_id),
            fetch_type='all'
        )
        
        if progress:
            logger.debug(f"✅ Found {len(progress)} progress records for user {discord_id} in guild {guild_id}")
        else:
            logger.debug(f"No progress found for user {discord_id} in guild {guild_id}")
        
        return progress
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting user progress: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting user progress for {discord_id} in guild {guild_id}: {e}", exc_info=True)
        raise


async def get_guild_leaderboard(guild_id: int, limit: int = 10):
    """Get leaderboard for a specific guild."""
    logger.debug(f"Getting leaderboard for guild {guild_id} (limit: {limit})")
    
    try:
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError(f"Invalid limit: {limit}")
        
        query = """
            SELECT u.username, 
                   COUNT(up.id) as completed_challenges,
                   SUM(CASE WHEN up.status = 'completed' THEN 1 ELSE 0 END) as total_points
            FROM users u
            LEFT JOIN user_progress up ON u.discord_id = up.user_id AND u.guild_id = up.guild_id
            WHERE u.guild_id = ?
            GROUP BY u.discord_id, u.username
            ORDER BY total_points DESC, completed_challenges DESC
            LIMIT ?
        """
        
        leaderboard = await execute_db_operation(
            f"get leaderboard for guild {guild_id}",
            query,
            (guild_id, limit),
            fetch_type='all'
        )
        
        if leaderboard:
            logger.debug(f"✅ Found {len(leaderboard)} users in leaderboard for guild {guild_id}")
        else:
            logger.debug(f"No users found in leaderboard for guild {guild_id}")
        
        return leaderboard
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting guild leaderboard: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting leaderboard for guild {guild_id}: {e}", exc_info=True)
        raise


async def get_user_achievements_guild_aware(discord_id: int, guild_id: int):
    """Get user achievements for a specific guild."""
    logger.debug(f"Getting achievements for user {discord_id} in guild {guild_id}")
    
    try:
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        
        query = """
            SELECT achievement, timestamp
            FROM achievements
            WHERE discord_id = ? AND guild_id = ?
            ORDER BY timestamp DESC
        """
        
        achievements = await execute_db_operation(
            f"get achievements for user {discord_id} in guild {guild_id}",
            query,
            (discord_id, guild_id),
            fetch_type='all'
        )
        
        if achievements:
            logger.debug(f"✅ Found {len(achievements)} achievements for user {discord_id} in guild {guild_id}")
        else:
            logger.debug(f"No achievements found for user {discord_id} in guild {guild_id}")
        
        return achievements
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting user achievements: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting achievements for {discord_id} in guild {guild_id}: {e}", exc_info=True)
        raise


async def get_user_manga_progress_guild_aware(discord_id: int, guild_id: int, manga_id: int = None):
    """Get user manga progress for a specific guild."""
    logger.debug(f"Getting manga progress for user {discord_id} in guild {guild_id}")
    
    try:
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        
        if manga_id:
            query = """
                SELECT * FROM user_manga_progress
                WHERE discord_id = ? AND guild_id = ? AND manga_id = ?
            """
            params = (discord_id, guild_id, manga_id)
            fetch_type = 'one'
        else:
            query = """
                SELECT * FROM user_manga_progress
                WHERE discord_id = ? AND guild_id = ?
                ORDER BY updated_at DESC
            """
            params = (discord_id, guild_id)
            fetch_type = 'all'
        
        progress = await execute_db_operation(
            f"get manga progress for user {discord_id} in guild {guild_id}",
            query,
            params,
            fetch_type=fetch_type
        )
        
        if progress:
            if manga_id:
                logger.debug(f"✅ Found manga progress for user {discord_id}, manga {manga_id} in guild {guild_id}")
            else:
                logger.debug(f"✅ Found {len(progress)} manga progress records for user {discord_id} in guild {guild_id}")
        else:
            logger.debug(f"No manga progress found for user {discord_id} in guild {guild_id}")
        
        return progress
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting manga progress: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting manga progress for {discord_id} in guild {guild_id}: {e}", exc_info=True)
        raise


async def register_user_guild_aware(discord_id: int, guild_id: int, username: str, anilist_username: str = None, anilist_id: int = None):
    """Register a user in a specific guild (alias for add_user_guild_aware)."""
    logger.info(f"Registering user {username} (ID: {discord_id}) in guild {guild_id}")
    
    try:
        await add_user_guild_aware(discord_id, guild_id, username, anilist_username, anilist_id)
        logger.info(f"✅ Successfully registered user {username} in guild {guild_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to register user {discord_id} in guild {guild_id}: {e}")
        raise


async def is_user_registered_in_guild(discord_id: int, guild_id: int):
    """Check if a user is registered in a specific guild."""
    logger.debug(f"Checking if user {discord_id} is registered in guild {guild_id}")
    
    try:
        user = await get_user_guild_aware(discord_id, guild_id)
        is_registered = user is not None
        
        logger.debug(f"User {discord_id} registration status in guild {guild_id}: {is_registered}")
        return is_registered
        
    except Exception as e:
        logger.error(f"❌ Error checking user registration for {discord_id} in guild {guild_id}: {e}")
        return False


async def get_guild_user_count(guild_id: int):
    """Get the number of registered users in a guild."""
    logger.debug(f"Getting user count for guild {guild_id}")
    
    try:
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        
        query = "SELECT COUNT(*) FROM users WHERE guild_id = ?"
        result = await execute_db_operation(
            f"get user count for guild {guild_id}",
            query,
            (guild_id,),
            fetch_type='one'
        )
        
        count = result[0] if result else 0
        logger.debug(f"✅ Found {count} users in guild {guild_id}")
        return count
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting guild user count: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error getting user count for guild {guild_id}: {e}", exc_info=True)
        raise


# ------------------------------------------------------
# GUILD-AWARE USER FUNCTIONS
# ------------------------------------------------------

async def save_user_guild_aware(discord_id: int, guild_id: int, username: str):
    """Save or update user with guild context - guild-aware version of save_user."""
    logger.info(f"Saving user (guild-aware): {username} (Discord ID: {discord_id}, Guild ID: {guild_id})")
    
    try:
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        if not isinstance(username, str) or not username.strip():
            raise ValueError(f"Invalid username: {username}")
        
        # Check if user already exists in this guild
        existing_user = await get_user_guild_aware(discord_id, guild_id)
        operation_type = "update" if existing_user else "insert"
        
        query = """
            INSERT INTO users (discord_id, guild_id, username, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(discord_id, guild_id) DO UPDATE SET 
                username=excluded.username,
                updated_at=CURRENT_TIMESTAMP
        """
        
        await execute_db_operation(
            f"save user {username} in guild {guild_id} ({operation_type})",
            query,
            (discord_id, guild_id, username.strip())
        )
        
        logger.info(f"✅ Successfully saved user: {username} in guild {guild_id} ({operation_type})")
        
    except ValueError as validation_error:
        logger.error(f"Validation error saving user: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error saving user {discord_id} in guild {guild_id}: {e}", exc_info=True)
        raise


async def upsert_user_stats_guild_aware(
    discord_id: int,
    guild_id: int,
    username: str,
    total_manga: int,
    total_anime: int,
    avg_manga_score: float,
    avg_anime_score: float,
    total_chapters: int = 0,
    total_episodes: int = 0 
):
    """Upsert user stats with guild context - note: user_stats table doesn't have guild_id yet, 
    so this function currently acts as a wrapper for backward compatibility.
    TODO: Add guild_id column to user_stats table for full guild isolation."""
    logger.info(f"Upserting stats (guild-aware) for user {username} (Discord ID: {discord_id}, Guild ID: {guild_id})")
    
    # For now, call the original function since user_stats doesn't have guild_id
    # This maintains functionality while we transition
    logger.warning(f"user_stats table doesn't have guild_id column yet - using global stats for user {discord_id}")
    
    return await upsert_user_stats(
        discord_id=discord_id,
        username=username,
        total_manga=total_manga,
        total_anime=total_anime,
        avg_manga_score=avg_manga_score,
        avg_anime_score=avg_anime_score,
        total_chapters=total_chapters,
        total_episodes=total_episodes
    )


async def get_guild_leaderboard_data(guild_id: int, leaderboard_type: str = "manga"):
    """Get leaderboard data for a specific guild"""
    logger.info(f"Getting {leaderboard_type} leaderboard data for guild {guild_id}")
    
    try:
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        if leaderboard_type not in ["manga", "anime", "combined"]:
            raise ValueError(f"Invalid leaderboard_type: {leaderboard_type}")
        
        query = """
            SELECT u.anilist_username, us.total_manga, us.total_anime, 
                   us.total_chapters, us.total_episodes, us.avg_manga_score, us.avg_anime_score
            FROM users u 
            JOIN user_stats us ON u.discord_id = us.discord_id
            WHERE u.guild_id = ? AND u.anilist_username IS NOT NULL
        """
        
        results = await execute_db_operation(
            f"get {leaderboard_type} leaderboard for guild {guild_id}",
            query,
            (guild_id,),
            fetch_type='all'
        )
        
        if not results:
            logger.info(f"No leaderboard data found for guild {guild_id}")
            return []
        
        # Filter and sort based on leaderboard type
        leaderboard_data = []
        for row in results:
            username, total_manga, total_anime, total_chapters, total_episodes, avg_manga_score, avg_anime_score = row
            
            if leaderboard_type == "manga":
                score = total_manga or 0
                secondary_score = total_chapters or 0
            elif leaderboard_type == "anime":
                score = total_anime or 0
                secondary_score = total_episodes or 0
            else:  # combined
                score = (total_manga or 0) + (total_anime or 0)
                secondary_score = (total_chapters or 0) + (total_episodes or 0)
            
            leaderboard_data.append({
                'username': username,
                'total_manga': total_manga or 0,
                'total_anime': total_anime or 0,
                'total_chapters': total_chapters or 0,
                'total_episodes': total_episodes or 0,
                'avg_manga_score': avg_manga_score or 0.0,
                'avg_anime_score': avg_anime_score or 0.0,
                'score': score,
                'secondary_score': secondary_score
            })
        
        # Sort by primary score, then secondary score
        leaderboard_data.sort(key=lambda x: (x['score'], x['secondary_score']), reverse=True)
        
        logger.info(f"✅ Retrieved {len(leaderboard_data)} entries for {leaderboard_type} leaderboard in guild {guild_id}")
        return leaderboard_data
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting guild leaderboard: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error getting leaderboard data for guild {guild_id}: {e}", exc_info=True)
        raise


async def get_all_users_guild_aware(guild_id: int):
    """Get all users for a specific guild - guild-aware version of get_all_users"""
    logger.info(f"Getting all users for guild {guild_id}")
    
    try:
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        
        query = "SELECT * FROM users WHERE guild_id = ?"
        users = await execute_db_operation(
            f"get all users for guild {guild_id}",
            query,
            (guild_id,),
            fetch_type='all'
        )
        
        logger.info(f"✅ Retrieved {len(users) if users else 0} users for guild {guild_id}")
        return users or []
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting guild users: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error getting users for guild {guild_id}: {e}", exc_info=True)
        raise


async def set_user_manga_progress_guild_aware(discord_id: int, guild_id: int, manga_id: int, chapter: int, rating: float):
    """Set user manga progress with guild context - guild-aware version."""
    logger.info(f"Setting manga progress (guild-aware) for user {discord_id}, manga {manga_id}, guild {guild_id}")
    
    try:
        # Validate input
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        if not isinstance(manga_id, int) or manga_id <= 0:
            raise ValueError(f"Invalid manga_id: {manga_id}")
        if not isinstance(chapter, int) or chapter < 0:
            raise ValueError(f"Invalid chapter: {chapter}")
        if not isinstance(rating, (int, float)) or not (0 <= rating <= 10):
            logger.warning(f"Invalid rating {rating}, clamping to 0-10 range")
            rating = max(0, min(10, float(rating)))
        
        logger.debug(f"Progress data - Chapter: {chapter}, Rating: {rating}")
        
        query = """
            INSERT INTO user_manga_progress (discord_id, guild_id, manga_id, current_chapter, rating, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(discord_id, guild_id, manga_id) DO UPDATE SET
                current_chapter=excluded.current_chapter,
                rating=excluded.rating,
                updated_at=CURRENT_TIMESTAMP
        """
        
        await execute_db_operation(
            f"set manga progress for user {discord_id} in guild {guild_id}",
            query,
            (discord_id, guild_id, manga_id, chapter, rating)
        )
        
        logger.info(f"✅ Set manga {manga_id} progress for user {discord_id} in guild {guild_id}: Chapter {chapter}, Rating {rating}")
        
    except ValueError as validation_error:
        logger.error(f"Validation error setting manga progress: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error setting manga progress for user {discord_id} in guild {guild_id}: {e}", exc_info=True)
        raise


async def upsert_user_manga_progress_guild_aware(discord_id, guild_id, manga_id, title, chapters, points, status, repeat=0, started_at=None):
    """Upsert user manga progress with guild context - guild-aware version."""
    logger.info(f"Upserting manga progress (guild-aware) for user {discord_id}, manga {manga_id}, guild {guild_id}")
    
    try:
        # Validate input
        if not isinstance(discord_id, int) or discord_id <= 0:
            raise ValueError(f"Invalid discord_id: {discord_id}")
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        if not isinstance(manga_id, int) or manga_id <= 0:
            raise ValueError(f"Invalid manga_id: {manga_id}")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"Invalid title: {title}")
        if not isinstance(chapters, int) or chapters < 0:
            raise ValueError(f"Invalid chapters: {chapters}")
        if not isinstance(points, (int, float)) or points < 0:
            raise ValueError(f"Invalid points: {points}")
        if not isinstance(status, str) or not status.strip():
            raise ValueError(f"Invalid status: {status}")
        if not isinstance(repeat, int) or repeat < 0:
            repeat = 0
        
        logger.debug(f"Manga progress data - Title: {title}, Chapters: {chapters}, Points: {points}, Status: {status}")
        
        query = """
            INSERT INTO user_manga_progress (
                discord_id, guild_id, manga_id, current_chapter, title, 
                points, status, repeat, started_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(discord_id, guild_id, manga_id) DO UPDATE SET
                current_chapter=excluded.current_chapter,
                title=excluded.title,
                points=excluded.points,
                status=excluded.status,
                repeat=excluded.repeat,
                started_at=COALESCE(excluded.started_at, user_manga_progress.started_at),
                updated_at=CURRENT_TIMESTAMP
        """
        
        await execute_db_operation(
            f"upsert manga progress for user {discord_id} in guild {guild_id}",
            query,
            (discord_id, guild_id, manga_id, chapters, title, points, status, repeat, started_at)
        )
        
        logger.info(f"✅ Upserted manga {manga_id} progress for user {discord_id} in guild {guild_id}: {chapters} chapters, {points} points")
        
    except ValueError as validation_error:
        logger.error(f"Validation error upserting manga progress: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error upserting manga progress for user {discord_id} in guild {guild_id}: {e}", exc_info=True)
        raise


async def get_guild_challenge_leaderboard_data(guild_id: int):
    """Get challenge leaderboard data for a specific guild"""
    logger.info(f"Getting challenge leaderboard data for guild {guild_id}")
    
    try:
        if not isinstance(guild_id, int) or guild_id <= 0:
            raise ValueError(f"Invalid guild_id: {guild_id}")
        
        query = """
            SELECT u.discord_id, COALESCE(SUM(ump.points), 0) AS total_points
            FROM users u
            LEFT JOIN user_manga_progress ump ON u.discord_id = ump.discord_id AND u.guild_id = ump.guild_id
            WHERE u.guild_id = ?
            GROUP BY u.discord_id
            HAVING total_points > 0
            ORDER BY total_points DESC
        """
        
        leaderboard_data = await execute_db_operation(
            f"get challenge leaderboard for guild {guild_id}",
            query,
            (guild_id,),
            fetch_type='all'
        )
        
        logger.info(f"✅ Retrieved {len(leaderboard_data) if leaderboard_data else 0} challenge leaderboard entries for guild {guild_id}")
        return leaderboard_data or []
        
    except ValueError as validation_error:
        logger.error(f"Validation error getting guild challenge leaderboard: {validation_error}")
        raise
    except Exception as e:
        logger.error(f"❌ Error getting challenge leaderboard for guild {guild_id}: {e}", exc_info=True)
        raise