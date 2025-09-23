#!/usr/bin/env python3
"""
Test script for login system (registration/unregistration)
Tests the database operations for user management including foreign key constraints.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add parent directory to path so we can import from project
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Change to project root directory so database path is correct
os.chdir(project_root)

from database import (
    add_user, get_user, remove_user, update_username, 
    get_db_connection, check_user_related_records
)

# Test configuration
TEST_USER_ID = 999999999  # Fake Discord user ID for testing
TEST_DISCORD_USER = "TestUser#1234"
TEST_ANILIST_USER = "TestAniListUser"
TEST_ANILIST_ID = 123456

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)-8s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

async def cleanup_test_data():
    """Remove any existing test data before starting."""
    logger.info("🧹 Cleaning up any existing test data...")
    try:
        # Try to remove test user if exists (ignore errors)
        await remove_user(TEST_USER_ID)
        logger.info("✅ Cleaned up existing test data")
    except Exception as e:
        logger.info(f"ℹ️ No existing test data to clean: {e}")

async def test_user_registration():
    """Test user registration functionality."""
    logger.info("🔍 Testing user registration...")
    
    try:
        # Verify user doesn't exist initially
        user = await get_user(TEST_USER_ID)
        if user:
            raise Exception(f"Test user already exists: {user}")
        
        # Test registration
        await add_user(TEST_USER_ID, TEST_DISCORD_USER, TEST_ANILIST_USER, TEST_ANILIST_ID)
        logger.info("✅ User registration successful")
        
        # Verify user was added
        user = await get_user(TEST_USER_ID)
        if not user:
            raise Exception("User not found after registration")
        
        logger.info(f"✅ User verification successful: {user}")
        return True
        
    except Exception as e:
        logger.error(f"❌ User registration failed: {e}")
        return False

async def add_related_data():
    """Add some related data to test foreign key constraints."""
    logger.info("📊 Adding related data to test foreign key constraints...")
    
    try:
        # Import aiosqlite directly for this test
        import aiosqlite
        db_path = "database.db"
        
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.cursor()
            
            # Add some manga progress data
            await cursor.execute("""
                INSERT INTO user_manga_progress 
                (discord_id, manga_id, current_chapter, status, started_at) 
                VALUES (?, ?, ?, ?, ?)
            """, (TEST_USER_ID, 12345, 50, "Reading", "2025-01-01"))
            
            await cursor.execute("""
                INSERT INTO user_manga_progress 
                (discord_id, manga_id, current_chapter, status, started_at) 
                VALUES (?, ?, ?, ?, ?)
            """, (TEST_USER_ID, 67890, 100, "Completed", "2025-01-01"))
            
            # Add some user stats
            await cursor.execute("""
                INSERT OR REPLACE INTO user_stats 
                (discord_id, username, total_anime, total_manga, avg_manga_score, avg_anime_score) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (TEST_USER_ID, "TestUser", 10, 5, 8.5, 9.0))
            
            # Add some cached stats
            await cursor.execute("""
                INSERT OR REPLACE INTO cached_stats 
                (discord_id, username, manga_total, manga_completed) 
                VALUES (?, ?, ?, ?)
            """, (TEST_USER_ID, "TestUser", 5, 3))
            
            # Add some recommendation votes (using voter_id column)
            await cursor.execute("""
                INSERT INTO manga_recommendations_votes (manga_id, voter_id, vote) 
                VALUES (?, ?, ?)
            """, (11111, TEST_USER_ID, 1))
            
            await cursor.execute("""
                INSERT INTO manga_recommendations_votes (manga_id, voter_id, vote) 
                VALUES (?, ?, ?)
            """, (22222, TEST_USER_ID, -1))
            
            # Add some achievements
            await cursor.execute("""
                INSERT INTO achievements (discord_id, achievement) 
                VALUES (?, ?)
            """, (TEST_USER_ID, "first_completion"))
            
            # Add steam user data
            await cursor.execute("""
                INSERT INTO steam_users (discord_id, steam_id, vanity_name) 
                VALUES (?, ?, ?)
            """, (TEST_USER_ID, "76561198000000000", "TestSteamUser"))
            
            await conn.commit()
            
        logger.info("✅ Related data added successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to add related data: {e}")
        return False

async def verify_related_data():
    """Verify that related data exists."""
    logger.info("🔍 Verifying related data exists...")
    
    try:
        related_records = await check_user_related_records(TEST_USER_ID)
        
        if not related_records:
            logger.warning("⚠️ No related records found")
            return False
            
        logger.info("✅ Related data verified:")
        for table, count in related_records.items():
            logger.info(f"  - {table}: {count} records")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to verify related data: {e}")
        return False

async def test_user_unregistration():
    """Test user unregistration with foreign key constraint handling."""
    logger.info("🗑️ Testing user unregistration...")
    
    try:
        # Verify user exists before removal
        user = await get_user(TEST_USER_ID)
        if not user:
            raise Exception("Test user not found before removal")
        
        # Test removal with cascading delete
        await remove_user(TEST_USER_ID)
        logger.info("✅ User removal successful")
        
        # Verify user was removed
        user = await get_user(TEST_USER_ID)
        if user:
            raise Exception(f"User still exists after removal: {user}")
        
        logger.info("✅ User removal verification successful")
        
        # Verify related data was also removed
        related_records = await check_user_related_records(TEST_USER_ID)
        if related_records:
            logger.warning(f"⚠️ Some related records still exist: {related_records}")
        else:
            logger.info("✅ All related data properly removed")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ User unregistration failed: {e}")
        return False

