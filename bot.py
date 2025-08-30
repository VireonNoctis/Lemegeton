# bot.py
import sys
import os
import asyncio
import logging
import discord
from discord.ext import commands

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
# Load Cogs
# ------------------------------------------------------
async def load_cogs():
    cogs_path = os.path.join(os.path.dirname(__file__), "cogs")
    for filename in os.listdir(cogs_path):
        if filename.endswith(".py") and filename != "__init__.py":
            cog_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                logger.info(f"Loaded cog: {cog_name}")
            except Exception:
                logger.exception(f"Failed to load cog {cog_name}")

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
    await bot.start(TOKEN)

# ------------------------------------------------------
# Entry Point
# ------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
