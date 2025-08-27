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
logger = logging.getLogger("AnimeCog")

# ------------------------------------------------------
# Anime Cog
# ------------------------------------------------------
class Anime(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Anime cog loaded")

    # --- Autocomplete for anime titles ---
    async def autocomplete_anime(self, interaction: discord.Interaction, current: str):
        if current.isdigit():
            return []  # No autocomplete for IDs

        query = """
        query ($search: String) {
            Page(perPage: 5) {
                media(search: $search, type: ANIME) {
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
                        logger.info(f"AniList API returned status {resp.status} for autocomplete query '{current}'")
                        return []
                    data = await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"AniList API request failed for autocomplete query '{current}': {e}")
            return []

        results = data.get("data", {}).get("Page", {}).get("media", [])
        return [
            app_commands.Choice(
                name=m["title"].get("english") or m["title"].get("romaji") or "Unknown",
                value=m["title"].get("english") or m["title"].get("romaji") or "Unknown"
            )
            for m in results
        ]

    # --- /anime command ---
    @app_commands.command(
        name="anime",
        description="Search AniList for anime by title or ID"
    )
    @app_commands.describe(query="Anime title or AniList ID")
    @app_commands.autocomplete(query=autocomplete_anime)
    async def anime(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()  # Visible to everyone
        logger.info(f"User {interaction.user.id} requested anime search for '{query}'")

        try:
            async with aiohttp.ClientSession() as session:
                users = await get_all_users() or []
                embed = await fetch_media(session, "ANIME", query, users, max_description=500)

            if embed is None:
                await interaction.followup.send("❌ Anime not found!", ephemeral=True)
                logger.info(f"Anime search for '{query}' returned no results")
                return

            await interaction.followup.send(embed=embed)
            logger.info(f"Anime search for '{query}' completed successfully")
        except Exception as e:
            logger.exception(f"Error processing /anime command for query '{query}': {e}")
            await interaction.followup.send("❌ An error occurred while searching for anime.", ephemeral=True)

# ------------------------------------------------------
# Cog Setup
# ------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Anime(bot))
