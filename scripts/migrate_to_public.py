#!/usr/bin/env python3
"""
Multi-Guild Migration Script for Lemegeton Bot
==============================================

This script migrates your single-guild bot to support multiple Discord servers.

IMPORTANT: This script makes irreversible changes to your database.
           Make sure to backup your database.db file before running!

Usage:
    python migrate_to_public.py --backup --current-guild-id YOUR_GUILD_ID
"""

import asyncio
import aiosqlite
import shutil
import argparse
from datetime import datetime
import os
import sys


class MultiGuildMigrator:
    def __init__(self, db_path: str = "database.db", current_guild_id: int = None):
        self.db_path = db_path
        self.current_guild_id = current_guild_id
        self.backup_path = None
        
    async def create_backup(self):
        """Create a timestamped backup of the current database"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.backup_path = f"database_backup_{timestamp}.db"
        
        if os.path.exists(self.db_path):
            shutil.copy2(self.db_path, self.backup_path)
            print(f"✅ Backup created: {self.backup_path}")
            return True
        else:
            print(f"❌ Database file not found: {self.db_path}")
            return False
    
    async def analyze_current_structure(self):
        """Analyze the current database structure"""
        print("\n📊 Analyzing current database structure...")
        
        async with aiosqlite.connect(self.db_path) as db:
            # Get all tables
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()
            
            guild_aware_tables = []
            needs_migration_tables = []
            
            for (table_name,) in tables:
                if table_name == 'sqlite_sequence':
                    continue
                    
                # Check if table has guild_id column
                cursor = await db.execute(f"PRAGMA table_info({table_name})")
                columns = await cursor.fetchall()
                
                has_guild_id = any(col[1] == 'guild_id' for col in columns)
                
                if has_guild_id:
                    guild_aware_tables.append(table_name)
                else:
                    needs_migration_tables.append(table_name)
            
            print(f"✅ Guild-aware tables ({len(guild_aware_tables)}): {', '.join(guild_aware_tables)}")
            print(f"❌ Tables needing migration ({len(needs_migration_tables)}): {', '.join(needs_migration_tables)}")
            
            return needs_migration_tables
    
    async def migrate_users_table(self):
        """Migrate the users table to support multiple guilds"""
        print("\n🔄 Migrating users table...")
        
        async with aiosqlite.connect(self.db_path) as db:
            # Check if users table exists and needs migration
            cursor = await db.execute("PRAGMA table_info(users)")
            columns = await cursor.fetchall()
            
            has_guild_id = any(col[1] == 'guild_id' for col in columns)
            
            if has_guild_id:
                print("✅ Users table already has guild_id column")
                return
            
            # Create new users table with guild support
            await db.execute("""
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
            """)
            
            # Migrate existing data
            if self.current_guild_id:
                await db.execute("""
                    INSERT INTO users_new (discord_id, guild_id, username, anilist_username, anilist_id)
                    SELECT discord_id, ?, username, anilist_username, anilist_id
                    FROM users
                """, (self.current_guild_id,))
            
            # Replace old table
            await db.execute("DROP TABLE users")
            await db.execute("ALTER TABLE users_new RENAME TO users")
            await db.commit()
            
            print("✅ Users table migrated successfully")
    
    async def migrate_table_with_guild_id(self, table_name: str):
        """Add guild_id column to a table and migrate existing data"""
        print(f"🔄 Migrating {table_name} table...")
        
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Check if table exists
                cursor = await db.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                exists = await cursor.fetchone()
                
                if not exists:
                    print(f"⚠️ Table {table_name} doesn't exist, skipping")
                    return
                
                # Check if already has guild_id
                cursor = await db.execute(f"PRAGMA table_info({table_name})")
                columns = await cursor.fetchall()
                
                has_guild_id = any(col[1] == 'guild_id' for col in columns)
                
                if has_guild_id:
                    print(f"✅ {table_name} already has guild_id column")
                    return
                
                # Add guild_id column
                await db.execute(f"ALTER TABLE {table_name} ADD COLUMN guild_id INTEGER")
                
                # Update existing records with current guild ID
                if self.current_guild_id:
                    await db.execute(f"UPDATE {table_name} SET guild_id = ? WHERE guild_id IS NULL", (self.current_guild_id,))
                
                await db.commit()
                print(f"✅ {table_name} migrated successfully")
                
            except Exception as e:
                print(f"❌ Error migrating {table_name}: {e}")
    
    async def create_guild_indexes(self):
        """Create indexes for better performance with guild_id queries"""
        print("\n🗂️ Creating guild-specific indexes...")
        
        indexes = [
            ("idx_users_guild_discord", "users", "guild_id, discord_id"),
            ("idx_user_progress_guild", "user_progress", "guild_id"),
            ("idx_achievements_guild", "achievements", "guild_id"),
            ("idx_cached_stats_guild", "cached_stats", "guild_id"),
            ("idx_user_manga_progress_guild", "user_manga_progress", "guild_id"),
        ]
        
        async with aiosqlite.connect(self.db_path) as db:
            for index_name, table, columns in indexes:
                try:
                    await db.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns})")
                    print(f"✅ Created index: {index_name}")
                except Exception as e:
                    print(f"⚠️ Could not create index {index_name}: {e}")
            
            await db.commit()
    
    async def validate_migration(self):
        """Validate that the migration was successful"""
        print("\n✅ Validating migration...")
        
        async with aiosqlite.connect(self.db_path) as db:
            # Check that all important tables have guild_id
            important_tables = ['users', 'user_progress', 'achievements', 'cached_stats']
            
            for table in important_tables:
                try:
                    cursor = await db.execute(f"PRAGMA table_info({table})")
                    columns = await cursor.fetchall()
                    
                    has_guild_id = any(col[1] == 'guild_id' for col in columns)
                    
                    if has_guild_id:
                        # Check data count
                        cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
                        count = await cursor.fetchone()
                        print(f"✅ {table}: has guild_id, {count[0]} records")
                    else:
                        print(f"❌ {table}: missing guild_id column")
                
                except Exception as e:
                    print(f"⚠️ Could not validate {table}: {e}")
    
    async def run_migration(self, create_backup=True):
        """Run the complete migration process"""
        print("🚀 Starting Multi-Guild Migration")
        print("=" * 50)
        
        if not self.current_guild_id:
            print("❌ Current guild ID not provided. Use --current-guild-id parameter")
            return False
        
        # Create backup
        if create_backup:
            if not await self.create_backup():
                return False
        
        # Analyze current structure
        tables_to_migrate = await self.analyze_current_structure()
        
        # Migrate critical tables
        await self.migrate_users_table()
        
        # Migrate other tables that need guild_id
        important_tables = [
            'user_manga_progress', 'achievements', 'cached_stats', 
            'user_progress', 'steam_users', 'user_leaves',
            'challenges', 'wrapped_stats'
        ]
        
        for table in important_tables:
            if table in tables_to_migrate:
                await self.migrate_table_with_guild_id(table)
        
        # Create indexes for performance
        await self.create_guild_indexes()
        
        # Validate migration
        await self.validate_migration()
        
        print("\n🎉 Migration completed successfully!")
        print(f"📁 Backup saved as: {self.backup_path}")
        print("\n⚠️ IMPORTANT: Update your bot code to use guild_id in all database queries")
        
        return True


async def main():
    parser = argparse.ArgumentParser(description='Migrate Lemegeton bot to multi-guild architecture')
    parser.add_argument('--current-guild-id', type=int, required=True,
                        help='Your current Discord server ID (where existing data should be assigned)')
    parser.add_argument('--db-path', default='database.db',
                        help='Path to database file (default: database.db)')
    parser.add_argument('--no-backup', action='store_true',
                        help='Skip creating backup (NOT RECOMMENDED)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Analyze only, don\'t make changes')
    parser.add_argument('--yes', action='store_true',
                        help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    migrator = MultiGuildMigrator(args.db_path, args.current_guild_id)
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        await migrator.analyze_current_structure()
        return
    
    # Confirm with user (unless --yes flag is used)
    if not args.yes:
        print(f"🔄 About to migrate database: {args.db_path}")
        print(f"📍 Current guild ID: {args.current_guild_id}")
        print(f"💾 Create backup: {'No' if args.no_backup else 'Yes'}")
        
        confirm = input("\n⚠️ This will make irreversible changes. Continue? (y/N): ")
        if confirm.lower() != 'y':
            print("❌ Migration cancelled")
            return
    
    success = await migrator.run_migration(create_backup=not args.no_backup)
    
    if success:
        print("\n📝 Next steps:")
        print("1. Update your bot code to include guild_id in database queries")
        print("2. Test the bot with multiple servers")
        print("3. Monitor database performance")
        print("4. Consider setting up proper backups for production")
    else:
        print("❌ Migration failed. Check the output above for errors.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n❌ Migration interrupted by user")
    except Exception as e:
        print(f"❌ Migration failed with error: {e}")
        sys.exit(1)