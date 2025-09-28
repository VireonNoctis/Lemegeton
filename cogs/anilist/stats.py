# cogs/stats.py
import discord
from discord.ext import commands
from discord import app_commands
import random
import logging
import aiohttp

from database import (
    get_user, save_user, upsert_user_stats,
    # Guild-aware functions
    get_user_guild_aware, save_user_guild_aware, upsert_user_stats_guild_aware
)

# -----------------------------
# Logging Setup
# -----------------------------
logger = logging.getLogger("Stats")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Show AniList stats if you are registered")
    async def stats(self, interaction: discord.Interaction):
        logger.info(f"Fetching stats for Discord user: {interaction.user.id} in guild: {interaction.guild.id}")
        
        # Use guild-aware function to get user
        user_record = await get_user_guild_aware(interaction.user.id, interaction.guild.id)
        if not user_record:
            view = discord.ui.View()
            view.add_item(RegisterButton(interaction.user.id, interaction.guild.id))
            await interaction.response.send_message(
                "❌ You are not registered with AniList.\nClick below to register:",
                view=view,
                ephemeral=True
            )
            return

        username = user_record[4]  # Guild-aware schema: (id, discord_id, guild_id, username, anilist_username, anilist_id, created_at, updated_at)
        await interaction.response.defer(ephemeral=False)
        await self.send_stats(interaction, username)

    async def send_stats(self, interaction: discord.Interaction, username: str):
        """Fetch AniList stats directly from API and send embed"""
        logger.info(f"Fetching AniList stats for username: {username}")

        query = """
        query ($username: String) {
          User(name: $username) {
            id
            name
            avatar { large }
            bannerImage
            statistics {
              anime {
                count
                meanScore
                genres { genre count }
                statuses { status count }
                scores { score count }
              }
              manga {
                count
                meanScore
                genres { genre count }
                statuses { status count }
                scores { score count }
              }
            }
          }
        }
        """
        variables = {"username": username}

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post("https://graphql.anilist.co", json={"query": query, "variables": variables}) as resp:
                    if resp.status != 200:
                        logger.error(f"AniList API request failed [status {resp.status}] for {username}")
                        await interaction.followup.send(f"⚠️ Failed to fetch AniList stats for {username}.", ephemeral=True)
                        return
                    data = await resp.json()
            except Exception as e:
                logger.error(f"Error fetching AniList stats: {e}")
                await interaction.followup.send(f"⚠️ Failed to fetch AniList stats for {username}.", ephemeral=True)
                return

        user_data = data.get("data", {}).get("User")
        if not user_data:
            logger.error(f"No AniList user data found for {username}")
            await interaction.followup.send(f"⚠️ No AniList data found for {username}.", ephemeral=True)
            return

        # -----------------------------
        # Extract stats
        # -----------------------------
        stats_anime = user_data["statistics"]["anime"]
        stats_manga = user_data["statistics"]["manga"]

        def calc_avg(scores):
            total = sum(s["score"] * s["count"] for s in scores)
            count = sum(s["count"] for s in scores)
            return round(total / count, 2) if count else 0

        anime_avg = calc_avg(stats_anime["scores"])
        manga_avg = calc_avg(stats_manga["scores"])

        # Top genres
        def top_genres(genres, top_n=5):
            sorted_genres = sorted(genres, key=lambda g: g["count"], reverse=True)
            return sorted_genres[:top_n] if sorted_genres else [{"genre": "N/A", "count": 0}]

        top_anime_genres = top_genres(stats_anime["genres"])
        top_manga_genres = top_genres(stats_manga["genres"])

        # Score distribution bars
        def score_bar(scores):
            bars = ""
            for s in sorted(scores, key=lambda x: x["score"], reverse=True):
                bars += f"{s['score']}⭐ " + "█" * min(s["count"], 10) + f" ({s['count']})\n"
            return bars if bars else "No data"

        anime_scores_bar = score_bar(stats_anime["scores"])
        manga_scores_bar = score_bar(stats_manga["scores"])

        # Save stats in DB
        await upsert_user_stats(
            interaction.user.id,
            user_data["name"],
            stats_manga["count"],
            stats_anime["count"],
            manga_avg,
            anime_avg
        )
        logger.info(f"Upserted stats for {interaction.user.id} ({user_data['name']})")

        # -----------------------------
        # Build embed
        # -----------------------------
        color = discord.Color.random()
        embed = discord.Embed(
            title=f"📊 AniList Stats for {user_data['name']}",
            url=f"https://anilist.co/user/{user_data['name']}/",
            color=color
        )

        # Anime
        embed.add_field(name="🎬 Anime Watched", value=f"{stats_anime['count']} entries", inline=True)
        embed.add_field(name="⭐ Avg Anime Score", value=str(anime_avg), inline=True)
        embed.add_field(
            name="❤️ Top Anime Genres",
            value=", ".join([g["genre"] for g in top_anime_genres]),
            inline=False
        )
        embed.add_field(name="📊 Anime Score Distribution", value=anime_scores_bar, inline=False)

        # Manga
        embed.add_field(name="📖 Manga Read", value=f"{stats_manga['count']} entries", inline=True)
        embed.add_field(name="⭐ Avg Manga Score", value=str(manga_avg), inline=True)
        embed.add_field(
            name="❤️ Top Manga Genres",
            value=", ".join([g["genre"] for g in top_manga_genres]),
            inline=False
        )
        embed.add_field(name="📊 Manga Score Distribution", value=manga_scores_bar, inline=False)

        # Profile images
        if avatar_url := user_data.get("avatar", {}).get("large"):
            embed.set_thumbnail(url=avatar_url)
        if banner_url := user_data.get("bannerImage"):
            embed.set_image(url=banner_url)

        embed.set_footer(text="Data from AniList")

        await interaction.followup.send(embed=embed)


# -----------------------------
# Registration Button and Modal
# -----------------------------
class RegisterButton(discord.ui.Button):
    def __init__(self, user_id: int, guild_id: int):
        super().__init__(label="Register AniList", style=discord.ButtonStyle.primary)
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AniListRegisterModal(self.user_id, self.guild_id))


class AniListRegisterModal(discord.ui.Modal, title="Register AniList"):
    username = discord.ui.TextInput(label="AniList Username", placeholder="e.g. yourusername", required=True)

    def __init__(self, user_id: int, guild_id: int):
        super().__init__()
        self.user_id = user_id
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        anilist_name = str(self.username.value).strip()
        
        # Use guild-aware function to save user
        await save_user_guild_aware(self.user_id, self.guild_id, anilist_name)

        # Fetch stats immediately after registering
        cog: Stats = interaction.client.get_cog("Stats")
        if cog:
            await cog.send_stats(interaction, anilist_name)
        else:
            await interaction.response.send_message(
                f"✅ Registered AniList username **{anilist_name}** successfully!",
                ephemeral=False
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
