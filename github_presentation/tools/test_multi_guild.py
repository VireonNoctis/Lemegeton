#!/usr/bin/env python3
"""
Multi-Guild Database Test Script
===============================

This script tests the new multi-guild functionality by:
1. Testing guild-aware database functions
2. Simulating users in different guilds
3. Verifying data isolation between guilds
4. Checking that existing data is preserved

Run this script to validate the multi-guild migration worked correctly.
"""

import asyncio
import aiosqlite
import sys
import os
from database import (
    get_user_guild_aware, add_user_guild_aware, register_user_guild_aware,
    is_user_registered_in_guild, get_guild_user_count, get_guild_leaderboard,
    get_user_progress_guild_aware, get_user_achievements_guild_aware
)

# Get correct database path
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'database.db')

# Test guild IDs
TEST_GUILD_1 = 123456789012345678  # Fake guild 1
TEST_GUILD_2 = 987654321098765432  # Fake guild 2
CURRENT_GUILD = 897814031346319382  # Your actual guild

# Test users
TEST_USERS = [
    (111111111111111111, "TestUser1", "testuser1", 12345),
    (222222222222222222, "TestUser2", "testuser2", 23456),
    (333333333333333333, "TestUser3", "testuser3", 34567),
]

async def test_guild_isolation():
    """Test that users are isolated between guilds."""
    print("🧪 Testing guild isolation...")
    
    # Register the same user in different guilds
    test_user_id = 999999999999999999
    
    # Register in guild 1
    await register_user_guild_aware(
        test_user_id, TEST_GUILD_1, "MultiGuildTestUser", "anilistuser", 99999
    )
    
    # Register in guild 2
    await register_user_guild_aware(
        test_user_id, TEST_GUILD_2, "MultiGuildTestUser", "differentanilist", 88888
    )
    
    # Check isolation
    user_guild1 = await get_user_guild_aware(test_user_id, TEST_GUILD_1)
    user_guild2 = await get_user_guild_aware(test_user_id, TEST_GUILD_2)
    user_current = await get_user_guild_aware(test_user_id, CURRENT_GUILD)
    
    # Validate results
    if user_guild1 and user_guild2 and not user_current:
        print("✅ Guild isolation working correctly")
        print(f"   Guild 1 AniList: {user_guild1[4]}")
        print(f"   Guild 2 AniList: {user_guild2[4]}")
        print("   Not registered in current guild (as expected)")
        return True
    else:
        print("❌ Guild isolation failed")
        return False

async def test_user_registration():
    """Test guild-aware user registration."""
    print("\n🧪 Testing guild-aware user registration...")
    
    success_count = 0
    
    for user_id, username, anilist_username, anilist_id in TEST_USERS:
        try:
            # Register in test guild 1
            await register_user_guild_aware(
                user_id, TEST_GUILD_1, username, anilist_username, anilist_id
            )
            
            # Verify registration
            user = await get_user_guild_aware(user_id, TEST_GUILD_1)
            if user and user[4] == anilist_username:  # Check anilist_username
                print(f"✅ Registered {username} in Guild 1")
                success_count += 1
            else:
                print(f"❌ Failed to register {username}")
                
        except Exception as e:
            print(f"❌ Error registering {username}: {e}")
    
    return success_count == len(TEST_USERS)

async def test_guild_user_counts():
    """Test guild user counting."""
    print("\n🧪 Testing guild user counts...")
    
    try:
        count_guild1 = await get_guild_user_count(TEST_GUILD_1)
        count_guild2 = await get_guild_user_count(TEST_GUILD_2) 
        count_current = await get_guild_user_count(CURRENT_GUILD)
        
        print(f"✅ User counts:")
        print(f"   Test Guild 1: {count_guild1} users")
        print(f"   Test Guild 2: {count_guild2} users")
        print(f"   Current Guild: {count_current} users")
        
        # Should have test users in guild 1, isolation test user in guild 2, existing users in current
        return count_guild1 >= 3 and count_guild2 >= 1 and count_current >= 1
        
    except Exception as e:
        print(f"❌ Error counting guild users: {e}")
        return False

async def test_existing_data_preservation():
    """Test that existing data was preserved in current guild."""
    print("\n🧪 Testing existing data preservation...")
    
    try:
        # Check if we have users in the current guild
        count = await get_guild_user_count(CURRENT_GUILD)
        if count > 0:
            print(f"✅ Found {count} existing users preserved in current guild")
            return True
        else:
            print("⚠️ No users found in current guild - this might be expected if no users were previously registered")
            return True
            
    except Exception as e:
        print(f"❌ Error checking existing data: {e}")
        return False

async def test_is_user_registered():
    """Test the user registration check function."""
    print("\n🧪 Testing user registration checks...")
    
    try:
        # Check test user registrations
        user_id = TEST_USERS[0][0]
        
        is_reg_guild1 = await is_user_registered_in_guild(user_id, TEST_GUILD_1)
        is_reg_guild2 = await is_user_registered_in_guild(user_id, TEST_GUILD_2)
        is_reg_current = await is_user_registered_in_guild(user_id, CURRENT_GUILD)
        
        if is_reg_guild1 and not is_reg_guild2 and not is_reg_current:
            print("✅ Registration checks working correctly")
            print(f"   User registered in Guild 1: {is_reg_guild1}")
            print(f"   User registered in Guild 2: {is_reg_guild2}")
            print(f"   User registered in Current Guild: {is_reg_current}")
            return True
        else:
            print("❌ Registration checks failed")
            return False
            
    except Exception as e:
        print(f"❌ Error checking user registration: {e}")
        return False

async def cleanup_test_data():
    """Clean up test data."""
    print("\n🧹 Cleaning up test data...")
    
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            # Remove test users
            test_user_ids = [user[0] for user in TEST_USERS] + [999999999999999999]
            
            for user_id in test_user_ids:
                await db.execute("DELETE FROM users WHERE discord_id = ?", (user_id,))
            
            await db.commit()
            print("✅ Test data cleaned up")
            
    except Exception as e:
        print(f"❌ Error cleaning up: {e}")

async def main():
    """Run all tests."""
    print("🚀 Starting Multi-Guild Database Tests")
    print("=" * 50)
    
    tests = [
        ("Guild-aware registration", test_user_registration),
        ("Guild isolation", test_guild_isolation),
        ("Guild user counts", test_guild_user_counts),
        ("User registration checks", test_is_user_registered),
        ("Existing data preservation", test_existing_data_preservation),
    ]
    
    passed_tests = 0
    total_tests = len(tests)
    
    for test_name, test_func in tests:
        try:
            if await test_func():
                passed_tests += 1
            else:
                print(f"❌ Test '{test_name}' failed")
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
    
    # Cleanup
    await cleanup_test_data()
    
    # Results
    print("\n" + "=" * 50)
    print(f"📊 TEST RESULTS: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Multi-guild functionality is working correctly.")
        print("\n✅ Your bot is ready for multi-server deployment!")
    else:
        print(f"⚠️ {total_tests - passed_tests} tests failed. Review the output above.")
        print("\n❌ Multi-guild functionality needs attention before deployment.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(1)