import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import logging
from typing import List, Dict, Optional
from discord.ui import View, Button
from config import GUILD_ID
from database import get_all_users

logger = logging.getLogger("BrowseCog")
API_URL = "https://graphql.anilist.co"
GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes?q="


class BrowseCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --------------------------------------------------
    # Fetch Media Info (Anime, Manga, LN)
    # --------------------------------------------------
    async def fetch_media(self, query: str, media_type: str) -> List[Dict]:
        graphql_query = {
            "query": """
            query ($search: String, $type: MediaType) {
                Page(perPage: 10) {
                    media(search: $search, type: $type) {
                        id
                        title { romaji english }
                        description(asHtml: false)
                        averageScore
                        siteUrl
                        status
                        episodes
                        chapters
                        volumes
                        startDate { year month day }
                        endDate { year month day }
                        genres
                        coverImage { large medium }
                        bannerImage
                        externalLinks { site url }
                        format
                    }
                }
            }
            """,
            "variables": {"search": query, "type": media_type}
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
    async def fetch_user_anilist_progress(self, anilist_username: str, media_id: int, media_type: str) -> Optional[Dict]:
        if not anilist_username or not media_id:
            return None

        query = """
        query($userName: String, $mediaId: Int, $type: MediaType) {
            User(name: $userName) {
                mediaListOptions {
                    scoreFormat
                }
            }
            MediaList(userName: $userName, mediaId: $mediaId, type: $type) {
                progress
                score
            }
        }
        """
        variables = {"userName": anilist_username, "mediaId": media_id, "type": media_type}

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

        user_opts = payload.get("data", {}).get("User", {}).get("mediaListOptions", {})
        score_format = user_opts.get("scoreFormat", "POINT_100")

        entry = payload.get("data", {}).get("MediaList")
        if not entry:
            return None

        progress = entry.get("progress")
        score = entry.get("score")

        # 🔄 Normalize based on score format
        rating10: Optional[float] = None
        if score is not None:
            try:
                if score_format == "POINT_100":
                    rating10 = round(score / 10.0, 1)
                elif score_format in ("POINT_10", "POINT_10_DECIMAL"):
                    rating10 = float(score)
                elif score_format == "POINT_5":
                    rating10 = round((score / 5) * 10, 1)
                elif score_format == "POINT_3":
                    # 1=Bad, 2=Average, 3=Good → map roughly to 3, 6, 9 out of 10
                    mapping = {1: 3.0, 2: 6.0, 3: 9.0}
                    rating10 = mapping.get(score, None)
            except Exception:
                rating10 = None

        return {"progress": progress, "rating10": rating10}


    # --------------------------------------------------
    # /Browse Command
    # --------------------------------------------------
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="browse",
        description="Search Anime, Manga, Light Novels and General Novels"
    )
    @app_commands.describe(
        media_type="Choose a media type",
        title="Choose the title"
    )
    @app_commands.choices(media_type=[
        app_commands.Choice(name="Anime", value="ANIME"),
        app_commands.Choice(name="Manga", value="MANGA"),
        app_commands.Choice(name="Light Novel", value="MANGA_NOVEL"),
        app_commands.Choice(name="General Novel", value="BOOK"),
    ])
    async def search(self, interaction: discord.Interaction, media_type: app_commands.Choice[str], title: str):
        # NOTE: media_type is now the first parameter so the slash command UI will show:
        # /browse <media_type> <title>
        await interaction.response.defer()

        chosen_type = media_type.value
        real_type = "MANGA" if chosen_type == "MANGA_NOVEL" else chosen_type

        if chosen_type == "BOOK":
            # 📚 Google Books Fetch
            async with aiohttp.ClientSession() as session:
                async with session.get(GOOGLE_BOOKS_URL + title) as response:
                    if response.status != 200:
                        await interaction.followup.send("❌ No results found.", ephemeral=True)
                        return
                    data = await response.json()
                    items = data.get("items", [])
                    if not items:
                        await interaction.followup.send("❌ No results found.", ephemeral=True)
                        return
                    book = items[0].get("volumeInfo", {})

            # --------------------------------------------------
            # Google Books Embed
            # --------------------------------------------------
            embed = discord.Embed(
                title=f"📚 {book.get('title', 'Unknown')}",
                url=book.get("infoLink"),
                description=book.get("description", "No description available."),
                color=discord.Color.random()
            )

            if "imageLinks" in book:
                embed.set_thumbnail(url=book["imageLinks"].get("thumbnail"))

            authors = ", ".join(book.get("authors", [])) if "authors" in book else "Unknown"
            embed.add_field(name="✍️ Authors", value=authors, inline=True)
            embed.add_field(name="📅 Published", value=book.get("publishedDate", "Unknown"), inline=True)
            embed.add_field(name="🏢 Publisher", value=book.get("publisher", "Unknown"), inline=True)
            embed.add_field(name="📄 Pages", value=book.get("pageCount", "Unknown"), inline=True)
            embed.add_field(name="⭐ Rating", value=str(book.get("averageRating", "?")) + "/5", inline=True)

            embed.set_footer(text="Fetched from Google Books")
            await interaction.followup.send(embed=embed)
            return

        # ✅ AniList Fetch
        results = await self.fetch_media(title, real_type)
        if not results:
            await interaction.followup.send("❌ No results found.", ephemeral=True)
            return

        media = results[0]

        if chosen_type == "MANGA_NOVEL" and media.get("format") != "NOVEL":
            await interaction.followup.send("❌ No Light Novel results found.", ephemeral=True)
            return

        # Format dates
        start_date = media.get("startDate", {})
        end_date = media.get("endDate", {})
        start_str = f"{start_date.get('year','?')}-{start_date.get('month','?')}-{start_date.get('day','?')}"
        end_str = (
            f"{end_date.get('year','?')}-{end_date.get('month','?')}-{end_date.get('day','?')}"
            if end_date else "Ongoing"
        )

        # Description
        raw_description = media.get("description") or "No description available."
        description = raw_description[:400] + "..." if len(raw_description) > 400 else raw_description
        genres = ", ".join(media.get("genres", [])) or "Unknown"

        # --------------------------------------------------
        # AniList Embed
        # --------------------------------------------------
        embed = discord.Embed(
            title=f"{'🎬' if real_type=='ANIME' else '📖'} {media['title']['romaji'] or media['title']['english']}",
            url=media["siteUrl"],
            description=description,
            color=discord.Color.random()
        )

        cover_url = media.get("coverImage", {}).get("medium") or media.get("coverImage", {}).get("large")
        if cover_url:
            embed.set_thumbnail(url=cover_url)

        banner_url = media.get("bannerImage")
        if banner_url:
            embed.set_image(url=banner_url)

        embed.add_field(name="⭐ Average Score", value=f"{media.get('averageScore', 'N/A')}%", inline=True)
        embed.add_field(name="📌 Status", value=media.get("status", "Unknown"), inline=True)

        if real_type == "ANIME":
            embed.add_field(name="📺 Episodes", value=media.get("episodes", '?'), inline=True)
        else:
            embed.add_field(name="📖 Chapters", value=media.get("chapters", '?'), inline=True)
            embed.add_field(name="📚 Volumes", value=media.get("volumes", '?'), inline=True)

        embed.add_field(name="🎭 Genres", value=genres, inline=False)
        embed.add_field(name="📅 Published", value=f"**Start:** {start_str}\n**End:** {end_str}", inline=False)

        # --------------------------------------------------
        # Registered Users' Progress (Second Page)
        # --------------------------------------------------
        users = await get_all_users()
        progress_embed = None

        if users:
            col_name = "Episodes" if real_type == "ANIME" else "Chapters"
            progress_lines = [f"`{'User':<20} {col_name:<10} {'Rating':<7}`"]
            progress_lines.append("`{:-<20} {:-<10} {:-<7}`".format("", "", ""))

            for user in users:
                discord_name = user[2]  # Assuming: (discord_id, discord_name, anilist_username)
                anilist_username = user[2] if len(user) > 2 else None

                anilist_progress = await self.fetch_user_anilist_progress(
                    anilist_username, media.get("id", 0), real_type
                )

                # ⬅️ Skip this user entirely if they don’t have the anime/manga
                if not anilist_progress:
                    continue

                total = media.get("episodes") if real_type == "ANIME" else media.get("chapters")
                progress_text = f"{anilist_progress['progress']}/{total or '?'}" if anilist_progress.get("progress") is not None else "—"
                rating_text = f"{anilist_progress['rating10']}/10" if anilist_progress.get("rating10") is not None else "—"

                progress_lines.append(f"`{discord_name:<20} {progress_text:<10} {rating_text:<7}`")

            # ✅ Only build the embed if there’s at least one valid user
            if len(progress_lines) > 2:
                progress_embed = discord.Embed(
                    title="👥 Registered Users' Progress",
                    description="\n".join(progress_lines),
                    color=discord.Color.blue()
                )
                progress_embed.set_footer(text="Fetched from AniList")


        mal_link = None
        for link in media.get("externalLinks", []):
            if link.get("site") == "MyAnimeList":
                mal_link = link.get("url")
                break
        if mal_link:
            embed.add_field(name="🔗 MyAnimeList", value=f"[View on MAL]({mal_link})", inline=False)

        embed.set_footer(text="Fetched from AniList")

        # Always send media info first
        if progress_embed:
            class PageView(View):
                def __init__(self, embed1, embed2):
                    super().__init__(timeout=120)
                    self.embed1 = embed1
                    self.embed2 = embed2

                @discord.ui.button(label="📖 Manga Info", style=discord.ButtonStyle.blurple)
                async def manga_info_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.edit_message(embed=self.embed1, view=self)

                @discord.ui.button(label="👥 User Progress", style=discord.ButtonStyle.green)
                async def user_progress_button(self, interaction: discord.Interaction, button: Button):
                    await interaction.response.edit_message(embed=self.embed2, view=self)

            view = PageView(embed, progress_embed)
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed)

    # --------------------------------------------------
    # Autocomplete
    # --------------------------------------------------
    @search.autocomplete("title")
    async def autocomplete_search(self, interaction: discord.Interaction, current: str):
        if len(current) < 2:
            return []

        media_type = getattr(interaction.namespace, "media_type", None)
        choices = []

        if media_type == "BOOK":
            async with aiohttp.ClientSession() as session:
                async with session.get(GOOGLE_BOOKS_URL + current) as response:
                    if response.status != 200:
                        return []
                    data = await response.json()
                    for item in data.get("items", [])[:10]:
                        info = item.get("volumeInfo", {})
                        title = info.get("title", "Unknown")[:100]
                        choices.append(app_commands.Choice(name=title, value=title))
        else:
            results = await self.fetch_media(current, "ANIME")
            for media in results[:10]:
                title = media["title"].get("romaji") or media["title"].get("english") or "Unknown"
                title = title[:100]
                choices.append(app_commands.Choice(name=title, value=title))

        return choices


async def setup(bot: commands.Bot):
    await bot.add_cog(BrowseCog(bot))
