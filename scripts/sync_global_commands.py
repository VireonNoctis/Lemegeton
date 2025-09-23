#!/usr/bin/env python3
"""
Script to properly sync all global commands and clear any remaining guild commands.
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

class CommandSyncer(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        """Load all cogs before syncing."""
        cogs_to_load = [
            'cogs.affinity',
            'cogs.anilist', 
            'cogs.browse',
            'cogs.challenge_leaderboard',
            'cogs.challenge_manage',
            'cogs.challenge_progress',
            'cogs.challenge_update',
            'cogs.changelog',
            'cogs.compare',
            'cogs.feedback',
            'cogs.help',
            'cogs.invite_tracker',
            'cogs.invite',
            'cogs.leaderboard',
            'cogs.login',
            'cogs.profile',
            'cogs.random',
            'cogs.recommendations',
            'cogs.search_similar',
            'cogs.stats',
            'cogs.steam',
            'cogs.timestamp',
            'cogs.trending',
            'cogs.watchlist'
        ]
        
        for cog in cogs_to_load:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Loaded {cog}")
            except Exception as e:
                logger.error(f"❌ Failed to load {cog}: {e}")

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.sync_commands()
        await self.close()

    async def sync_commands(self):
        """Sync commands properly."""
        try:
            guild = discord.Object(id=GUILD_ID)
            
            # Step 1: Clear any remaining guild commands
            logger.info("🧹 Clearing any remaining guild commands...")
            self.tree.clear_commands(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("✅ Guild commands cleared")
            
            # Step 2: Count current app commands in tree
            app_commands = self.tree.get_commands()
            logger.info(f"📝 Found {len(app_commands)} commands to sync globally:")
            for cmd in app_commands:
                if hasattr(cmd, 'name'):
                    logger.info(f"  - {cmd.name}")
            
            # Step 3: Sync global commands
            logger.info("🌍 Syncing global commands...")
            synced = await self.tree.sync()
            logger.info(f"✅ Synced {len(synced)} global commands:")
            for cmd in synced:
                logger.info(f"  - {cmd.name}")
            
            # Step 4: Verify final state
            await asyncio.sleep(2)  # Give Discord time to update
            
            guild_commands = await self.tree.fetch_commands(guild=guild)
            global_commands = await self.tree.fetch_commands()
            
            logger.info(f"📊 Final status:")
            logger.info(f"  🏰 Guild commands: {len(guild_commands)}")
            logger.info(f"  🌍 Global commands: {len(global_commands)}")
            
            if len(guild_commands) == 0 and len(global_commands) > 0:
                logger.info("🎉 SUCCESS: All commands are now global, no duplicates!")
            else:
                logger.warning("⚠️  Check required - unexpected command state")
                
        except Exception as e:
            logger.error(f"Error syncing commands: {e}")

async def main():
    """Main function to run the command syncer."""
    bot = CommandSyncer()
    
    try:
        logger.info("Starting command sync process...")
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    asyncio.run(main())