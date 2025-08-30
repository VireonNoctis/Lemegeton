import discord
from discord.ext import commands
from discord import app_commands
import random

from database import get_user, save_user, upsert_user_stats
from helpers.media_helper import fetch_user_stats


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Show AniList stats if you are registered")
    async def stats(self, interaction: discord.Interaction):
        # Check if user is registered
        user = await get_user(interaction.user.id)
        if not user:
            # If not registered, show register button
            view = discord.ui.View()
            view.add_item(RegisterButton(interaction.user.id))
            await interaction.response.send_message(
                "❌ You are not registered with AniList.\nClick below to register:",
                view=view,
                ephemeral=True
            )
            return

        username = user[1]  # DB schema: (id, discord_id, username) or (discord_id, username)
        await self.send_stats(interaction, username)

    async def send_stats(self, interaction: discord.Interaction, username: str):
        """Helper to fetch stats and send embed"""
        data = await fetch_user_stats(username)
        user_data = data.get("data", {}).get("User")

        if not user_data:
            await interaction.followup.send(f"⚠️ Failed to fetch AniList stats for {username}.", ephemeral=True)
            return

        stats_anime = user_data["statistics"]["anime"]
        stats_manga = user_data["statistics"]["manga"]

        # Calculate averages from score distribution
        def calc_avg(scores):
            total = sum(s["score"] * s["count"] for s in scores)
            count = sum(s["count"] for s in scores)
            return round(total / count, 2) if count else 0

        anime_avg = calc_avg(stats_anime["scores"])
        manga_avg = calc_avg(stats_manga["scores"])

        fav_anime = max(stats_anime["genres"], key=lambda g: g["count"], default={"genre": "N/A"})
        fav_manga = max(stats_manga["genres"], key=lambda g: g["count"], default={"genre": "N/A"})

        # ✅ Save stats to database
        await upsert_user_stats(
            interaction.user.id,
            user_data["name"],
            stats_manga["count"],
            stats_anime["count"],
            manga_avg,
            anime_avg
        )

        # 🎨 Random embed color
        color = discord.Color(random.randint(0, 0xFFFFFF))

        # 📊 Stats embed
        embed = discord.Embed(
            title=f"📊 AniList Stats for {user_data['name']}",
            url=f"https://anilist.co/user/{user_data['name']}/",
            color=color
        )
        embed.add_field(name="🎬 Anime Watched", value=f"{stats_anime['count']} entries", inline=True)
        embed.add_field(name="⭐ Avg Anime Score", value=str(anime_avg), inline=True)
        embed.add_field(name="❤️ Fav Anime Genre", value=fav_anime['genre'], inline=True)

        embed.add_field(name="📖 Manga Read", value=f"{stats_manga['count']} entries", inline=True)
        embed.add_field(name="⭐ Avg Manga Score", value=str(manga_avg), inline=True)
        embed.add_field(name="❤️ Fav Manga Genre", value=fav_manga['genre'], inline=True)

        # ✅ Add avatar + banner
        avatar_url = user_data.get("avatar", {}).get("large")
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        banner_url = user_data.get("bannerImage")
        if banner_url:
            embed.set_image(url=banner_url)

        embed.set_footer(text="Data from AniList")

        await interaction.followup.send(embed=embed)


class RegisterButton(discord.ui.Button):
    def __init__(self, user_id: int):
        super().__init__(label="Register AniList", style=discord.ButtonStyle.primary)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AniListRegisterModal(self.user_id))


class AniListRegisterModal(discord.ui.Modal, title="Register AniList"):
    username = discord.ui.TextInput(label="AniList Username", placeholder="e.g. yourusername", required=True)

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        anilist_name = str(self.username.value).strip()
        await save_user(self.user_id, anilist_name)

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
