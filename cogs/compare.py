import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
from config import GUILD_ID

API_URL = "https://graphql.anilist.co"


class Compare(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------
    # Fetch AniList data
    # ---------------------------------------------------------
    async def fetch_anilist(self, query: str, media_type: str):
        graphql_query = {
            "query": """
            query ($search: String, $type: MediaType) {
                Media(search: $search, type: $type) {
                    id
                    title { romaji english native }
                    description(asHtml: false)
                    averageScore
                    popularity
                    favourites
                    rankings { rank type context year season allTime }
                    siteUrl
                    status
                    episodes
                    chapters
                    volumes
                    duration
                    genres
                    startDate { year month day }
                    endDate { year month day }
                    coverImage { large medium color }
                    studios(isMain: true) { nodes { name } }
                    format
                }
            }
            """,
            "variables": {"search": query, "type": media_type.upper()},
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=graphql_query) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("data", {}).get("Media")

    # ---------------------------------------------------------
    # Utility helpers
    # ---------------------------------------------------------
    def safe(self, val, fallback="?"):
        return val if val else fallback

    def date_str(self, d):
        if not d or not d.get("year"):
            return "?"
        return f"{d.get('year', '?')}-{d.get('month', '?')}-{d.get('day', '?')}"

    def calculate_watch_time(self, episodes, duration):
        if not episodes or not duration:
            return "?"
        hours = (episodes * duration) / 60
        return f"~{hours:.1f} hrs"

    def calculate_read_time(self, chapters):
        if not chapters:
            return "?"
        hours = (chapters * 15) / 60  # Assuming ~15 minutes per chapter
        return f"~{hours:.1f} hrs"

    # ---------------------------------------------------------
    # Build enhanced embed
    # ---------------------------------------------------------
    def build_compare_embed(self, media1: dict, media2: dict, media_type: str) -> discord.Embed:
        title1 = media1["title"].get("english") or media1["title"].get("romaji")
        title2 = media2["title"].get("english") or media2["title"].get("romaji")

        score1 = media1.get("averageScore") or 0
        score2 = media2.get("averageScore") or 0

        # Dynamic color: blue if close, green if tied, purple if one dominates
        score_diff = abs(score1 - score2)
        if score_diff < 5:
            color = discord.Color.green()
        elif score_diff < 15:
            color = discord.Color.blue()
        elif score_diff < 25:
            color = discord.Color.purple()
        else:
            color = discord.Color.red()

        embed = discord.Embed(
            title=f"⚔️ Comparing\n{title1} 🆚 {title2}",
            description="Here’s a **side-by-side comparison** powered by AniList:",
            color=color,
        )

        # Winner highlight helper
        def crown(val1, val2):
            if val1 == val2:
                return "🤝"
            return "🏆" if val1 > val2 else ""

        # ------------------------
        # Key stats comparison
        # ------------------------
        embed.add_field(
            name="⭐ Average Score",
            value=f"{score1}% {crown(score1, score2)} 🆚 {crown(score2, score1)} {score2}%",
            inline=False,
        )

        pop1 = media1.get("popularity") or 0
        pop2 = media2.get("popularity") or 0
        embed.add_field(
            name="🔥 Popularity",
            value=f"{pop1:,} {crown(pop1, pop2)} 🆚 {crown(pop2, pop1)} {pop2:,}",
            inline=False,
        )

        fav1 = media1.get("favourites") or 0
        fav2 = media2.get("favourites") or 0
        embed.add_field(
            name="❤️ Favourites",
            value=f"{fav1:,} {crown(fav1, fav2)} 🆚 {crown(fav2, fav1)} {fav2:,}",
            inline=False,
        )

        # ------------------------
        # Episodes / Chapters / Volumes
        # ------------------------
        if media_type == "ANIME":
            episodes1 = media1.get("episodes")
            episodes2 = media2.get("episodes")
            duration1 = media1.get("duration")
            duration2 = media2.get("duration")
            embed.add_field(
                name="📺 Episodes",
                value=f"{self.safe(episodes1)} 🆚 {self.safe(episodes2)}",
                inline=True,
            )
            embed.add_field(
                name="⏱ Estimated Watch Time",
                value=f"{self.calculate_watch_time(episodes1, duration1)} 🆚 {self.calculate_watch_time(episodes2, duration2)}",
                inline=True,
            )
        else:
            chapters1 = media1.get("chapters")
            chapters2 = media2.get("chapters")
            volumes1 = media1.get("volumes")
            volumes2 = media2.get("volumes")
            embed.add_field(
                name="📖 Chapters",
                value=f"{self.safe(chapters1)} 🆚 {self.safe(chapters2)}",
                inline=True,
            )
            embed.add_field(
                name="📚 Volumes",
                value=f"{self.safe(volumes1)} 🆚 {self.safe(volumes2)}",
                inline=True,
            )
            embed.add_field(
                name="⏱ Estimated Read Time",
                value=f"{self.calculate_read_time(chapters1)} 🆚 {self.calculate_read_time(chapters2)}",
                inline=False,
            )

        # ------------------------
        # Shared & unique genres
        # ------------------------
        genres1 = set(media1.get("genres", []))
        genres2 = set(media2.get("genres", []))

        shared_genres = ", ".join(genres1 & genres2) or "None"
        unique1 = ", ".join(genres1 - genres2) or "None"
        unique2 = ", ".join(genres2 - genres1) or "None"

        embed.add_field(name="🎭 Shared Genres", value=shared_genres, inline=False)
        embed.add_field(name=f"🎭 Unique to {title1}", value=unique1, inline=True)
        embed.add_field(name=f"🎭 Unique to {title2}", value=unique2, inline=True)

        # ------------------------
        # Cover Images
        # ------------------------
        embed.set_thumbnail(url=media1.get("coverImage", {}).get("large"))
        embed.set_image(url=media2.get("coverImage", {}).get("large"))

        embed.set_footer(text="📊 Powered by AniList API")
        return embed

    # ---------------------------------------------------------
    # View with buttons
    # ---------------------------------------------------------
    class CompareView(discord.ui.View):
        def __init__(self, url1: str, url2: str):
            super().__init__(timeout=None)
            self.add_item(discord.ui.Button(label="🔗 AniList Title 1", url=url1))
            self.add_item(discord.ui.Button(label="🔗 AniList Title 2", url=url2))

    # ---------------------------------------------------------
    # Slash Command: /compare
    # ---------------------------------------------------------
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="compare",
        description="⚔️ Compare two Anime or Manga titles from AniList",
    )
    @app_commands.describe(
        media_type="Choose whether you're comparing Anime or Manga",
        title1="First title to compare",
        title2="Second title to compare",
    )
    @app_commands.choices(
        media_type=[
            app_commands.Choice(name="Anime", value="ANIME"),
            app_commands.Choice(name="Manga", value="MANGA"),
        ]
    )
    async def compare(
        self,
        interaction: discord.Interaction,
        media_type: app_commands.Choice[str],
        title1: str,
        title2: str,
    ):
        await interaction.response.defer()

        # Fetch data for both titles
        media1 = await self.fetch_anilist(title1, media_type.value)
        media2 = await self.fetch_anilist(title2, media_type.value)

        if not media1 or not media2:
            await interaction.followup.send(
                "❌ One or both titles were not found on AniList.", ephemeral=True
            )
            return

        embed = self.build_compare_embed(media1, media2, media_type.value)
        view = self.CompareView(media1["siteUrl"], media2["siteUrl"])

        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Compare(bot))
