import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from database import get_all_users
from helpers.media_helper import fetch_media
import logging

# ------------------------------------------------------
# Simple Logging Setup
# ------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("MangaCog")  # clear name for logging

# ------------------------------------------------------
# Manga Cog
# ------------------------------------------------------
class Manga(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Autocomplete for manga titles ---
    async def autocomplete_manga(self, interaction: discord.Interaction, current: str):
        if not current or current.isdigit():
            return []

        query = """
        query ($search: String) {
            Page(perPage: 5) {
                media(search: $search, type: MANGA) {
                    title { romaji english }
                }
            }
        }
        """
        variables = {"search": current}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://graphql.anilist.co", json={"query": query, "variables": variables}) as resp:
                    if resp.status != 200:
                        logger.info(f"AniList API returned status {resp.status}")
                        return []
                    data = await resp.json()
        except aiohttp.ClientError as e:
            logger.warning(f"AniList API request failed: {e}")
            return []

        media_list = data.get("data", {}).get("Page", {}).get("media", [])
        return [
            app_commands.Choice(
                name=m["title"].get("english") or m["title"].get("romaji") or "Unknown",
                value=m["title"].get("english") or m["title"].get("romaji") or "Unknown"
            )
            for m in media_list
        ]

    # --- /manga command ---
    @app_commands.command(
        name="manga",
        description="Search AniList for manga by title or ID"
    )
    @app_commands.describe(query="Manga title or AniList ID")
    @app_commands.autocomplete(query=autocomplete_manga)
    async def manga(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()  # Allow longer processing
        logger.info(f"User {interaction.user.id} requested manga '{query}'")

        # Fetch users from DB
        try:
            users = await get_all_users() or []
            logger.debug(f"Fetched {len(users)} users from database")
        except Exception as e:
            logger.warning(f"Error fetching users from DB: {e}")
            users = []

        # Fetch manga data
        try:
            async with aiohttp.ClientSession() as session:
                embed = await fetch_media(session, "MANGA", query, users, max_description=500)

            if not embed:
                logger.info(f"Manga '{query}' not found")
                await interaction.followup.send("❌ Manga not found!", ephemeral=True)
                return

            await interaction.followup.send(embed=embed)
            logger.info(f"Sent manga embed for '{query}' to user {interaction.user.id}")

        except Exception as e:
            logger.exception(f"Error processing /manga command for '{query}': {e}")
            await interaction.followup.send(
                "❌ An error occurred while searching for manga.", ephemeral=True
            )


# ------------------------------------------------------
# Cog Setup
# ------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Manga(bot))
