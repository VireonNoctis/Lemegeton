import discord
from discord.ext import commands
from discord import app_commands
import random

from helpers.media_helper import fetch_watchlist
from database import get_user


class Watchlist(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

        # Case 1: A Discord user was selected
        if user:
            db_user = await get_user(user.id)
            if not db_user:
                await interaction.followup.send(
                    f"❌ {user.mention} is not registered in our database. Please use the AniList username option.",
                    ephemeral=True
                )
                return
            username = db_user[1]  # DB schema: (discord_id, anilist_name)

        # Case 2: No username provided → default to self (if registered)
        elif not username:
            db_user = await get_user(interaction.user.id)
            if db_user:
                username = db_user[1]
            else:
                await interaction.followup.send(
                    "⚠️ You must provide either a registered server user or an AniList username. (You are not registered either!)",
                    ephemeral=True
                )
                return

        # Case 3: AniList username manually typed → use directly
        # (no DB check required here)

        # Fetch watchlist
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

        if not anime_entries and not manga_entries:
            await interaction.followup.send(f"ℹ️ **{username}** is not watching or reading anything right now.")
            return

        embed = discord.Embed(
            title=f"📺 Watchlist for {username}",
            description="Here’s what they are currently watching/reading:",
            color=discord.Color(random.randint(0, 0xFFFFFF))
        )

        if anime_entries:
            embed.add_field(name="🎬 Anime", value="\n".join(anime_entries[:10]), inline=False)
        if manga_entries:
            embed.add_field(name="📖 Manga / 📚 Light Novels", value="\n".join(manga_entries[:10]), inline=False)

        embed.set_footer(text="Data from AniList")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Watchlist(bot))
