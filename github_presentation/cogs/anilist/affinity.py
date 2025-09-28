import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import aiosqlite
import asyncio
import logging
import os
import math
from pathlib import Path
from config import DB_PATH

# ------------------------------------------------------
# Logging Setup - Auto-clearing
# ------------------------------------------------------
LOG_DIR = Path("logs")
try:
    LOG_DIR.mkdir(exist_ok=True)
except Exception:
    # If we can't create the logs dir (permission issues), continue and rely on StreamHandler
    pass

LOG_FILE = LOG_DIR / "affinity.log"

# Attempt to clear the log file on startup but tolerate locks (Windows)
try:
    if LOG_FILE.exists():
        try:
            LOG_FILE.unlink()
        except PermissionError:
            # File is in use by another process (e.g., external log viewer) — continue
            pass
except Exception:
    # Best-effort only; do not fail import
    pass

# Setup logger
logger = logging.getLogger("affinity")
logger.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Try to add a FileHandler; fall back to StreamHandler on PermissionError
try:
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    # Avoid adding duplicate file handlers for the same file
    if not any(
        isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == str(LOG_FILE)
        for h in logger.handlers
    ):
        logger.addHandler(file_handler)
    logger.info("Affinity cog logging initialized - writing to %s", LOG_FILE)
except PermissionError:
    # Fall back to console logging when file cannot be opened
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(stream_handler)
    logger.warning("Could not open affinity log file (permission denied); logging to stdout/stderr instead")
except Exception:
    # Any other unexpected error: use StreamHandler as a safe fallback
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        logger.addHandler(stream_handler)
    logger.exception("Unexpected error initializing affinity logger; using StreamHandler")

# ------------------------------------------------------
# Constants
# ------------------------------------------------------
API_URL = "https://graphql.anilist.co"
MAX_RETRIES = 3
RETRY_DELAY = 2
REQUEST_TIMEOUT = 10


