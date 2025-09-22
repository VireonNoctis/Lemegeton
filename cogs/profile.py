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
        formats { format count }
      }
      manga {
        count
        meanScore
        genres { genre count }
        statuses { status count }
        scores { score count }
        formats { format count }
        countries { country count }
      }
    }
    favourites {
      anime(perPage: 10) {
        nodes {
          id
          title { romaji english }
          coverImage { large }
          siteUrl
          averageScore
          genres
          format
          episodes
          status
        }
      }
      manga(perPage: 10) {
        nodes {
          id
          title { romaji english }
          coverImage { large }
          siteUrl
          averageScore
          genres
          format
          chapters
          volumes
          status
        }
      }
      characters(perPage: 10) {
        nodes {
          id
          name { full }
          image { large }
          siteUrl
        }
      }
      studios(perPage: 10) {
        nodes {
          id
          name
          siteUrl
        }
      }
      staff(perPage: 10) {
        nodes {
          id
          name { full }
          image { large }
          siteUrl
          primaryOccupations
        }
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
    a_dropped = status_count(anime_stats.get("statuses", []), "DROPPED")
    m_dropped = status_count(manga_stats.get("statuses", []), "DROPPED")

    # Totals
    total_manga = manga_stats.get("count", 0)
    total_anime = anime_stats.get("count", 0)

    # Means (use weighted by buckets, not AniList meanScore to keep consistent with bars)
    a_avg = calc_weighted_avg(anime_stats.get("scores", []))
    m_avg = calc_weighted_avg(manga_stats.get("scores", []))

    # Format distribution for manga - using country data to distinguish Manga/Manhwa/Manhua
    # Adjust counts to exclude planning entries
    total_manga_entries = total_manga
    manga_planning_ratio = m_planning / total_manga_entries if total_manga_entries > 0 else 0
    logger.info(f"Manga planning ratio: {manga_planning_ratio} (planning: {m_planning}, total: {total_manga_entries})")
    
    format_distribution = {}
    logger.info(f"Manga formats from AniList: {manga_stats.get('formats', [])}")
    logger.info(f"Manga countries from AniList: {manga_stats.get('countries', [])}")
    
    # Initialize all format types to 0
    format_distribution = {
        "Manga": 0,      # Japan
        "Manhwa": 0,     # South Korea
        "Manhua": 0,     # China
        "Light Novel": 0,
        "Novel": 0,
        "One Shot": 0,
        "Doujinshi": 0
    }
    
    # Process country data to get Manga/Manhwa/Manhua distinction
    for country_data in manga_stats.get("countries", []):
        country = country_data.get("country", "Unknown")
        count = country_data.get("count", 0)
        # Adjust count to exclude planning entries (assume planning is distributed proportionally)
        adjusted_count = int(count * (1 - manga_planning_ratio))
        logger.info(f"Processing manga country: {country} with count: {count} -> adjusted: {adjusted_count}")
        
        if country == "JP":  # Japan
            format_distribution["Manga"] += adjusted_count
        elif country == "KR":  # South Korea
            format_distribution["Manhwa"] += adjusted_count  
        elif country == "CN":  # China
            format_distribution["Manhua"] += adjusted_count
        else:
            # For other countries, add to general manga category
            format_distribution["Manga"] += adjusted_count
            logger.info(f"Unknown country {country}, adding to Manga category")
    
    # Process format data for other types (Light Novel, Novel, One Shot, etc.)
    for f in manga_stats.get("formats", []):
        format_name = f.get("format", "Unknown")
        count = f.get("count", 0)
        # Adjust count to exclude planning entries
        adjusted_count = int(count * (1 - manga_planning_ratio))
        logger.info(f"Processing manga format: {format_name} with count: {count} -> adjusted: {adjusted_count}")
        
        if format_name == "LIGHT_NOVEL":
            format_distribution["Light Novel"] = adjusted_count
        elif format_name == "NOVEL":
            format_distribution["Novel"] = adjusted_count
        elif format_name == "ONE_SHOT":
            format_distribution["One Shot"] = adjusted_count
        elif format_name == "DOUJINSHI":
            format_distribution["Doujinshi"] = adjusted_count
        # Note: We don't process "MANGA" format here since we're using country data instead
    
    logger.info(f"Final manga format_distribution (excluding planning): {format_distribution}")

    # Format distribution for anime - exclude planning entries
    total_anime_entries = total_anime
    anime_planning_ratio = a_planning / total_anime_entries if total_anime_entries > 0 else 0
    logger.info(f"Anime planning ratio: {anime_planning_ratio} (planning: {a_planning}, total: {total_anime_entries})")
    
    anime_format_distribution = {}
    for f in anime_stats.get("formats", []):
        format_name = f.get("format", "Unknown")
        count = f.get("count", 0)
        # Adjust count to exclude planning entries
        adjusted_count = int(count * (1 - anime_planning_ratio))
        logger.info(f"Processing anime format: {format_name} with count: {count} -> adjusted: {adjusted_count}")
        
        # Map AniList anime format names to more readable names
        if format_name == "TV":
            format_display = "TV Series"
        elif format_name == "MOVIE":
            format_display = "Movie"
        elif format_name == "OVA":
            format_display = "OVA"
        elif format_name == "ONA":
            format_display = "ONA"
        elif format_name == "SPECIAL":
            format_display = "Special"
        elif format_name == "TV_SHORT":
            format_display = "TV Short"
        elif format_name == "MUSIC":
            format_display = "Music Video"
        else:
            format_display = format_name.replace("_", " ").title()
        
        anime_format_distribution[format_display] = adjusted_count
    
    logger.info(f"Final anime format_distribution (excluding planning): {anime_format_distribution}")

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

    # COMPLETION RATE ACHIEVEMENTS (only started entries)
    # Calculate completion rate as: Completed / (Completed + Dropped + Paused + Current)
    # This gives us the percentage of started content that was actually finished
    total_started_entries = (a_completed + m_completed + a_dropped + m_dropped + 
                           a_paused + m_paused + a_watching + m_reading)
    
    # Debug logging to understand the values
    logger.info(f"Completion rate calculation: total_anime={total_anime}, total_manga={total_manga}")
    logger.info(f"a_completed={a_completed}, m_completed={m_completed}, a_planning={a_planning}, m_planning={m_planning}")
    logger.info(f"a_dropped={a_dropped}, m_dropped={m_dropped}, a_paused={a_paused}, m_paused={m_paused}")
    logger.info(f"a_watching={a_watching}, m_reading={m_reading}")
    logger.info(f"total_started_entries={total_started_entries}")
    
    if total_started_entries > 0:
        completion_rate = (a_completed + m_completed) / total_started_entries
        # Cap completion rate at 100% to prevent impossible values
        completion_rate = min(completion_rate, 1.0)
        
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
            "completion_rate": min((a_completed + m_completed) / total_started_entries, 1.0) if total_started_entries > 0 else 0,
            "format_distribution": format_distribution,
            "anime_format_distribution": anime_format_distribution
        }
    }


