import sys
import os
import asyncio
import discord
from discord.ext import commands

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import TOKEN, GUILD_ID, BOT_ID
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("SyncCommands")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, application_id=BOT_ID)

async def load_cogs():
    for filename in os.listdir(os.path.join(os.path.dirname(__file__), "../cogs")):
        if filename.endswith(".py") and filename != "__init__.py":
            cog_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                logger.info(f"Loaded cog: {cog_name}")
            except Exception as e:
                logger.exception(f"Failed to load cog {cog_name}")

async def sync_commands():
    # Explicit login ensures application_id is set properly
    await bot.login(TOKEN)
    await load_cogs()

    guild = discord.Object(id=GUILD_ID)

    # Sync guild commands
    synced = await bot.tree.sync(guild=guild)
    logger.info(f"✅ Synced {len(synced)} guild commands for {GUILD_ID}")

    # Sync global commands
    global_synced = await bot.tree.sync()
    logger.info(f"✅ Synced {len(global_synced)} global commands")

    # Close the connection
    await bot.close()

if __name__ == "__main__":
    asyncio.run(sync_commands())
