# cogs/profile.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import logging
from typing import Optional, List, Dict, Tuple

from database import get_user, save_user, upsert_user_stats
from config import GUILD_ID

ANILIST_API_URL = "https://graphql.anilist.co"

logger = logging.getLogger("Profile")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(h)


# -----------------------------
# AniList fetch helpers
# -----------------------------
USER_STATS_QUERY = """
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

async def fetch_user_stats(username: str) -> Optional[dict]:
    variables = {"username": username}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(ANILIST_API_URL, json={"query": USER_STATS_QUERY, "variables": variables}) as resp:
                if resp.status != 200:
                    logger.error(f"AniList API request failed [{resp.status}] for {username}")
                    return None
                return await resp.json()
        except Exception as e:
            logger.exception(f"Error fetching AniList stats for {username}: {e}")
            return None


# -----------------------------
# Utility: build text sections
# -----------------------------
def calc_weighted_avg(scores: List[Dict[str, int]]) -> float:
    total = sum(s["score"] * s["count"] for s in scores)
    count = sum(s["count"] for s in scores)
    return round(total / count, 2) if count else 0.0

def top_genres(genres: List[Dict[str, int]], n: int = 5) -> List[str]:
    return [g["genre"] for g in sorted(genres, key=lambda g: g["count"], reverse=True)[:n]]

def score_bar(scores: List[Dict[str, int]]) -> str:
    # Sorted high→low, up to 10 blocks per score bucket
    if not scores:
        return "No data"
    parts = []
    for s in sorted(scores, key=lambda x: x["score"], reverse=True):
        blocks = "█" * min(s["count"], 10)
        parts.append(f"{s['score']}⭐ {blocks} ({s['count']})")
    out = "\n".join(parts)
    return out if len(out) <= 1024 else out[:1020] + "…"

def status_count(statuses: List[Dict[str, int]], key: str) -> int:
    for s in statuses:
        if s["status"] == key:
            return s["count"]
    return 0

def build_achievements(anime_stats: dict, manga_stats: dict) -> List[str]:
    ach = []

    # Helper: counts
    a_completed = status_count(anime_stats.get("statuses", []), "COMPLETED")
    m_completed = status_count(manga_stats.get("statuses", []), "COMPLETED")

    # Totals
    total_manga = manga_stats.get("count", 0)
    total_anime = anime_stats.get("count", 0)

    # Means (use weighted by buckets, not AniList meanScore to keep consistent with bars)
    a_avg = calc_weighted_avg(anime_stats.get("scores", []))
    m_avg = calc_weighted_avg(manga_stats.get("scores", []))

    # Completion milestones
    if m_completed >= 100:  ach.append("📚 Manga Enthusiast (100+ Manga)")
    if m_completed >= 250:  ach.append("📖 Bookworm (250+ Manga)")
    if m_completed >= 500:  ach.append("📚 Completionist (500+ Manga)")
    if m_completed >= 1000: ach.append("📚 Ultimate Manga Collector (1000+ Manga)")

    if a_completed >= 100:  ach.append("🎬 Anime Enthusiast (100+ Anime)")
    if a_completed >= 250:  ach.append("🎥 Binge Watcher (250+ Anime)")
    if a_completed >= 500:  ach.append("🎬 Anime Addict (500+ Anime)")
    if a_completed >= 1000: ach.append("🎬 Anime Marathoner (1000+ Anime)")

    # High scores
    if m_avg >= 8: ach.append("🏆 Manga Critic (Avg ≥ 8)")
    if m_avg >= 9: ach.append("🥇 Score Master (Avg ≥ 9)")
    if a_avg >= 8: ach.append("🎖 Anime Critic (Avg ≥ 8)")
    if a_avg >= 9: ach.append("🥇 Anime Score Master (Avg ≥ 9)")

    # Genre variety / binge using statistics.genres counts
    all_genres = {}
    for g in manga_stats.get("genres", []):
        all_genres[g["genre"]] = all_genres.get(g["genre"], 0) + g["count"]
    for g in anime_stats.get("genres", []):
        all_genres[g["genre"]] = all_genres.get(g["genre"], 0) + g["count"]

    if len(all_genres) >= 10:
        ach.append("🔄 Mixed Tastes (10+ genres)")
    if any(v >= 50 for v in all_genres.values()):
        ach.append("🔥 Binge Mode (50+ in one genre)")

    # Activity
    if total_manga >= 100 or total_anime >= 100:
        ach.append("📝 Active User (100+ entries)")

    return ach


# -----------------------------
# The Cog
# -----------------------------
class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(name="profile", description="View your AniList profile (with stats & achievements) or another user's.")
    @app_commands.describe(user="Optional: Discord user whose profile to view")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user

        # fetch AniList username from DB
        record = await get_user(target.id)  # schema: (id, discord_id, username)
        if not record:
            # Not registered → present registration
            view = discord.ui.View()
            view.add_item(RegisterButton(target.id))
            await interaction.response.send_message(
                f"❌ {target.mention} hasn’t registered an AniList username.\nClick below to register:",
                view=view,
                ephemeral=True if target.id == interaction.user.id else False
            )
            return

        username = record[2]
        await interaction.response.defer(ephemeral=False)

        data = await fetch_user_stats(username)
        if not data:
            await interaction.followup.send(f"⚠️ Failed to fetch AniList data for **{username}**.", ephemeral=True)
            return

        user_data = data.get("data", {}).get("User")
        if not user_data:
            await interaction.followup.send(f"⚠️ No AniList data found for **{username}**.", ephemeral=True)
            return

        stats_anime = user_data["statistics"]["anime"]
        stats_manga = user_data["statistics"]["manga"]

        # Compute weighted averages from distribution buckets
        anime_avg = calc_weighted_avg(stats_anime.get("scores", []))
        manga_avg = calc_weighted_avg(stats_manga.get("scores", []))

        # Persist headline stats
        await upsert_user_stats(
            discord_id=target.id,
            username=user_data["name"],
            total_manga=stats_manga.get("count", 0),
            total_anime=stats_anime.get("count", 0),
            avg_manga_score=manga_avg,
            avg_anime_score=anime_avg
        )

        # Build pages
        avatar_url = (user_data.get("avatar") or {}).get("large")
        banner_url = user_data.get("bannerImage")
        profile_url = f"https://anilist.co/user/{user_data['name']}/"

        # Manga page
        manga_embed = discord.Embed(
            title=f"📖 {user_data['name']}'s Manga Profile",
            url=profile_url,
            color=discord.Color.blurple()
        )
        if avatar_url: manga_embed.set_thumbnail(url=avatar_url)
        if banner_url: manga_embed.set_image(url=banner_url)
        manga_embed.add_field(name="Total Manga", value=str(stats_manga.get("count", 0)), inline=True)
        manga_embed.add_field(name="Avg Score", value=str(manga_avg), inline=True)
        manga_embed.add_field(
            name="Top Genres",
            value=", ".join(top_genres(stats_manga.get("genres", []), 5)) or "N/A",
            inline=False
        )
        manga_embed.add_field(
            name="Score Distribution",
            value=score_bar(stats_manga.get("scores", [])),
            inline=False
        )
        manga_embed.set_footer(text="Data from AniList • Page 1/3")

        # Anime page
        anime_embed = discord.Embed(
            title=f"🎬 {user_data['name']}'s Anime Profile",
            url=profile_url,
            color=discord.Color.green()
        )
        if avatar_url: anime_embed.set_thumbnail(url=avatar_url)
        if banner_url: anime_embed.set_image(url=banner_url)
        anime_embed.add_field(name="Total Anime", value=str(stats_anime.get("count", 0)), inline=True)
        anime_embed.add_field(name="Avg Score", value=str(anime_avg), inline=True)
        anime_embed.add_field(
            name="Top Genres",
            value=", ".join(top_genres(stats_anime.get("genres", []), 5)) or "N/A",
            inline=False
        )
        anime_embed.add_field(
            name="Score Distribution",
            value=score_bar(stats_anime.get("scores", [])),
            inline=False
        )
        anime_embed.set_footer(text="Data from AniList • Page 2/3")

        # Achievements pages (paginate 10 per page)
        achievements = build_achievements(stats_anime, stats_manga)
        ach_pages: List[discord.Embed] = []
        if not achievements:
            e = discord.Embed(
                title=f"🏅 Achievements — {user_data['name']}",
                description="No achievements yet. Keep watching/reading!",
                url=profile_url,
                color=discord.Color.gold()
            )
            if avatar_url: e.set_thumbnail(url=avatar_url)
            e.set_footer(text="Data from AniList • Page 3/3")
            ach_pages.append(e)
        else:
            page_size = 10
            for i in range(0, len(achievements), page_size):
                chunk = achievements[i:i+page_size]
                page_num = (i // page_size) + 3  # pages start at 3
                e = discord.Embed(
                    title=f"🏅 Achievements — {user_data['name']}",
                    description="\n".join(f"{idx+1+i}. {a}" for idx, a in enumerate(chunk)),
                    url=profile_url,
                    color=discord.Color.gold()
                )
                if avatar_url: e.set_thumbnail(url=avatar_url)
                e.set_footer(text=f"Data from AniList • Page {page_num}/{2 + ((len(achievements)-1)//page_size + 1)}")
                ach_pages.append(e)

        pages: List[discord.Embed] = [manga_embed, anime_embed] + ach_pages

        # Send first page and attach pager
        msg = await interaction.followup.send(embed=pages[0], view=Pager(pages))


class Pager(discord.ui.View):
    def __init__(self, pages: List[discord.Embed]):
        super().__init__(timeout=120)
        self.pages = pages
        self.index = 0

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.pages)
        await interaction.response.edit_message(embed=self.pages[self.index], view=self)


# -----------------------------
# Registration UI
# -----------------------------
class RegisterButton(discord.ui.Button):
    def __init__(self, user_id: int):
        super().__init__(label="Register AniList", style=discord.ButtonStyle.primary)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        # Only allow the intended user to register themselves
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You can’t register for someone else.", ephemeral=True)
            return
        await interaction.response.send_modal(AniListRegisterModal(self.user_id))


class AniListRegisterModal(discord.ui.Modal, title="Register AniList"):
    username = discord.ui.TextInput(label="AniList Username", placeholder="e.g. yourusername", required=True)

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        anilist_name = str(self.username.value).strip()
        await save_user(self.user_id, anilist_name)

        # After registering, immediately show the new profile
        cog: Profile = interaction.client.get_cog("Profile")
        if cog:
            # Call /profile for this same user
            await cog.profile.callback(cog, interaction, None)  # reuse handler (no target -> self)
        else:
            await interaction.response.send_message(
                f"✅ Registered AniList username **{anilist_name}** successfully! Try `/profile`.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
