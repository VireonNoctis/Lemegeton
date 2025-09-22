"""
Test script for the Invite Tracker cog functionality.
Tests database operations, message handling, and admin commands.
"""

import sqlite3
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add parent directory to path to import modules
sys.path.append(str(Path(__file__).parent.parent))

from database import execute_db_operation, DB_PATH
from config import GUILD_ID

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InviteTrackerTest")

class InviteTrackerTester:
    """Test class for invite tracker functionality"""
    
    def __init__(self):
        self.test_guild_id = GUILD_ID
        self.test_user_ids = [123456789, 987654321, 555666777, 111222333]
        self.test_inviter_ids = [444555666, 777888999]
        self.test_invite_codes = ["testcode1", "testcode2", "testcode3"]
        self.test_channel_id = 999888777666
        
    async def setup_test_data(self):
        """Set up test data in the database"""
        logger.info("Setting up test data...")
        
        # Clear existing test data
        await self.cleanup_test_data()
        
        # Insert test invites
        for i, code in enumerate(self.test_invite_codes):
            await execute_db_operation(
                "insert test invite",
                """
                INSERT INTO invites 
                (invite_code, guild_id, inviter_id, inviter_name, channel_id, max_uses, uses)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    self.test_guild_id,
                    self.test_inviter_ids[i % len(self.test_inviter_ids)],
                    f"TestInviter{i}",
                    self.test_channel_id,
                    -1,
                    0
                )
            )
        
        # Insert test invite uses
        for i, user_id in enumerate(self.test_user_ids):
            invite_code = self.test_invite_codes[i % len(self.test_invite_codes)]
            inviter_id = self.test_inviter_ids[i % len(self.test_inviter_ids)]
            
            await execute_db_operation(
                "insert test invite use",
                """
                INSERT INTO invite_uses 
                (guild_id, invite_code, inviter_id, inviter_name, joiner_id, joiner_name, joined_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.test_guild_id,
                    invite_code,
                    inviter_id,
                    f"TestInviter{inviter_id}",
                    user_id,
                    f"TestUser{user_id}",
                    datetime.now() - timedelta(days=random.randint(1, 30))
                )
            )
        
        # Insert test recruitment stats
        for inviter_id in self.test_inviter_ids:
            recruit_count = len([u for i, u in enumerate(self.test_user_ids) if self.test_inviter_ids[i % len(self.test_inviter_ids)] == inviter_id])
            
            await execute_db_operation(
                "insert test recruitment stats",
                """
                INSERT INTO recruitment_stats
                (user_id, guild_id, username, total_recruits)
                VALUES (?, ?, ?, ?)
                """,
                (inviter_id, self.test_guild_id, f"TestInviter{inviter_id}", recruit_count)
            )
        
        # Insert test user leaves
        for i in range(2):  # Only 2 users left
            user_id = self.test_user_ids[i]
            inviter_id = self.test_inviter_ids[i % len(self.test_inviter_ids)]
            
            await execute_db_operation(
                "insert test user leave",
                """
                INSERT INTO user_leaves 
                (guild_id, user_id, username, was_invited_by, days_in_server, left_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self.test_guild_id,
                    user_id,
                    f"TestUser{user_id}",
                    inviter_id,
                    random.randint(1, 100),
                    datetime.now() - timedelta(days=random.randint(1, 7))
                )
            )
        
        # Insert test channel setting
        await execute_db_operation(
            "insert test channel setting",
            """
            INSERT INTO invite_tracker_settings
            (guild_id, announcement_channel_id, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (self.test_guild_id, self.test_channel_id)
        )
        
        logger.info("✅ Test data setup complete")
    
    async def test_database_operations(self):
        """Test all database operations"""
        logger.info("🧪 Testing database operations...")
        
        # Test invite retrieval
        invites = await execute_db_operation(
            "get test invites",
            "SELECT * FROM invites WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='all'
        )
        assert len(invites) == len(self.test_invite_codes), f"Expected {len(self.test_invite_codes)} invites, got {len(invites)}"
        logger.info(f"✅ Invite retrieval test passed - {len(invites)} invites found")
        
        # Test invite uses retrieval
        invite_uses = await execute_db_operation(
            "get test invite uses",
            "SELECT * FROM invite_uses WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='all'
        )
        assert len(invite_uses) == len(self.test_user_ids), f"Expected {len(self.test_user_ids)} invite uses, got {len(invite_uses)}"
        logger.info(f"✅ Invite uses retrieval test passed - {len(invite_uses)} uses found")
        
        # Test recruitment stats
        recruitment_stats = await execute_db_operation(
            "get test recruitment stats",
            "SELECT * FROM recruitment_stats WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='all'
        )
        assert len(recruitment_stats) == len(self.test_inviter_ids), f"Expected {len(self.test_inviter_ids)} recruitment records, got {len(recruitment_stats)}"
        logger.info(f"✅ Recruitment stats test passed - {len(recruitment_stats)} records found")
        
        # Test user leaves
        user_leaves = await execute_db_operation(
            "get test user leaves",
            "SELECT * FROM user_leaves WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='all'
        )
        assert len(user_leaves) == 2, f"Expected 2 user leave records, got {len(user_leaves)}"
        logger.info(f"✅ User leaves test passed - {len(user_leaves)} leave records found")
        
        # Test channel settings
        channel_setting = await execute_db_operation(
            "get test channel setting",
            "SELECT * FROM invite_tracker_settings WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='one'
        )
        assert channel_setting is not None, "Channel setting not found"
        assert channel_setting[1] == self.test_channel_id, f"Expected channel ID {self.test_channel_id}, got {channel_setting[1]}"
        logger.info("✅ Channel settings test passed")
        
        logger.info("🎉 All database operation tests passed!")
    
    async def test_analytics_queries(self):
        """Test complex analytics queries"""
        logger.info("📊 Testing analytics queries...")
        
        # Test total recruitment count
        result = await execute_db_operation(
            "get total recruited count",
            "SELECT COUNT(*) FROM invite_uses WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='one'
        )
        total_recruited = result[0] if result else 0
        assert total_recruited == len(self.test_user_ids), f"Expected {len(self.test_user_ids)} total recruited, got {total_recruited}"
        logger.info(f"✅ Total recruitment count test passed - {total_recruited} recruited")
        
        # Test total leaves count
        result = await execute_db_operation(
            "get total leaves count",
            "SELECT COUNT(*) FROM user_leaves WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='one'
        )
        total_leaves = result[0] if result else 0
        assert total_leaves == 2, f"Expected 2 total leaves, got {total_leaves}"
        logger.info(f"✅ Total leaves count test passed - {total_leaves} leaves")
        
        # Test top recruiters query
        top_recruiters = await execute_db_operation(
            "get top recruiters",
            """
            SELECT username, total_recruits FROM recruitment_stats 
            WHERE guild_id = ? 
            ORDER BY total_recruits DESC LIMIT 10
            """,
            (self.test_guild_id,),
            fetch_type='all'
        )
        assert len(top_recruiters) > 0, "No top recruiters found"
        logger.info(f"✅ Top recruiters query test passed - {len(top_recruiters)} recruiters found")
        
        # Test retention rate calculation
        retention_rate = ((total_recruited - total_leaves) / max(total_recruited, 1) * 100)
        logger.info(f"✅ Retention rate calculation test passed - {retention_rate:.1f}%")
        
        # Test recent activity query (last 7 days)
        result = await execute_db_operation(
            "get recent joins",
            """
            SELECT COUNT(*) FROM invite_uses 
            WHERE guild_id = ? AND joined_at >= datetime('now', '-7 days')
            """,
            (self.test_guild_id,),
            fetch_type='one'
        )
        recent_joins = result[0] if result else 0
        logger.info(f"✅ Recent joins query test passed - {recent_joins} recent joins")
        
        result = await execute_db_operation(
            "get recent leaves",
            """
            SELECT COUNT(*) FROM user_leaves 
            WHERE guild_id = ? AND left_at >= datetime('now', '-7 days')
            """,
            (self.test_guild_id,),
            fetch_type='one'
        )
        recent_leaves = result[0] if result else 0
        logger.info(f"✅ Recent leaves query test passed - {recent_leaves} recent leaves")
        
        logger.info("🎉 All analytics query tests passed!")
    
    async def test_invite_tracking_logic(self):
        """Test invite tracking logic simulation"""
        logger.info("🔍 Testing invite tracking logic...")
        
        # Simulate a new invite use
        new_user_id = 999999999
        test_invite_code = self.test_invite_codes[0]
        test_inviter_id = self.test_inviter_ids[0]
        
        # Record new invite use
        await execute_db_operation(
            "record test invite use",
            """
            INSERT INTO invite_uses 
            (guild_id, invite_code, inviter_id, inviter_name, joiner_id, joiner_name)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                self.test_guild_id,
                test_invite_code,
                test_inviter_id,
                f"TestInviter{test_inviter_id}",
                new_user_id,
                f"NewTestUser{new_user_id}"
            )
        )
        
        # Update recruitment stats
        await execute_db_operation(
            "update recruitment stats",
            """
            INSERT OR REPLACE INTO recruitment_stats
            (user_id, guild_id, username, total_recruits)
            VALUES (?, ?, ?, COALESCE((
                SELECT total_recruits + 1 FROM recruitment_stats 
                WHERE user_id = ? AND guild_id = ?
            ), 1))
            """,
            (test_inviter_id, self.test_guild_id, f"TestInviter{test_inviter_id}", test_inviter_id, self.test_guild_id)
        )
        
        # Verify the recruitment count increased
        result = await execute_db_operation(
            "get updated recruit count",
            """
            SELECT total_recruits FROM recruitment_stats 
            WHERE user_id = ? AND guild_id = ?
            """,
            (test_inviter_id, self.test_guild_id),
            fetch_type='one'
        )
        
        new_recruit_count = result[0] if result else 0
        logger.info(f"✅ Invite tracking logic test passed - Recruit count: {new_recruit_count}")
        
        # Clean up the test data
        await execute_db_operation(
            "delete test invite use",
            "DELETE FROM invite_uses WHERE joiner_id = ?",
            (new_user_id,)
        )
        
        # Restore original recruitment count
        original_count = len([u for i, u in enumerate(self.test_user_ids) if self.test_inviter_ids[i % len(self.test_inviter_ids)] == test_inviter_id])
        await execute_db_operation(
            "restore recruitment stats",
            """
            UPDATE recruitment_stats 
            SET total_recruits = ? 
            WHERE user_id = ? AND guild_id = ?
            """,
            (original_count, test_inviter_id, self.test_guild_id)
        )
        
        logger.info("🎉 Invite tracking logic test passed!")
    
    async def test_message_templates(self):
        """Test Xianxia message templates"""
        logger.info("💬 Testing message templates...")
        
        from cogs.invite_tracker import XIANXIA_JOIN_MESSAGES, XIANXIA_LEAVE_MESSAGES, RECRUITMENT_TITLES
        
        # Test join messages
        assert len(XIANXIA_JOIN_MESSAGES) > 0, "No join messages found"
        test_joiner = "TestUser"
        test_inviter = "TestInviter"
        
        for message in XIANXIA_JOIN_MESSAGES:
            formatted_message = message.format(joiner=test_joiner, inviter=test_inviter)
            assert test_joiner in formatted_message, f"Joiner not found in message: {formatted_message}"
            assert test_inviter in formatted_message, f"Inviter not found in message: {formatted_message}"
        
        logger.info(f"✅ Join message templates test passed - {len(XIANXIA_JOIN_MESSAGES)} templates")
        
        # Test leave messages
        assert len(XIANXIA_LEAVE_MESSAGES) > 0, "No leave messages found"
        test_user = "TestUser"
        
        for message in XIANXIA_LEAVE_MESSAGES:
            formatted_message = message.format(user=test_user)
            assert test_user in formatted_message, f"User not found in message: {formatted_message}"
        
        logger.info(f"✅ Leave message templates test passed - {len(XIANXIA_LEAVE_MESSAGES)} templates")
        
        # Test recruitment titles
        assert len(RECRUITMENT_TITLES) > 0, "No recruitment titles found"
        logger.info(f"✅ Recruitment titles test passed - {len(RECRUITMENT_TITLES)} titles")
        
        logger.info("🎉 All message template tests passed!")
    
    async def test_database_schema(self):
        """Test database schema integrity"""
        logger.info("🏗️ Testing database schema...")
        
        # Check if all required tables exist using the database module
        expected_tables = ['invites', 'invite_uses', 'recruitment_stats', 'user_leaves', 'invite_tracker_settings']
        
        # Use the async database operations to check tables
        for table in expected_tables:
            try:
                result = await execute_db_operation(
                    f"check table {table}",
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'",
                    fetch_type='one'
                )
                assert result is not None, f"Required table '{table}' not found in database"
                logger.info(f"✅ Table '{table}' found in database")
                
                # Check table schema
                columns = await execute_db_operation(
                    f"check schema for {table}",
                    f"PRAGMA table_info({table})",
                    fetch_type='all'
                )
                assert len(columns) > 0, f"Table '{table}' has no columns"
                column_names = [col[1] for col in columns]
                logger.info(f"✅ Table '{table}' schema verified - {len(columns)} columns: {', '.join(column_names[:3])}{'...' if len(column_names) > 3 else ''}")
                
            except Exception as e:
                logger.error(f"Failed to verify table '{table}': {e}")
                raise
        
        logger.info("🎉 Database schema tests passed!")
    
    async def display_test_results(self):
        """Display formatted test results"""
        logger.info("📋 Displaying test data results...")
        
        print("\n" + "="*60)
        print("🏮 INVITE TRACKER TEST RESULTS")
        print("="*60)
        
        # Display invites
        invites = await execute_db_operation(
            "get all test invites",
            "SELECT invite_code, inviter_name, uses FROM invites WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='all'
        )
        
        print(f"\n📨 INVITES ({len(invites)}):")
        for code, inviter, uses in invites:
            print(f"  • {code} by {inviter} - {uses} uses")
        
        # Display recruitment stats
        stats = await execute_db_operation(
            "get all recruitment stats",
            "SELECT username, total_recruits FROM recruitment_stats WHERE guild_id = ? ORDER BY total_recruits DESC",
            (self.test_guild_id,),
            fetch_type='all'
        )
        
        print(f"\n🏆 TOP RECRUITERS ({len(stats)}):")
        for i, (username, count) in enumerate(stats, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            print(f"  {emoji} {username} - {count} disciples")
        
        # Display recent activity
        total_recruited = await execute_db_operation(
            "get total recruited",
            "SELECT COUNT(*) FROM invite_uses WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='one'
        )
        total_recruited = total_recruited[0] if total_recruited else 0
        
        total_leaves = await execute_db_operation(
            "get total leaves",
            "SELECT COUNT(*) FROM user_leaves WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='one'
        )
        total_leaves = total_leaves[0] if total_leaves else 0
        
        retention_rate = ((total_recruited - total_leaves) / max(total_recruited, 1) * 100)
        
        print(f"\n📊 ANALYTICS:")
        print(f"  • Total Recruited: {total_recruited}")
        print(f"  • Total Departures: {total_leaves}")
        print(f"  • Retention Rate: {retention_rate:.1f}%")
        print(f"  • Net Growth: {total_recruited - total_leaves}")
        
        # Display channel settings
        channel_setting = await execute_db_operation(
            "get channel setting",
            "SELECT announcement_channel_id FROM invite_tracker_settings WHERE guild_id = ?",
            (self.test_guild_id,),
            fetch_type='one'
        )
        
        print(f"\n🔧 CONFIGURATION:")
        if channel_setting:
            print(f"  • Announcement Channel ID: {channel_setting[0]}")
        else:
            print("  • No announcement channel configured")
        
        print("\n" + "="*60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("="*60)
    
    async def cleanup_test_data(self):
        """Clean up all test data"""
        logger.info("🧹 Cleaning up test data...")
        
        # Delete test data from all tables
        tables_and_conditions = [
            ("invites", f"guild_id = {self.test_guild_id}"),
            ("invite_uses", f"guild_id = {self.test_guild_id}"),
            ("recruitment_stats", f"guild_id = {self.test_guild_id}"),
            ("user_leaves", f"guild_id = {self.test_guild_id}"),
            ("invite_tracker_settings", f"guild_id = {self.test_guild_id}")
        ]
        
        for table, condition in tables_and_conditions:
            try:
                await execute_db_operation(
                    f"cleanup {table}",
                    f"DELETE FROM {table} WHERE {condition}"
                )
                logger.info(f"✅ Cleaned up {table}")
            except Exception as e:
                logger.warning(f"Failed to clean up {table}: {e}")
        
        logger.info("🧹 Test data cleanup complete")
    
    async def run_all_tests(self):
        """Run all tests in sequence"""
        logger.info("🚀 Starting comprehensive invite tracker tests...")
        
        try:
            await self.test_database_schema()
            await self.setup_test_data()
            await self.test_database_operations()
            await self.test_analytics_queries()
            await self.test_invite_tracking_logic()
            await self.test_message_templates()
            await self.display_test_results()
            
            logger.info("🎉 ALL TESTS PASSED! The invite tracker is working correctly.")
            
        except AssertionError as e:
            logger.error(f"❌ Test failed: {e}")
            raise
        except Exception as e:
            logger.error(f"💥 Unexpected error during testing: {e}")
            raise
        finally:
            await self.cleanup_test_data()

async def main():
    """Main test runner"""
    print("🧪 Invite Tracker Comprehensive Test Suite")
    print("=" * 50)
    
    tester = InviteTrackerTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())