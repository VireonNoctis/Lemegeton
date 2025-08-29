import discord
from discord.ext import commands
import logging
import asyncio

from config import TOKEN, GUILD_ID, BOT_ID
from database import init_challenge_rules_table, init_db

# ------------------------------------------------------
# Logging Setup
# ------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------
# Bot Configuration
# ------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, application_id=BOT_ID)

# ------------------------------------------------------
# Cog Extensions
# ------------------------------------------------------
COGS = {
    "cogs.registration": "Registration",
    "cogs.manga": "Manga",
    "cogs.unregister": "Unregister",
    "cogs.challenge_rules": "ChallengeRules",
    "cogs.changelog": "Changelog",
    "cogs.anime": "Anime",
    "cogs.profile": "Profile",
    "cogs.recommendations": "Recommendations",
}

# ------------------------------------------------------
# Load All Cogs
# ------------------------------------------------------
async def load_cogs():
    for cog_path, class_name in COGS.items():
        try:
            await bot.load_extension(cog_path)
            logger.info("✅ Loaded cog: %s", class_name)
        except commands.errors.ExtensionAlreadyLoaded:
            logger.warning("⚠ Cog '%s' already loaded, skipping", class_name)
        except Exception as e:
            logger.exception("❌ Failed to load cog '%s': %s", class_name, e)

# ------------------------------------------------------
# Bot Ready Event
# ------------------------------------------------------
@bot.event
async def on_ready():
    logger.info("Bot is starting...")

    # Initialize database tables
    try:
        await init_db()
        await init_challenge_rules_table()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.exception("❌ Database initialization failed: %s", e)

    guild = discord.Object(id=GUILD_ID)

    # Sync all slash commands to the guild
    try:
        synced_commands = await bot.tree.sync(guild=guild)
        logger.info("✅ Synced %d slash commands to guild %s", len(synced_commands), GUILD_ID)
    except Exception as e:
        logger.exception("❌ Failed to sync slash commands: %s", e)

    # Verify loaded cogs
    for _, class_name in COGS.items():  # underscore used for unused cog_path
        if bot.get_cog(class_name):
            logger.info("✅ Cog '%s' is loaded and ready", class_name)
        else:
            logger.warning("❌ Cog '%s' is NOT loaded", class_name)

    logger.info("✅ Logged in as %s (ID: %s)", bot.user, bot.user.id)

# ------------------------------------------------------
# Main Entry Point
# ------------------------------------------------------
async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
