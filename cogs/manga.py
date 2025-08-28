# cogs/manga.py
import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional
from helpers.media_helper import fetch_anilist_entries
import logging
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# -----------------------------
# Dropdown UI for selecting manga
# -----------------------------
class MangaDropdown(discord.ui.Select):
    def __init__(self, results: List[dict]):
        options = [
            discord.SelectOption(label=r["title"]["romaji"][:100], value=str(r["id"]))
            for r in results[:25]
        ]
        super().__init__(placeholder="Choose a manga...", min_values=1, max_values=1, options=options)
        self.results = results
        self.selected: Optional[dict] = None

    async def callback(self, interaction: discord.Interaction):
        manga_id = int(self.values[0])
        self.selected = next((m for m in self.results if m["id"] == manga_id), None)
        await interaction.response.defer()
        self.view.stop()


class MangaDropdownView(discord.ui.View):
    def __init__(self, results: List[dict], timeout: int = 30):
        super().__init__(timeout=timeout)
        self.dropdown = MangaDropdown(results)
        self.add_item(self.dropdown)

    async def wait_for_selection(self) -> Optional[dict]:
        await self.wait()
        return self.dropdown.selected


# -----------------------------
# Manga Cog
# -----------------------------
class MangaCog(commands.Cog):
    def __init__(self, bot: commands.Bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.cache = {}  # {query: (timestamp, results)}
        self.cache_duration = 300  # 5 minutes

        # Attach the command to bot.tree
        self.bot.tree.add_command(self.manga, guild=discord.Object(id=self.guild_id))

    # -----------------------------
    # Fetch manga results with cache
    # -----------------------------
    async def get_manga_results(self, query: str) -> List[dict]:
        query_lower = query.lower()
        if query_lower in self.cache:
            ts, results = self.cache[query_lower]
            if time.time() - ts < self.cache_duration:
                return results

        results = await fetch_anilist_entries(query)
        self.cache[query_lower] = (time.time(), results)
        return results

    # -----------------------------
    # Slash command: /manga
    # -----------------------------
    @app_commands.command(
        name="manga",
        description="Search for manga information from AniList"
    )
    @app_commands.describe(title="Enter the title of the manga")
    async def manga(self, interaction: discord.Interaction, title: str):
        await interaction.response.defer(thinking=True)
        results = await self.get_manga_results(title)

        if not results:
            await interaction.followup.send("❌ No manga found.", ephemeral=True)
            return

        # Only 1 result → send embed immediately
        if len(results) == 1:
            embed = await self.build_embed(results[0])
            await interaction.followup.send(embed=embed)
            return

        # Multiple results → show dropdown
        view = MangaDropdownView(results)
        msg = await interaction.followup.send(
            "🔍 Multiple results found. Choose one:", view=view, ephemeral=True
        )
        selected = await view.wait_for_selection()
        await msg.delete()

        if not selected:
            await interaction.followup.send("❌ Selection timed out.", ephemeral=True)
            return

        embed = await self.build_embed(selected)
        await interaction.followup.send(embed=embed)

    # -----------------------------
    # Autocomplete for title
    # -----------------------------
    @manga.autocomplete("title")
    async def autocomplete_title(self, interaction: discord.Interaction, current: str):
        results = await self.get_manga_results(current)
        return [
            app_commands.Choice(
                name=m["title"]["romaji"][:100],
                value=m["title"]["romaji"]
            )
            for m in results[:25]
        ]

    # -----------------------------
    # Build the embed
    # -----------------------------
    async def build_embed(self, manga: dict) -> discord.Embed:
        title = manga["title"].get("romaji") or manga["title"].get("english") or "Unknown"
        description = manga.get("description", "No description available.")
        url = manga.get("siteUrl", "")
        image = manga["coverImage"].get("extraLarge") or manga["coverImage"].get("large")

        embed = discord.Embed(
            title=title,
            description=description[:4000],
            url=url,
            color=discord.Color.blurple()
        )
        if image:
            embed.set_thumbnail(url=image)

        if "genres" in manga:
            embed.add_field(name="Genres", value=", ".join(manga["genres"]), inline=False)
        if "chapters" in manga:
            embed.add_field(name="Chapters", value=str(manga["chapters"]), inline=True)
        if "status" in manga:
            embed.add_field(name="Status", value=str(manga["status"]).title(), inline=True)
        if "averageScore" in manga:
            embed.add_field(name="Score", value=f"{manga['averageScore']}%", inline=True)

        return embed


# -----------------------------
# Cog setup
# -----------------------------
async def setup(bot: commands.Bot):
    # Replace 123456789 with your guild ID
    guild_id = 123456789
    await bot.add_cog(MangaCog(bot, guild_id))
