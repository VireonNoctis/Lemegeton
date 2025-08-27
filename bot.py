import discord
from discord.ext import commands
from config import TOKEN, GUILD_ID, BOT_ID
from database import init_db, init_challenge_rules_table
import logging
import asyncio

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
# List of Cog Extensions
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
    "cogs.auto_embed": "AutoEmbed"
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
            logger.info("⚠ Cog '%s' already loaded, skipping", class_name)
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
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.exception("❌ Database initialization failed: %s", e)

    guild = discord.Object(id=GUILD_ID)

    # Delete old guild commands
    try:
        existing_commands = await bot.tree.fetch_commands(guild=guild)
        for cmd in existing_commands:
            await bot.tree.delete_command(cmd.name, guild=guild)
            logger.info("🗑 Deleted old command '%s' from guild", cmd.name)
    except Exception as e:
        logger.exception("❌ Failed to delete old commands: %s", e)

    # Sync all slash commands to the guild
    try:
        synced = await bot.tree.sync(guild=guild)
        logger.info("✅ Synced %d slash commands to guild %s", len(synced), GUILD_ID)
    except Exception as e:
        logger.exception("❌ Failed to sync slash commands: %s", e)

    # Verify loaded cogs
    for cog_path, class_name in COGS.items():
        if bot.get_cog(class_name):
            logger.info("✅ Cog '%s' is loaded and ready!", class_name)
        else:
            logger.warning("❌ Cog '%s' is NOT loaded!", class_name)

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
