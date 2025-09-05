import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
import asyncio

from config import GUILD_ID


class Trending(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="trending",
        description="🔥 View the currently trending anime, manga, or light novels on AniList"
    )
    @app_commands.describe(
        media_type="Choose Anime, Manga, Light Novels, or All"
    )
    @app_commands.choices(
        media_type=[
            app_commands.Choice(name="Anime 🎬", value="ANIME"),
            app_commands.Choice(name="Manga 📖", value="MANGA"),
            app_commands.Choice(name="Light Novels 📚", value="LN"),
            app_commands.Choice(name="All 🌐", value="ALL")
        ]
    )
    async def trending(
        self,
        interaction: discord.Interaction,
        media_type: app_commands.Choice[str] = None
    ):
        await interaction.response.defer()

        media_type = media_type.value if media_type else "ANIME"

        # 🔹 AniList GraphQL Query
        query = """
        query ($type: MediaType) {
          Page(page: 1, perPage: 10) {
            media(type: $type, sort: TRENDING_DESC) {
              id
              title {
                romaji
                english
              }
              format
              coverImage {
                large
              }
              siteUrl
              trending
            }
          }
        }
        """

        # 🔹 Fetch trending data from AniList
        async def fetch_trending(fetch_type: str, label: str):
            variables = {"type": fetch_type}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://graphql.anilist.co",
                    json={"query": query, "variables": variables}
                ) as resp:
                    data = await resp.json()

            media_list = data.get("data", {}).get("Page", {}).get("media", [])
            if label == "LN":
                media_list = [m for m in media_list if m.get("format") == "NOVEL"]

            return media_list

        # 🎨 Build a more aesthetic embed
        async def build_embed(media_list, label: str):
            if not media_list:
                return None

            # 🌈 Smooth gradient-inspired random color
            colors = [
                0xF08080, 0xFF8C00, 0xFFD700, 0x32CD32,
                0x00CED1, 0x1E90FF, 0xBA55D3, 0xFF69B4
            ]
            random_color = discord.Color(random.choice(colors))

            # 🏷️ Type icons for better styling
            type_icons = {"ANIME": "🎬", "MANGA": "📖", "LN": "📚"}

            embed = discord.Embed(
                title=f"{type_icons.get(label, '')} Top 10 Trending {label.capitalize()}",
                url="https://anilist.co",  # ✅ Makes the embed title clickable
                description=f"🔥 Here's what's **hot** on **AniList** right now!\nStay up to date with the latest trends 🚀",
                color=random_color
            )


            for i, m in enumerate(media_list, start=1):
                title = m["title"].get("romaji") or m["title"].get("english") or "Unknown Title"
                url = m["siteUrl"]
                score = m.get("trending", 0)

                embed.add_field(
                    name=f"**#{i}** • {title}",
                    value=f"🔗 [View on AniList]({url}) • ✨ **Trending Score:** `{score}`",
                    inline=False
                )


            # 🖼️ Thumbnail: First trending item cover
            embed.set_thumbnail(url=media_list[0]["coverImage"]["large"])

            # 🌟 Better footer with emoji & subtle branding
            embed.set_footer(
                text="⚡ Powered by AniList • Data updates every few hours",
                icon_url=media_list[0]["coverImage"]["large"]
            )

            return embed

        # 🔹 Handle "All" option → fetch Anime, Manga, Light Novels together
        if media_type == "ALL":
            anime, manga, ln = await asyncio.gather(
                fetch_trending("ANIME", "ANIME"),
                fetch_trending("MANGA", "MANGA"),
                fetch_trending("MANGA", "LN")
            )

            embeds = []
            for media_list, label in [(anime, "ANIME"), (manga, "MANGA"), (ln, "LN")]:
                embed = await build_embed(media_list, label)
                if embed:
                    embeds.append(embed)

            if not embeds:
                await interaction.followup.send(
                    "⚠️ No trending results found on AniList.",
                    ephemeral=True
                )
                return

            await interaction.followup.send(embeds=embeds)
            return

        # 🔹 Otherwise fetch a single media type
        fetch_type = "MANGA" if media_type == "LN" else media_type
        media_list = await fetch_trending(fetch_type, media_type)

        if not media_list:
            await interaction.followup.send(
                f"⚠️ No trending {media_type.capitalize()} found at the moment.",
                ephemeral=True
            )
            return

        embed = await build_embed(media_list, media_type)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Trending(bot))
