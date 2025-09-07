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

    async def fetch_anilist(self, query: str) -> dict:
        graphql_query = {
            "query": """
            query ($search: String) {
                Media(search: $search) {
                    id
                    title { romaji english native }
                    description(asHtml: false)
                    averageScore
                    siteUrl
                    status
                    episodes
                    chapters
                    volumes
                    genres
                    startDate { year month day }
                    endDate { year month day }
                    coverImage { large medium }
                    bannerImage
                    format
                }
            }
            """,
            "variables": {"search": query}
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=graphql_query) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("data", {}).get("Media")

    def build_compare_embed(self, media1: dict, media2: dict) -> discord.Embed:
        def safe(val, fallback="?"):
            return val if val else fallback

        def date_str(d):
            if not d:
                return "?"
            return f"{d.get('year','?')}-{d.get('month','?')}-{d.get('day','?')}"

        title1 = media1["title"].get("english") or media1["title"].get("romaji")
        title2 = media2["title"].get("english") or media2["title"].get("romaji")

        embed = discord.Embed(
            title=f"⚔️ Comparing\n{title1} 🆚 {title2}",
            description="Here’s a side-by-side comparison from AniList:",
            color=random.choice([discord.Color.red(), discord.Color.blue(), discord.Color.green()])
        )

        embed.add_field(
            name="⭐ Average Score",
            value=f"{safe(media1.get('averageScore'))}% 🆚 {safe(media2.get('averageScore'))}%",
            inline=False
        )
        embed.add_field(
            name="📌 Status",
            value=f"{safe(media1.get('status'))} 🆚 {safe(media2.get('status'))}",
            inline=False
        )

        if media1.get("episodes") or media2.get("episodes"):
            embed.add_field(
                name="📺 Episodes",
                value=f"{safe(media1.get('episodes'))} 🆚 {safe(media2.get('episodes'))}",
                inline=False
            )
        if media1.get("chapters") or media2.get("chapters"):
            embed.add_field(
                name="📖 Chapters",
                value=f"{safe(media1.get('chapters'))} 🆚 {safe(media2.get('chapters'))}",
                inline=False
            )
        if media1.get("volumes") or media2.get("volumes"):
            embed.add_field(
                name="📚 Volumes",
                value=f"{safe(media1.get('volumes'))} 🆚 {safe(media2.get('volumes'))}",
                inline=False
            )

        embed.add_field(
            name="🎭 Genres",
            value=f"{', '.join(media1.get('genres', [])) or '?'} 🆚 {', '.join(media2.get('genres', [])) or '?'}",
            inline=False
        )
        embed.add_field(
            name="📅 Start Date",
            value=f"{date_str(media1.get('startDate'))} 🆚 {date_str(media2.get('startDate'))}",
            inline=False
        )
        embed.add_field(
            name="📅 End Date",
            value=f"{date_str(media1.get('endDate'))} 🆚 {date_str(media2.get('endDate'))}",
            inline=False
        )

        # Covers
        embed.set_thumbnail(url=media1.get("coverImage", {}).get("large"))
        embed.set_image(url=media2.get("coverImage", {}).get("large"))

        embed.set_footer(text="📊 Powered by AniList API")
        return embed

    class CompareView(discord.ui.View):
        def __init__(self, url1: str, url2: str):
            super().__init__(timeout=None)
            self.add_item(discord.ui.Button(label="🔗 AniList Title 1", url=url1))
            self.add_item(discord.ui.Button(label="🔗 AniList Title 2", url=url2))

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="compare", description="⚔️ Compare two Anime/Manga/Light Novels from AniList")
    async def compare(self, interaction: discord.Interaction, title1: str, title2: str):
        await interaction.response.defer()

        media1 = await self.fetch_anilist(title1)
        media2 = await self.fetch_anilist(title2)

        if not media1 or not media2:
            await interaction.followup.send("❌ One or both titles were not found on AniList.", ephemeral=True)
            return

        embed = self.build_compare_embed(media1, media2)
        view = self.CompareView(media1["siteUrl"], media2["siteUrl"])

        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Compare(bot))
