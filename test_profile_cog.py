#!/usr/bin/env python3
"""
Simple bot test to load just the profile cog
This isolates the profile functionality from other problematic cogs
"""

import asyncio
import logging
import discord
from discord.ext import commands

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a minimal bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot logged in as {bot.user}")
    print("🔧 Attempting to load profile cog...")
    
    try:
        await bot.load_extension('cogs.profile')
        print("✅ Profile cog loaded successfully!")
        
        # Test if the cog has the command we expect
        profile_cog = bot.get_cog('Profile')
        if profile_cog:
            print(f"✅ Profile cog found: {profile_cog}")
            print(f"✅ Commands available: {list(profile_cog.get_commands())}")
        else:
            print("❌ Profile cog not found after loading")
            
    except Exception as e:
        print(f"❌ Failed to load profile cog: {e}")
        import traceback
        traceback.print_exc()
    
    # Don't actually connect to Discord - just test loading
    await bot.close()

async def test_profile_cog():
    """Test loading the profile cog without connecting to Discord"""
    print("🔍 Testing Profile Cog Loading...")
    print("=" * 50)
    
    try:
        # Just test the import and basic functionality
        print("📦 Testing cog import...")
        
        # We'll simulate the bot environment
        fake_bot = type('Bot', (), {})()
        fake_bot.user = type('User', (), {'id': 12345})()
        
        # Try importing the profile module directly
        import sys
        import os
        sys.path.append(os.path.join(os.getcwd(), 'cogs'))
        
        from cogs.profile import Profile, build_achievements
        print("✅ Profile cog imported successfully")
        
        # Check if the function exists
        if callable(build_achievements):
            print("✅ build_achievements function found")
        else:
            print("❌ build_achievements function not found")
        
        # Check if the Profile class exists
        if Profile:
            print("✅ Profile class found")
        else:
            print("❌ Profile class not found")
            
        print("✅ Profile cog test completed successfully!")
        
    except Exception as e:
        print(f"❌ Profile cog test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run the simple test
    asyncio.run(test_profile_cog())