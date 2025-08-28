# bot.py
import discord
from discord.ext import commands
from config import TOKEN, GUILD_ID, BOT_ID
import logging
import asyncio

# -----------------------------
# Logging Setup
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# -----------------------------
# Bot Configuration
# -----------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, application_id=BOT_ID)

# -----------------------------
# Cog List
# -----------------------------
COGS = {
    "cogs.registration": "Registration",
    "cogs.manga": "Manga",
    "cogs.unregister": "Unregister",
    "cogs.challenge_rules": "ChallengeRules",
    "cogs.changelog": "Changelog",
    "cogs.anime": "Anime",
    "cogs.profile": "Profile",
    "cogs.recommendations": "Recommendations"
}

# -----------------------------
# Load Cogs
# -----------------------------
async def load_cogs():
    for cog_path, class_name in COGS.items():
        try:
            if cog_path in bot.extensions:
                await bot.unload_extension(cog_path)
            await bot.load_extension(cog_path)
            logger.info("✅ Loaded cog: %s", class_name)
        except Exception as e:
            logger.exception("❌ Failed to load cog '%s': %s", class_name, e)

# -----------------------------
# Ready Event
# -----------------------------
@bot.event
async def on_ready():
    logger.info("Bot is starting...")

    guild = discord.Object(id=GUILD_ID)

    # -----------------------------
    # Log all loaded cogs
    # -----------------------------
    for cog_name, cog_instance in bot.cogs.items():
        logger.info("   • Cog loaded: %s", cog_name)

    # -----------------------------
    # Sync slash commands for the guild
    # -----------------------------
    try:
        synced = await bot.tree.sync(guild=guild)
        logger.info("✅ Synced %d slash commands to guild %s", len(synced), GUILD_ID)
        for cmd in synced:
            logger.info("   • /%s", cmd.name)
    except Exception as e:
        logger.exception("❌ Failed to sync slash commands: %s", e)

    logger.info("✅ Logged in as %s (ID: %s)", bot.user, bot.user.id)

# -----------------------------
# Main Entry Point
# -----------------------------
async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
