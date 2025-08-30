import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
from helpers.media_helper import fetch_media_by_title

import logging
logger = logging.getLogger("SearchSimilarCog")


class SearchSimilar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

        try:
            async with aiohttp.ClientSession() as session:
                media_info = await fetch_media_by_title(session, title, fetch_type)
                
                if not media_info:
                    await interaction.followup.send(
                        f"⚠️ Could not find a **{media_type.lower()}** titled '{title}'",
                        ephemeral=True
                    )
                    return

                similar_edges = media_info.get("relations", {}).get("edges", [])
                similar_series = [
                    edge["node"] for edge in similar_edges
                    if edge["relationType"] in ["ADAPTATION", "PREQUEL", "SEQUEL", "SIDE_STORY", "SPIN_OFF", "ALTERNATIVE"]
                ]

                if not similar_series:
                    await interaction.followup.send(
                        f"⚠️ No similar {media_type.lower()} found for '{title}'",
                        ephemeral=True
                    )
                    return

                # Sort or pick top 10 (if needed)
                top_similar = similar_series[:10]

                # Random embed color
                random_color = discord.Color(random.randint(0, 0xFFFFFF))

                # Media type icons
                type_icons = {
                    "ANIME": "🎬",
                    "MANGA": "📖",
                    "LN": "📚"
                }

                embed = discord.Embed(
                    title=f"{type_icons.get(media_type, '')} Similar {media_type.capitalize()} to '{title}'",
                    color=random_color
                )

                for i, media in enumerate(top_similar, start=1):
                    media_title = media["title"].get("romaji") \
                                  or media["title"].get("english") \
                                  or "Unknown"
                    embed.add_field(
                        name=f"{i}. {media_title}",
                        value=f"Type: {media.get('format', 'Unknown')} | Status: {media.get('status', 'Unknown')}",
                        inline=False
                    )

                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.exception(f"⚠️ Error searching similar series for '{title}': {e}")
            await interaction.followup.send(
                "⚠️ Something went wrong while searching for similar series.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(SearchSimilar(bot))
