#!/usr/bin/env python3
"""Test script to verify both anilist and steam cogs can load without conflicts."""

import asyncio
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import bot

async def test_cog_loading():
    """Test loading both anilist and steam cogs."""
    try:
        print("Loading anilist cog...")
        await bot.load_extension('cogs.anilist')
        print("✅ anilist cog loaded successfully")
        
        print("Loading steam cog...")
        await bot.load_extension('cogs.steam')
        print("✅ steam cog loaded successfully")
        
        print("🎉 Both cogs loaded without conflicts!")
        
        # List commands to verify
        commands = bot.tree.get_commands()
        steam_commands = [cmd for cmd in commands if hasattr(cmd, 'name') and 'steam' in cmd.name.lower()]
        
        print(f"Found {len(steam_commands)} steam-related commands:")
        for cmd in steam_commands:
            print(f"  - {cmd.name}")
            
    except Exception as e:
        print(f"❌ Error loading cogs: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_cog_loading())
    sys.exit(0 if success else 1)