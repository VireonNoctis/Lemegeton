# bot.py
import sys
import os
import asyncio
import logging
import discord
from discord.ext import commands
from time import time

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import TOKEN, GUILD_ID, BOT_ID

# ------------------------------------------------------
# Logging Setup
# ------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("Bot")

# ------------------------------------------------------
# Intents and Bot Setup
# ------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents, application_id=BOT_ID)

# ------------------------------------------------------
# Cog timestamps for tracking changes
# ------------------------------------------------------
cog_timestamps = {}

async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and filename != "__init__.py":
            cog_name = f"cogs.{filename[:-3]}"
            file_path = os.path.join("cogs", filename)
            last_mod = os.path.getmtime(file_path)

            # Check if we need to reload
            if cog_name in bot.extensions:
                if cog_timestamps.get(cog_name, 0) < last_mod:
                    try:
                        await bot.reload_extension(cog_name)
                        logger.info(f"Reloaded cog: {cog_name}")
                        cog_timestamps[cog_name] = last_mod
                    except Exception:
                        logger.exception(f"Failed to reload cog {cog_name}")
            else:
                try:
                    await bot.load_extension(cog_name)
                    logger.info(f"Loaded cog: {cog_name}")
                    cog_timestamps[cog_name] = last_mod
                except Exception:
                    logger.exception(f"Failed to load cog {cog_name}")

# ------------------------------------------------------
# Watch cogs folder for changes
# ------------------------------------------------------
async def watch_cogs():
    while True:
        await load_cogs()
        await asyncio.sleep(2)  # check every 2 seconds

# ------------------------------------------------------
# Events
# ------------------------------------------------------
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info("------")

    # Sync guild commands
    guild = discord.Object(id=GUILD_ID)
    synced = await bot.tree.sync(guild=guild)
    logger.info(f"✅ Synced {len(synced)} guild commands for {GUILD_ID}")

    # Sync global commands
    global_synced = await bot.tree.sync()
    logger.info(f"✅ Synced {len(global_synced)} global commands")

# ------------------------------------------------------
# Run Bot
# ------------------------------------------------------
async def main():
    await load_cogs()
    # Start watching cogs in the background
    asyncio.create_task(watch_cogs())
    await bot.start(TOKEN)

# ------------------------------------------------------
# Entry Point
# ------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
