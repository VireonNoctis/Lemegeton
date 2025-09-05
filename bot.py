# bot.py
import sys
import os
import asyncio
import logging
import time
import aiohttp
import discord
from discord.ext import commands
from database import init_db

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
# AniList API Function
# ------------------------------------------------------
ANILIST_API_URL = "https://graphql.anilist.co"

async def fetch_trending_anime_list():
    query = """
    query {
        Page(page: 1, perPage: 10) {
            media(sort: TRENDING_DESC, type: ANIME) {
                title {
                    romaji
                    english
                }
            }
        }
    }
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(ANILIST_API_URL, json={"query": query}) as response:
            if response.status != 200:
                logger.error(f"AniList API request failed: {response.status}")
                return ["AniList API ❤️"]
            data = await response.json()
            anime_list = data["data"]["Page"]["media"]
            return [
                anime["title"]["english"] or anime["title"]["romaji"]
                for anime in anime_list
            ] or ["AniList API ❤️"]

# ------------------------------------------------------
# Streaming Status Loop
# ------------------------------------------------------
async def update_streaming_status():
    await bot.wait_until_ready()

    trending = await fetch_trending_anime_list()
    index = 0
    refresh_interval = 3 * 60 * 60  # every 3 hours
    last_refresh = time.time()

    while not bot.is_closed():
        anime_title = trending[index]
        stream = discord.Streaming(
            name=f"Trending: {anime_title}",
            url="https://anilist.co"
        )
        await bot.change_presence(activity=stream)
        logger.info(f"🎥 Streaming status updated to: {anime_title}")

        # Move to next anime, loop back if at end
        index = (index + 1) % len(trending)

        # Refresh trending list if 3 hours passed
        if time.time() - last_refresh >= refresh_interval:
            logger.info("🔄 Refreshing AniList trending list...")
            trending = await fetch_trending_anime_list()
            index = 0
            last_refresh = time.time()

        await asyncio.sleep(300)  # wait 5 minutes before updating again

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

    # Start AniList status updater
    bot.loop.create_task(update_streaming_status())

# ------------------------------------------------------
# Run Bot
# ------------------------------------------------------
async def main():
    # Initialize all database tables first
    await init_db()

    # Load cogs
    await load_cogs()

    # Start watching cogs in the background
    asyncio.create_task(watch_cogs())

    # Start the bot
    await bot.start(TOKEN)

# ------------------------------------------------------
# Entry Point
# ------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
