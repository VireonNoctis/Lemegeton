# scripts/test_register_unregister.py
import asyncio
import sys
import os
import bot

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import add_user, get_user, update_username, remove_user


# -------------------------------
# Test Data
# -------------------------------
TEST_USER_ID = 1234567890
TEST_USERNAME = "TestUser"

# -------------------------------
# Test Functions
# -------------------------------

@bot.event
async def on_ready():
    print(f"Bot is in guilds: {[g.id for g in bot.guilds]}")


async def test_register():
    print(f"Registering user {TEST_USER_ID} with username '{TEST_USERNAME}'...")
    user = await get_user(TEST_USER_ID)
    if user:
        print(f"User already exists, updating username to '{TEST_USERNAME}'")
        await update_username(TEST_USER_ID, TEST_USERNAME)
    else:
        await add_user(TEST_USER_ID, TEST_USERNAME)
        print("User added successfully!")

    user = await get_user(TEST_USER_ID)
    print("Current user data:", user)

async def test_unregister():
    print(f"Unregistering user {TEST_USER_ID}...")
    user = await get_user(TEST_USER_ID)
    if not user:
        print("User does not exist, nothing to remove.")
    else:
        await remove_user(TEST_USER_ID)
        print("User removed successfully!")

    user = await get_user(TEST_USER_ID)
    print("Current user data after removal:", user)

# -------------------------------
# Run Tests
# -------------------------------
async def main():
    await test_register()
    print("\n---\n")
    await test_unregister()

if __name__ == "__main__":
    asyncio.run(main())
