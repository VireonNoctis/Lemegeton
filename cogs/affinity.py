import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import aiosqlite
import asyncio
import logging
import os
from pathlib import Path
from config import GUILD_ID

# ------------------------------------------------------
# Logging Setup - Auto-clearing
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "affinity.log"

# Clear the log file on startup
if LOG_FILE.exists():
    LOG_FILE.unlink()

# Setup logger
logger = logging.getLogger("affinity")
logger.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)

# Add handler if not already added
if not logger.handlers:
    logger.addHandler(file_handler)

logger.info("Affinity cog logging initialized - log file cleared")

# ------------------------------------------------------
# Constants
# ------------------------------------------------------
API_URL = "https://graphql.anilist.co"
DB_PATH = "database.db"
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
    # Calculate affinity between two users
    # ---------------------------------------------------------
    def calculate_affinity(self, user1: dict, user2: dict) -> float:
        """Calculate comprehensive affinity score between two users."""
        logger.debug(f"Calculating affinity between {user1.get('name')} and {user2.get('name')}")
        
        def weighted_overlap(set1, set2, weight=1.0):
            """Calculate weighted overlap between two sets."""
            shared = set1 & set2
            if not shared:
                return 0.0
                
            # Simplified scoring without complex rarity calculations
            overlap_ratio = len(shared) / max(len(set1 | set2), 1)
            return weight * overlap_ratio

        def similarity_score(a, b):
            """Calculate similarity between two numeric values."""
            if a == 0 and b == 0:
                return 1.0
            return 1 - abs(a - b) / max(abs(a), abs(b), 1)

        # Extract favorites
        fav_anime1 = {a["id"] for a in user1.get("favourites", {}).get("anime", {}).get("nodes", [])}
        fav_anime2 = {a["id"] for a in user2.get("favourites", {}).get("anime", {}).get("nodes", [])}
        fav_manga1 = {m["id"] for m in user1.get("favourites", {}).get("manga", {}).get("nodes", [])}
        fav_manga2 = {m["id"] for m in user2.get("favourites", {}).get("manga", {}).get("nodes", [])}
        fav_char1 = {c["id"] for c in user1.get("favourites", {}).get("characters", {}).get("nodes", [])}
        fav_char2 = {c["id"] for c in user2.get("favourites", {}).get("characters", {}).get("nodes", [])}

        # Calculate favorite overlaps
        fav_score = (
            weighted_overlap(fav_anime1, fav_anime2, 1.5) +
            weighted_overlap(fav_manga1, fav_manga2, 1.2) +
            weighted_overlap(fav_char1, fav_char2, 1.0)
        )

        # Extract statistics
        anime_stats1 = user1.get("statistics", {}).get("anime", {})
        anime_stats2 = user2.get("statistics", {}).get("anime", {})
        manga_stats1 = user1.get("statistics", {}).get("manga", {})
        manga_stats2 = user2.get("statistics", {}).get("manga", {})

        # Calculate statistical similarities
        anime_count_score = similarity_score(anime_stats1.get("count", 0), anime_stats2.get("count", 0))
        anime_score_score = similarity_score(anime_stats1.get("meanScore", 0), anime_stats2.get("meanScore", 0))
        anime_episodes_score = similarity_score(anime_stats1.get("episodesWatched", 0), anime_stats2.get("episodesWatched", 0))

        manga_count_score = similarity_score(manga_stats1.get("count", 0), manga_stats2.get("count", 0))
        manga_score_score = similarity_score(manga_stats1.get("meanScore", 0), manga_stats2.get("meanScore", 0))
        manga_chapters_score = similarity_score(manga_stats1.get("chaptersRead", 0), manga_stats2.get("chaptersRead", 0))

        # Genre and format overlap
        genres1 = {g["genre"] for g in anime_stats1.get("genres", [])} | {g["genre"] for g in manga_stats1.get("genres", [])}
        genres2 = {g["genre"] for g in anime_stats2.get("genres", [])} | {g["genre"] for g in manga_stats2.get("genres", [])}
        genre_score = len(genres1 & genres2) / max(len(genres1 | genres2), 1)

        formats1 = {f["format"] for f in anime_stats1.get("formats", [])} | {f["format"] for f in manga_stats1.get("formats", [])}
        formats2 = {f["format"] for f in anime_stats2.get("formats", [])} | {f["format"] for f in manga_stats2.get("formats", [])}
        format_score = len(formats1 & formats2) / max(len(formats1 | formats2), 1)

        # Final weighted calculation
        affinity_score = round(
            fav_score * 35 +
            (anime_count_score + anime_score_score + anime_episodes_score) / 3 * 15 +
            (manga_count_score + manga_score_score + manga_chapters_score) / 3 * 15 +
            genre_score * 10 +
            format_score * 10 +
            0.5 * 15,  # Base compatibility score
            2
        )

        final_score = min(affinity_score, 100.0)
        logger.debug(f"Affinity calculated: {final_score}%")
        return final_score

    # ---------------------------------------------------------
    # Paginated Embed View
    # ---------------------------------------------------------
    class AffinityView(discord.ui.View):
        def __init__(self, entries, user_name):
            super().__init__(timeout=300)  # 5 minute timeout
            self.entries = entries
            self.page = 0
            self.user_name = user_name
            self.per_page = 10
            logger.debug(f"AffinityView created with {len(entries)} entries for {user_name}")

        def get_embed(self):
            """Generate the current page embed."""
            start = self.page * self.per_page
            end = start + self.per_page
            current_entries = self.entries[start:end]
            total_pages = (len(self.entries) - 1) // self.per_page + 1

            description = "\n".join(
                f"{i}. `{score}%` — <@{discord_id}>"
                for i, (discord_id, score) in enumerate(current_entries, start=start + 1)
            )

            if not description:
                description = "No users found."

            embed = discord.Embed(
                title=f"💞 Affinity Ranking for {self.user_name}",
                description=description,
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"Page {self.page + 1}/{total_pages} • {len(self.entries)} total results")
            return embed

        async def on_timeout(self):
            """Handle view timeout."""
            logger.info(f"AffinityView timed out for {self.user_name}")
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

    # ---------------------------------------------------------
    # Slash Command: /affinity
    # ---------------------------------------------------------
    @app_commands.guilds(discord.Object(id=GUILD_ID))
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

            # Calculate affinities
            logger.info(f"Starting affinity calculations for {anilist_username}")
            results = []
            successful_comparisons = 0
            
            for other_discord_id, other_anilist in all_users:
                other_user = await self.fetch_user(other_anilist)
                if other_user:
                    score = self.calculate_affinity(me, other_user)
                    results.append((other_discord_id, score))
                    successful_comparisons += 1
                    logger.debug(f"Calculated affinity with {other_anilist}: {score}%")
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
            
            logger.info(f"Affinity calculation completed: {successful_comparisons}/{len(all_users)} successful comparisons")

            # Create and send paginated view
            view = self.AffinityView(results, user_display)
            await interaction.followup.send(embed=view.get_embed(), view=view)
            logger.info(f"Affinity results sent for {user_display}")
            
        except Exception as e:
            logger.error(f"Error in affinity command for {user_display}: {e}")
            await interaction.followup.send(
                "❌ An error occurred while calculating affinities. Please try again later.", 
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Affinity(bot))