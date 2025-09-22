import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import calendar
import random
from collections import Counter

from config import GUILD_ID
from database import get_user

# ------------------------------------------------------
# Logging Setup - Clears on each bot run
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "wrapped.log"

# Clear the log file on startup
if LOG_FILE.exists():
    LOG_FILE.unlink()

# Create logger
logger = logging.getLogger("Wrapped")
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

logger.info("Wrapped cog logging initialized - log file cleared")

# ------------------------------------------------------
# Constants
# ------------------------------------------------------
ANILIST_API_URL = "https://graphql.anilist.co"
REQUEST_TIMEOUT = 15

# Color schemes for different wrapped themes
WRAPPED_COLORS = {
    "anime": 0x02A9FF,
    "manga": 0xFF6B96,
    "mixed": 0x9A59C4,
    "achievement": 0xFFD700,
    "stats": 0x1ED760
}

# Fun emojis for different stats
STAT_EMOJIS = {
    "anime": "🎬",
    "manga": "📖",
    "episodes": "📺",
    "chapters": "📃",
    "hours": "⏰",
    "days": "📅",
    "genres": "🎭",
    "score": "⭐",
    "completed": "✅",
    "watching": "👀",
    "planning": "📝"
}


class WrappedView(discord.ui.View):
    """Interactive view for navigating wrapped statistics"""
    
    def __init__(self, user_data: Dict, period: str, username: str):
        super().__init__(timeout=300)
        self.user_data = user_data
        self.period = period
        self.username = username
        self.current_page = 0
        self.total_pages = 5  # Overview, Anime, Manga, Achievements, Year in Review
        
    async def get_embed(self, page: int) -> discord.Embed:
        """Generate embed for specific page"""
        if page == 0:
            return self._overview_embed()
        elif page == 1:
            return self._anime_embed()
        elif page == 2:
            return self._manga_embed()
        elif page == 3:
            return self._achievements_embed()
        elif page == 4:
            return self._year_review_embed()
        else:
            return self._overview_embed()
    
    def _overview_embed(self) -> discord.Embed:
        """Create overview statistics embed"""
        stats = self.user_data.get("stats", {})
        period_text = f"{self.period.title()}" if self.period != "all_time" else "All Time"
        
        embed = discord.Embed(
            title=f"🎊 {self.username}'s {period_text} Wrapped",
            description=f"Your anime & manga journey in {period_text.lower()}",
            color=WRAPPED_COLORS["mixed"]
        )
        
        # Main stats
        total_anime = stats.get("anime", {}).get("count", 0)
        total_manga = stats.get("manga", {}).get("count", 0)
        total_episodes = stats.get("anime", {}).get("episodesWatched", 0)
        total_chapters = stats.get("manga", {}).get("chaptersRead", 0)
        
        embed.add_field(
            name="📊 Your Numbers",
            value=f"{STAT_EMOJIS['anime']} **{total_anime}** Anime\n"
                  f"{STAT_EMOJIS['manga']} **{total_manga}** Manga\n"
                  f"{STAT_EMOJIS['episodes']} **{total_episodes}** Episodes\n"
                  f"{STAT_EMOJIS['chapters']} **{total_chapters}** Chapters",
            inline=True
        )
        
        # Time calculations
        anime_hours = round(total_episodes * 24 / 60, 1)  # Assuming 24min episodes
        manga_hours = round(total_chapters * 5 / 60, 1)   # Assuming 5min chapters
        total_hours = anime_hours + manga_hours
        
        embed.add_field(
            name="⏰ Time Spent",
            value=f"**{total_hours}** hours total\n"
                  f"**{round(total_hours / 24, 1)}** days\n"
                  f"**{anime_hours}**h anime\n"
                  f"**{manga_hours}**h manga",
            inline=True
        )
        
        # Top genres
        top_genres = self.user_data.get("top_genres", [])[:3]
        genre_text = "\n".join([f"**{genre['name']}** ({genre['count']})" for genre in top_genres]) if top_genres else "No data"
        
        embed.add_field(
            name="🎭 Favorite Genres",
            value=genre_text,
            inline=True
        )
        
        embed.set_footer(text=f"Page 1/{self.total_pages} • Use buttons to navigate")
        return embed
    
    def _anime_embed(self) -> discord.Embed:
        """Create anime-specific statistics embed"""
        anime_stats = self.user_data.get("stats", {}).get("anime", {})
        period_text = f"{self.period.title()}" if self.period != "all_time" else "All Time"
        
        embed = discord.Embed(
            title=f"🎬 Your {period_text} Anime",
            description="Your anime watching journey",
            color=WRAPPED_COLORS["anime"]
        )
        
        # Status breakdown
        status_counts = anime_stats.get("statuses", {})
        embed.add_field(
            name="📊 Status Breakdown",
            value=f"{STAT_EMOJIS['completed']} **{status_counts.get('COMPLETED', 0)}** Completed\n"
                  f"{STAT_EMOJIS['watching']} **{status_counts.get('CURRENT', 0)}** Watching\n"
                  f"{STAT_EMOJIS['planning']} **{status_counts.get('PLANNING', 0)}** Planning\n"
                  f"⏸️ **{status_counts.get('PAUSED', 0)}** Paused",
            inline=True
        )
        
        # Top anime
        top_anime = self.user_data.get("top_anime", [])[:5]
        if top_anime:
            anime_list = []
            for i, anime in enumerate(top_anime, 1):
                score = f" ({anime.get('score', 'N/A')}/10)" if anime.get('score') else ""
                anime_list.append(f"{i}. **{anime['title']}**{score}")
            
            embed.add_field(
                name="🏆 Top Rated Anime",
                value="\n".join(anime_list),
                inline=False
            )
        
        # Episodes and time stats
        episodes = anime_stats.get("episodesWatched", 0)
        hours = round(episodes * 24 / 60, 1)
        days = round(hours / 24, 1)
        
        embed.add_field(
            name="⏰ Watch Time",
            value=f"**{episodes}** episodes watched\n"
                  f"**{hours}** hours of anime\n"
                  f"**{days}** days total",
            inline=True
        )
        
        # Average score
        mean_score = anime_stats.get("meanScore", 0)
        if mean_score > 0:
            embed.add_field(
                name="⭐ Average Score",
                value=f"**{mean_score}/100**\n"
                      f"({round(mean_score/10, 1)}/10)",
                inline=True
            )
        
        embed.set_footer(text=f"Page 2/{self.total_pages} • Anime Statistics")
        return embed
    
    def _manga_embed(self) -> discord.Embed:
        """Create manga-specific statistics embed"""
        manga_stats = self.user_data.get("stats", {}).get("manga", {})
        period_text = f"{self.period.title()}" if self.period != "all_time" else "All Time"
        
        embed = discord.Embed(
            title=f"📖 Your {period_text} Manga",
            description="Your manga reading journey",
            color=WRAPPED_COLORS["manga"]
        )
        
        # Status breakdown
        status_counts = manga_stats.get("statuses", {})
        embed.add_field(
            name="📊 Status Breakdown",
            value=f"{STAT_EMOJIS['completed']} **{status_counts.get('COMPLETED', 0)}** Completed\n"
                  f"📖 **{status_counts.get('CURRENT', 0)}** Reading\n"
                  f"{STAT_EMOJIS['planning']} **{status_counts.get('PLANNING', 0)}** Planning\n"
                  f"⏸️ **{status_counts.get('PAUSED', 0)}** Paused",
            inline=True
        )
        
        # Top manga
        top_manga = self.user_data.get("top_manga", [])[:5]
        if top_manga:
            manga_list = []
            for i, manga in enumerate(top_manga, 1):
                score = f" ({manga.get('score', 'N/A')}/10)" if manga.get('score') else ""
                manga_list.append(f"{i}. **{manga['title']}**{score}")
            
            embed.add_field(
                name="🏆 Top Rated Manga",
                value="\n".join(manga_list),
                inline=False
            )
        
        # Chapters and time stats
        chapters = manga_stats.get("chaptersRead", 0)
        hours = round(chapters * 5 / 60, 1)  # Assuming 5min per chapter
        
        embed.add_field(
            name="📃 Reading Stats",
            value=f"**{chapters}** chapters read\n"
                  f"**{hours}** hours of reading\n"
                  f"**{round(hours / 24, 1)}** days total",
            inline=True
        )
        
        # Average score
        mean_score = manga_stats.get("meanScore", 0)
        if mean_score > 0:
            embed.add_field(
                name="⭐ Average Score",
                value=f"**{mean_score}/100**\n"
                      f"({round(mean_score/10, 1)}/10)",
                inline=True
            )
        
        embed.set_footer(text=f"Page 3/{self.total_pages} • Manga Statistics")
        return embed
    
    def _achievements_embed(self) -> discord.Embed:
        """Create achievements and milestones embed"""
        period_text = f"{self.period.title()}" if self.period != "all_time" else "All Time"
        
        embed = discord.Embed(
            title=f"🏆 Your {period_text} Achievements",
            description="Milestones and special moments",
            color=WRAPPED_COLORS["achievement"]
        )
        
        achievements = []
        stats = self.user_data.get("stats", {})
        
        # Episode milestones
        total_episodes = stats.get("anime", {}).get("episodesWatched", 0)
        if total_episodes >= 1000:
            achievements.append("🎬 **Episode Collector** - 1000+ episodes watched!")
        elif total_episodes >= 500:
            achievements.append("📺 **Binge Master** - 500+ episodes watched!")
        elif total_episodes >= 100:
            achievements.append("👀 **Regular Viewer** - 100+ episodes watched!")
        
        # Chapter milestones
        total_chapters = stats.get("manga", {}).get("chaptersRead", 0)
        if total_chapters >= 5000:
            achievements.append("📚 **Manga Librarian** - 5000+ chapters read!")
        elif total_chapters >= 1000:
            achievements.append("📖 **Chapter Champion** - 1000+ chapters read!")
        elif total_chapters >= 500:
            achievements.append("📃 **Page Turner** - 500+ chapters read!")
        
        # Completion achievements
        anime_completed = stats.get("anime", {}).get("statuses", {}).get("COMPLETED", 0)
        manga_completed = stats.get("manga", {}).get("statuses", {}).get("COMPLETED", 0)
        
        if anime_completed >= 100:
            achievements.append("✅ **Completion King/Queen** - 100+ anime completed!")
        elif anime_completed >= 50:
            achievements.append("🏁 **Finisher** - 50+ anime completed!")
        
        if manga_completed >= 50:
            achievements.append("📋 **Manga Master** - 50+ manga completed!")
        
        # Genre diversity
        top_genres = self.user_data.get("top_genres", [])
        if len(top_genres) >= 10:
            achievements.append("🎭 **Genre Explorer** - 10+ different genres!")
        
        # Score achievements
        anime_mean = stats.get("anime", {}).get("meanScore", 0)
        manga_mean = stats.get("manga", {}).get("meanScore", 0)
        
        if anime_mean >= 80 or manga_mean >= 80:
            achievements.append("⭐ **High Standards** - Average score 8.0+!")
        
        if not achievements:
            achievements.append("🌱 **Getting Started** - Your journey begins here!")
        
        embed.add_field(
            name="🏆 Unlocked Achievements",
            value="\n".join(achievements[:10]),  # Limit to 10
            inline=False
        )
        
        # Fun facts
        fun_facts = self._generate_fun_facts()
        if fun_facts:
            embed.add_field(
                name="🎉 Fun Facts",
                value="\n".join(fun_facts[:3]),
                inline=False
            )
        
        embed.set_footer(text=f"Page 4/{self.total_pages} • Achievements & Milestones")
        return embed
    
    def _year_review_embed(self) -> discord.Embed:
        """Create year in review summary embed"""
        period_text = f"{self.period.title()}" if self.period != "all_time" else "All Time"
        
        embed = discord.Embed(
            title=f"🌟 Your {period_text} In Review",
            description="The highlights of your anime & manga journey",
            color=WRAPPED_COLORS["stats"]
        )
        
        # Create summary stats
        stats = self.user_data.get("stats", {})
        total_anime = stats.get("anime", {}).get("count", 0)
        total_manga = stats.get("manga", {}).get("count", 0)
        total_episodes = stats.get("anime", {}).get("episodesWatched", 0)
        total_chapters = stats.get("manga", {}).get("chaptersRead", 0)
        
        # Summary message
        if total_anime > 0 or total_manga > 0:
            summary_parts = []
            if total_anime > 0:
                summary_parts.append(f"watched **{total_anime}** anime")
            if total_manga > 0:
                summary_parts.append(f"read **{total_manga}** manga")
            
            summary = f"You {' and '.join(summary_parts)}"
            
            if total_episodes > 0 and total_chapters > 0:
                summary += f", consuming **{total_episodes}** episodes and **{total_chapters}** chapters"
            elif total_episodes > 0:
                summary += f", watching **{total_episodes}** episodes"
            elif total_chapters > 0:
                summary += f", reading **{total_chapters}** chapters"
            
            summary += "!"
        else:
            summary = "Your anime and manga adventure is just beginning!"
        
        embed.add_field(
            name="📝 Summary",
            value=summary,
            inline=False
        )
        
        # Favorite discovery
        top_anime = self.user_data.get("top_anime", [])
        top_manga = self.user_data.get("top_manga", [])
        
        discoveries = []
        if top_anime:
            discoveries.append(f"🎬 **{top_anime[0]['title']}** (Anime)")
        if top_manga:
            discoveries.append(f"📖 **{top_manga[0]['title']}** (Manga)")
        
        if discoveries:
            embed.add_field(
                name="✨ Top Discoveries",
                value="\n".join(discoveries[:2]),
                inline=True
            )
        
        # Most active genre
        top_genres = self.user_data.get("top_genres", [])
        if top_genres:
            embed.add_field(
                name="🎭 Favorite Genre",
                value=f"**{top_genres[0]['name']}**\n({top_genres[0]['count']} series)",
                inline=True
            )
        
        # Motivational message
        messages = [
            "Keep exploring new worlds! 🌍",
            "Your taste keeps getting better! ✨",
            "Amazing progress this year! 🚀",
            "What an incredible journey! 🎊",
            "Your anime/manga knowledge is growing! 📚",
            "Keep discovering new favorites! 💫"
        ]
        
        embed.add_field(
            name="🌟 Keep Going!",
            value=random.choice(messages),
            inline=False
        )
        
        embed.set_footer(text=f"Page 5/{self.total_pages} • Thanks for using Lemegeton!")
        return embed
    
    def _generate_fun_facts(self) -> List[str]:
        """Generate fun facts about user's activity"""
        facts = []
        stats = self.user_data.get("stats", {})
        
        # Time-based facts
        total_episodes = stats.get("anime", {}).get("episodesWatched", 0)
        total_chapters = stats.get("manga", {}).get("chaptersRead", 0)
        
        if total_episodes > 0:
            hours = round(total_episodes * 24 / 60, 1)
            if hours >= 24:
                days = round(hours / 24, 1)
                facts.append(f"🕐 You've watched {days} days worth of anime!")
            else:
                facts.append(f"⏰ You've watched {hours} hours of anime!")
        
        if total_chapters > 0:
            if total_chapters >= 1000:
                facts.append(f"📚 That's enough chapters to fill several manga volumes!")
            else:
                facts.append(f"📖 You've read {total_chapters} chapters!")
        
        # Genre facts
        top_genres = self.user_data.get("top_genres", [])
        if len(top_genres) >= 5:
            facts.append(f"🎭 You've explored {len(top_genres)} different genres!")
        
        return facts
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        else:
            self.current_page = self.total_pages - 1
        
        embed = await self.get_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        else:
            self.current_page = 0
        
        embed = await self.get_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🔀 Random Page", style=discord.ButtonStyle.primary)
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page = random.randint(0, self.total_pages - 1)
        embed = await self.get_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="📤 Share", style=discord.ButtonStyle.success)
    async def share_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Make the message public for sharing
        embed = await self.get_embed(self.current_page)
        embed.set_footer(text=f"{embed.footer.text} • Shared by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)


class Wrapped(commands.Cog):
    """Generate beautiful yearly/monthly wrapped statistics for users"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Wrapped cog initialized")
    
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="wrapped",
        description="🎊 Get your anime & manga Wrapped - yearly or monthly statistics!"
    )
    @app_commands.describe(
        period="Choose the time period for your wrapped statistics",
        user="View another user's wrapped (if they're registered)"
    )
    @app_commands.choices(
        period=[
            app_commands.Choice(name="2024 📅", value="2024"),
            app_commands.Choice(name="2023 📅", value="2023"),
            app_commands.Choice(name="This Month 📆", value="current_month"),
            app_commands.Choice(name="Last Month 📆", value="last_month"),
            app_commands.Choice(name="All Time 🌟", value="all_time")
        ]
    )
    async def wrapped(
        self,
        interaction: discord.Interaction,
        period: app_commands.Choice[str] = None,
        user: discord.Member = None
    ):
        """Main wrapped command"""
        selected_period = period.value if period else "all_time"
        target_user = user or interaction.user
        
        logger.info(f"Wrapped command invoked by {interaction.user} for {target_user} - Period: {selected_period}")
        
        # Check if user is registered
        user_record = await get_user(target_user.id)
        if not user_record:
            embed = discord.Embed(
                title="❌ User Not Registered",
                description=f"{target_user.display_name} needs to be registered with AniList to view wrapped statistics.\n\nUse `/login` to register!",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        username = user_record[2]  # AniList username
        await interaction.response.defer()
        
        try:
            # Collect user data
            logger.info(f"Collecting wrapped data for {username} ({selected_period})")
            user_data = await self._collect_user_data(username, selected_period)
            
            if not user_data:
                embed = discord.Embed(
                    title="❌ Data Collection Failed",
                    description="Unable to collect wrapped data. Please try again later.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Create interactive wrapped view
            view = WrappedView(user_data, selected_period, username)
            embed = await view.get_embed(0)  # Start with overview
            
            await interaction.followup.send(embed=embed, view=view)
            logger.info(f"Wrapped successfully generated for {username}")
            
        except Exception as e:
            logger.error(f"Error generating wrapped for {username}: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while generating your wrapped. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def _collect_user_data(self, username: str, period: str) -> Optional[Dict]:
        """Collect comprehensive user data from AniList API"""
        try:
            # Determine date range
            start_date, end_date = self._get_date_range(period)
            
            # GraphQL query for user statistics
            query = """
            query ($username: String, $startDate: FuzzyDateInt, $endDate: FuzzyDateInt) {
              User(name: $username) {
                id
                name
                statistics {
                  anime {
                    count
                    episodesWatched
                    meanScore
                    minutesWatched
                    statuses {
                      status
                      count
                    }
                    genres {
                      genre
                      count
                      meanScore
                    }
                  }
                  manga {
                    count
                    chaptersRead
                    volumesRead
                    meanScore
                    statuses {
                      status
                      count
                    }
                    genres {
                      genre
                      count
                      meanScore
                    }
                  }
                }
                favourites {
                  anime {
                    nodes {
                      id
                      title { romaji english }
                      averageScore
                    }
                  }
                  manga {
                    nodes {
                      id
                      title { romaji english }
                      averageScore
                    }
                  }
                }
              }
              
              # Get user's top rated anime
              animeList: MediaListCollection(
                userName: $username,
                type: ANIME,
                status: COMPLETED,
                sort: [SCORE_DESC]
              ) {
                lists {
                  entries {
                    score
                    media {
                      id
                      title { romaji english }
                      averageScore
                    }
                  }
                }
              }
              
              # Get user's top rated manga  
              mangaList: MediaListCollection(
                userName: $username,
                type: MANGA,
                status: COMPLETED,
                sort: [SCORE_DESC]
              ) {
                lists {
                  entries {
                    score
                    media {
                      id
                      title { romaji english }
                      averageScore
                    }
                  }
                }
              }
            }
            """
            
            variables = {
                "username": username,
                "startDate": start_date,
                "endDate": end_date
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as session:
                async with session.post(
                    ANILIST_API_URL,
                    json={"query": query, "variables": variables}
                ) as response:
                    if response.status != 200:
                        logger.error(f"AniList API error: {response.status}")
                        return None
                    
                    data = await response.json()
                    if "errors" in data:
                        logger.error(f"AniList API errors: {data['errors']}")
                        return None
                    
                    return self._process_user_data(data["data"])
            
        except Exception as e:
            logger.error(f"Error collecting user data for {username}: {e}")
            return None
    
    def _get_date_range(self, period: str) -> Tuple[Optional[int], Optional[int]]:
        """Get start and end date for the specified period"""
        now = datetime.now()
        
        if period == "2024":
            return 20240101, 20241231
        elif period == "2023":
            return 20230101, 20231231
        elif period == "current_month":
            start = datetime(now.year, now.month, 1)
            # Last day of current month
            end = datetime(now.year, now.month, calendar.monthrange(now.year, now.month)[1])
            return int(start.strftime("%Y%m%d")), int(end.strftime("%Y%m%d"))
        elif period == "last_month":
            # Go to first day of current month, then back one day to get last month
            last_month_end = datetime(now.year, now.month, 1) - timedelta(days=1)
            last_month_start = datetime(last_month_end.year, last_month_end.month, 1)
            return int(last_month_start.strftime("%Y%m%d")), int(last_month_end.strftime("%Y%m%d"))
        else:  # all_time
            return None, None
    
    def _process_user_data(self, data: Dict) -> Dict:
        """Process and structure the user data from AniList API"""
        user = data.get("User", {})
        anime_list = data.get("animeList", {})
        manga_list = data.get("mangaList", {})
        
        # Process statistics
        anime_stats = user.get("statistics", {}).get("anime", {})
        manga_stats = user.get("statistics", {}).get("manga", {})
        
        # Convert status lists to dictionaries
        anime_statuses = {status["status"]: status["count"] for status in anime_stats.get("statuses", [])}
        manga_statuses = {status["status"]: status["count"] for status in manga_stats.get("statuses", [])}
        
        # Process genres
        anime_genres = anime_stats.get("genres", [])
        manga_genres = manga_stats.get("genres", [])
        
        # Combine and count all genres
        all_genres = Counter()
        for genre in anime_genres:
            all_genres[genre["genre"]] += genre["count"]
        for genre in manga_genres:
            all_genres[genre["genre"]] += genre["count"]
        
        top_genres = [{"name": genre, "count": count} for genre, count in all_genres.most_common(10)]
        
        # Process top rated media
        top_anime = []
        for entry_list in anime_list.get("lists", []):
            for entry in entry_list.get("entries", []):
                if entry.get("score", 0) > 0:  # Only include scored entries
                    media = entry["media"]
                    title = media["title"]["romaji"] or media["title"]["english"] or "Unknown"
                    top_anime.append({
                        "title": title,
                        "score": entry["score"]
                    })
        
        top_manga = []
        for entry_list in manga_list.get("lists", []):
            for entry in entry_list.get("entries", []):
                if entry.get("score", 0) > 0:
                    media = entry["media"]
                    title = media["title"]["romaji"] or media["title"]["english"] or "Unknown"
                    top_manga.append({
                        "title": title,
                        "score": entry["score"]
                    })
        
        # Sort by score and take top 10
        top_anime = sorted(top_anime, key=lambda x: x["score"], reverse=True)[:10]
        top_manga = sorted(top_manga, key=lambda x: x["score"], reverse=True)[:10]
        
        return {
            "stats": {
                "anime": {
                    "count": anime_stats.get("count", 0),
                    "episodesWatched": anime_stats.get("episodesWatched", 0),
                    "meanScore": anime_stats.get("meanScore", 0),
                    "minutesWatched": anime_stats.get("minutesWatched", 0),
                    "statuses": anime_statuses
                },
                "manga": {
                    "count": manga_stats.get("count", 0),
                    "chaptersRead": manga_stats.get("chaptersRead", 0),
                    "volumesRead": manga_stats.get("volumesRead", 0),
                    "meanScore": manga_stats.get("meanScore", 0),
                    "statuses": manga_statuses
                }
            },
            "top_genres": top_genres,
            "top_anime": top_anime,
            "top_manga": top_manga
        }
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("Wrapped cog loaded successfully")
    
    async def cog_unload(self):
        """Called when the cog is unloaded"""
        logger.info("Wrapped cog unloaded")


async def setup(bot: commands.Bot):
    await bot.add_cog(Wrapped(bot))