def build_favorites_embed(user_data: dict, avatar_url: str, profile_url: str) -> discord.Embed:
    """Build favorites embed showing user's favorite anime and manga"""
    embed = discord.Embed(
        title=f"⭐ {user_data['name']}'s Favorites",
        url=profile_url,
        color=discord.Color.from_rgb(255, 182, 193)  # Light pink
    )
    
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    
    favourites = user_data.get("favourites", {})
    
    # Favorite Anime
    fav_anime = favourites.get("anime", {}).get("nodes", [])
    if fav_anime:
        anime_list = []
        for anime in fav_anime[:5]:  # Show top 5
            title = anime["title"].get("english") or anime["title"].get("romaji") or "Unknown"
            anime_list.append(f"• [{title}]({anime['siteUrl']})")
        
        embed.add_field(
            name="🎬 Favorite Anime",
            value="\n".join(anime_list),
            inline=False
        )
    else:
        embed.add_field(
            name="🎬 Favorite Anime", 
            value="*No favorite anime set*",
            inline=False
        )
    
    # Favorite Manga
    fav_manga = favourites.get("manga", {}).get("nodes", [])
    if fav_manga:
        manga_list = []
        for manga in fav_manga[:5]:  # Show top 5
            title = manga["title"].get("english") or manga["title"].get("romaji") or "Unknown"
            manga_list.append(f"• [{title}]({manga['siteUrl']})")
        
        embed.add_field(
            name="📚 Favorite Manga",
            value="\n".join(manga_list),
            inline=False
        )
    else:
        embed.add_field(
            name="📚 Favorite Manga",
            value="*No favorite manga set*", 
            inline=False
        )
    
    # Favorite Characters
    fav_characters = favourites.get("characters", {}).get("nodes", [])
    if fav_characters:
        character_list = []
        for character in fav_characters[:5]:  # Show top 5
            name = character["name"].get("full") or "Unknown"
            character_list.append(f"• [{name}]({character['siteUrl']})")
        
        embed.add_field(
            name="👥 Favorite Characters",
            value="\n".join(character_list),
            inline=False
        )
    else:
        embed.add_field(
            name="👥 Favorite Characters",
            value="*No favorite characters set*",
            inline=False
        )

    # Add a note about favorites
    total_anime = len(fav_anime)
    total_manga = len(fav_manga)
    
    embed.set_footer(text="Data from AniList")
    return embed


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
        manga_embed.set_footer(text="Data from AniList • Page 1/2")

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
        anime_embed.set_footer(text="Data from AniList • Page 2/2")

        # Achievements data
        achievements_data = build_achievements(stats_anime, stats_manga)
        
        # Create achievements and favorites button views
        achievements_view = AchievementsView(achievements_data, user_data, avatar_url, profile_url)
        favorites_view = FavoritesView(user_data, avatar_url, profile_url)

        pages: List[discord.Embed] = [manga_embed, anime_embed]

        # Send first page and attach pager with achievements and favorites buttons
        pager = ProfilePager(pages, achievements_view, favorites_view)
        achievements_view.profile_pager = pager  # Set the reference after creating the pager
        favorites_view.profile_pager = pager  # Set the reference after creating the pager
        msg = await interaction.followup.send(embed=pages[0], view=pager)


