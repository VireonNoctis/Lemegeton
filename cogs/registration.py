import discord
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID
from database import add_user, get_user, update_username  # Ensure these are async functions
import logging
import re
from typing import Optional

# ------------------------------------------------------
# Logging Setup
# ------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("RegistrationCog")

# ------------------------------------------------------
# Constants and Validation
# ------------------------------------------------------
MAX_USERNAME_LENGTH = 50
USERNAME_REGEX = r"^[\w-]+$"

def is_valid_username(username: str) -> bool:
    """Check if username meets length and character requirements."""
    return bool(re.match(USERNAME_REGEX, username)) and 0 < len(username) <= MAX_USERNAME_LENGTH

# ------------------------------------------------------
# Registration Cog
# ------------------------------------------------------
class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Core logic callable from tests ---
    async def handle_register(self, user_id: int, username: str) -> str:
        username = username.strip()
        if not username:
            return "❌ Username cannot be empty."
        if len(username) > MAX_USERNAME_LENGTH:
            return f"❌ Username too long. Maximum {MAX_USERNAME_LENGTH} characters allowed."
        if not re.match(USERNAME_REGEX, username):
            return "❌ Invalid username. Only letters, numbers, underscores, and hyphens are allowed."

        try:
            user: Optional[dict] = await get_user(user_id)
            if user:
                await update_username(user_id, username)
                logger.info(f"Updated username for user {user_id} -> '{username}'")
                return f"✅ Your username has been updated to **{username}**!"
            else:
                await add_user(user_id, username)
                logger.info(f"Registered new user {user_id} with username '{username}'")
                return f"🎉 Successfully registered with username **{username}**!"
        except Exception as e:
            logger.exception(f"Error in handle_register for user {user_id}")
            return "❌ An error occurred while registering you. Please try again later."

    # --- Discord Slash Command ---
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="register",
        description="Register yourself to the system with your AniList username"
    )
    @app_commands.describe(username="Your AniList username")
    async def register(self, interaction: discord.Interaction, username: str):
        result = await self.handle_register(interaction.user.id, username)
        await interaction.response.send_message(result, ephemeral=True)

# ------------------------------------------------------
# Cog Setup
# ------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))
