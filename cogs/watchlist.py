import discord
from discord.ext import commands
from discord import app_commands
import random

from config import GUILD_ID
from helpers.media_helper import fetch_watchlist
from database import get_user


class WatchlistView(discord.ui.View):
    def __init__(self, pages, user_name: str):
        super().__init__(timeout=120)  # 2-minute timeout
        self.pages = pages
        self.current_page = 0
        self.user_name = user_name

    async def update_message(self, interaction: discord.Interaction):
        embed = self.pages[self.current_page]
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()


class Watchlist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="watchlist",
        description="📺 Show what someone is currently watching or reading on AniList"
    )
    @app_commands.describe(
        user="Choose a registered server user",
        username="Or type an AniList username"
    )
    async def watchlist(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
        username: str = None
    ):
        await interaction.response.defer()

        # Case 1: Discord user
        if user:
            db_user = await get_user(user.id)
            if not db_user:
                await interaction.followup.send(
                    f"❌ {user.mention} is not registered in our database. Please use the AniList username option.",
                    ephemeral=True
                )
                return
            username = db_user[2]

        # Case 2: Default to self if no args
        elif not username:
            db_user = await get_user(interaction.user.id)
            if db_user:
                username = db_user[2]
            else:
                await interaction.followup.send(
                    "⚠️ You must provide either a registered server user or an AniList username. (You are not registered either!)",
                    ephemeral=True
                )
                return

        # Fetch AniList watchlist
        data = await fetch_watchlist(username)
        if not data:
            await interaction.followup.send(f"⚠️ Could not fetch watchlist for **{username}**.", ephemeral=True)
            return

        anime_lists = data.get("anime", [])
        manga_lists = data.get("manga", [])

        anime_entries = []
        for group in anime_lists:
            for e in group.get("entries", []):
                media = e["media"]
                title = media["title"].get("english") or media["title"].get("romaji") or "Unknown"
                progress = e.get("progress", 0)
                total = media.get("episodes") or "?"
                anime_entries.append(f"🎬 [{title}]({media['siteUrl']}) — Ep {progress}/{total}")

        manga_entries = []
        for group in manga_lists:
            for e in group.get("entries", []):
                media = e["media"]
                title = media["title"].get("english") or media["title"].get("romaji") or "Unknown"
                progress = e.get("progress", 0)
                total = media.get("chapters") or "?"
                format_type = "📚 LN" if media.get("format") == "NOVEL" else "📖 Manga"
                manga_entries.append(f"{format_type} [{title}]({media['siteUrl']}) — Ch {progress}/{total}")

        all_entries = anime_entries + manga_entries
        if not all_entries:
            await interaction.followup.send(f"ℹ️ **{username}** is not watching or reading anything right now.")
            return

        # Split into pages of 10
        pages = []
        for i in range(0, len(all_entries), 10):
            chunk = all_entries[i:i+10]
            embed = discord.Embed(
                title=f"📺 Watchlist for {username}",
                description="\n".join(chunk),
                color=discord.Color(random.randint(0, 0xFFFFFF))
            )
            embed.set_footer(text=f"Page {len(pages)+1}/{(len(all_entries)+9)//10} • Data from AniList")
            pages.append(embed)

        # If only one page, just send normally
        if len(pages) == 1:
            await interaction.followup.send(embed=pages[0])
            return

        # Send with pagination view
        view = WatchlistView(pages, username)
        await interaction.followup.send(embed=pages[0], view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Watchlist(bot))