class ProfilePager(discord.ui.View):
    def __init__(self, pages: List[discord.Embed], achievements_view, favorites_view):
        super().__init__(timeout=120)
        self.pages = pages
        self.index = 0
        self.achievements_view = achievements_view
        self.favorites_view = favorites_view

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

    @discord.ui.button(label="⭐ Favorites", style=discord.ButtonStyle.primary)
    async def show_favorites(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=self.favorites_view.get_current_embed(),
            view=self.favorites_view
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
        
        embed.set_footer(text=f"Achieved: {len(achieved)} • Achievements Page 1/3")
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
                embed.set_footer(text=f"Progress: {len(progress)} items (showing first 8) • Achievements Page 2/3")
            else:
                embed.set_footer(text=f"Progress: {len(progress)} items • Achievements Page 2/3")
        else:
            embed.description = "All available achievements unlocked! 🎉"
            embed.set_footer(text="Progress: Complete • Achievements Page 2/3")
        
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
        
        # Format Distribution - Manga
        format_dist = stats.get("format_distribution", {})
        logger.info(f"Stats format_distribution: {format_dist}")
        if format_dist:
            format_lines = []
            # Sort by count (descending) and take top entries
            sorted_formats = sorted(format_dist.items(), key=lambda x: x[1], reverse=True)
            logger.info(f"Sorted manga formats: {sorted_formats}")
            for format_name, count in sorted_formats:
                logger.info(f"Checking manga format {format_name} with count {count}")
                # Show all formats, even with 0 count for debugging
                # if count > 0:  # Only show formats with content
                # Add emojis for different manga formats
                if format_name == "Manga":
                    emoji = "📚"
                elif format_name == "Manhwa":
                    emoji = "📚"
                elif format_name == "Manhua":
                    emoji = "📚"
                elif format_name == "Light Novel":
                    emoji = "📖"
                elif format_name == "Novel":
                    emoji = "📕"
                elif format_name == "One Shot":
                    emoji = "📄"
                elif format_name == "Doujinshi":
                    emoji = "📗"
                else:
                    emoji = "📚"
                
                if count > 0:  # Only add non-zero entries to the display
                    format_lines.append(f"{emoji} **{format_name}** - {count:,} entries")
            
            logger.info(f"Final manga format_lines: {format_lines}")
            if format_lines:
                embed.add_field(
                    name="📚 Manga Format Distribution",
                    value="\n".join(format_lines),
                    inline=True
                )
            else:
                logger.info("No manga format lines to display (all counts were 0)")
        else:
            logger.info("No manga format distribution data found in stats")
        
        # Format Distribution - Anime
        anime_format_dist = stats.get("anime_format_distribution", {})
        if anime_format_dist:
            anime_format_lines = []
            # Sort by count (descending) and take top entries
            sorted_anime_formats = sorted(anime_format_dist.items(), key=lambda x: x[1], reverse=True)
            for format_name, count in sorted_anime_formats:
                if count > 0:  # Only show formats with content
                    anime_format_lines.append(f"**{format_name}** - {count:,} entries")
            
            if anime_format_lines:
                embed.add_field(
                    name="🎬 Anime Format Distribution",
                    value="\n".join(anime_format_lines),
                    inline=True
                )
        
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        
        embed.set_footer(text="Achievement Statistics • Achievements Page 3/3")
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


class FavoritesView(discord.ui.View):
    def __init__(self, user_data: Dict, avatar_url: str, profile_url: str, profile_pager=None):
        super().__init__(timeout=120)
        self.user_data = user_data
        self.avatar_url = avatar_url
        self.profile_url = profile_url
        self.profile_pager = profile_pager
        self.current_page = 0  # 0=Anime, 1=Manga, 2=Characters, 3=Studios, 4=Staff
        self.page_names = ["Anime", "Manga", "Characters", "Studios", "Staff"]
    
    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
    
    def get_current_embed(self) -> discord.Embed:
        """Get the current favorites page embed"""
        if self.current_page == 0:
            return self.build_anime_favorites()
        elif self.current_page == 1:
            return self.build_manga_favorites()
        elif self.current_page == 2:
            return self.build_character_favorites()
        elif self.current_page == 3:
            return self.build_studio_favorites()
        elif self.current_page == 4:
            return self.build_staff_favorites()
        else:
            return self.build_anime_favorites()
    
    def build_anime_favorites(self) -> discord.Embed:
        """Build anime favorites page"""
        embed = discord.Embed(
            title=f"🎬 {self.user_data['name']}'s Favorite Anime",
            url=self.profile_url,
            color=discord.Color.blue()
        )
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        
        fav_anime = self.user_data.get("favourites", {}).get("anime", {}).get("nodes", [])
        if fav_anime:
            anime_list = []
            for i, anime in enumerate(fav_anime[:10], 1):
                title = anime["title"].get("english") or anime["title"].get("romaji") or "Unknown"
                score = f" ({anime['averageScore']}%)" if anime.get('averageScore') else ""
                anime_list.append(f"{i}. [{title}]({anime['siteUrl']}){score}")
            
            embed.description = "\n".join(anime_list)
        else:
            embed.description = "*No favorite anime set*"
        
        embed.set_footer(text=f"Data from AniList • {self.page_names[self.current_page]} ({self.current_page + 1}/5)")
        return embed
    
    def build_manga_favorites(self) -> discord.Embed:
        """Build manga favorites page"""
        embed = discord.Embed(
            title=f"📚 {self.user_data['name']}'s Favorite Manga",
            url=self.profile_url,
            color=discord.Color.green()
        )
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        
        fav_manga = self.user_data.get("favourites", {}).get("manga", {}).get("nodes", [])
        if fav_manga:
            manga_list = []
            for i, manga in enumerate(fav_manga[:10], 1):
                title = manga["title"].get("english") or manga["title"].get("romaji") or "Unknown"
                score = f" ({manga['averageScore']}%)" if manga.get('averageScore') else ""
                manga_list.append(f"{i}. [{title}]({manga['siteUrl']}){score}")
            
            embed.description = "\n".join(manga_list)
        else:
            embed.description = "*No favorite manga set*"
        
        embed.set_footer(text=f"Data from AniList • {self.page_names[self.current_page]} ({self.current_page + 1}/5)")
        return embed
    
    def build_character_favorites(self) -> discord.Embed:
        """Build character favorites page"""
        embed = discord.Embed(
            title=f"👥 {self.user_data['name']}'s Favorite Characters",
            url=self.profile_url,
            color=discord.Color.purple()
        )
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        
        fav_characters = self.user_data.get("favourites", {}).get("characters", {}).get("nodes", [])
        if fav_characters:
            character_list = []
            for i, character in enumerate(fav_characters[:10], 1):
                name = character["name"].get("full") or "Unknown"
                character_list.append(f"{i}. [{name}]({character['siteUrl']})")
            
            embed.description = "\n".join(character_list)
        else:
            embed.description = "*No favorite characters set*"
        
        embed.set_footer(text=f"Data from AniList • {self.page_names[self.current_page]} ({self.current_page + 1}/5)")
        return embed
    
    def build_studio_favorites(self) -> discord.Embed:
        """Build studio favorites page"""
        embed = discord.Embed(
            title=f"🎭 {self.user_data['name']}'s Favorite Studios",
            url=self.profile_url,
            color=discord.Color.gold()
        )
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        
        fav_studios = self.user_data.get("favourites", {}).get("studios", {}).get("nodes", [])
        if fav_studios:
            studio_list = []
            for i, studio in enumerate(fav_studios[:10], 1):
                name = studio.get("name") or "Unknown"
                studio_list.append(f"{i}. [{name}]({studio['siteUrl']})")
            
            embed.description = "\n".join(studio_list)
        else:
            embed.description = "*No favorite studios set*"
        
        embed.set_footer(text=f"Data from AniList • {self.page_names[self.current_page]} ({self.current_page + 1}/5)")
        return embed
    
    def build_staff_favorites(self) -> discord.Embed:
        """Build staff favorites page"""
        embed = discord.Embed(
            title=f"👨‍💼 {self.user_data['name']}'s Favorite Staff",
            url=self.profile_url,
            color=discord.Color.orange()
        )
        if self.avatar_url:
            embed.set_thumbnail(url=self.avatar_url)
        
        fav_staff = self.user_data.get("favourites", {}).get("staff", {}).get("nodes", [])
        if fav_staff:
            staff_list = []
            for i, staff in enumerate(fav_staff[:10], 1):
                name = staff["name"].get("full") or "Unknown"
                occupations = staff.get("primaryOccupations", [])
                occupation_text = f" ({', '.join(occupations[:2])})" if occupations else ""
                staff_list.append(f"{i}. [{name}]({staff['siteUrl']}){occupation_text}")
            
            embed.description = "\n".join(staff_list)
        else:
            embed.description = "*No favorite staff set*"
        
        embed.set_footer(text=f"Data from AniList • {self.page_names[self.current_page]} ({self.current_page + 1}/5)")
        return embed
    
    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page - 1) % 5
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = (self.current_page + 1) % 5
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="🎬 Anime", style=discord.ButtonStyle.primary)
    async def show_anime(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 0
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="📚 Manga", style=discord.ButtonStyle.primary)
    async def show_manga(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 1
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="👥 Characters", style=discord.ButtonStyle.primary, row=1)
    async def show_characters(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 2
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="🎭 Studios", style=discord.ButtonStyle.primary, row=1)
    async def show_studios(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 3
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="👨‍💼 Staff", style=discord.ButtonStyle.primary, row=1)
    async def show_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = 4
        await interaction.response.edit_message(embed=self.get_current_embed(), view=self)
    
    @discord.ui.button(label="◀ Back to Profile", style=discord.ButtonStyle.secondary, row=2)
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
