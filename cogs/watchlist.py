import discord
from discord.ext import commands
from discord import app_commands
import random
import logging
import os
from pathlib import Path

from helpers.media_helper import fetch_watchlist
from database import get_user_guild_aware

# ------------------------------------------------------
# Logging Setup - Clears on each bot run
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "watchlist.log"

# Clear the log file on startup
if LOG_FILE.exists():
    LOG_FILE.unlink()

# Create logger
logger = logging.getLogger("Watchlist")
logger.setLevel(logging.INFO)

# Remove existing handlers to avoid duplicates
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create file handler
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(file_handler)

logger.info("Watchlist cog logging initialized - log file cleared")


class WatchlistView(discord.ui.View):
    def __init__(self, pages, user_name: str):
        super().__init__(timeout=120)  # 2-minute timeout
        self.pages = pages
        self.current_page = 0
        self.user_name = user_name
        logger.info(f"Created WatchlistView for {user_name} with {len(pages)} pages")

    async def update_message(self, interaction: discord.Interaction):
        embed = self.pages[self.current_page]
        logger.info(f"Updating watchlist message to page {self.current_page + 1}/{len(self.pages)} for user {self.user_name}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            logger.info(f"User {interaction.user} navigated back to page {self.current_page + 1} in {self.user_name}'s watchlist")
            await self.update_message(interaction)
        else:
            logger.debug(f"User {interaction.user} tried to go back from first page in {self.user_name}'s watchlist")
            await interaction.response.defer()

    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            logger.info(f"User {interaction.user} navigated forward to page {self.current_page + 1} in {self.user_name}'s watchlist")
            await self.update_message(interaction)
        else:
            logger.debug(f"User {interaction.user} tried to go forward from last page in {self.user_name}'s watchlist")
            await interaction.response.defer()

    async def on_timeout(self):
        logger.info(f"WatchlistView for {self.user_name} timed out after 2 minutes")
        for item in self.children:
            item.disabled = True


class Watchlist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Watchlist cog initialized")

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
        logger.info(f"Watchlist command invoked by {interaction.user} (ID: {interaction.user.id})")
        logger.info(f"Parameters: user={user}, username={username}")
        
        await interaction.response.defer()

        # Case 1: Discord user
        if user:
            logger.info(f"Looking up Discord user: {user} (ID: {user.id})")
            db_user = await get_user_guild_aware(user.id, interaction.guild.id)
            if not db_user:
                logger.warning(f"Discord user {user} (ID: {user.id}) not found in database")
                await interaction.followup.send(
                    f"❌ {user.mention} is not registered in our database. Please use the AniList username option.",
                    ephemeral=True
                )
                return
            username = db_user[2]
            logger.info(f"Found AniList username for {user}: {username}")

        # Case 2: Default to self if no args
        elif not username:
            logger.info(f"No parameters provided, checking command user's registration: {interaction.user}")
            db_user = await get_user_guild_aware(interaction.user.id, interaction.guild.id)
            if db_user:
                username = db_user[2]
                logger.info(f"Found AniList username for command user: {username}")
            else:
                logger.warning(f"Command user {interaction.user} (ID: {interaction.user.id}) not registered in database")
                await interaction.followup.send(
                    "⚠️ You must provide either a registered server user or an AniList username. (You are not registered either!)",
                    ephemeral=True
                )
                return

        logger.info(f"Fetching watchlist data for AniList user: {username}")
        
        # Fetch AniList watchlist
        try:
            data = await fetch_watchlist(username)
        except Exception as e:
            logger.error(f"Exception occurred while fetching watchlist for {username}: {e}")
            await interaction.followup.send(f"⚠️ An error occurred while fetching watchlist for **{username}**.", ephemeral=True)
            return
            
        if not data:
            logger.warning(f"No watchlist data returned for username: {username}")
            await interaction.followup.send(f"⚠️ Could not fetch watchlist for **{username}**.", ephemeral=True)
            return

        logger.info(f"Successfully fetched watchlist data for {username}")
        
        anime_lists = data.get("anime", [])
        manga_lists = data.get("manga", [])
        logger.info(f"Found {len(anime_lists)} anime groups and {len(manga_lists)} manga groups for {username}")

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
        logger.info(f"Processed watchlist for {username}: {len(anime_entries)} anime, {len(manga_entries)} manga, {len(all_entries)} total entries")
        
        if not all_entries:
            logger.info(f"No current entries found for {username}")
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

        logger.info(f"Created {len(pages)} pages for {username}'s watchlist")

        # If only one page, just send normally
        if len(pages) == 1:
            logger.info(f"Sending single-page watchlist for {username} to {interaction.user}")
            await interaction.followup.send(embed=pages[0])
            return

        # Send with pagination view
        logger.info(f"Sending multi-page watchlist ({len(pages)} pages) for {username} to {interaction.user}")
        view = WatchlistView(pages, username)
        await interaction.followup.send(embed=pages[0], view=view)
        logger.info(f"Watchlist command completed successfully for {username}")

    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("Watchlist cog loaded successfully")

    async def cog_unload(self):
        """Called when the cog is unloaded"""
        logger.info("Watchlist cog unloaded")


async def setup(bot: commands.Bot):
    await bot.add_cog(Watchlist(bot))
