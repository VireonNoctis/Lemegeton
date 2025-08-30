import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random

class Hot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="hot",
        description="🔥 See the currently trending series on AniList"
    )
    @app_commands.describe(
        media_type="Choose Anime, Manga, Light Novels, or All"
    )
    @app_commands.choices(
        media_type=[
            app_commands.Choice(name="Anime", value="ANIME"),
            app_commands.Choice(name="Manga", value="MANGA"),
            app_commands.Choice(name="Light Novels", value="LN"),
            app_commands.Choice(name="All", value="ALL")
        ]
    )
    async def hot(
        self,
        interaction: discord.Interaction,
        media_type: app_commands.Choice[str] = None
    ):
        await interaction.response.defer()

        media_type = media_type.value if media_type else "ANIME"

        # AniList GraphQL query for trending
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

        async def fetch_trending(fetch_type: str, label: str):
            variables = {"type": fetch_type}
            async with aiohttp.ClientSession() as session:
                async with session.post("https://graphql.anilist.co", json={"query": query, "variables": variables}) as resp:
                    data = await resp.json()

            media_list = data.get("data", {}).get("Page", {}).get("media", [])
            if label == "LN":
                media_list = [m for m in media_list if m.get("format") == "NOVEL"]

            return media_list

        async def build_embed(media_list, label: str):
            if not media_list:
                return None

            random_color = discord.Color(random.randint(0, 0xFFFFFF))
            type_icons = {"ANIME": "🎬", "MANGA": "📖", "LN": "📚"}

            embed = discord.Embed(
                title=f"{type_icons.get(label, '')} Trending {label.capitalize()}",
                description=f"🔥 Top trending {label.lower()} on AniList right now!",
                color=random_color
            )

            for i, m in enumerate(media_list, start=1):
                title = m["title"].get("romaji") or m["title"].get("english") or "Unknown"
                url = m["siteUrl"]
                score = m.get("trending", 0)

                embed.add_field(
                    name=f"{i}. [{title}]({url})",
                    value=f"🔥 Trending Score: {score}",
                    inline=False
                )

            embed.set_thumbnail(url=media_list[0]["coverImage"]["large"])
            return embed

        # Handle "All" separately
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
                await interaction.followup.send("⚠️ No trending results found.", ephemeral=True)
                return

            await interaction.followup.send(embeds=embeds)
            return

        # Otherwise fetch only the selected type
        fetch_type = "MANGA" if media_type == "LN" else media_type
        media_list = await fetch_trending(fetch_type, media_type)

        if not media_list:
            await interaction.followup.send(
                f"⚠️ No trending {media_type.capitalize()} found right now.",
                ephemeral=True
            )
            return

        embed = await build_embed(media_list, media_type)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Hot(bot))
