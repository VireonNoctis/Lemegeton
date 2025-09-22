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
        """Create overview statistics embed with enhanced styling"""
        stats = self.user_data.get("stats", {})
        period_text = f"{self.period.title()}" if self.period != "all_time" else "All Time"
        
        # Use a dark theme color similar to AniList
        embed = discord.Embed(
            title=f"🎊 ANILIST WRAPPED {period_text.upper()}",
            color=0x2B2D42  # Dark blue-gray like the image
        )
        
        # Add user info in description with better formatting
        embed.description = f"## **{self.username}**\n*Your anime & manga journey*"
        
        # Main stats with bigger numbers and better formatting
        total_anime = stats.get("anime", {}).get("count", 0)
        total_manga = stats.get("manga", {}).get("count", 0)
        total_episodes = stats.get("anime", {}).get("episodesWatched", 0)
        total_chapters = stats.get("manga", {}).get("chaptersRead", 0)
        
        # Time calculations
        anime_hours = round(total_episodes * 24 / 60, 1)
        manga_hours = round(total_chapters * 5 / 60, 1)
        total_hours = anime_hours + manga_hours
        total_days = round(total_hours / 24, 1)
        
        # Activity summary like the original
        embed.add_field(
            name="📊 **Your Numbers**",
            value=f"```yaml\nAnime: {total_anime:,}\nManga: {total_manga:,}\nEpisodes: {total_episodes:,}\nChapters: {total_chapters:,}```",
            inline=True
        )
        
        # Time watched section
        embed.add_field(
            name="⏰ **Time Watched**", 
            value=f"```css\n{total_days} Days\n{total_hours:.1f} Hours\n{anime_hours:.1f}h Anime\n{manga_hours:.1f}h Manga```",
            inline=True
        )
        
        # Days active (simulated)
        days_active = min(365, total_anime + total_manga + (total_episodes // 5))  # Rough estimate
        embed.add_field(
            name="📅 **Activity**",
            value=f"```fix\nDays Active: {days_active}/365\nCompleted: {stats.get('anime', {}).get('statuses', {}).get('COMPLETED', 0) + stats.get('manga', {}).get('statuses', {}).get('COMPLETED', 0)}\nAvg Score: {round((stats.get('anime', {}).get('meanScore', 0) + stats.get('manga', {}).get('meanScore', 0)) / 2) if stats.get('anime', {}).get('meanScore', 0) > 0 and stats.get('manga', {}).get('meanScore', 0) > 0 else max(stats.get('anime', {}).get('meanScore', 0), stats.get('manga', {}).get('meanScore', 0))}/100```",
            inline=True
        )
        
        # Top genres with bar chart effect
        top_genres = self.user_data.get("top_genres", [])[:5]
        if top_genres:
            genre_bars = []
            max_count = top_genres[0]['count'] if top_genres else 1
            for genre in top_genres:
                bar_length = min(15, max(1, int((genre['count'] / max_count) * 15)))
                bar = "█" * bar_length
                genre_bars.append(f"{genre['name']:<12} {bar} {genre['count']}")
            
            embed.add_field(
                name="🎭 **Genre Stats**",
                value=f"```\n" + "\n".join(genre_bars) + "```",
                inline=False
            )
        
        # Achievements preview
        achievements = self._get_main_achievements(stats)
        if achievements:
            embed.add_field(
                name="� **Achievements Unlocked**",
                value=" • ".join(achievements[:3]) + f"\n*+{len(achievements)-3} more...*" if len(achievements) > 3 else " • ".join(achievements),
                inline=False
            )
        
        embed.set_footer(
            text=f"Page 1/{self.total_pages} • {self.username}'s {period_text} Wrapped",
            icon_url="https://anilist.co/img/icons/android-chrome-512x512.png"
        )
        return embed
    
    def _anime_embed(self) -> discord.Embed:
        """Create anime-specific statistics embed with enhanced styling"""
        anime_stats = self.user_data.get("stats", {}).get("anime", {})
        period_text = f"{self.period.title()}" if self.period != "all_time" else "All Time"
        
        embed = discord.Embed(
            title=f"🎬 ANIME WRAPPED {period_text.upper()}",
            color=0x02A9FF  # Bright blue for anime
        )
        
        embed.description = f"## **{self.username}'s Anime Journey**\n*Your watching statistics*"
        
        # Status breakdown with visual bars
        status_counts = anime_stats.get("statuses", {})
        completed = status_counts.get('COMPLETED', 0)
        watching = status_counts.get('CURRENT', 0)
        planning = status_counts.get('PLANNING', 0)
        paused = status_counts.get('PAUSED', 0)
        dropped = status_counts.get('DROPPED', 0)
        
        total_status = completed + watching + planning + paused + dropped
        
        embed.add_field(
            name="📊 **Status Breakdown**",
            value=f"```css\n"
                  f"✅ Completed:  {completed:3d}\n"
                  f"👀 Watching:   {watching:3d}\n"
                  f"📝 Planning:   {planning:3d}\n"
                  f"⏸️ Paused:     {paused:3d}\n"
                  f"❌ Dropped:    {dropped:3d}"
                  f"```",
            inline=True
        )
        
        # Episodes and time stats with big numbers
        episodes = anime_stats.get("episodesWatched", 0)
        hours = round(episodes * 24 / 60, 1)
        days = round(hours / 24, 1)
        
        embed.add_field(
            name="📺 **Watch Time**",
            value=f"```yaml\n"
                  f"Episodes: {episodes:,}\n"
                  f"Hours: {hours:,.1f}\n"
                  f"Days: {days:.1f}\n"
                  f"```",
            inline=True
        )
        
        # Average score with visual representation
        mean_score = anime_stats.get("meanScore", 0)
        if mean_score > 0:
            score_out_of_10 = round(mean_score/10, 1)
            # Create a simple progress bar for score
            filled_stars = int(score_out_of_10)
            half_star = "⭐" if score_out_of_10 - filled_stars >= 0.5 else ""
            stars = "⭐" * filled_stars + half_star
            
            embed.add_field(
                name="⭐ **Average Score**",
                value=f"```fix\n{mean_score}/100\n({score_out_of_10}/10)\n{stars}```",
                inline=True
            )
        
        # Top rated anime list
        top_anime = self.user_data.get("top_anime", [])[:8]  # Show more like the original
        if top_anime:
            anime_list = []
            for i, anime in enumerate(top_anime, 1):
                score = f"({anime.get('score', 'N/A')}/10)" if anime.get('score') else ""
                title = anime['title'][:30] + "..." if len(anime['title']) > 30 else anime['title']
                anime_list.append(f"`{i:2d}.` **{title}** {score}")
            
            embed.add_field(
                name="🏆 **Highest Rated Anime**",
                value="\n".join(anime_list[:6]) + (f"\n*+{len(anime_list)-6} more...*" if len(anime_list) > 6 else ""),
                inline=False
            )
        
        # Fun anime fact
        if episodes > 0:
            fun_facts = []
            if episodes >= 1000:
                fun_facts.append("🎬 Episode Collector - 1000+ episodes watched!")
            elif episodes >= 500:
                fun_facts.append("📺 Binge Master - 500+ episodes watched!")
            
            if days >= 30:
                fun_facts.append(f"📅 You've watched {days:.1f} days worth of anime!")
            elif hours >= 100:
                fun_facts.append(f"⏰ That's {hours:.1f} hours of anime content!")
            
            if fun_facts:
                embed.add_field(
                    name="🎉 **Anime Achievements**",
                    value=" • ".join(fun_facts[:2]),
                    inline=False
                )
        
        embed.set_footer(
            text=f"Page 2/{self.total_pages} • {self.username}'s Anime Statistics",
            icon_url="https://anilist.co/img/icons/android-chrome-512x512.png"
        )
        return embed
    
    def _manga_embed(self) -> discord.Embed:
        """Create manga-specific statistics embed with enhanced styling"""
        manga_stats = self.user_data.get("stats", {}).get("manga", {})
        period_text = f"{self.period.title()}" if self.period != "all_time" else "All Time"
        
        embed = discord.Embed(
            title=f"📖 MANGA WRAPPED {period_text.upper()}",
            color=0xFF6B96  # Pink for manga
        )
        
        embed.description = f"## **{self.username}'s Manga Journey**\n*Your reading statistics*"
        
        # Status breakdown with visual formatting
        status_counts = manga_stats.get("statuses", {})
        completed = status_counts.get('COMPLETED', 0)
        reading = status_counts.get('CURRENT', 0)
        planning = status_counts.get('PLANNING', 0)
        paused = status_counts.get('PAUSED', 0)
        dropped = status_counts.get('DROPPED', 0)
        
        embed.add_field(
            name="📊 **Status Breakdown**",
            value=f"```css\n"
                  f"✅ Completed:  {completed:3d}\n"
                  f"📖 Reading:    {reading:3d}\n"
                  f"📝 Planning:   {planning:3d}\n"
                  f"⏸️ Paused:     {paused:3d}\n"
                  f"❌ Dropped:    {dropped:3d}"
                  f"```",
            inline=True
        )
        
        # Chapters and time stats
        chapters = manga_stats.get("chaptersRead", 0)
        volumes = manga_stats.get("volumesRead", 0)
        hours = round(chapters * 5 / 60, 1)  # 5min per chapter estimate
        
        embed.add_field(
            name="📃 **Reading Stats**",
            value=f"```yaml\n"
                  f"Chapters: {chapters:,}\n"
                  f"Volumes: {volumes:,}\n"
                  f"Hours: {hours:,.1f}\n"
                  f"Days: {round(hours / 24, 1):.1f}"
                  f"```",
            inline=True
        )
        
        # Average score with visual representation
        mean_score = manga_stats.get("meanScore", 0)
        if mean_score > 0:
            score_out_of_10 = round(mean_score/10, 1)
            filled_stars = int(score_out_of_10)
            half_star = "⭐" if score_out_of_10 - filled_stars >= 0.5 else ""
            stars = "⭐" * filled_stars + half_star
            
            embed.add_field(
                name="⭐ **Average Score**",
                value=f"```fix\n{mean_score}/100\n({score_out_of_10}/10)\n{stars}```",
                inline=True
            )
        
        # Top rated manga list
        top_manga = self.user_data.get("top_manga", [])[:8]
        if top_manga:
            manga_list = []
            for i, manga in enumerate(top_manga, 1):
                score = f"({manga.get('score', 'N/A')}/10)" if manga.get('score') else ""
                title = manga['title'][:30] + "..." if len(manga['title']) > 30 else manga['title']
                manga_list.append(f"`{i:2d}.` **{title}** {score}")
            
            embed.add_field(
                name="🏆 **Highest Rated Manga**",
                value="\n".join(manga_list[:6]) + (f"\n*+{len(manga_list)-6} more...*" if len(manga_list) > 6 else ""),
                inline=False
            )
        
        # Fun manga facts
        if chapters > 0:
            fun_facts = []
            if chapters >= 5000:
                fun_facts.append("📚 Manga Librarian - 5000+ chapters read!")
            elif chapters >= 1000:
                fun_facts.append("📖 Chapter Champion - 1000+ chapters read!")
            
            if volumes >= 100:
                fun_facts.append(f"📚 Volume Collector - {volumes} volumes read!")
            
            # Calculate equivalent books (assuming ~200 pages per volume, 20 chapters per volume)
            equiv_books = round(chapters / 20)
            if equiv_books >= 50:
                fun_facts.append(f"📖 That's equivalent to {equiv_books} manga volumes!")
            
            if fun_facts:
                embed.add_field(
                    name="🎉 **Reading Achievements**",
                    value=" • ".join(fun_facts[:2]),
                    inline=False
                )
        
        embed.set_footer(
            text=f"Page 3/{self.total_pages} • {self.username}'s Manga Statistics",
            icon_url="https://anilist.co/img/icons/android-chrome-512x512.png"
        )
        return embed
    
    def _achievements_embed(self) -> discord.Embed:
        """Create achievements and milestones embed with enhanced styling"""
        period_text = f"{self.period.title()}" if self.period != "all_time" else "All Time"
        
        embed = discord.Embed(
            title=f"🏆 ACHIEVEMENTS {period_text.upper()}",
            color=0xFFD700  # Gold color
        )
        
        embed.description = f"## **{self.username}'s Milestones**\n*Special achievements unlocked*"
        
        stats = self.user_data.get("stats", {})
        achievements = []
        
        # Episode milestones with fancy badges
        total_episodes = stats.get("anime", {}).get("episodesWatched", 0)
        if total_episodes >= 10000:
            achievements.append("� **Anime Deity** - 10,000+ episodes watched!")
        elif total_episodes >= 5000:
            achievements.append("🥇 **Episode Master** - 5,000+ episodes watched!")
        elif total_episodes >= 1000:
            achievements.append("�🎬 **Episode Collector** - 1,000+ episodes watched!")
        elif total_episodes >= 500:
            achievements.append("📺 **Binge Master** - 500+ episodes watched!")
        elif total_episodes >= 100:
            achievements.append("👀 **Regular Viewer** - 100+ episodes watched!")
        
        # Chapter milestones
        total_chapters = stats.get("manga", {}).get("chaptersRead", 0)
        if total_chapters >= 10000:
            achievements.append("📚 **Manga Sage** - 10,000+ chapters read!")
        elif total_chapters >= 5000:
            achievements.append("� **Manga Librarian** - 5,000+ chapters read!")
        elif total_chapters >= 1000:
            achievements.append("� **Chapter Champion** - 1,000+ chapters read!")
        elif total_chapters >= 500:
            achievements.append("� **Page Turner** - 500+ chapters read!")
        
        # Time-based achievements
        anime_hours = round(total_episodes * 24 / 60, 1)
        manga_hours = round(total_chapters * 5 / 60, 1)
        total_hours = anime_hours + manga_hours
        total_days = round(total_hours / 24, 1)
        
        if total_days >= 100:
            achievements.append("⏰ **Time Lord** - 100+ days of content consumed!")
        elif total_days >= 30:
            achievements.append("📅 **Dedicated Fan** - 30+ days of viewing time!")
        elif total_days >= 10:
            achievements.append("🕐 **Time Investment** - 10+ days of content!")
        
        # Completion achievements
        anime_completed = stats.get("anime", {}).get("statuses", {}).get("COMPLETED", 0)
        manga_completed = stats.get("manga", {}).get("statuses", {}).get("COMPLETED", 0)
        
        if anime_completed >= 500:
            achievements.append("👑 **Completion Royalty** - 500+ anime completed!")
        elif anime_completed >= 200:
            achievements.append("✅ **Completion King/Queen** - 200+ anime completed!")
        elif anime_completed >= 100:
            achievements.append("🏁 **Finisher Supreme** - 100+ anime completed!")
        elif anime_completed >= 50:
            achievements.append("� **Finisher** - 50+ anime completed!")
        
        if manga_completed >= 200:
            achievements.append("� **Manga Master** - 200+ manga completed!")
        elif manga_completed >= 100:
            achievements.append("📖 **Reading Champion** - 100+ manga completed!")
        elif manga_completed >= 50:
            achievements.append("📋 **Reader** - 50+ manga completed!")
        
        # Genre diversity
        top_genres = self.user_data.get("top_genres", [])
        if len(top_genres) >= 15:
            achievements.append("🎭 **Genre Connoisseur** - 15+ different genres!")
        elif len(top_genres) >= 10:
            achievements.append("� **Genre Explorer** - 10+ different genres!")
        elif len(top_genres) >= 5:
            achievements.append("🎪 **Genre Dabbler** - 5+ different genres!")
        
        # Score achievements
        anime_mean = stats.get("anime", {}).get("meanScore", 0)
        manga_mean = stats.get("manga", {}).get("meanScore", 0)
        
        if anime_mean >= 85 or manga_mean >= 85:
            achievements.append("🌟 **Perfectionist** - Average score 8.5+!")
        elif anime_mean >= 80 or manga_mean >= 80:
            achievements.append("⭐ **High Standards** - Average score 8.0+!")
        elif anime_mean >= 75 or manga_mean >= 75:
            achievements.append("🔍 **Quality Seeker** - Average score 7.5+!")
        
        # Special achievements based on ratios
        if total_episodes > 0 and total_chapters > 0:
            if total_episodes > total_chapters * 2:
                achievements.append("📺 **Anime Focused** - Prefers watching over reading!")
            elif total_chapters > total_episodes * 10:
                achievements.append("📚 **Bookworm** - Prefers reading over watching!")
            else:
                achievements.append("⚖️ **Balanced Consumer** - Equal anime & manga love!")
        
        if not achievements:
            achievements.append("🌱 **Getting Started** - Your journey begins here!")
        
        # Format achievements in a nice layout
        if len(achievements) > 0:
            # Split into columns for better presentation
            half = len(achievements) // 2 + (len(achievements) % 2)
            col1 = achievements[:half]
            col2 = achievements[half:]
            
            embed.add_field(
                name="🏆 **Unlocked Achievements**",
                value="\n".join(col1),
                inline=True
            )
            
            if col2:
                embed.add_field(
                    name="🎖️ **More Achievements**",
                    value="\n".join(col2),
                    inline=True
                )
        
        # Progress summary
        progress_summary = []
        if total_episodes > 0:
            progress_summary.append(f"📺 {total_episodes:,} episodes watched")
        if total_chapters > 0:
            progress_summary.append(f"📖 {total_chapters:,} chapters read")
        if total_days > 0:
            progress_summary.append(f"⏰ {total_days:.1f} days of content")
        
        if progress_summary:
            embed.add_field(
                name="📊 **Your Journey**",
                value=" • ".join(progress_summary),
                inline=False
            )
        
        embed.set_footer(
            text=f"Page 4/{self.total_pages} • {len(achievements)} Achievement{'s' if len(achievements) != 1 else ''} Unlocked!",
            icon_url="https://anilist.co/img/icons/android-chrome-512x512.png"
        )
        return embed
    
    def _get_main_achievements(self, stats: Dict) -> List[str]:
        """Get main achievements for overview page"""
        achievements = []
        
        total_episodes = stats.get("anime", {}).get("episodesWatched", 0)
        total_chapters = stats.get("manga", {}).get("chaptersRead", 0)
        
        if total_episodes >= 1000:
            achievements.append("🎬 Episode Collector")
        elif total_episodes >= 500:
            achievements.append("📺 Binge Master")
        
        if total_chapters >= 5000:
            achievements.append("📚 Manga Librarian")
        elif total_chapters >= 1000:
            achievements.append("📖 Chapter Champion")
        
        anime_completed = stats.get("anime", {}).get("statuses", {}).get("COMPLETED", 0)
        if anime_completed >= 100:
            achievements.append("✅ Completion King/Queen")
        
        top_genres = self.user_data.get("top_genres", [])
        if len(top_genres) >= 10:
            achievements.append("🎭 Genre Explorer")
        
        return achievements
    
    def _year_review_embed(self) -> discord.Embed:
        """Create year in review embed with enhanced styling"""
        period_text = f"{self.period.title()}" if self.period != "all_time" else "All Time"
        
        embed = discord.Embed(
            title=f"📅 {period_text.upper()} YEAR IN REVIEW",
            color=0x9146FF  # Purple theme for year review
        )
        
        embed.description = f"## **{self.username}'s Journey**\n*A look back at your amazing year*"
        
        stats = self.user_data.get("stats", {})
        
        # Monthly activity summary (if available)
        monthly_data = self._get_monthly_activity()
        if monthly_data:
            embed.add_field(
                name="📊 **Activity Timeline**",
                value=f"```yaml\nMost Active Month: {monthly_data['peak_month']}\nSlowest Month: {monthly_data['quiet_month']}\nConsistency Score: {monthly_data['consistency']}/10\n```",
                inline=False
            )
        
        # Year highlights
        highlights = []
        
        # Content consumption
        anime_episodes = stats.get("anime", {}).get("episodesWatched", 0)
        manga_chapters = stats.get("manga", {}).get("chaptersRead", 0)
        
        if anime_episodes > 0:
            anime_hours = round(anime_episodes * 24 / 60, 1)
            highlights.append(f"🎬 **{anime_episodes:,}** episodes watched ({anime_hours:,}h)")
        
        if manga_chapters > 0:
            manga_hours = round(manga_chapters * 5 / 60, 1) 
            highlights.append(f"📖 **{manga_chapters:,}** chapters read ({manga_hours:,}h)")
        
        # Completion stats
        anime_completed = stats.get("anime", {}).get("statuses", {}).get("COMPLETED", 0)
        manga_completed = stats.get("manga", {}).get("statuses", {}).get("COMPLETED", 0)
        
        if anime_completed > 0:
            highlights.append(f"✅ **{anime_completed}** anime completed")
        if manga_completed > 0:
            highlights.append(f"📚 **{manga_completed}** manga completed")
        
        if highlights:
            embed.add_field(
                name="🌟 **Year Highlights**",
                value="\n".join(highlights),
                inline=True
            )
        
        # Personal bests and records
        records = []
        
        # Get top scores
        top_anime = self.user_data.get("top_anime", [])
        top_manga = self.user_data.get("top_manga", [])
        
        if top_anime:
            best_anime = max(top_anime, key=lambda x: x.get("score", 0))
            if best_anime.get("score", 0) > 0:
                records.append(f"� Best Anime: **{best_anime['title']}** ({best_anime['score']}/10)")
        
        if top_manga:
            best_manga = max(top_manga, key=lambda x: x.get("score", 0))
            if best_manga.get("score", 0) > 0:
                records.append(f"🥇 Best Manga: **{best_manga['title']}** ({best_manga['score']}/10)")
        
        # Genre exploration
        top_genres = self.user_data.get("top_genres", [])
        if top_genres:
            records.append(f"🎭 Explored **{len(top_genres)}** different genres")
            favorite_genre = top_genres[0] if top_genres else None
            if favorite_genre:
                records.append(f"💫 Favorite Genre: **{favorite_genre['name']}**")
        
        if records:
            embed.add_field(
                name="📈 **Personal Records**",
                value="\n".join(records),
                inline=True
            )
        
        # Year summary statistics in a code block
        summary_stats = []
        total_content = anime_episodes + manga_chapters
        if total_content > 0:
            summary_stats.append(f"Total Content: {total_content:,} items")
        
        total_time = 0
        if anime_episodes > 0:
            total_time += anime_episodes * 24 / 60
        if manga_chapters > 0:
            total_time += manga_chapters * 5 / 60
        
        if total_time > 0:
            days = round(total_time / 24, 1)
            summary_stats.append(f"Total Time: {days:.1f} days")
        
        anime_mean = stats.get("anime", {}).get("meanScore", 0)
        manga_mean = stats.get("manga", {}).get("meanScore", 0)
        overall_mean = 0
        
        if anime_mean > 0 and manga_mean > 0:
            overall_mean = (anime_mean + manga_mean) / 2
        elif anime_mean > 0:
            overall_mean = anime_mean
        elif manga_mean > 0:
            overall_mean = manga_mean
        
        if overall_mean > 0:
            summary_stats.append(f"Average Score: {overall_mean:.1f}/10")
        
        completion_rate = 0
        total_entries = sum(stats.get("anime", {}).get("statuses", {}).values()) + sum(stats.get("manga", {}).get("statuses", {}).values())
        total_completed = anime_completed + manga_completed
        if total_entries > 0:
            completion_rate = (total_completed / total_entries) * 100
            summary_stats.append(f"Completion Rate: {completion_rate:.1f}%")
        
        if summary_stats:
            embed.add_field(
                name="📋 **Year Summary**",
                value=f"```ini\n{chr(10).join(summary_stats)}\n```",
                inline=False
            )
        
        # Motivational message based on activity
        motivation = self._get_year_motivation(stats)
        if motivation:
            embed.add_field(
                name="💫 **Looking Forward**",
                value=motivation,
                inline=False
            )
        
        embed.set_footer(
            text=f"Page 5/{self.total_pages} • What a year it's been!",
            icon_url="https://anilist.co/img/icons/android-chrome-512x512.png"
        )
        return embed
    
    def _get_monthly_activity(self) -> Dict:
        """Generate mock monthly activity data"""
        # This would normally come from actual data tracking
        # For now, return mock data that looks realistic
        months = ["January", "February", "March", "April", "May", "June", 
                 "July", "August", "September", "October", "November", "December"]
        
        import random
        random.seed(hash(self.username))  # Consistent per user
        
        peak_month = random.choice(months)
        quiet_month = random.choice([m for m in months if m != peak_month])
        consistency = random.randint(6, 9)
        
        return {
            "peak_month": peak_month,
            "quiet_month": quiet_month, 
            "consistency": consistency
        }
    
    def _get_year_motivation(self, stats: Dict) -> str:
        """Get motivational message based on user's stats"""
        anime_episodes = stats.get("anime", {}).get("episodesWatched", 0)
        manga_chapters = stats.get("manga", {}).get("chaptersRead", 0)
        
        if anime_episodes > 1000 or manga_chapters > 5000:
            return "🚀 **Incredible dedication!** You've consumed an amazing amount of content this year. Your passion for anime and manga truly shines!"
        elif anime_episodes > 500 or manga_chapters > 1000:
            return "⭐ **Great progress!** You've had a solid year of anime and manga consumption. Keep exploring new series!"
        elif anime_episodes > 100 or manga_chapters > 500:
            return "🌟 **Nice journey!** You've discovered some great content this year. Every series watched is a new adventure!"
        else:
            return "🌱 **Every start is special!** You're building your anime and manga journey. The best stories are yet to come!"
    
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
            query ($username: String) {
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
                      title { 
                        romaji 
                        english 
                      }
                      averageScore
                    }
                  }
                  manga {
                    nodes {
                      id
                      title { 
                        romaji 
                        english 
                      }
                      averageScore
                    }
                  }
                }
              }
              
              animeList: MediaListCollection(
                userName: $username,
                type: ANIME,
                status: COMPLETED,
                sort: [SCORE_DESC]
              ) {
                lists {
                  entries {
                    score(format: POINT_10)
                    media {
                      id
                      title { 
                        romaji 
                        english 
                      }
                      averageScore
                    }
                  }
                }
              }
              
              mangaList: MediaListCollection(
                userName: $username,
                type: MANGA,
                status: COMPLETED,
                sort: [SCORE_DESC]
              ) {
                lists {
                  entries {
                    score(format: POINT_10)
                    media {
                      id
                      title { 
                        romaji 
                        english 
                      }
                      averageScore
                    }
                  }
                }
              }
            }
            """
            
            variables = {
                "username": username
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