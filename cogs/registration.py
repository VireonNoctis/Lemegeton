import discord
from discord import app_commands
from discord.ext import commands
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

    @app_commands.command(
        name="register",
        description="Register yourself to the system with your AniList username"
    )
    @app_commands.describe(username="Your AniList username")
    async def register(self, interaction: discord.Interaction, username: str):
        username = username.strip()
        logger.info(f"User {interaction.user.id} attempting to register with username '{username}'")

        # --- Username Validation ---
        if not username:
            logger.info(f"User {interaction.user.id} submitted an empty username")
            await interaction.response.send_message("❌ Username cannot be empty.", ephemeral=True)
            return

        if len(username) > MAX_USERNAME_LENGTH:
            logger.info(f"User {interaction.user.id} submitted a too-long username '{username}'")
            await interaction.response.send_message(
                f"❌ Username too long. Maximum {MAX_USERNAME_LENGTH} characters allowed.", ephemeral=True
            )
            return

        if not re.match(USERNAME_REGEX, username):
            logger.info(f"User {interaction.user.id} submitted invalid characters in username '{username}'")
            await interaction.response.send_message(
                "❌ Invalid username. Only letters, numbers, underscores, and hyphens are allowed.", ephemeral=True
            )
            return

        # --- Main Logic with Exception Handling ---
        try:
            user: Optional[dict] = await get_user(interaction.user.id)
            if user:
                # Update existing user
                await update_username(interaction.user.id, username)
                logger.info(f"Updated username for user {interaction.user.id} -> '{username}'")
                await interaction.response.send_message(
                    f"✅ Your username has been updated to **{username}**!", ephemeral=True
                )
            else:
                # Add new user
                await add_user(interaction.user.id, username)
                logger.info(f"Registered new user {interaction.user.id} with username '{username}'")
                await interaction.response.send_message(
                    f"🎉 Successfully registered with username **{username}**!", ephemeral=True
                )
        except Exception as e:
            logger.exception(f"Error in /register for user {interaction.user.id}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while registering you. Please try again later.", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while registering you. Please try again later.", ephemeral=True
                )

# ------------------------------------------------------
# Cog Setup
# ------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))
