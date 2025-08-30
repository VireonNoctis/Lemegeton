import discord
from discord.ext import commands, tasks
from discord import app_commands
from typing import List, Dict, Optional
from database import gather_user_stats, update_user_stats
import logging

# ------------------------------------------------------
# Simple Logging Setup
# ------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("LeaderboardCog")

# ------------------------------------------------------
# Leaderboard Cog
# ------------------------------------------------------
class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_stats_task.start()
        logger.info("Leaderboard cog loaded and background task started")

    def cog_unload(self):
        self.update_stats_task.cancel()
        logger.info("Leaderboard cog unloaded and background task canceled")

    @tasks.loop(hours=24)
    async def update_stats_task(self):
        try:
            await update_user_stats()
            logger.info("Leaderboard stats updated successfully")
        except Exception as e:
            logger.exception(f"Failed to update leaderboard stats: {e}")

    def create_leaderboard_pages(self, stats: List[Dict], media_type: str):
        pages = []

        if media_type == "manga":
            total_key = "manga_total"
            completed_key = "manga_completed"
            avg_score_key = "manga_avg"
            progress_key = "manga_progress"
            chapters_key = "manga_chapters"
        else:
            total_key = "anime_total"
            completed_key = "anime_completed"
            avg_score_key = "anime_avg"
            progress_key = "anime_progress"
            chapters_key = None

        # Total Entries
        embed_total = discord.Embed(
            title=f"🏆 {media_type.capitalize()} Leaderboard: Total Entries",
            color=discord.Color.gold()
        )
        for i, user in enumerate(sorted(stats, key=lambda x: x[total_key], reverse=True)[:10], start=1):
            embed_total.add_field(name=f"{i}. {user['username']}", value=f"Total: {user[total_key]}", inline=False)
        pages.append(embed_total)

        # Completed
        embed_completed = discord.Embed(
            title=f"🏆 {media_type.capitalize()} Leaderboard: Completed",
            color=discord.Color.blue()
        )
        for i, user in enumerate(sorted(stats, key=lambda x: x[completed_key], reverse=True)[:10], start=1):
            embed_completed.add_field(name=f"{i}. {user['username']}", value=f"Completed: {user[completed_key]}", inline=False)
        pages.append(embed_completed)

        # Average Score
        embed_avg = discord.Embed(
            title=f"🏆 {media_type.capitalize()} Leaderboard: Average Score",
            color=discord.Color.green()
        )
        for i, user in enumerate(sorted(stats, key=lambda x: x[avg_score_key], reverse=True)[:10], start=1):
            embed_avg.add_field(name=f"{i}. {user['username']}", value=f"Avg Score: {user[avg_score_key]}", inline=False)
        pages.append(embed_avg)

        # Golden Ratio (Average Chapters per Manga)
        if media_type == "manga":
            embed_golden = discord.Embed(
                title=f"🏆 {media_type.capitalize()} Leaderboard: Golden Ratio",
                description="Average chapters per manga entry",
                color=discord.Color.purple()
            )
            sorted_golden = sorted(
                stats,
                key=lambda x: (x[chapters_key] / x[total_key]) if x[total_key] else 0,
                reverse=True
            )
            for i, user in enumerate(sorted_golden[:10], start=1):
                avg_chap = (user[chapters_key] / user[total_key]) if user[total_key] else 0
                embed_golden.add_field(
                    name=f"{i}. {user['username']}",
                    value=f"Avg Chapters per Manga: {round(avg_chap, 2)}",
                    inline=False
                )
            pages.append(embed_golden)

        logger.debug(f"Created {len(pages)} leaderboard pages for {media_type}")
        return pages

    @app_commands.command(name="leaderboard", description="View the server leaderboard with cached AniList stats")
    @app_commands.choices(media=[
        app_commands.Choice(name="manga", value="manga"),
        app_commands.Choice(name="anime", value="anime")
    ])
    async def leaderboard(self, interaction: discord.Interaction, media: Optional[str] = "manga"):
        await interaction.response.defer()
        logger.info(f"User {interaction.user.id} requested {media} leaderboard")

        try:
            stats = await gather_user_stats()
            if not stats:
                await interaction.followup.send("No registered users found.")
                logger.info("Leaderboard request failed: no users found")
                return

            pages = self.create_leaderboard_pages(stats, media)
            current = 0
            msg = await interaction.followup.send(embed=pages[current])

            class Pager(discord.ui.View):
                def __init__(self, cog):
                    super().__init__(timeout=120)
                    self.cog = cog

                @discord.ui.button(label="◀", style=discord.ButtonStyle.grey)
                async def prev(self, interaction_: discord.Interaction, button: discord.ui.Button):
                    nonlocal current
                    current = (current - 1) % len(pages)
                    await interaction_.response.edit_message(embed=pages[current])

                @discord.ui.button(label="▶", style=discord.ButtonStyle.grey)
                async def next(self, interaction_: discord.Interaction, button: discord.ui.Button):
                    nonlocal current
                    current = (current + 1) % len(pages)
                    await interaction_.response.edit_message(embed=pages[current])

                @discord.ui.button(label="🔄 Force Update", style=discord.ButtonStyle.green)
                async def force_update(self, interaction_: discord.Interaction, button: discord.ui.Button):
                    await interaction_.response.defer()
                    try:
                        await update_user_stats()
                        updated_stats = await gather_user_stats()
                        nonlocal pages, current
                        pages = self.cog.create_leaderboard_pages(updated_stats, media)
                        current = 0
                        await interaction_.followup.send("✅ Leaderboard updated successfully!", ephemeral=True)
                        await interaction_.edit_original_response(embed=pages[current])
                        logger.info(f"Leaderboard forced update by user {interaction_.user.id}")
                    except Exception as e:
                        await interaction_.followup.send(f"❌ Failed to update leaderboard: {e}", ephemeral=True)
                        logger.exception(f"Failed leaderboard update by user {interaction_.user.id}: {e}")

            await msg.edit(view=Pager(self))

        except Exception as e:
            await interaction.followup.send("❌ An error occurred while fetching the leaderboard.", ephemeral=True)
            logger.exception(f"Error in /leaderboard command: {e}")


# ------------------------------------------------------
# Cog Setup
# ------------------------------------------------------
async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