class Affinity(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------
    # Fetch AniList user data with retries
    # ---------------------------------------------------------
    async def fetch_user(self, username: str):
        """Fetch user data from AniList API with retry logic."""
        query = """
        query ($name: String) {
          User(name: $name) {
            id
            name
            avatar { large }
            statistics {
              anime { count meanScore episodesWatched genres { genre count } formats { format count } }
              manga { count meanScore chaptersRead genres { genre count } formats { format count } }
            }
            favourites {
              anime { nodes { id } }
              manga { nodes { id } }
              characters { nodes { id } }
            }
          }
        }
        """
        
        logger.info(f"Fetching AniList data for user: {username}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        API_URL, 
                        json={"query": query, "variables": {"name": username}}, 
                        timeout=REQUEST_TIMEOUT
                    ) as resp:
                        if resp.status != 200:
                            logger.warning(f"HTTP {resp.status} for user {username} (attempt {attempt})")
                            continue
                            
                        data = await resp.json()
                        user_data = data.get("data", {}).get("User")
                        
                        if user_data:
                            logger.info(f"Successfully fetched data for user: {username}")
                            return user_data
                        else:
                            logger.warning(f"No user data returned for {username} (attempt {attempt})")
                            
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching data for {username} (attempt {attempt})")
            except Exception as e:
                logger.error(f"Error fetching data for {username} (attempt {attempt}): {e}")
                
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_DELAY)
        
        logger.error(f"Failed to fetch data for {username} after {MAX_RETRIES} attempts")
        return None

    # ---------------------------------------------------------
    # Advanced Affinity Calculation System
    # ---------------------------------------------------------
    def calculate_affinity(self, user1: dict, user2: dict, return_breakdown=False) -> float:
        """Calculate ultra-comprehensive affinity score using advanced weighting systems."""
        logger.debug(f"Calculating advanced affinity between {user1.get('name')} and {user2.get('name')}")
        
        # ===== UTILITY FUNCTIONS =====
        def weighted_jaccard(set1, set2, rarity_weights=None):
            """Advanced Jaccard similarity with rarity weighting."""
            if not set1 or not set2:
                return 0.0
            
            intersection = set1 & set2
            union = set1 | set2
            
            if not intersection:
                return 0.0
            
            if rarity_weights:
                # Weight by inverse rarity (rare items count more)
                intersection_weight = sum(rarity_weights.get(item, 1.0) for item in intersection)
                union_weight = sum(rarity_weights.get(item, 1.0) for item in union)
                return intersection_weight / max(union_weight, 1)
            
            return len(intersection) / len(union)

        def gaussian_similarity(a, b, sigma=1.0):
            """Gaussian similarity function for numeric values."""
            if a == 0 and b == 0:
                return 1.0
            diff = abs(a - b)
            max_val = max(abs(a), abs(b), 1)
            normalized_diff = diff / max_val
            return math.exp(-(normalized_diff ** 2) / (2 * sigma ** 2))

        def log_similarity(a, b):
            """Logarithmic similarity for highly variable numeric data."""
            if a == 0 and b == 0:
                return 1.0
            log_a = math.log(max(a, 1))
            log_b = math.log(max(b, 1))
            return 1 / (1 + abs(log_a - log_b))

        def experience_weight(count):
            """Weight based on user experience level."""
            if count == 0:
                return 0.1
            elif count < 10:
                return 0.3
            elif count < 50:
                return 0.6
            elif count < 100:
                return 0.8
            elif count < 500:
                return 1.0
            else:
                return 1.2  # Bonus for very experienced users

        def diversity_score(genres_list, formats_list):
            """Calculate diversity bonus based on genre/format variety."""
            total_items = len(genres_list) + len(formats_list)
            if total_items == 0:
                return 0.0
            unique_genres = len(set(g.get("genre", "") for g in genres_list))
            unique_formats = len(set(f.get("format", "") for f in formats_list))
            return (unique_genres + unique_formats) / max(total_items, 1) * 0.5

        def scoring_pattern_similarity(stats1, stats2):
            """Analyze scoring patterns and tendencies."""
            score1 = stats1.get("meanScore", 0)
            score2 = stats2.get("meanScore", 0)
            
            # Classify scoring tendencies
            def score_tendency(score):
                if score == 0:
                    return "unrated"
                elif score < 4:
                    return "harsh"
                elif score < 6:
                    return "critical"
                elif score < 7.5:
                    return "moderate"
                elif score < 8.5:
                    return "generous"
                else:
                    return "very_generous"
            
            tendency1 = score_tendency(score1)
            tendency2 = score_tendency(score2)
            
            # Award points for similar scoring patterns
            if tendency1 == tendency2:
                return 1.0
            elif abs(score1 - score2) <= 0.5:
                return 0.8
            elif abs(score1 - score2) <= 1.0:
                return 0.6
            elif abs(score1 - score2) <= 1.5:
                return 0.4
            else:
                return 0.2

        # ===== DATA EXTRACTION =====
        # Extract favorites with enhanced structure
        fav_anime1 = {a["id"] for a in user1.get("favourites", {}).get("anime", {}).get("nodes", [])}
        fav_anime2 = {a["id"] for a in user2.get("favourites", {}).get("anime", {}).get("nodes", [])}
        fav_manga1 = {m["id"] for m in user1.get("favourites", {}).get("manga", {}).get("nodes", [])}
        fav_manga2 = {m["id"] for m in user2.get("favourites", {}).get("manga", {}).get("nodes", [])}
        fav_char1 = {c["id"] for c in user1.get("favourites", {}).get("characters", {}).get("nodes", [])}
        fav_char2 = {c["id"] for c in user2.get("favourites", {}).get("characters", {}).get("nodes", [])}

        # Extract comprehensive statistics
        anime_stats1 = user1.get("statistics", {}).get("anime", {})
        anime_stats2 = user2.get("statistics", {}).get("anime", {})
        manga_stats1 = user1.get("statistics", {}).get("manga", {})
        manga_stats2 = user2.get("statistics", {}).get("manga", {})

        # ===== SCORING COMPONENTS =====
        
        # 1. FAVORITES AFFINITY (25% weight)
        anime_fav_score = weighted_jaccard(fav_anime1, fav_anime2) * 2.0  # High weight for anime favorites
        manga_fav_score = weighted_jaccard(fav_manga1, fav_manga2) * 1.8  # High weight for manga favorites
        char_fav_score = weighted_jaccard(fav_char1, fav_char2) * 1.5   # Character favorites
        
        # Bonus for having any shared favorites at all
        shared_favorites_bonus = 0
        if fav_anime1 & fav_anime2 or fav_manga1 & fav_manga2 or fav_char1 & fav_char2:
            shared_favorites_bonus = 0.3
        
        favorites_score = (anime_fav_score + manga_fav_score + char_fav_score + shared_favorites_bonus) * 6.25

        # 2. CONSUMPTION PATTERNS (20% weight)
        anime_count1 = anime_stats1.get("count", 0)
        anime_count2 = anime_stats2.get("count", 0)
        manga_count1 = manga_stats1.get("count", 0)  
        manga_count2 = manga_stats2.get("count", 0)
        
        # Experience-weighted consumption similarity
        anime_exp_weight1 = experience_weight(anime_count1)
        anime_exp_weight2 = experience_weight(anime_count2)
        manga_exp_weight1 = experience_weight(manga_count1)
        manga_exp_weight2 = experience_weight(manga_count2)
        
        avg_anime_weight = (anime_exp_weight1 + anime_exp_weight2) / 2
        avg_manga_weight = (manga_exp_weight1 + manga_exp_weight2) / 2
        
        anime_count_sim = gaussian_similarity(anime_count1, anime_count2, sigma=0.8) * avg_anime_weight
        manga_count_sim = gaussian_similarity(manga_count1, manga_count2, sigma=0.8) * avg_manga_weight
        
        # Episode/Chapter consumption patterns
        episodes1 = anime_stats1.get("episodesWatched", 0)
        episodes2 = anime_stats2.get("episodesWatched", 0)
        chapters1 = manga_stats1.get("chaptersRead", 0)
        chapters2 = manga_stats2.get("chaptersRead", 0)
        
        episode_sim = log_similarity(episodes1, episodes2)
        chapter_sim = log_similarity(chapters1, chapters2)
        
        consumption_score = (anime_count_sim * 0.3 + manga_count_sim * 0.25 + 
                           episode_sim * 0.25 + chapter_sim * 0.2) * 20

        # 3. SCORING COMPATIBILITY (15% weight)
        anime_scoring_sim = scoring_pattern_similarity(anime_stats1, anime_stats2)
        manga_scoring_sim = scoring_pattern_similarity(manga_stats1, manga_stats2)
        
        # Additional scoring analysis
        anime_score_sim = gaussian_similarity(anime_stats1.get("meanScore", 0), 
                                            anime_stats2.get("meanScore", 0), sigma=0.6)
        manga_score_sim = gaussian_similarity(manga_stats1.get("meanScore", 0), 
                                            manga_stats2.get("meanScore", 0), sigma=0.6)
        
        scoring_score = (anime_scoring_sim * 0.4 + manga_scoring_sim * 0.35 + 
                        anime_score_sim * 0.15 + manga_score_sim * 0.1) * 15

        # 4. GENRE AFFINITY WITH WEIGHTED PREFERENCES (15% weight)
        anime_genres1 = anime_stats1.get("genres", [])
        anime_genres2 = anime_stats2.get("genres", [])
        manga_genres1 = manga_stats1.get("genres", [])
        manga_genres2 = manga_stats2.get("genres", [])
        
        # Create weighted genre sets (weight by count)
        def create_weighted_genre_dict(genre_list):
            return {g["genre"]: g["count"] for g in genre_list if g.get("genre") and g.get("count", 0) > 0}
        
        anime_genre_weights1 = create_weighted_genre_dict(anime_genres1)
        anime_genre_weights2 = create_weighted_genre_dict(anime_genres2)
        manga_genre_weights1 = create_weighted_genre_dict(manga_genres1)
        manga_genre_weights2 = create_weighted_genre_dict(manga_genres2)
        
        def weighted_genre_similarity(weights1, weights2):
            if not weights1 or not weights2:
                return 0.0
            
            common_genres = set(weights1.keys()) & set(weights2.keys())
            if not common_genres:
                return 0.0
            
            # Calculate weighted cosine similarity
            dot_product = sum(weights1[g] * weights2[g] for g in common_genres)
            norm1 = math.sqrt(sum(w**2 for w in weights1.values()))
            norm2 = math.sqrt(sum(w**2 for w in weights2.values()))
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            return dot_product / (norm1 * norm2)
        
        anime_genre_sim = weighted_genre_similarity(anime_genre_weights1, anime_genre_weights2)
        manga_genre_sim = weighted_genre_similarity(manga_genre_weights1, manga_genre_weights2)
        
        # Diversity bonus
        diversity1 = diversity_score(anime_genres1 + manga_genres1, [])
        diversity2 = diversity_score(anime_genres2 + manga_genres2, [])
        diversity_bonus = gaussian_similarity(diversity1, diversity2, sigma=0.5) * 0.3
        
        genre_score = (anime_genre_sim * 0.5 + manga_genre_sim * 0.4 + diversity_bonus * 0.1) * 15

        # 5. FORMAT PREFERENCES (10% weight)
        anime_formats1 = anime_stats1.get("formats", [])
        anime_formats2 = anime_stats2.get("formats", [])
        manga_formats1 = manga_stats1.get("formats", [])
        manga_formats2 = manga_stats2.get("formats", [])
        
        anime_format_weights1 = {f["format"]: f["count"] for f in anime_formats1 if f.get("format") and f.get("count", 0) > 0}
        anime_format_weights2 = {f["format"]: f["count"] for f in anime_formats2 if f.get("format") and f.get("count", 0) > 0}
        manga_format_weights1 = {f["format"]: f["count"] for f in manga_formats1 if f.get("format") and f.get("count", 0) > 0}
        manga_format_weights2 = {f["format"]: f["count"] for f in manga_formats2 if f.get("format") and f.get("count", 0) > 0}
        
        anime_format_sim = weighted_genre_similarity(anime_format_weights1, anime_format_weights2)
        manga_format_sim = weighted_genre_similarity(manga_format_weights1, manga_format_weights2)
        
        format_score = (anime_format_sim * 0.6 + manga_format_sim * 0.4) * 10

        # 6. ACTIVITY LEVEL COMPATIBILITY (8% weight)
        total_anime1 = anime_count1 + episodes1 / 12  # Normalize episodes to "series equivalent"
        total_anime2 = anime_count2 + episodes2 / 12
        total_manga1 = manga_count1 + chapters1 / 50   # Normalize chapters to "series equivalent"  
        total_manga2 = manga_count2 + chapters2 / 50
        
        total_activity1 = total_anime1 + total_manga1
        total_activity2 = total_anime2 + total_manga2
        
        activity_sim = gaussian_similarity(total_activity1, total_activity2, sigma=1.0)
        
        # Bonus for both being active users
        if total_activity1 > 10 and total_activity2 > 10:
            activity_sim *= 1.2
            
        activity_score = activity_sim * 8

        # 7. BALANCE FACTOR (7% weight) - Anime vs Manga preference balance
        def media_balance(anime_count, manga_count):
            total = anime_count + manga_count
            if total == 0:
                return 0.5  # Neutral
            return anime_count / total
        
        balance1 = media_balance(anime_count1, manga_count1)
        balance2 = media_balance(anime_count2, manga_count2)
        
        balance_sim = gaussian_similarity(balance1, balance2, sigma=0.4)
        balance_score = balance_sim * 7

        # ===== FINAL CALCULATION =====
        raw_score = (
            favorites_score +      # 25%
            consumption_score +    # 20%
            scoring_score +        # 15%
            genre_score +          # 15%
            format_score +         # 10%
            activity_score +       # 8%
            balance_score          # 7%
        )
        
        # Apply experience multiplier (bonus for comparing experienced users)
        min_experience = min(avg_anime_weight, avg_manga_weight)
        experience_multiplier = 0.9 + (min_experience * 0.2)  # 0.9 to 1.1 multiplier
        
        # Apply completion bonus (users who complete series vs droppers)
        # This would need additional data, so we'll use a placeholder
        completion_bonus = 1.0
        
        final_score = min(raw_score * experience_multiplier * completion_bonus, 100.0)
        
        logger.debug(f"Advanced affinity breakdown - Favorites: {favorites_score:.2f}, "
                    f"Consumption: {consumption_score:.2f}, Scoring: {scoring_score:.2f}, "
                    f"Genres: {genre_score:.2f}, Formats: {format_score:.2f}, "
                    f"Activity: {activity_score:.2f}, Balance: {balance_score:.2f}")
        logger.debug(f"Final affinity calculated: {final_score:.2f}%")
        
        if return_breakdown:
            breakdown = {
                'favorites': favorites_score,
                'consumption': consumption_score,
                'scoring': scoring_score,
                'genres': genre_score,
                'formats': format_score,
                'activity': activity_score,
                'balance': balance_score
            }
            return round(final_score, 2), breakdown
        
        return round(final_score, 2)

    # ---------------------------------------------------------
    # Enhanced Paginated Embed View with Detailed Breakdowns
    # ---------------------------------------------------------
    class AffinityView(discord.ui.View):
        def __init__(self, entries, user_name, detailed_data=None):
            super().__init__(timeout=300)  # 5 minute timeout
            self.entries = entries
            self.page = 0
            self.user_name = user_name
            self.per_page = 8  # Reduced to allow for more detail
            self.detailed_data = detailed_data or {}
            self.show_details = False
            logger.debug(f"Enhanced AffinityView created with {len(entries)} entries for {user_name}")

        def get_embed(self):
            """Generate the current page embed with enhanced information."""
            start = self.page * self.per_page
            end = start + self.per_page
            current_entries = self.entries[start:end]
            total_pages = (len(self.entries) - 1) // self.per_page + 1

            if self.show_details:
                # Detailed view with score breakdowns
                description_parts = []
                for i, (discord_id, score) in enumerate(current_entries, start=start + 1):
                    base_info = f"{i}. `{score}%` — <@{discord_id}>"
                    
                    # Add breakdown if available
                    if discord_id in self.detailed_data:
                        breakdown = self.detailed_data[discord_id]
                        detail = (f"\n   └ *Fav: {breakdown.get('favorites', 0):.1f}% | "
                                f"Usage: {breakdown.get('consumption', 0):.1f}% | "
                                f"Score: {breakdown.get('scoring', 0):.1f}% | "
                                f"Genre: {breakdown.get('genres', 0):.1f}%*")
                        base_info += detail
                    
                    description_parts.append(base_info)
                
                description = "\n".join(description_parts)
                embed_title = f"💞 Detailed Affinity Ranking for {self.user_name}"
            else:
                # Standard compact view
                description = "\n".join(
                    f"{i}. `{score}%` — <@{discord_id}>"
                    for i, (discord_id, score) in enumerate(current_entries, start=start + 1)
                )
                embed_title = f"💞 Affinity Ranking for {self.user_name}"

            if not description:
                description = "No users found."

            # Color coding based on average affinity
            if current_entries:
                avg_score = sum(score for _, score in current_entries) / len(current_entries)
                if avg_score >= 80:
                    color = discord.Color.gold()
                elif avg_score >= 60:
                    color = discord.Color.green()
                elif avg_score >= 40:
                    color = discord.Color.orange()
                else:
                    color = discord.Color.red()
            else:
                color = discord.Color.blurple()

            embed = discord.Embed(
                title=embed_title,
                description=description,
                color=color
            )
            
            # Enhanced footer with statistics
            if self.entries:
                highest_score = max(score for _, score in self.entries)
                avg_all_score = sum(score for _, score in self.entries) / len(self.entries)
                footer_text = (f"Page {self.page + 1}/{total_pages} • {len(self.entries)} total results\n"
                             f"Highest: {highest_score}% • Average: {avg_all_score:.1f}%")
                if self.show_details:
                    footer_text += " • Showing detailed breakdown"
            else:
                footer_text = f"Page {self.page + 1}/{total_pages} • No results"
                
            embed.set_footer(text=footer_text)
            return embed

        async def on_timeout(self):
            """Handle view timeout."""
            logger.info(f"Enhanced AffinityView timed out for {self.user_name}")
            # Disable all buttons
            for item in self.children:
                item.disabled = True

        @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.blurple)
        async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            """Go to previous page."""
            if self.page > 0:
                self.page -= 1
                logger.debug(f"AffinityView: Moving to page {self.page + 1} for {self.user_name}")
                await interaction.response.edit_message(embed=self.get_embed(), view=self)
            else:
                await interaction.response.defer()

        @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.blurple)
        async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            """Go to next page."""
            max_page = (len(self.entries) - 1) // self.per_page
            if self.page < max_page:
                self.page += 1
                logger.debug(f"AffinityView: Moving to page {self.page + 1} for {self.user_name}")
                await interaction.response.edit_message(embed=self.get_embed(), view=self)
            else:
                await interaction.response.defer()

        @discord.ui.button(label="📊 Toggle Details", style=discord.ButtonStyle.secondary)
        async def toggle_details(self, interaction: discord.Interaction, button: discord.ui.Button):
            """Toggle between standard and detailed view."""
            self.show_details = not self.show_details
            logger.debug(f"AffinityView: Toggled details to {self.show_details} for {self.user_name}")
            await interaction.response.edit_message(embed=self.get_embed(), view=self)

    # ---------------------------------------------------------
    # Slash Command: /affinity
    # ---------------------------------------------------------
    @app_commands.command(
        name="affinity",
        description="Compare your affinity with all registered AniList users"
    )
    async def affinity(self, interaction: discord.Interaction):
        """Calculate and display affinity rankings for the requesting user."""
        await interaction.response.defer()
        
        discord_id = interaction.user.id
        user_display = interaction.user.display_name
        
        logger.info(f"Affinity command started by {user_display} (ID: {discord_id})")
        
        try:
            # Get user's AniList username
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT anilist_username FROM users WHERE discord_id = ?", 
                    (discord_id,)
                )
                row = await cursor.fetchone()
                
                if not row:
                    logger.warning(f"User {user_display} (ID: {discord_id}) not registered")
                    await interaction.followup.send(
                        "❌ You are not registered. Use `/register` to link your AniList account first.", 
                        ephemeral=True
                    )
                    return
                    
                anilist_username = row[0]
                logger.info(f"Found AniList username: {anilist_username} for {user_display}")

                # Get all other users
                cursor = await db.execute(
                    "SELECT discord_id, anilist_username FROM users WHERE discord_id != ? AND anilist_username IS NOT NULL",
                    (discord_id,)
                )
                all_users = await cursor.fetchall()
                
            logger.info(f"Found {len(all_users)} other users to compare with")
            
            if not all_users:
                await interaction.followup.send(
                    "❌ No other registered users found to compare with.", 
                    ephemeral=True
                )
                return

            # Fetch requesting user's data
            me = await self.fetch_user(anilist_username)
            if not me:
                logger.error(f"Failed to fetch AniList data for {anilist_username}")
                await interaction.followup.send(
                    "❌ Could not fetch your AniList data. Make sure your profile is public and try again.", 
                    ephemeral=True
                )
                return

            # Calculate affinities with detailed breakdowns
            logger.info(f"Starting advanced affinity calculations for {anilist_username}")
            results = []
            detailed_data = {}
            successful_comparisons = 0
            
            for other_discord_id, other_anilist in all_users:
                other_user = await self.fetch_user(other_anilist)
                if other_user:
                    score, breakdown = self.calculate_affinity(me, other_user, return_breakdown=True)
                    results.append((other_discord_id, score))
                    detailed_data[other_discord_id] = breakdown
                    successful_comparisons += 1
                    logger.debug(f"Calculated advanced affinity with {other_anilist}: {score}%")
                else:
                    logger.warning(f"Failed to fetch data for {other_anilist}")

            if not results:
                logger.warning("No successful affinity calculations")
                await interaction.followup.send(
                    "❌ Could not fetch data for any other users. Please try again later.", 
                    ephemeral=True
                )
                return

            # Sort results by affinity score (highest first)
            results.sort(key=lambda x: x[1], reverse=True)
            
            logger.info(f"Advanced affinity calculation completed: {successful_comparisons}/{len(all_users)} successful comparisons")

            # Create and send enhanced paginated view with detailed breakdowns
            view = self.AffinityView(results, user_display, detailed_data)
            await interaction.followup.send(embed=view.get_embed(), view=view)
            logger.info(f"Enhanced affinity results sent for {user_display}")
            
        except Exception as e:
            logger.error(f"Error in affinity command for {user_display}: {e}")
            await interaction.followup.send(
                "❌ An error occurred while calculating affinities. Please try again later.", 
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Affinity(bot))