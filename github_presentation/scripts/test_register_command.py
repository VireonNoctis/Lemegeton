# scripts/test_register_command.py
import sys
import os
import asyncio

# Add project root to sys.path so imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cogs.registration import Registration
from database import get_user, remove_user

# -------------------------------
# Test Data
# -------------------------------
TEST_USER_ID = 1234567890
TEST_USERNAME = "TestUserMock"

# -------------------------------
# Test Function
# -------------------------------
async def test_register():
    bot = None  # No bot needed for offline test
    cog = Registration(bot)

    # Clean up any existing test user
    await remove_user(TEST_USER_ID)

    # Call the core registration logic directly
    result = await cog.handle_register(TEST_USER_ID, TEST_USERNAME)
    print("Result:", result)

    # Check database state
    user = await get_user(TEST_USER_ID)
    print("User data after /register:", user)

# -------------------------------
# Run Test
# -------------------------------
if __name__ == "__main__":
    asyncio.run(test_register())
