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

def build_achievements(anime_stats: dict, manga_stats: dict) -> Dict[str, any]:
    """Build achievements with progress tracking"""
    achieved = []
    progress = []

    # Helper: counts
    a_completed = status_count(anime_stats.get("statuses", []), "COMPLETED")
    m_completed = status_count(manga_stats.get("statuses", []), "COMPLETED")
    a_planning = status_count(anime_stats.get("statuses", []), "PLANNING")
    m_planning = status_count(manga_stats.get("statuses", []), "PLANNING")
    a_watching = status_count(anime_stats.get("statuses", []), "CURRENT")
    m_reading = status_count(manga_stats.get("statuses", []), "CURRENT")
    a_paused = status_count(anime_stats.get("statuses", []), "PAUSED")
    m_paused = status_count(manga_stats.get("statuses", []), "PAUSED")

    # Totals
    total_manga = manga_stats.get("count", 0)
    total_anime = anime_stats.get("count", 0)

    # Means (use weighted by buckets, not AniList meanScore to keep consistent with bars)
    a_avg = calc_weighted_avg(anime_stats.get("scores", []))
    m_avg = calc_weighted_avg(manga_stats.get("scores", []))

    # Genre variety calculation
    all_genres = {}
    for g in manga_stats.get("genres", []):
        all_genres[g["genre"]] = all_genres.get(g["genre"], 0) + g["count"]
    for g in anime_stats.get("genres", []):
        all_genres[g["genre"]] = all_genres.get(g["genre"], 0) + g["count"]
    
    unique_genres = len(all_genres)
    max_genre_count = max(all_genres.values()) if all_genres else 0

    # MANGA COMPLETION ACHIEVEMENTS
    manga_milestones = [
        (10, "📚 First Steps (10 Manga)"),
        (25, "📖 Getting Started (25 Manga)"),
        (50, "📚 Reader (50 Manga)"),
        (100, "📚 Manga Enthusiast (100 Manga)"),
        (250, "📖 Bookworm (250 Manga)"),
        (500, "📚 Completionist (500 Manga)"),
        (750, "📚 Manga Master (750 Manga)"),
        (1000, "📚 Ultimate Manga Collector (1000 Manga)")
    ]

    for threshold, title in manga_milestones:
        if m_completed >= threshold:
            achieved.append(title)
        else:
            prog_bar = "█" * min(10, int(m_completed / threshold * 10))
            prog_bar += "░" * (10 - len(prog_bar))
            progress.append(f"{title}\n`{prog_bar}` {m_completed}/{threshold}")
            break

    # ANIME COMPLETION ACHIEVEMENTS
    anime_milestones = [
        (10, "🎬 First Watch (10 Anime)"),
        (25, "🎥 Getting Into It (25 Anime)"),
        (50, "🎬 Watcher (50 Anime)"),
        (100, "🎬 Anime Enthusiast (100 Anime)"),
        (250, "🎥 Binge Watcher (250 Anime)"),
        (500, "🎬 Anime Addict (500 Anime)"),
        (750, "🎬 Anime Master (750 Anime)"),
        (1000, "🎬 Anime Marathoner (1000 Anime)")
    ]

    for threshold, title in anime_milestones:
        if a_completed >= threshold:
            achieved.append(title)
        else:
            prog_bar = "█" * min(10, int(a_completed / threshold * 10))
            prog_bar += "░" * (10 - len(prog_bar))
            progress.append(f"{title}\n`{prog_bar}` {a_completed}/{threshold}")
            break

    # SCORING ACHIEVEMENTS
    score_achievements = [
        (6.0, "⭐ Fair Critic"),
        (7.0, "⭐⭐ Good Taste"),
        (8.0, "🏆 High Standards"),
        (8.5, "🥇 Elite Critic"),
        (9.0, "💎 Perfect Taste")
    ]

    # Manga scoring
    for threshold, title in score_achievements:
        if m_avg >= threshold and m_completed >= 10:
            achieved.append(f"{title} (Manga: {m_avg})")
        elif m_completed >= 10:
            next_threshold = next((t for t, _ in score_achievements if t > m_avg), None)
            if next_threshold:
                prog_bar = "█" * min(10, int(m_avg / next_threshold * 10))
                prog_bar += "░" * (10 - len(prog_bar))
                next_title = next(title for t, title in score_achievements if t == next_threshold)
                progress.append(f"{next_title} (Manga)\n`{prog_bar}` {m_avg:.1f}/{next_threshold}")
            break

    # Anime scoring
    for threshold, title in score_achievements:
        if a_avg >= threshold and a_completed >= 10:
            achieved.append(f"{title} (Anime: {a_avg})")
        elif a_completed >= 10:
            next_threshold = next((t for t, _ in score_achievements if t > a_avg), None)
            if next_threshold:
                prog_bar = "█" * min(10, int(a_avg / next_threshold * 10))
                prog_bar += "░" * (10 - len(prog_bar))
                next_title = next(title for t, title in score_achievements if t == next_threshold)
                progress.append(f"{next_title} (Anime)\n`{prog_bar}` {a_avg:.1f}/{next_threshold}")
            break

    # GENRE VARIETY ACHIEVEMENTS
    genre_milestones = [
        (5, "🎭 Explorer (5+ genres)"),
        (10, "🔄 Mixed Tastes (10+ genres)"),
        (15, "🌟 Genre Connoisseur (15+ genres)"),
        (20, "🌈 Diversity Master (20+ genres)")
    ]

    for threshold, title in genre_milestones:
        if unique_genres >= threshold:
            achieved.append(title)
        else:
            prog_bar = "█" * min(10, int(unique_genres / threshold * 10))
            prog_bar += "░" * (10 - len(prog_bar))
            progress.append(f"{title}\n`{prog_bar}` {unique_genres}/{threshold}")
            break

    # BINGE ACHIEVEMENTS
    binge_milestones = [
        (25, "🔥 Genre Fan"),
        (50, "🔥 Binge Mode"),
        (100, "🔥 Obsessed"),
        (200, "🔥 Genre Master")
    ]

    for threshold, title in binge_milestones:
        if max_genre_count >= threshold:
            achieved.append(f"{title} ({max_genre_count} in one genre)")
        else:
            prog_bar = "█" * min(10, int(max_genre_count / threshold * 10))
            prog_bar += "░" * (10 - len(prog_bar))
            progress.append(f"{title}\n`{prog_bar}` {max_genre_count}/{threshold}")
            break

    # ACTIVITY ACHIEVEMENTS
    total_entries = total_manga + total_anime
    activity_milestones = [
        (50, "📝 Getting Active (50+ entries)"),
        (100, "📝 Active User (100+ entries)"),
        (250, "📝 Super Active (250+ entries)"),
        (500, "📝 Power User (500+ entries)"),
        (1000, "📝 Database Destroyer (1000+ entries)")
    ]

    for threshold, title in activity_milestones:
        if total_entries >= threshold:
            achieved.append(title)
        else:
            prog_bar = "█" * min(10, int(total_entries / threshold * 10))
            prog_bar += "░" * (10 - len(prog_bar))
            progress.append(f"{title}\n`{prog_bar}` {total_entries}/{threshold}")
            break

    # PLANNING ACHIEVEMENTS
    total_planning = a_planning + m_planning
    if total_planning >= 100:
        achieved.append("📋 Planning Master (100+ planned)")
    elif total_planning >= 50:
        achieved.append("📋 Future Watcher (50+ planned)")
    elif total_planning >= 10:
        achieved.append("� Organized (10+ planned)")

    # MULTITASKING ACHIEVEMENTS
    total_current = a_watching + m_reading
    if total_current >= 20:
        achieved.append("⚡ Multitasker (20+ current)")
    elif total_current >= 10:
        achieved.append("⚡ Juggler (10+ current)")

    # COMPLETION RATE ACHIEVEMENTS
    if total_entries > 0:
        completion_rate = (a_completed + m_completed) / total_entries
        if completion_rate >= 0.8:
            achieved.append(f"✅ Finisher ({completion_rate:.1%} completion rate)")
        elif completion_rate >= 0.6:
            achieved.append(f"✅ Good Follow-Through ({completion_rate:.1%} completion rate)")

    return {
        "achieved": achieved,
        "progress": progress,
        "stats": {
            "manga_completed": m_completed,
            "anime_completed": a_completed,
            "manga_avg": m_avg,
            "anime_avg": a_avg,
            "total_genres": unique_genres,
            "max_genre": max_genre_count,
            "total_entries": total_entries,
            "completion_rate": (a_completed + m_completed) / total_entries if total_entries > 0 else 0
        }
    }


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
        achievements_data = build_achievements(stats_anime, stats_manga)
        
        # Create achievements button view
        view = AchievementsView(achievements_data, user_data, avatar_url, profile_url)

        pages: List[discord.Embed] = [manga_embed, anime_embed]

        # Send first page and attach pager with achievements button
        pager = ProfilePager(pages, view)
        view.profile_pager = pager  # Set the reference after creating the pager
        msg = await interaction.followup.send(embed=pages[0], view=pager)


