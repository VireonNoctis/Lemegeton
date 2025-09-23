import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
import logging
from pathlib import Path

from helpers.media_helper import fetch_media_by_title

# ------------------------------------------------------
# Logging Setup - Clears on each bot run
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "search_similar.log"

# Clear the log file on startup
if LOG_FILE.exists():
    LOG_FILE.unlink()

# Create logger
logger = logging.getLogger("SearchSimilar")
logger.setLevel(logging.INFO)

# Remove existing handlers to avoid duplicates
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create file handler
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(file_handler)

logger.info("SearchSimilar cog logging initialized - log file cleared")

# ------------------------------------------------------
# Constants
# ------------------------------------------------------
TYPE_ICONS = {"ANIME": "🎬", "MANGA": "📖", "LN": "📚"}
VALID_RELATION_TYPES = ["ADAPTATION", "PREQUEL", "SEQUEL", "SIDE_STORY", "SPIN_OFF", "ALTERNATIVE"]
MAX_SIMILAR_RESULTS = 10


class SearchSimilar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("SearchSimilar cog initialized")

    @app_commands.command(
        name="search_similar",
        description="🔍 Find similar series based on a given title"
    )
    @app_commands.describe(
        title="The title of the anime/manga/light novel you want to find similar series for",
        media_type="Choose the type of media to search for"
    )
    @app_commands.choices(
        media_type=[
            app_commands.Choice(name="Manga 📖", value="MANGA"),
            app_commands.Choice(name="Anime 🎬", value="ANIME"),
            app_commands.Choice(name="Light Novels 📚", value="LN")
        ]
    )
    async def search_similar(
        self,
        interaction: discord.Interaction,
        title: str,
        media_type: app_commands.Choice[str] = None
    ):
        selected_type = media_type.value if media_type else "MANGA"
        logger.info(f"SearchSimilar command invoked by {interaction.user} (ID: {interaction.user.id}) - Title: '{title}', Type: {selected_type}")
        
        await interaction.response.defer()

        try:
            fetch_type = "MANGA" if selected_type == "LN" else selected_type
            logger.info(f"Searching for media titled '{title}' with type {fetch_type}")

            async with aiohttp.ClientSession() as session:
                media_info = await fetch_media_by_title(session, title, fetch_type)
                
                if not media_info:
                    logger.warning(f"No media found for title '{title}' with type {selected_type}")
                    await interaction.followup.send(
                        f"⚠️ Could not find a **{selected_type.lower()}** titled '{title}'. Please check the spelling and try again.",
                        ephemeral=True
                    )
                    return

                logger.info(f"Successfully found media for '{title}': ID {media_info.get('id', 'unknown')}")
                
                # Build and send embed
                embed = self._build_similar_embed(media_info, title, selected_type)
                await interaction.followup.send(embed=embed)
                logger.info(f"SearchSimilar command completed successfully for {interaction.user}")

        except Exception as e:
            logger.error(f"Exception in search_similar command for {interaction.user} (ID: {interaction.user.id}): {e}")
            await interaction.followup.send(
                "❌ An error occurred while searching for similar series. Please try again later.",
                ephemeral=True
            )

    def _build_similar_embed(self, media_info: dict, original_title: str, media_type: str):
        """Build a Discord embed for similar series results"""
        random_color = discord.Color(random.randint(0, 0xFFFFFF))
        
        # Get basic media information
        cover_image = media_info.get("coverImage", {}).get("large")
        banner_image = media_info.get("bannerImage")
        description = media_info.get("description", "No description available")
        
        # Truncate description if too long
        if len(description) > 300:
            description = description[:297] + "..."
        
        embed = discord.Embed(
            title=f"{TYPE_ICONS.get(media_type, '🔍')} Similar {media_type.capitalize()} to '{original_title}'",
            description=description,
            color=random_color
        )

        # Set images
        if cover_image:
            embed.set_thumbnail(url=cover_image)
        if banner_image:
            embed.set_image(url=banner_image)

        # Add basic info field
        self._add_media_info_field(embed, media_info)
        
        # Process and add similar series
        similar_count = self._add_similar_series_fields(embed, media_info, original_title)
        
        # Set footer with result count
        embed.set_footer(text=f"Found {similar_count} related series • Data from AniList")
        
        return embed

    def _add_media_info_field(self, embed: discord.Embed, media_info: dict):
        """Add basic media information to the embed"""
        genres = ", ".join(media_info.get("genres", [])) or "Unknown"
        avg_score = media_info.get("averageScore") or "N/A"
        status = media_info.get("status", "Unknown")
        format_ = media_info.get("format", "Unknown")

        embed.add_field(
            name="📊 Media Information",
            value=f"**Format:** {format_}\n**Status:** {status}\n**Score:** {avg_score}/100\n**Genres:** {genres}",
            inline=False
        )

    def _add_similar_series_fields(self, embed: discord.Embed, media_info: dict, original_title: str):
        """Add similar series fields to the embed and return count"""
        similar_edges = media_info.get("relations", {}).get("edges", [])
        similar_series = [
            edge for edge in similar_edges
            if edge.get("relationType") in VALID_RELATION_TYPES
        ]

        if not similar_series:
            embed.add_field(
                name="❌ No Related Series Found",
                value=f"No similar series found for '{original_title}'. This might be a standalone work or the relations data is not available.",
                inline=False
            )
            logger.info(f"No similar series found for '{original_title}'")
            return 0

        # Limit results and process them
        limited_series = similar_series[:MAX_SIMILAR_RESULTS]
        logger.info(f"Found {len(similar_series)} related series for '{original_title}', showing {len(limited_series)}")

        for i, edge in enumerate(limited_series, start=1):
            media = edge.get("node", {})
            relation_type = edge.get("relationType", "Related")
            
            media_title = media.get("title", {}).get("romaji") or media.get("title", {}).get("english") or "Unknown"
            media_format = media.get("format", "Unknown")
            media_status = media.get("status", "Unknown")
            
            field_value = f"**Type:** {media_format}\n**Status:** {media_status}\n**Relation:** {relation_type.replace('_', ' ').title()}"
            
            embed.add_field(
                name=f"{i}. {media_title}",
                value=field_value,
                inline=True
            )
            
            # Add spacing every 3 fields for better readability
            if i % 3 == 0 and i < len(limited_series):
                embed.add_field(name="\u200b", value="\u200b", inline=False)

        return len(limited_series)

    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("SearchSimilar cog loaded successfully")

    async def cog_unload(self):
        """Called when the cog is unloaded"""
        logger.info("SearchSimilar cog unloaded")


async def setup(bot: commands.Bot):
    await bot.add_cog(SearchSimilar(bot))
