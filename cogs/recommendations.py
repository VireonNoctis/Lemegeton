import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Dict
import aiohttp
import asyncio
from helpers.media_helper import fetch_anilist_entries, fetch_media
from database import get_all_users

import logging
logger = logging.getLogger("RecommendationsCog")

class Recommendations(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="recommendations",
        description="Get top AniList recommendations based on highly rated media by registered users"
    )
    async def recommendations(self, interaction: discord.Interaction, media_type: str = "MANGA"):
        await interaction.response.defer()
        media_type = media_type.upper()
        if media_type not in ["MANGA", "ANIME"]:
            await interaction.followup.send("Media type must be 'MANGA' or 'ANIME'.", ephemeral=True)
            return

        users = await get_all_users()
        if not users:
            await interaction.followup.send("No registered users found.", ephemeral=True)
            return

        recommendations_votes: Dict[str, int] = {}
        semaphore = asyncio.Semaphore(5)

        async def process_user(username: str):
            async with semaphore:
                entries = await fetch_anilist_entries(username, media_type)
                # Filter for high-rated entries
                high_rated = [e for e in entries if e["score"] >= 7.5]

                # Fetch recommendations for each high-rated media
                async with aiohttp.ClientSession() as session:
                    for entry in high_rated:
                        try:
                            media_info = await fetch_media(session, media_type, entry["id"], users=None)
                            if not media_info:
                                continue
                            # Extract recommended titles from description
                            desc = media_info.description or ""
                            # Simple regex to catch titles (could be improved with better parsing)
                            rec_titles = [line.strip() for line in desc.split("\n") if line.strip()]
                            for title in rec_titles:
                                # Increment vote
                                recommendations_votes[title] = recommendations_votes.get(title, 0) + 1
                        except Exception as e:
                            logger.warning(f"Failed to process media {entry['id']} for {username}: {e}")

        await asyncio.gather(*(process_user(user[1]) for user in users))

        # Sort top recommendations
        top_recs = sorted(recommendations_votes.items(), key=lambda x: x[1], reverse=True)[:10]
        if not top_recs:
            await interaction.followup.send("No recommendations found from high-rated entries.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Top {media_type.capitalize()} Recommendations",
            description="\n".join([f"{i+1}. {title} — Votes: {votes}" for i, (title, votes) in enumerate(top_recs)]),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Recommendations(bot))