class ProfilePager(discord.ui.View):
    def __init__(self, pages: List[discord.Embed], achievements_view):
        super().__init__(timeout=120)
        self.pages = pages
        self.index = 0
        self.achievements_view = achievements_view

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

    @discord.ui.button(label="🏅 Achievements", style=discord.ButtonStyle.primary)
    async def show_achievements(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=self.achievements_view.get_current_embed(),
            view=self.achievements_view
        )


class AchievementsView(discord.ui.View):
    def __init__(self, achievements_data: Dict, user_data: Dict, avatar_url: str, profile_url: str, profile_pager=None):
        super().__init__(timeout=120)
        self.achievements_data = achievements_data
        self.user_data = user_data
        self.avatar_url = avatar_url
        self.profile_url = profile_url
        self.current_page = 0  # 0 = achieved, 1 = progress, 2 = stats
        self.profile_pager = profile_pager

    def get_current_embed(self) -> discord.Embed:
        if self.current_page == 0:
            return self.get_achieved_embed()
        elif self.current_page == 1:
            return self.get_progress_embed()
        else:
            return self.get_stats_embed()

    def get_achieved_embed(self) -> discord.Embed:
        achieved = self.achievements_data["achieved"]
        embed = discord.Embed(
            title=f"🏅 Achievements — {self.user_data['name']}",
            url=self.profile_url,
            color=discord.Color.gold()
        )
        
        if achieved:
            description = "\n".join(f"✅ {achievement}" for achievement in achieved)
            embed.description = description if len(description) <= 4096 else description[:4090] + "..."
        else:
            embed.description = "No achievements unlocked yet. Keep watching and reading to unlock more!"
        
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        
        embed.set_footer(text=f"Achieved: {len(achieved)} • Page 1/3")
        return embed

    def get_progress_embed(self) -> discord.Embed:
        progress = self.achievements_data["progress"]
        embed = discord.Embed(
            title=f"📈 Progress — {self.user_data['name']}",
            url=self.profile_url,
            color=discord.Color.blue()
        )
        
        if progress:
            # Show only first 8 progress items to fit in embed
            description = "\n\n".join(progress[:8])
            embed.description = description if len(description) <= 4096 else description[:4090] + "..."
            
            if len(progress) > 8:
                embed.set_footer(text=f"Progress: {len(progress)} items (showing first 8) • Page 2/3")
            else:
                embed.set_footer(text=f"Progress: {len(progress)} items • Page 2/3")
        else:
            embed.description = "All available achievements unlocked! 🎉"
            embed.set_footer(text="Progress: Complete • Page 2/3")
        
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        
        return embed

    def get_stats_embed(self) -> discord.Embed:
        stats = self.achievements_data["stats"]
        embed = discord.Embed(
            title=f"📊 Achievement Stats — {self.user_data['name']}",
            url=self.profile_url,
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="📚 Manga Stats",
            value=f"Completed: **{stats['manga_completed']:,}**\nAvg Score: **{stats['manga_avg']:.1f}**",
            inline=True
        )
        
        embed.add_field(
            name="🎬 Anime Stats", 
            value=f"Completed: **{stats['anime_completed']:,}**\nAvg Score: **{stats['anime_avg']:.1f}**",
            inline=True
        )
        
        embed.add_field(
            name="🎭 Variety",
            value=f"Genres: **{stats['total_genres']}**\nMax in One: **{stats['max_genre']}**",
            inline=True
        )
        
        embed.add_field(
            name="📝 Activity",
            value=f"Total Entries: **{stats['total_entries']:,}**",
            inline=True
        )
        
        embed.add_field(
            name="✅ Completion Rate",
            value=f"**{stats['completion_rate']:.1%}**",
            inline=True
        )
        
        achieved_count = len(self.achievements_data["achieved"])
        progress_count = len(self.achievements_data["progress"])
        total_possible = achieved_count + progress_count
        
        embed.add_field(
            name="🏆 Achievement Progress",
            value=f"**{achieved_count}/{total_possible}** unlocked",
            inline=True
        )
        
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        
        embed.set_footer(text="Achievement Statistics • Page 3/3")
        return embed

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

    @discord.ui.button(label="🏅 Achieved", style=discord.ButtonStyle.success)
    async def show_achieved(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    @discord.ui.button(label="📈 Progress", style=discord.ButtonStyle.primary)
    async def show_progress(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 1
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.secondary)
    async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 2
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)

    @discord.ui.button(label="◀ Back to Profile", style=discord.ButtonStyle.secondary, row=1)
    async def back_to_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.profile_pager:
            await interaction.response.edit_message(
                embed=self.profile_pager.pages[self.profile_pager.index],
                view=self.profile_pager
            )


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
