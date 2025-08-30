import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
from config import GUILD_ID
from helpers.media_helper import fetch_media_by_title

import logging
logger = logging.getLogger("SearchSimilarCog")


class SearchSimilar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="search_similar",
        description="Find similar series based on a given title"
    )
    @app_commands.describe(
        title="The title of the anime/manga/light novel you want to find similar series for"
    )
    @app_commands.choices(
        media_type=[
            app_commands.Choice(name="Manga", value="MANGA"),
            app_commands.Choice(name="Anime", value="ANIME"),
            app_commands.Choice(name="Light Novels", value="LN")
        ]
    )
    async def search_similar(
        self,
        interaction: discord.Interaction,
        title: str,
        media_type: app_commands.Choice[str] = None
    ):
        await interaction.response.defer()
        media_type = media_type.value if media_type else "MANGA"
        fetch_type = "MANGA" if media_type == "LN" else media_type

        logger.info(f"Fetching similar series for '{title}' ({media_type})")

        try:
            async with aiohttp.ClientSession() as session:
                media_info = await fetch_media_by_title(session, title, fetch_type)
                if not media_info:
                    logger.warning(f"Could not find media titled '{title}'")
                    await interaction.followup.send(
                        f"⚠️ Could not find a **{media_type.lower()}** titled '{title}'",
                        ephemeral=True
                    )
                    return

                cover_image = media_info.get("coverImage", {}).get("large")
                banner_image = media_info.get("bannerImage")
                random_color = discord.Color(random.randint(0, 0xFFFFFF))
                type_icons = {"ANIME": "🎬", "MANGA": "📖", "LN": "📚"}

                embed = discord.Embed(
                    title=f"{type_icons.get(media_type, '')} Similar {media_type.capitalize()} to '{title}'",
                    description=(media_info.get("description", "No description available")[:200] + "..."),
                    color=random_color
                )

                if cover_image:
                    embed.set_thumbnail(url=cover_image)
                if banner_image:
                    embed.set_image(url=banner_image)

                genres = ", ".join(media_info.get("genres", [])) or "Unknown"
                avg_score = media_info.get("averageScore", "N/A")
                status = media_info.get("status", "Unknown")
                format_ = media_info.get("format", "Unknown")

                embed.add_field(
                    name="Info",
                    value=f"**Format:** {format_}\n**Status:** {status}\n**Score:** {avg_score}\n**Genres:** {genres}",
                    inline=False
                )

                similar_edges = media_info.get("relations", {}).get("edges", [])
                similar_series = [
                    edge["node"] for edge in similar_edges
                    if edge["relationType"] in ["ADAPTATION", "PREQUEL", "SEQUEL", "SIDE_STORY", "SPIN_OFF", "ALTERNATIVE"]
                ]

                if similar_series:
                    for i, media in enumerate(similar_series[:10], start=1):
                        media_title = media["title"].get("romaji") or media["title"].get("english") or "Unknown"
                        relation_type = media.get("relationType", "Related")
                        media_format = media.get("format", "Unknown")
                        media_status = media.get("status", "Unknown")
                        thumb = media.get("coverImage", {}).get("small")

                        # Use Markdown link with image if available
                        if thumb:
                            field_value = f"[​]({thumb}) Type: {media_format} | Status: {media_status}"
                        else:
                            field_value = f"Type: {media_format} | Status: {media_status}"

                        embed.add_field(
                            name=f"{i}. {media_title} ({relation_type})",
                            value=field_value,
                            inline=True
                        )

                    logger.info(f"Found {len(similar_series)} similar series for '{title}'")
                else:
                    embed.add_field(
                        name="No similar series found",
                        value=f"⚠️ No similar {media_type.lower()} found for '{title}'",
                        inline=False
                    )
                    logger.info(f"No similar series found for '{title}'")

                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception(f"Error searching similar series for '{title}': {e}")
            await interaction.followup.send(
                "⚠️ Something went wrong while searching for similar series.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(SearchSimilar(bot))
