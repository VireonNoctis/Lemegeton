from asyncio.log import logger
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import random
import re
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

        # AniList GraphQL query with full details
        query = """
        query ($type: MediaType) {
          Page(page: 1, perPage: 10) {
            media(type: $type, sort: TRENDING_DESC) {
              id
              title { romaji english }
              format
              status
              episodes
              chapters
              genres
              averageScore
              description(asHtml: false)
              coverImage { large }
              siteUrl
              trending
            }
          }
        }
        """

        async def fetch_trending(fetch_type: str, label: str):
            variables = {"type": fetch_type}
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(
                        "https://graphql.anilist.co",
                        json={"query": query, "variables": variables},
                        timeout=10
                    ) as resp:
                        if resp.status != 200:
                            # Log the failure
                            logger.warning(f"AniList request failed with status {resp.status}")
                            return []

                        data = await resp.json()
                except Exception as e:
                    logger.error(f"Failed to fetch AniList trending: {e}")
                    return []

            # Check if response contains data
            page_data = data.get("data", {}).get("Page") if data else None
            if not page_data:
                logger.warning(f"No Page data returned from AniList: {data}")
                return []

            media_list = page_data.get("media", [])
            if label == "LN":
                media_list = [m for m in media_list if m.get("format") == "NOVEL"]

            return media_list


        def build_embed_entry(m: dict, rank: int, label: str):
            type_colors = {"ANIME": 0x1E90FF, "MANGA": 0xFF69B4, "LN": 0x8A2BE2}
            color = discord.Color(type_colors.get(label, 0x00CED1))
            type_icons = {"ANIME": "🎬", "MANGA": "📖", "LN": "📚"}

            title_data = m.get("title") or {}
            title = title_data.get("english") or title_data.get("romaji") or "Unknown Title"
            url = m.get("siteUrl") or "#"
            score = m.get("trending") or 0
            format_ = m.get("format") or "Unknown"
            status = m.get("status") or "Unknown"
            episodes = m.get("episodes") or m.get("chapters") or "N/A"
            genres = ", ".join(m.get("genres") or []) or "N/A"
            avg_score = m.get("averageScore") or "N/A"

            # Clean description
            raw_desc = m.get("description") or "No description available"
            clean_desc = re.sub(r"<[^>]+>", "", raw_desc)
            clean_desc = (clean_desc[:500] + "...") if len(clean_desc) > 500 else clean_desc

            embed = discord.Embed(
                title=f"{type_icons.get(label, '')} #{rank} • {title}",
                description=(
                    f"Trending Score: {score}\n"
                    f"Format: {format_}\n"
                    f"Status: {status}\n"
                    f"Episodes/Chapters: {episodes}\n"
                    f"Genres: {genres}\n"
                    f"Average Score: {avg_score}\n\n"
                    f"Description: {clean_desc}"
                ),
                color=color
            )

            cover_url = m.get("coverImage", {}).get("large")
            if cover_url:
                embed.set_thumbnail(url=cover_url)

            embed.set_author(
                name="AniList Trending",
                url="https://anilist.co/",
                icon_url="https://anilist.co/img/icons/android-chrome-512x512.png"
            )
            embed.set_footer(
                text=f"⚡ Powered by AniList • {label} Trending",
                icon_url="https://anilist.co/img/icons/android-chrome-512x512.png"
            )
            embed.add_field(name="Link", value=f"[View on AniList]({url})", inline=False)
            return embed


        # Handle "ALL" option
        media_types_to_fetch = []
        if media_type == "ALL":
            media_types_to_fetch = [("ANIME", "ANIME"), ("MANGA", "MANGA"), ("LN", "LN")]
        else:
            label = media_type
            fetch_type = "MANGA" if label == "LN" else label
            media_types_to_fetch = [(fetch_type, label)]

        all_embeds = []

        for fetch_type, label in media_types_to_fetch:
            media_list = await fetch_trending(fetch_type, label)
            if not media_list:
                continue
            for i, m in enumerate(media_list):
                all_embeds.append(build_embed_entry(m, i + 1, label))

        if not all_embeds:
            await interaction.followup.send("⚠️ No trending results found.", ephemeral=True)
            return

        # Pagination view
        class PaginatedView(discord.ui.View):
            def __init__(self, embeds):
                super().__init__(timeout=180)
                self.embeds = embeds
                self.current = 0

            async def update_message(self, interaction: discord.Interaction):
                embed = self.embeds[self.current]
                embed.set_footer(text=f"Page {self.current+1}/{len(self.embeds)} • {embed.footer.text}")
                try:
                    await interaction.response.edit_message(embed=embed, view=self)
                except discord.errors.InteractionResponded:
                    await interaction.followup.edit_message(
                        message_id=interaction.message.id, embed=embed, view=self
                    )

            @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary)
            async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current = (self.current - 1) % len(self.embeds)
                await self.update_message(interaction)

            @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary)
            async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current = (self.current + 1) % len(self.embeds)
                await self.update_message(interaction)

        view = PaginatedView(all_embeds)
        await interaction.followup.send(embed=all_embeds[0], view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Trending(bot))
