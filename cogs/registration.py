import discord
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID
from database import add_user, get_user, update_username
import logging
import re
import aiohttp
from typing import Optional

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("RegistrationCog")

# Constants
MAX_USERNAME_LENGTH = 50
USERNAME_REGEX = r"^[\w-]+$"

def is_valid_username(username: str) -> bool:
    return bool(re.match(USERNAME_REGEX, username)) and 0 < len(username) <= MAX_USERNAME_LENGTH

# -------------------------------
# Helper: fetch AniList ID
# -------------------------------
async def fetch_anilist_id(anilist_username: str) -> Optional[int]:
    query = """
    query ($name: String) {
      User(name: $name) { id }
    }
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://graphql.anilist.co",
            json={"query": query, "variables": {"name": anilist_username}}
        ) as resp:
            data = await resp.json()
            user = data.get("data", {}).get("User")
            if user and "id" in user:
                return user["id"]
            return None

# -------------------------------
# Registration Cog
# -------------------------------
class Registration(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def handle_register(self, user_id: int, anilist_username: str) -> str:
        anilist_username = anilist_username.strip()
        if not anilist_username:
            return "❌ AniList username cannot be empty."
        if len(anilist_username) > MAX_USERNAME_LENGTH:
            return f"❌ Username too long. Maximum {MAX_USERNAME_LENGTH} characters allowed."
        if not re.match(USERNAME_REGEX, anilist_username):
            return "❌ Invalid username. Only letters, numbers, underscores, and hyphens are allowed."

        # Fetch AniList ID
        anilist_id = await fetch_anilist_id(anilist_username)
        if not anilist_id:
            return f"❌ Could not find AniList user **{anilist_username}**."

        try:
            user: Optional[dict] = await get_user(user_id)
            if user:
                await update_username(user_id, anilist_username)
                logger.info(f"Updated username for user {user_id} -> '{anilist_username}'")
                return f"✅ Your AniList username has been updated to **{anilist_username}**!"
            else:
                await add_user(user_id, anilist_username, anilist_username, anilist_id)
                logger.info(f"Registered new user {user_id} with AniList username '{anilist_username}' and ID {anilist_id}")
                return f"🎉 Successfully registered with AniList username **{anilist_username}**!"
        except Exception as e:
            logger.exception(f"Error in handle_register for user {user_id}")
            return "❌ An error occurred while registering you. Please try again later."

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="register",
        description="Register yourself with your AniList username"
    )
    @app_commands.describe(username="Your AniList username")
    async def register(self, interaction: discord.Interaction, username: str):
        result = await self.handle_register(interaction.user.id, username)
        await interaction.response.send_message(result, ephemeral=True)


# -------------------------------
# Cog Setup
# -------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Registration(bot))
