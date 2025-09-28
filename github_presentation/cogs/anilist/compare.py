import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
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
                    siteUrl
                    status
                    episodes
                    chapters
                    volumes
                    duration
                    genres
                    coverImage { large medium color }
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
    # Helpers
    # ---------------------------------------------------------
    def safe(self, val, fallback="?"):
        return val if val else fallback

    def calculate_watch_time(self, episodes, duration):
        if not episodes or not duration:
            return "?"
        hours = (episodes * duration) / 60
        return f"~{hours:.1f} hrs"

    def calculate_read_time(self, chapters):
        if not chapters:
            return "?"
        hours = (chapters * 15) / 60  # ~15 min per chapter
        return f"~{hours:.1f} hrs"

    def format_vs(self, val1, val2, crown_func):
        """Format values in left vs right style with crowns"""
        return f"{val1} {crown_func(val1, val2)}  🆚  {crown_func(val2, val1)} {val2}"

    # ---------------------------------------------------------
    # Build Embed
    # ---------------------------------------------------------
    def build_compare_embed(self, media1: dict, media2: dict, media_type: str) -> discord.Embed:
        title1 = media1["title"].get("english") or media1["title"].get("romaji")
        title2 = media2["title"].get("english") or media2["title"].get("romaji")

        score1 = media1.get("averageScore") or 0
        score2 = media2.get("averageScore") or 0

        # Color logic
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
            title=f"⚔️ Comparing",
            description=f"**{title1}** 🆚 **{title2}**\n\nHere’s a **side-by-side comparison** powered by AniList:",
            color=color,
        )

        # Crown helper
        def crown(val1, val2):
            if val1 == val2:
                return "🤝"
            return "🏆" if val1 > val2 else ""

        # Stats
        embed.add_field(
            name="⭐ Average Score",
            value=self.format_vs(f"{score1}%", f"{score2}%", crown),
            inline=False,
        )

        pop1 = media1.get("popularity") or 0
        pop2 = media2.get("popularity") or 0
        embed.add_field(
            name="🔥 Popularity",
            value=self.format_vs(f"{pop1:,}", f"{pop2:,}", crown),
            inline=False,
        )

        fav1 = media1.get("favourites") or 0
        fav2 = media2.get("favourites") or 0
        embed.add_field(
            name="❤️ Favourites",
            value=self.format_vs(f"{fav1:,}", f"{fav2:,}", crown),
            inline=False,
        )

        # Episodes / Chapters
        if media_type == "ANIME":
            e1, e2 = media1.get("episodes"), media2.get("episodes")
            d1, d2 = media1.get("duration"), media2.get("duration")
            embed.add_field(
                name="📺 Episodes",
                value=self.format_vs(self.safe(e1), self.safe(e2), crown),
                inline=True,
            )
            embed.add_field(
                name="⏱ Estimated Watch Time",
                value=self.format_vs(
                    self.calculate_watch_time(e1, d1),
                    self.calculate_watch_time(e2, d2),
                    crown,
                ),
                inline=True,
            )
        else:
            c1, c2 = media1.get("chapters"), media2.get("chapters")
            v1, v2 = media1.get("volumes"), media2.get("volumes")
            embed.add_field(
                name="📖 Chapters",
                value=self.format_vs(self.safe(c1), self.safe(c2), crown),
                inline=True,
            )
            embed.add_field(
                name="📚 Volumes",
                value=self.format_vs(self.safe(v1), self.safe(v2), crown),
                inline=True,
            )
            embed.add_field(
                name="⏱ Estimated Read Time",
                value=self.format_vs(self.calculate_read_time(c1), self.calculate_read_time(c2), crown),
                inline=False,
            )

        # Genres
        genres1, genres2 = set(media1.get("genres", [])), set(media2.get("genres", []))
        embed.add_field(name="🎭 Shared Genres", value=", ".join(genres1 & genres2) or "None", inline=False)
        embed.add_field(name=f"🎭 Unique to {title1}", value=", ".join(genres1 - genres2) or "None", inline=True)
        embed.add_field(name=f"🎭 Unique to {title2}", value=", ".join(genres2 - genres1) or "None", inline=True)

        # Covers side by side
        embed.set_thumbnail(url=media1["coverImage"]["large"])  # left
        embed.set_image(url=media2["coverImage"]["large"])      # right (large image below)

        embed.set_footer(text="📊 Powered by AniList API")
        return embed

    # ---------------------------------------------------------
    # Buttons
    # ---------------------------------------------------------
    class CompareView(discord.ui.View):
        def __init__(self, url1: str, url2: str):
            super().__init__(timeout=None)
            self.add_item(discord.ui.Button(label="🔗 AniList Title 1", url=url1))
            self.add_item(discord.ui.Button(label="🔗 AniList Title 2", url=url2))

    # ---------------------------------------------------------
    # Slash Command
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

        media1 = await self.fetch_anilist(title1, media_type.value)
        media2 = await self.fetch_anilist(title2, media_type.value)

        if not media1 or not media2:
            await interaction.followup.send("❌ One or both titles were not found on AniList.", ephemeral=True)
            return

        embed = self.build_compare_embed(media1, media2, media_type.value)
        view = self.CompareView(media1["siteUrl"], media2["siteUrl"])
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Compare(bot))
