import discord
from discord.ext import commands
from discord import app_commands
from typing import Dict
import aiohttp
import asyncio
import random
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
    @app_commands.describe(
        media_type="Which type of recommendations do you want to see?"
    )
    @app_commands.choices(
        media_type=[
            app_commands.Choice(name="Manga", value="MANGA"),
            app_commands.Choice(name="Anime", value="ANIME"),
            app_commands.Choice(name="Light Novels", value="LN")
        ]
    )
    async def recommendations(
        self,
        interaction: discord.Interaction,
        media_type: app_commands.Choice[str] = None
    ):
        await interaction.response.defer()

        media_type = media_type.value if media_type else "MANGA"
        users = await get_all_users()
        if not users:
            await interaction.followup.send("⚠️ No registered users found.", ephemeral=True)
            return

        recommendations_votes: Dict[str, int] = {}
        semaphore = asyncio.Semaphore(5)

        async def process_user(username: str):
            async with semaphore:
                # LN = AniList "MANGA" entries but format = "NOVEL"
                fetch_type = "MANGA" if media_type == "LN" else media_type
                entries = await fetch_anilist_entries(username, fetch_type)
                if not entries:
                    return "NO_ENTRIES"

                # If LN, filter only novels
                if media_type == "LN":
                    entries = [e for e in entries if e.get("format") == "NOVEL"]

                if not entries:
                    return "NO_ENTRIES"

                # Collect all IDs user already has
                user_media_ids = {e["id"] for e in entries}

                # Filter for high-rated entries (7.5+ out of 10)
                high_rated = [e for e in entries if e.get("score", 0) >= 7.5]

                async with aiohttp.ClientSession() as session:
                    for entry in high_rated:
                        try:
                            media_info = await fetch_media(session, fetch_type, entry["id"])
                            if not media_info:
                                continue

                            rec_edges = media_info.get("recommendations", {}).get("edges", [])
                            for edge in rec_edges:
                                rec_media = edge["node"]["mediaRecommendation"]
                                votes = edge["node"].get("rating", 1)

                                if not rec_media:
                                    continue

                                rec_id = rec_media["id"]
                                # 🔥 Skip if user already has this title
                                if rec_id in user_media_ids:
                                    continue

                                title = rec_media["title"].get("romaji") \
                                        or rec_media["title"].get("english") \
                                        or "Unknown"

                                recommendations_votes[title] = recommendations_votes.get(title, 0) + votes

                        except Exception as e:
                            logger.warning(f"⚠️ Failed to process media {entry['id']} for {username}: {e}")

        # Run all users in parallel
        results = await asyncio.gather(*(process_user(user[1]) for user in users))

        # If no entries for chosen type
        if all(r == "NO_ENTRIES" or r is None for r in results):
            await interaction.followup.send(
                f"⚠️ Looks like no registered users have any **{media_type.capitalize()}** yet. Add some to AniList first!",
                ephemeral=True
            )
            return

        # Sort and pick top 10
        top_recs = sorted(recommendations_votes.items(), key=lambda x: x[1], reverse=True)[:10]
        if not top_recs:
            await interaction.followup.send(
                f"⚠️ No new {media_type.lower()} recommendations found. Try rating more titles first!",
                ephemeral=True
            )
            return

        # Random embed color
        random_color = discord.Color(random.randint(0, 0xFFFFFF))

        # Media type icons
        type_icons = {
            "ANIME": "🎬",
            "MANGA": "📖",
            "LN": "📚"
        }

        # Build embed
        embed = discord.Embed(
            title=f"{type_icons.get(media_type, '')} Top {media_type.capitalize()} Recommendations",
            description="(Only showing **new titles** you haven’t added yet!)",
            color=random_color
        )
        for i, (title, votes) in enumerate(top_recs, start=1):
            embed.add_field(name=f"{i}. {title}", value=f"Votes: {votes}", inline=False)

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Recommendations(bot))
