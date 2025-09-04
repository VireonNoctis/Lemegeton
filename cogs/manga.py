import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import logging
from typing import List, Dict, Optional

from config import GUILD_ID
from database import get_all_users  # ✅ Using get_all_users

logger = logging.getLogger("MangaCog")
API_URL = "https://graphql.anilist.co"


class Manga(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache: Dict[str, List[Dict]] = {}

    # --------------------------------------------------
    # Fetch Manga Info from AniList
    # --------------------------------------------------
    async def fetch_manga(self, query: str) -> List[Dict]:
        graphql_query = {
            "query": """
            query ($search: String) {
                Page(perPage: 10) {
                    media(search: $search, type: MANGA) {
                        id
                        title { romaji english }
                        description(asHtml: false)
                        averageScore
                        siteUrl
                        status
                        chapters
                        volumes
                        startDate { year month day }
                        endDate { year month day }
                        genres
                        coverImage { large medium }
                    }
                }
            }
            """,
            "variables": {"search": query}
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=graphql_query) as response:
                if response.status != 200:
                    logger.error(f"Failed AniList request: {response.status}")
                    return []
                data = await response.json()
                return data.get("data", {}).get("Page", {}).get("media", [])

    # --------------------------------------------------
    # Fetch AniList Progress & Rating for a User
    # --------------------------------------------------
    async def fetch_user_anilist_progress(self, anilist_username: str, media_id: int) -> Optional[Dict]:
        """Return {'progress': int|None, 'rating10': float|None} for the given user/media, or None."""
        if not anilist_username or not media_id:
            return None

        query = """
        query($userName: String, $mediaId: Int) {
          MediaList(userName: $userName, mediaId: $mediaId, type: MANGA) {
            progress
            score
          }
        }
        """
        variables = {"userName": anilist_username, "mediaId": media_id}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL, json={"query": query, "variables": variables}) as resp:
                    if resp.status != 200:
                        logger.warning(f"AniList fetch failed ({resp.status}) for {anilist_username=} {media_id=}")
                        return None
                    payload = await resp.json()
        except Exception:
            logger.exception("Error requesting AniList user progress")
            return None

        entry = payload.get("data", {}).get("MediaList")
        if not entry:
            return None

        progress = entry.get("progress")
        score = entry.get("score")  # AniList score can be 0–100 or 0–10 depending on user settings

        rating10: Optional[float]
        if score is None:
            rating10 = None
        else:
            try:
                rating10 = float(score) if float(score) <= 10 else round(float(score) / 10.0, 1)
            except Exception:
                rating10 = None

        return {"progress": progress, "rating10": rating10}

    # --------------------------------------------------
    # /manga Command – Now Shows Progress for All Users
    # --------------------------------------------------
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="manga", description="Search for manga info + all users' progress")
    @app_commands.describe(title="Manga title to search for")
    async def manga_search(self, interaction: discord.Interaction, title: str):
        await interaction.response.defer()

        # ✅ Fetch manga details
        results = await self.fetch_manga(title)
        if not results:
            await interaction.followup.send("❌ No results found.", ephemeral=True)
            return

        manga = results[0]

        # Format dates
        start_date = manga.get("startDate", {})
        end_date = manga.get("endDate", {})
        start_str = f"{start_date.get('year','?')}-{start_date.get('month','?')}-{start_date.get('day','?')}"
        end_str = (
            f"{end_date.get('year','?')}-{end_date.get('month','?')}-{end_date.get('day','?')}"
            if end_date else "Ongoing"
        )

        # Description handling
        raw_description = manga.get("description") or "No description available."
        description = (
            raw_description[:400] + "..."
            if len(raw_description) > 400
            else raw_description
        )
        genres = ", ".join(manga.get("genres", [])) or "Unknown"

        # --------------------------------------------------
        # Embed Layout
        # --------------------------------------------------
        embed = discord.Embed(
            title=f"📚 {manga['title']['romaji'] or manga['title']['english']}",
            url=manga["siteUrl"],
            description=description,
            color=discord.Color.purple()
        )

        cover_url = manga.get("coverImage", {}).get("medium") or manga.get("coverImage", {}).get("large")
        if cover_url:
            embed.set_thumbnail(url=cover_url)

        embed.add_field(name="⭐ Average Score", value=f"{manga.get('averageScore', 'N/A')}%", inline=True)
        embed.add_field(name="📌 Status", value=manga.get("status", "Unknown"), inline=True)
        embed.add_field(name="📖 Chapters", value=manga.get("chapters", '?'), inline=True)
        embed.add_field(name="📚 Volumes", value=manga.get("volumes", '?'), inline=True)
        embed.add_field(name="🎭 Genres", value=genres, inline=False)
        embed.add_field(name="📅 Published", value=f"**Start:** {start_str}\n**End:** {end_str}", inline=False)

        # --------------------------------------------------
        # ✅ Show progress for all registered users (table-style)
        # --------------------------------------------------
        users = await get_all_users()
        if users:
            # Table header
            progress_lines = ["`{:<20} {:<10} {:<7}`".format("User", "Chapters", "Rating")]
            progress_lines.append("`{:-<20} {:-<10} {:-<7}`".format("", "", ""))  # separator

            for user in users:
                # Assuming structure: (discord_id, discord_name, anilist_username)
                discord_name = user[2]  # Discord username
                anilist_username = user[2] if len(user) > 2 else None

                # Fetch AniList progress for this manga
                anilist_progress = await self.fetch_user_anilist_progress(anilist_username, manga.get("id", 0))

                # Skip users with failed fetches
                if not anilist_progress:
                    chapter_text = "—"
                    rating_text = "—"
                else:
                    total_ch = manga.get("chapters") or "?"
                    chapter_text = f"{anilist_progress['progress']}/{total_ch}" if anilist_progress.get("progress") is not None else "—"
                    rating_text = f"{anilist_progress['rating10']}/10" if anilist_progress.get("rating10") is not None else "—"


                # Format chapter progress
                chapter_text = "—"
                if anilist_progress and anilist_progress.get("progress") is not None:
                    total_ch = manga.get("chapters") or "?"
                    chapter_text = f"{anilist_progress['progress']}/{total_ch}"

                # Format rating
                rating_text = "—"
                if anilist_progress and anilist_progress.get("rating10") is not None:
                    rating_text = f"{anilist_progress['rating10']}/10"

                # Append formatted line
                progress_lines.append(f"`{discord_name:<20} {chapter_text:<10} {rating_text:<7}`")

            # Add to embed
            embed.add_field(
                name="👥 Registered Users' Progress",
                value="\n".join(progress_lines),
                inline=False
            )


        embed.set_footer(text="Fetched from AniList | Use /manga to search again")
        await interaction.followup.send(embed=embed)

    # --------------------------------------------------
    # Autocomplete
    # --------------------------------------------------
    @manga_search.autocomplete("title")
    async def autocomplete_manga(self, interaction: discord.Interaction, current: str):
        if len(current) < 2:
            return []

        results = await self.fetch_manga(current)
        choices = []
        for manga in results[:10]:
            title = manga["title"].get("romaji") or manga["title"].get("english") or "Unknown"
            title = title[:100]
            choices.append(app_commands.Choice(name=title, value=title))

        return choices


async def setup(bot: commands.Bot):
    await bot.add_cog(Manga(bot))
