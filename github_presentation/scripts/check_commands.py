#!/usr/bin/env python3
"""
Script to check command sync status and troubleshoot duplicates.
"""

import asyncio
import discord
from discord.ext import commands
import logging
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TOKEN, GUILD_ID

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CommandChecker(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.check_commands()
        await self.close()

    async def check_commands(self):
        """Check current command sync status."""
        try:
            guild = discord.Object(id=GUILD_ID)
            
            # Check guild commands
            guild_commands = await self.tree.fetch_commands(guild=guild)
            logger.info(f"🏰 Guild-specific commands: {len(guild_commands)}")
            if guild_commands:
                for cmd in guild_commands:
                    logger.info(f"  - {cmd.name} (Guild)")
            
            # Check global commands
            global_commands = await self.tree.fetch_commands()
            logger.info(f"🌍 Global commands: {len(global_commands)}")
            if global_commands:
                for cmd in global_commands:
                    logger.info(f"  - {cmd.name} (Global)")
            
            # Summary
            total_visible = len(guild_commands) + len(global_commands)
            logger.info(f"📊 Total commands visible in guild: {total_visible}")
            
            if len(guild_commands) > 0 and len(global_commands) > 0:
                logger.warning("⚠️  ISSUE: Both guild and global commands exist - this causes duplicates!")
                logger.info("💡 Solution: Guild commands override global ones, causing duplicates to appear")
            elif len(guild_commands) > 0:
                logger.info("✅ Only guild commands exist")
            elif len(global_commands) > 0:
                logger.info("✅ Only global commands exist - no duplicates expected")
            else:
                logger.warning("⚠️  No commands found!")
                
        except Exception as e:
            logger.error(f"Error checking commands: {e}")

async def main():
    """Main function to run the command checker."""
    bot = CommandChecker()
    
    try:
        logger.info("Checking command sync status...")
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    asyncio.run(main())