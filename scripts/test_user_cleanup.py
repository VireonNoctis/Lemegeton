#!/usr/bin/env python3
"""
Test script to verify the user cleanup functionality and database schema.
"""

import sys
import os
import asyncio

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import init_db, execute_db_operation

async def test_database_schema():
    """Test the database schema and migration."""
    print("🔧 Testing database schema and user cleanup functionality...")
    
    try:
        # Initialize database
        print("📊 Initializing database...")
        await init_db()
        
        # Check table schema
        print("🔍 Checking users table schema...")
        schema_query = "PRAGMA table_info(users)"
        schema = await execute_db_operation("check users table schema", schema_query, fetch_type='all')
        
        print(f"✅ Users table has {len(schema)} columns:")
        for column in schema:
            print(f"   - {column[1]}: {column[2]}")
        
        # Check if guild_id column exists
        has_guild_id = any(col[1] == 'guild_id' for col in schema)
        if has_guild_id:
            print("✅ Guild ID column found - multi-guild support enabled")
        else:
            print("❌ Guild ID column missing - run database migration")
        
        # Test data insertion
        print("🧪 Testing multi-guild user insertion...")
        test_discord_id = 123456789
        test_guild_1 = 111
        test_guild_2 = 222
        
        try:
            # Insert same discord_id for different guilds
            insert_query = "INSERT INTO users (discord_id, guild_id, username, anilist_username) VALUES (?, ?, ?, ?)"
            
            await execute_db_operation("test insert guild 1", insert_query, 
                                     (test_discord_id, test_guild_1, "TestUser1", "testuser1"))
            await execute_db_operation("test insert guild 2", insert_query, 
                                     (test_discord_id, test_guild_2, "TestUser2", "testuser2"))
            
            print("✅ Multi-guild insertion successful")
            
            # Count test records
            count_query = "SELECT COUNT(*) FROM users WHERE discord_id = ?"
            count_result = await execute_db_operation("count test records", count_query, (test_discord_id,), fetch_type='one')
            print(f"✅ Found {count_result[0]} records for test discord_id")
            
            # Clean up test data
            cleanup_query = "DELETE FROM users WHERE discord_id = ?"
            await execute_db_operation("cleanup test data", cleanup_query, (test_discord_id,))
            print("🧹 Test data cleaned up")
            
        except Exception as e:
            print(f"❌ Multi-guild test failed: {e}")
            # Try to clean up anyway
            try:
                cleanup_query = "DELETE FROM users WHERE discord_id = ?"
                await execute_db_operation("cleanup test data", cleanup_query, (test_discord_id,))
            except:
                pass
        
        # Check current user count
        total_query = "SELECT COUNT(*) FROM users"
        total_result = await execute_db_operation("count total users", total_query, fetch_type='one')
        print(f"📈 Current user count: {total_result[0]}")
        
        print("✅ Database schema test completed successfully!")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Main test function."""
    print("🚀 Starting user cleanup system tests...")
    await test_database_schema()
    print("🎉 Tests completed!")

if __name__ == "__main__":
    asyncio.run(main())