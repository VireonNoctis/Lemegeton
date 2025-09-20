import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import aiohttp
import asyncio
import time
from typing import Dict, List, Tuple

from database import get_all_users, upsert_user_stats, DB_PATH
from helpers.media_helper import fetch_user_stats
from config import GUILD_ID

CACHE_TTL = 86400  # 1 day
last_fetch: Dict[int, float] = {}  # timestamp cache per user
PAGE_SIZE = 5  # 5 users per page


class LeaderboardView(discord.ui.View):
    def __init__(self, leaderboard_data: List[Tuple[str, int, int, float]], medium: str = "manga"):
        super().__init__(timeout=300)
        self.leaderboard_data = leaderboard_data
        self.current_page = 0
        self.max_page = (len(leaderboard_data) - 1) // PAGE_SIZE
        self.medium = medium.lower()

        # Disable buttons if not needed
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_page

    async def update_embed(self, message: discord.Message):
        start = self.current_page * PAGE_SIZE
        end = start + PAGE_SIZE
        page_data = self.leaderboard_data[start:end]

        title = "🏆 Golden Ratio"
        desc_medium = "manga"
        stat_label = "Average Chapters per Manga"
        if self.medium == "anime":
            desc_medium = "anime"
            stat_label = "Average Episodes per Anime"

        embed = discord.Embed(
            title=title,
            description=f"Users ranked by {stat_label} (Page {self.current_page + 1}/{self.max_page + 1}) — showing {desc_medium}",
            color=discord.Color.random()
        )

        for idx, (username, total_media, total_units, avg_units) in enumerate(page_data, start=start + 1):
            embed.add_field(
                name=f"{idx}. {username}",
                value=f"Total {desc_medium.title()}: {total_media}\nTotal {'Chapters' if self.medium=='manga' else 'Episodes'}: {total_units}\n{stat_label}: {avg_units:.2f}",
                inline=False
            )

        embed.set_footer(text="Leaderboard based on cached AniList stats (updates once per day)")

        # Always edit the message itself for buttons
        await message.edit(embed=embed, view=self)

    @discord.ui.button(label="◀️ Prev", style=discord.ButtonStyle.blurple)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.prev_button.disabled = self.current_page == 0
            self.next_button.disabled = False
            await self.update_embed(interaction.message)
        await interaction.response.defer()  # acknowledge the click

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.blurple)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_page:
            self.current_page += 1
            self.next_button.disabled = self.current_page >= self.max_page
            self.prev_button.disabled = False
            await self.update_embed(interaction.message)
        await interaction.response.defer()


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def fetch_and_cache_stats(self):
        users = await get_all_users()
        async with aiohttp.ClientSession() as session:
            for user in users:
                discord_id, username = user[1], user[2]
                now = time.time()
                if discord_id in last_fetch and now - last_fetch[discord_id] < CACHE_TTL:
                    continue

                data = await fetch_user_stats(username)
                if not data or "data" not in data or "User" not in data["data"]:
                    continue

                user_data = data["data"]["User"]
                manga_stats = user_data.get("statistics", {}).get("manga", {})
                total_manga = manga_stats.get("count") or 0
                total_chapters = manga_stats.get("chaptersRead") or 0
                anime_stats = user_data.get("statistics", {}).get("anime", {})
                total_anime = anime_stats.get("count") or 0
                # try to read episodes/units if available (field name may vary depending on your AniList query)
                total_episodes = anime_stats.get("chaptersRead") or anime_stats.get("episodesWatched") or 0
                avg_manga_score = manga_stats.get("meanScore") or 0
                avg_anime_score = anime_stats.get("meanScore") or 0

                await upsert_user_stats(
                    discord_id,
                    username,
                    total_manga,
                    total_anime,
                    avg_manga_score,
                    avg_anime_score,
                    total_chapters,
                    total_episodes
                )
                last_fetch[discord_id] = now

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.choices(medium=[
        app_commands.Choice(name="Manga", value="manga"),
        app_commands.Choice(name="Anime", value="anime"),
    ])
    @app_commands.command(
        name="leaderboard",
        description="📊 Show leaderboard: highest average chapters per manga or episodes per anime"
    )
    async def leaderboard(self, interaction: discord.Interaction, medium: app_commands.Choice[str]):
        await interaction.response.defer()
        chosen = (medium.value if isinstance(medium, app_commands.Choice) else str(medium)).lower()
        await self.fetch_and_cache_stats()

        # Choose columns based on medium
        if chosen == "anime":
            sql = "SELECT username, total_anime, total_episodes FROM user_stats"
        else:
            sql = "SELECT username, total_manga, total_chapters FROM user_stats"

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(sql)
            rows = await cursor.fetchall()
            await cursor.close()

        if not rows:
            await interaction.followup.send("⚠️ No user stats found.", ephemeral=True)
            return

        leaderboard_data = []
        for username, total_media, total_units in rows:
            # guard against zero/None divisions
            total_media = total_media or 0
            total_units = total_units if total_units is not None else 0
            if total_media and total_units is not None:
                avg_units = total_units / total_media if total_media else 0
                leaderboard_data.append((username, total_media, total_units, avg_units))

        if not leaderboard_data:
            await interaction.followup.send("⚠️ No progress data found for the selected medium.", ephemeral=True)
            return

        # Sort all users by average units per media in descending order
        leaderboard_data.sort(key=lambda x: x[3], reverse=True)

        # Create the view with medium awareness
        view = LeaderboardView(leaderboard_data, medium=chosen)

        # Send an empty embed first and get the message object
        loading_title = f"Loading {chosen} leaderboard..."
        msg = await interaction.followup.send(embed=discord.Embed(title=loading_title), view=view)

        # Update the embed with actual content
        await view.update_embed(msg)

async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))