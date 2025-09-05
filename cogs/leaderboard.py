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
    def __init__(self, leaderboard_data: List[Tuple[str, int, int, float]]):
        super().__init__(timeout=300)
        self.leaderboard_data = leaderboard_data
        self.current_page = 0
        self.max_page = (len(leaderboard_data) - 1) // PAGE_SIZE

        # Disable buttons if not needed
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= self.max_page

    async def update_embed(self, message: discord.Message):
        start = self.current_page * PAGE_SIZE
        end = start + PAGE_SIZE
        page_data = self.leaderboard_data[start:end]

        embed = discord.Embed(
            title="🏆 Golden Ratio",
            description=f"Users ranked by average chapters read per manga (Page {self.current_page + 1}/{self.max_page + 1})",
            color=discord.Color.random()
        )

        for idx, (username, total_manga, total_chapters, avg_chapters) in enumerate(page_data, start=start + 1):
            embed.add_field(
                name=f"{idx}. {username}",
                value=f"Total Manga: {total_manga}\nTotal Chapters: {total_chapters}\nAverage Chapters per Manga: {avg_chapters:.2f}",
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
                total_anime = user_data.get("statistics", {}).get("anime", {}).get("count") or 0
                avg_manga_score = manga_stats.get("meanScore") or 0
                avg_anime_score = user_data.get("statistics", {}).get("anime", {}).get("meanScore") or 0

                await upsert_user_stats(
                    discord_id,
                    username,
                    total_manga,
                    total_anime,
                    avg_manga_score,
                    avg_anime_score,
                    total_chapters
                )
                last_fetch[discord_id] = now

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="leaderboard",
        description="📊 Show leaderboard: highest average chapters per manga read"
    )
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.fetch_and_cache_stats()

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT username, total_manga, total_chapters FROM user_stats"
            )
            rows = await cursor.fetchall()
            await cursor.close()

        if not rows:
            await interaction.followup.send("⚠️ No user stats found.", ephemeral=True)
            return

        leaderboard_data = []
        for username, total_manga, total_chapters in rows:
            if total_manga and total_chapters is not None:
                avg_chapters = total_chapters / total_manga
                leaderboard_data.append((username, total_manga, total_chapters, avg_chapters))

        if not leaderboard_data:
            await interaction.followup.send("⚠️ No manga progress data found.", ephemeral=True)
            return
        
        # Sort all users by average chapters per manga in descending order
        leaderboard_data.sort(key=lambda x: x[3], reverse=True)

        # Create the view
        view = LeaderboardView(leaderboard_data)

        # Send an empty embed first and get the message object
        msg = await interaction.followup.send(embed=discord.Embed(title="Loading leaderboard..."), view=view)

        # Update the embed with actual content
        await view.update_embed(msg)



async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))
