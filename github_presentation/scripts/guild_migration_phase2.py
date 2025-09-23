#!/usr/bin/env python3
"""
Guild Migration Script - Phase 2
Add guild_id columns to remaining tables for full multi-guild support
"""

import sqlite3
import logging
import sys
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('logs/guild_migration_phase2.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = "database.db"
BACKUP_PATH = f"database_guild_migration_phase2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

def create_backup():
    """Create a backup of the database before migration"""
    try:
        import shutil
        shutil.copy2(DB_PATH, BACKUP_PATH)
        logger.info(f"✅ Database backup created: {BACKUP_PATH}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to create backup: {e}")
        return False

def migrate_user_stats():
    """Add guild_id to user_stats table"""
    logger.info("Migrating user_stats table...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if guild_id already exists
        cursor.execute("PRAGMA table_info(user_stats);")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'guild_id' in columns:
            logger.info("user_stats already has guild_id column")
            return True
        
        # Add guild_id column
        cursor.execute("ALTER TABLE user_stats ADD COLUMN guild_id INTEGER;")
        
        # Create index for better performance
        cursor.execute("CREATE INDEX idx_user_stats_guild_id ON user_stats(guild_id);")
        
        # Update existing records with a default guild_id (you'll need to set this)
        # For now, we'll leave them NULL and they'll be updated when users interact
        logger.info("✅ Added guild_id column to user_stats")
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to migrate user_stats: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def migrate_challenges_tables():
    """Add guild_id to challenge-related tables"""
    challenge_tables = [
        'global_challenges',
        'challenge_rules', 
        'manga_challenges',
        'challenge_manga'
    ]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        for table in challenge_tables:
            logger.info(f"Migrating {table} table...")
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            if not cursor.fetchone():
                logger.warning(f"Table {table} not found, skipping")
                continue
            
            # Check if guild_id already exists
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'guild_id' in columns:
                logger.info(f"{table} already has guild_id column")
                continue
                
            # Add guild_id column
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN guild_id INTEGER;")
            
            # Create index
            cursor.execute(f"CREATE INDEX idx_{table}_guild_id ON {table}(guild_id);")
            
            logger.info(f"✅ Added guild_id column to {table}")
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to migrate challenge tables: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def migrate_other_tables():
    """Add guild_id to remaining tables"""
    other_tables = [
        'user_progress_checkpoint',
        'manga_recommendations_votes'
    ]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        for table in other_tables:
            logger.info(f"Migrating {table} table...")
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
            if not cursor.fetchone():
                logger.warning(f"Table {table} not found, skipping")
                continue
            
            # Check if guild_id already exists
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'guild_id' in columns:
                logger.info(f"{table} already has guild_id column")
                continue
                
            # Add guild_id column
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN guild_id INTEGER;")
            
            # Create index
            cursor.execute(f"CREATE INDEX idx_{table}_guild_id ON {table}(guild_id);")
            
            logger.info(f"✅ Added guild_id column to {table}")
        
        conn.commit()
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to migrate other tables: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def verify_migration():
    """Verify that all tables now have guild_id columns"""
    logger.info("Verifying migration...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get all table names (excluding sqlite_sequence)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence';")
        tables = [row[0] for row in cursor.fetchall()]
        
        guild_ready_count = 0
        total_tables = len(tables)
        
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'guild_id' in columns:
                guild_ready_count += 1
        
        logger.info(f"Migration verification: {guild_ready_count}/{total_tables} tables are guild-ready")
        
        if guild_ready_count == total_tables:
            logger.info("🎉 ALL TABLES ARE NOW GUILD-READY!")
            return True
        else:
            remaining = total_tables - guild_ready_count
            logger.warning(f"⚠️ {remaining} tables still need migration")
            return False
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False
    finally:
        conn.close()

def main():
    """Main migration process"""
    logger.info("=" * 60)
    logger.info("STARTING GUILD MIGRATION - PHASE 2")
    logger.info("=" * 60)
    
    # Create backup
    if not create_backup():
        logger.error("Cannot proceed without backup")
        return False
    
    # Run migrations
    success = True
    
    if not migrate_user_stats():
        success = False
    
    if not migrate_challenges_tables():
        success = False
        
    if not migrate_other_tables():
        success = False
    
    # Verify results
    verify_migration()
    
    if success:
        logger.info("🎉 Guild migration Phase 2 completed successfully!")
        logger.info(f"Backup available at: {BACKUP_PATH}")
    else:
        logger.error("❌ Migration completed with errors")
        logger.info(f"Database backup available for recovery: {BACKUP_PATH}")
    
    return success

if __name__ == "__main__":
    main()