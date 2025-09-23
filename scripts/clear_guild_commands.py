#!/usr/bin/env python3
"""
Script to clear guild-specific commands and ensure only global commands remain.
This fixes the issue of duplicate commands in guilds.
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

class CommandCleaner(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.clear_duplicate_commands()
        await self.close()

    async def clear_duplicate_commands(self):
        """Clear guild-specific commands to remove duplicates."""
        try:
            guild = discord.Object(id=GUILD_ID)
            
            # Get current guild commands
            guild_commands = await self.tree.sync(guild=guild)
            logger.info(f"Found {len(guild_commands)} guild-specific commands")
            
            # Clear all guild commands
            self.tree.clear_commands(guild=guild)
            cleared_commands = await self.tree.sync(guild=guild)
            logger.info(f"Cleared guild commands. Remaining: {len(cleared_commands)}")
            
            # Get global commands to verify they exist
            global_commands = await self.tree.sync()
            logger.info(f"Global commands available: {len(global_commands)}")
            
            # List global command names for verification
            if global_commands:
                command_names = [cmd.name for cmd in global_commands]
                logger.info(f"Global commands: {', '.join(command_names)}")
            
            logger.info("✅ Successfully cleared duplicate guild commands!")
            logger.info("Your guild should now only show global commands (no duplicates)")
            
        except Exception as e:
            logger.error(f"Error clearing commands: {e}")
            raise

async def main():
    """Main function to run the command cleaner."""
    bot = CommandCleaner()
    
    try:
        logger.info("Starting command cleanup process...")
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
    except Exception as e:
        logger.error(f"Error running bot: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    asyncio.run(main())