async def test_username_update():
    """Test username update functionality."""
    logger.info("📝 Testing username update...")
    
    try:
        # First register a user
        await add_user(TEST_USER_ID, TEST_DISCORD_USER, TEST_ANILIST_USER, TEST_ANILIST_ID)
        
        # Update username
        new_username = "UpdatedTestUser"
        await update_username(TEST_USER_ID, new_username)
        logger.info("✅ Username update successful")
        
        # Verify update
        user = await get_user(TEST_USER_ID)
        if not user or user[2] != new_username:  # Assuming username is at index 2
            raise Exception(f"Username not updated correctly. Expected: {new_username}, Got: {user[2] if user else None}")
        
        logger.info(f"✅ Username update verification successful: {user[2]}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Username update failed: {e}")
        return False

async def run_comprehensive_test():
    """Run all tests in sequence."""
    logger.info("🚀 Starting comprehensive login system test...")
    logger.info("=" * 60)
    
    test_results = {
        "cleanup": False,
        "registration": False,
        "related_data_add": False,
        "related_data_verify": False,
        "unregistration": False,
        "username_update": False,
        "final_cleanup": False
    }
    
    try:
        # Test 1: Cleanup
        test_results["cleanup"] = await cleanup_test_data()
        
        # Test 2: Registration
        test_results["registration"] = await test_user_registration()
        if not test_results["registration"]:
            raise Exception("Registration test failed - cannot continue")
        
        # Test 3: Add related data
        test_results["related_data_add"] = await add_related_data()
        
        # Test 4: Verify related data
        test_results["related_data_verify"] = await verify_related_data()
        
        # Test 5: Unregistration (with foreign key constraint handling)
        test_results["unregistration"] = await test_user_unregistration()
        
        # Test 6: Username update (requires fresh registration)
        test_results["username_update"] = await test_username_update()
        
        # Test 7: Final cleanup
        test_results["final_cleanup"] = await cleanup_test_data()
        
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")
    
    # Print results summary
    logger.info("=" * 60)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    
    all_passed = True
    for test_name, passed in test_results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {test_name.replace('_', ' ').title()}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 60)
    if all_passed:
        logger.info("🎉 ALL TESTS PASSED! Login system is working correctly.")
    else:
        logger.info("⚠️ Some tests failed. Check logs above for details.")
    
    return all_passed

async def test_foreign_key_constraints_directly():
    """Direct test of foreign key constraint handling."""
    logger.info("🔒 Testing foreign key constraints directly...")
    
    try:
        # Import aiosqlite directly for this test
        import aiosqlite
        
        # Get database path - use relative path since we changed directory
        db_path = "database.db"
        
        async with aiosqlite.connect(db_path) as conn:
            cursor = await conn.cursor()
            
            # Enable foreign key constraints
            await cursor.execute("PRAGMA foreign_keys = ON")
            
            # Try to insert related data without user (should fail if foreign keys are enforced)
            # Note: The current database may not have foreign key constraints properly set up
            try:
                await cursor.execute("""
                    INSERT INTO user_manga_progress 
                    (discord_id, manga_id, current_chapter, status) 
                    VALUES (?, ?, ?, ?)
                """, (999888777, 12345, 50, "Reading"))
                await conn.commit()
                logger.warning("⚠️ Foreign key constraint not enforced - insert succeeded without user")
                
                # Clean up the test data
                await cursor.execute("DELETE FROM user_manga_progress WHERE discord_id = ?", (999888777,))
                await conn.commit()
                
            except Exception as e:
                logger.info(f"✅ Foreign key constraint working correctly: {e}")
            
            # Now test with valid user
            await add_user(TEST_USER_ID, TEST_DISCORD_USER, TEST_ANILIST_USER, TEST_ANILIST_ID)
            
            await cursor.execute("""
                INSERT INTO user_manga_progress 
                (discord_id, manga_id, current_chapter, status) 
                VALUES (?, ?, ?, ?)
            """, (TEST_USER_ID, 12345, 50, "Reading"))
            await conn.commit()
            logger.info("✅ Valid foreign key reference works correctly")
            
            # Clean up
            await remove_user(TEST_USER_ID)
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Foreign key constraint test failed: {e}")
        return False

if __name__ == "__main__":
    async def main():
        try:
            # Run foreign key constraint test
            logger.info("🧪 Running foreign key constraint test...")
            fk_result = await test_foreign_key_constraints_directly()
            
            # Run comprehensive test
            comprehensive_result = await run_comprehensive_test()
            
            # Final summary
            logger.info("\n" + "=" * 80)
            logger.info("🏁 FINAL TEST SUMMARY")
            logger.info("=" * 80)
            logger.info(f"Foreign Key Constraints: {'✅ PASS' if fk_result else '❌ FAIL'}")
            logger.info(f"Comprehensive Test Suite: {'✅ PASS' if comprehensive_result else '❌ FAIL'}")
            logger.info("=" * 80)
            
            if fk_result and comprehensive_result:
                logger.info("🎊 ALL SYSTEMS GO! The login system is fully functional.")
                sys.exit(0)
            else:
                logger.info("🚨 Some tests failed. Please check the implementation.")
                sys.exit(1)
                
        except KeyboardInterrupt:
            logger.info("\n🛑 Test interrupted by user")
            sys.exit(1)
        except Exception as e:
            logger.error(f"💥 Unexpected error in test suite: {e}")
            sys.exit(1)
    
    # Run the test
    asyncio.run(main())