import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import aiohttp
import logging
import os
from pathlib import Path
from typing import Optional, List, Tuple
from config import GUILD_ID
from database import DB_PATH

# Configuration constants
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "challenge_change.log"
ANILIST_API_URL = "https://graphql.anilist.co"
VIEW_TIMEOUT = 120
MAX_TITLE_LENGTH = 100
MAX_MANGA_ID = 999999

# Ensure logs directory exists
LOG_DIR.mkdir(exist_ok=True)

# Set up file-based logging with auto-clearing
logger = logging.getLogger("ChallengeChange")
logger.setLevel(logging.DEBUG)

# Clear handlers to avoid duplicates
logger.handlers.clear()

# Create file handler that clears on startup
file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter(
    fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(file_handler)

logger.info("Challenge Change cog logging system initialized")

class ChallengeManagementView(discord.ui.View):
    """Interactive view for challenge management actions."""
    
    def __init__(self, user_id: int):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.user_id = user_id
        logger.debug(f"Created ChallengeManagementView for user ID: {user_id}")

    @discord.ui.button(label="➕ Add Manga", style=discord.ButtonStyle.success, emoji="➕")
    async def add_manga_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show modal for adding manga to challenge."""
        logger.info(f"Add manga button clicked by {interaction.user.display_name} (ID: {self.user_id})")
        
        modal = AddMangaModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🗑️ Remove Manga", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def remove_manga_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show modal for removing manga from challenge."""
        logger.info(f"Remove manga button clicked by {interaction.user.display_name} (ID: {self.user_id})")
        
        modal = RemoveMangaModal()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="📋 List Challenges", style=discord.ButtonStyle.secondary, emoji="📋")
    async def list_challenges_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show all active challenges."""
        logger.info(f"List challenges button clicked by {interaction.user.display_name} (ID: {self.user_id})")
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            challenge_cog = interaction.client.get_cog("ChallengeChange")
            if challenge_cog:
                challenges_info = await challenge_cog.get_all_challenges()
                
                if not challenges_info:
                    embed = discord.Embed(
                        title="📋 Challenge List",
                        description="No active challenges found.",
                        color=discord.Color.orange()
                    )
                else:
                    embed = discord.Embed(
                        title="📋 Active Challenges",
                        description=f"Found {len(challenges_info)} active challenge(s):",
                        color=discord.Color.blue()
                    )
                    
                    for i, (challenge_id, title, manga_count) in enumerate(challenges_info[:10], 1):
                        embed.add_field(
                            name=f"{i}. {title}",
                            value=f"ID: `{challenge_id}` • {manga_count} manga",
                            inline=False
                        )
                    
                    if len(challenges_info) > 10:
                        embed.set_footer(text=f"Showing first 10 of {len(challenges_info)} challenges")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("❌ System error: Challenge management not available.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error listing challenges: {e}", exc_info=True)
            await interaction.followup.send("❌ Error retrieving challenge list.", ephemeral=True)

    @discord.ui.button(label="🔍 Search Manga", style=discord.ButtonStyle.primary, emoji="🔍")
    async def search_manga_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show information about a specific manga."""
        logger.info(f"Search manga button clicked by {interaction.user.display_name} (ID: {self.user_id})")
        
        modal = SearchMangaModal()
        await interaction.response.send_modal(modal)

    async def on_timeout(self):
        """Handle view timeout by disabling buttons."""
        try:
            self.clear_items()
            logger.debug(f"ChallengeManagementView timed out for user ID: {self.user_id}")
        except Exception as e:
            logger.error(f"Error handling ChallengeManagementView timeout: {e}", exc_info=True)


class AddMangaModal(discord.ui.Modal):
    """Modal for adding manga to challenges."""
    
    def __init__(self):
        super().__init__(title="➕ Add Manga to Challenge")
        
        self.challenge_title = discord.ui.TextInput(
            label="Challenge Title",
            placeholder="Enter challenge title (will be created if it doesn't exist)",
            required=True,
            max_length=MAX_TITLE_LENGTH
        )
        self.add_item(self.challenge_title)
        
        self.manga_id = discord.ui.TextInput(
            label="AniList Manga ID",
            placeholder="Enter the AniList manga ID number",
            required=True,
            max_length=10
        )
        self.add_item(self.manga_id)
        
        self.total_chapters = discord.ui.TextInput(
            label="Total Chapters (Optional)",
            placeholder="Override chapter count (leave blank to use AniList data)",
            required=False,
            max_length=10
        )
        self.add_item(self.total_chapters)
        
        logger.debug("Created AddMangaModal")

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission for adding manga."""
        logger.info(f"Add manga modal submitted by {interaction.user.display_name} (ID: {interaction.user.id})")
        logger.debug(f"Parameters: title='{self.challenge_title.value}', manga_id='{self.manga_id.value}', chapters='{self.total_chapters.value}'")
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate manga ID
            try:
                manga_id_int = int(self.manga_id.value.strip())
                if manga_id_int <= 0 or manga_id_int > MAX_MANGA_ID:
                    await interaction.followup.send("❌ Invalid manga ID. Must be a positive number.", ephemeral=True)
                    return
            except ValueError:
                await interaction.followup.send("❌ Invalid manga ID. Must be a number.", ephemeral=True)
                return
            
            # Validate chapters if provided
            chapters_override = None
            if self.total_chapters.value.strip():
                try:
                    chapters_override = int(self.total_chapters.value.strip())
                    if chapters_override <= 0:
                        await interaction.followup.send("❌ Total chapters must be a positive number.", ephemeral=True)
                        return
                except ValueError:
                    await interaction.followup.send("❌ Invalid chapter count. Must be a number.", ephemeral=True)
                    return
            
            # Process the request
            challenge_cog = interaction.client.get_cog("ChallengeChange")
            if challenge_cog:
                result = await challenge_cog.handle_add_manga(
                    self.challenge_title.value.strip(),
                    manga_id_int,
                    chapters_override
                )
                await interaction.followup.send(result, ephemeral=True)
            else:
                await interaction.followup.send("❌ System error: Challenge management not available.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in add manga modal: {e}", exc_info=True)
            await interaction.followup.send("❌ An error occurred while adding manga.", ephemeral=True)


class RemoveMangaModal(discord.ui.Modal):
    """Modal for removing manga from challenges."""
    
    def __init__(self):
        super().__init__(title="🗑️ Remove Manga from Challenge")
        
        self.manga_id = discord.ui.TextInput(
            label="AniList Manga ID",
            placeholder="Enter the AniList manga ID to remove",
            required=True,
            max_length=10
        )
        self.add_item(self.manga_id)
        
        logger.debug("Created RemoveMangaModal")

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission for removing manga."""
        logger.info(f"Remove manga modal submitted by {interaction.user.display_name} (ID: {interaction.user.id})")
        logger.debug(f"Parameters: manga_id='{self.manga_id.value}'")
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate manga ID
            try:
                manga_id_int = int(self.manga_id.value.strip())
                if manga_id_int <= 0 or manga_id_int > MAX_MANGA_ID:
                    await interaction.followup.send("❌ Invalid manga ID. Must be a positive number.", ephemeral=True)
                    return
            except ValueError:
                await interaction.followup.send("❌ Invalid manga ID. Must be a number.", ephemeral=True)
                return
            
            # Process the request
            challenge_cog = interaction.client.get_cog("ChallengeChange")
            if challenge_cog:
                result = await challenge_cog.handle_remove_manga(manga_id_int)
                await interaction.followup.send(result, ephemeral=True)
            else:
                await interaction.followup.send("❌ System error: Challenge management not available.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in remove manga modal: {e}", exc_info=True)
            await interaction.followup.send("❌ An error occurred while removing manga.", ephemeral=True)


class SearchMangaModal(discord.ui.Modal):
    """Modal for searching manga information."""
    
    def __init__(self):
        super().__init__(title="🔍 Search Manga Information")
        
        self.manga_id = discord.ui.TextInput(
            label="AniList Manga ID",
            placeholder="Enter the AniList manga ID to search for",
            required=True,
            max_length=10
        )
        self.add_item(self.manga_id)
        
        logger.debug("Created SearchMangaModal")

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission for searching manga."""
        logger.info(f"Search manga modal submitted by {interaction.user.display_name} (ID: {interaction.user.id})")
        logger.debug(f"Parameters: manga_id='{self.manga_id.value}'")
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Validate manga ID
            try:
                manga_id_int = int(self.manga_id.value.strip())
                if manga_id_int <= 0 or manga_id_int > MAX_MANGA_ID:
                    await interaction.followup.send("❌ Invalid manga ID. Must be a positive number.", ephemeral=True)
                    return
            except ValueError:
                await interaction.followup.send("❌ Invalid manga ID. Must be a number.", ephemeral=True)
                return
            
            # Process the request
            challenge_cog = interaction.client.get_cog("ChallengeChange")
            if challenge_cog:
                result = await challenge_cog.handle_search_manga(manga_id_int)
                await interaction.followup.send(embed=result, ephemeral=True)
            else:
                await interaction.followup.send("❌ System error: Challenge management not available.", ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in search manga modal: {e}", exc_info=True)
            await interaction.followup.send("❌ An error occurred while searching for manga.", ephemeral=True)

class ChallengeManage(commands.Cog):
    """Discord cog for interactive challenge management."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Challenge Management cog initialized")

    async def get_all_challenges(self) -> List[Tuple[int, str, int]]:
        """Get all challenges with manga counts. Returns list of (challenge_id, title, manga_count)."""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    """
                    SELECT gc.challenge_id, gc.title, COUNT(cm.manga_id) as manga_count
                    FROM global_challenges gc
                    LEFT JOIN challenge_manga cm ON gc.challenge_id = cm.challenge_id
                    GROUP BY gc.challenge_id, gc.title
                    ORDER BY gc.title
                    """
                )
                results = await cursor.fetchall()
                await cursor.close()
                
                logger.debug(f"Retrieved {len(results)} challenges from database")
                return results
                
        except Exception as e:
            logger.error(f"Error retrieving challenges: {e}", exc_info=True)
            return []

    async def handle_add_manga(self, title: str, manga_id: int, total_chapters: Optional[int] = None) -> str:
        """Handle adding manga to challenge with validation and logging."""
        logger.info(f"Processing add manga request: title='{title}', manga_id={manga_id}, chapters={total_chapters}")
        
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Check if manga already exists
                existing_info = await self._check_manga_exists(db, manga_id)
                if existing_info:
                    existing_challenge_id, existing_manga_title = existing_info
                    existing_challenge_title = await self._get_challenge_info(db, existing_challenge_id)
                    return (f"⚠️ Manga **{existing_manga_title}** (ID: `{manga_id}`) already exists in challenge "
                           f"**{existing_challenge_title or 'Unknown'}** (ID: {existing_challenge_id}).")

                # Get or create challenge
                challenge_id = await self._get_or_create_challenge(db, title)

                # Get manga information
                if total_chapters is not None:
                    manga_title = f"Manga {manga_id}"
                    logger.debug(f"Using provided chapter count: {total_chapters}")
                else:
                    anilist_info = await self._fetch_anilist_manga_info(manga_id)
                    if not anilist_info:
                        return (f"⚠️ Manga ID `{manga_id}` not found on AniList or API error occurred. "
                               f"Please try again or specify total chapters manually.")
                    
                    manga_title, total_chapters = anilist_info

                # Add manga to challenge
                await self._add_manga_to_challenge(db, challenge_id, manga_id, manga_title, total_chapters)

                logger.info(f"Successfully added manga '{manga_title}' (ID: {manga_id}) to challenge '{title}' (ID: {challenge_id})")
                return f"✅ Manga **{manga_title}** ({total_chapters} chapters) added to challenge **{title}**!"
                
        except Exception as e:
            logger.error(f"Error in handle_add_manga: {e}", exc_info=True)
            return "❌ An error occurred while adding manga to the challenge. Please try again later."

    async def handle_remove_manga(self, manga_id: int) -> str:
        """Handle removing manga from challenge with validation and logging."""
        logger.info(f"Processing remove manga request: manga_id={manga_id}")
        
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # Check if manga exists
                existing_info = await self._check_manga_exists(db, manga_id)
                if not existing_info:
                    return f"⚠️ Manga ID `{manga_id}` is not currently in any challenge."

                existing_challenge_id, existing_manga_title = existing_info
                existing_challenge_title = await self._get_challenge_info(db, existing_challenge_id)

                # Remove manga from challenge
                removal_success = await self._remove_manga_from_challenge(db, manga_id)
                
                if removal_success:
                    logger.info(f"Successfully removed manga '{existing_manga_title}' (ID: {manga_id}) from challenge '{existing_challenge_title}' (ID: {existing_challenge_id})")
                    return (f"✅ Manga **{existing_manga_title}** (ID: `{manga_id}`) "
                           f"removed from challenge **{existing_challenge_title or 'Unknown'}**!")
                else:
                    return f"⚠️ Failed to remove manga ID `{manga_id}` from challenge. It may have been removed already."
                    
        except Exception as e:
            logger.error(f"Error in handle_remove_manga: {e}", exc_info=True)
            return "❌ An error occurred while removing manga from the challenge. Please try again later."

    async def handle_search_manga(self, manga_id: int) -> discord.Embed:
        """Handle searching for manga information and return an embed."""
        logger.info(f"Processing search manga request: manga_id={manga_id}")
        
        try:
            # Get AniList information
            anilist_info = await self._fetch_anilist_manga_info(manga_id)
            
            async with aiosqlite.connect(DB_PATH) as db:
                # Check if manga is in any challenge
                challenge_info = await self._check_manga_exists(db, manga_id)
                
                if not anilist_info:
                    embed = discord.Embed(
                        title="🔍 Manga Search Results",
                        description=f"❌ Manga ID `{manga_id}` not found on AniList.",
                        color=discord.Color.red()
                    )
                    return embed
                
                manga_title, total_chapters = anilist_info
                
                embed = discord.Embed(
                    title="🔍 Manga Information",
                    description=f"**{manga_title}**",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="📊 Details",
                    value=f"**ID:** `{manga_id}`\n**Chapters:** {total_chapters or 'Unknown'}",
                    inline=True
                )
                
                if challenge_info:
                    challenge_id, _ = challenge_info
                    challenge_title = await self._get_challenge_info(db, challenge_id)
                    embed.add_field(
                        name="🎯 Challenge Status",
                        value=f"✅ In challenge: **{challenge_title or 'Unknown'}**\n(ID: {challenge_id})",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="🎯 Challenge Status",
                        value="❌ Not in any challenge",
                        inline=True
                    )
                
                embed.set_footer(text=f"AniList ID: {manga_id}")
                
                logger.info(f"Successfully retrieved information for manga '{manga_title}' (ID: {manga_id})")
                return embed
                
        except Exception as e:
            logger.error(f"Error in handle_search_manga: {e}", exc_info=True)
            embed = discord.Embed(
                title="🔍 Manga Search Results",
                description="❌ An error occurred while searching for manga information.",
                color=discord.Color.red()
            )
            return embed

    async def _check_manga_exists(self, db: aiosqlite.Connection, manga_id: int) -> tuple[int, str] | None:
        """Check if manga already exists in any challenge. Returns (challenge_id, manga_title) if exists."""
        try:
            logger.debug(f"Checking if manga ID {manga_id} exists in any challenge")
            cursor = await db.execute(
                "SELECT challenge_id, title FROM challenge_manga WHERE manga_id = ?", (manga_id,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            
            if row:
                logger.debug(f"Manga ID {manga_id} found in challenge ID {row[0]}: '{row[1]}'")
                return (row[0], row[1])
            else:
                logger.debug(f"Manga ID {manga_id} not found in any challenge")
                return None
                
        except Exception as e:
            logger.error(f"Database error checking manga existence: {e}", exc_info=True)
            raise

    async def _get_or_create_challenge(self, db: aiosqlite.Connection, title: str) -> int:
        """Get existing challenge or create new one. Returns challenge_id."""
        try:
            logger.debug(f"Checking if challenge '{title}' exists")
            cursor = await db.execute(
                "SELECT challenge_id FROM global_challenges WHERE title = ?", (title,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            
            if row:
                challenge_id = row[0]
                logger.info(f"Challenge '{title}' exists (ID: {challenge_id})")
                return challenge_id
            else:
                logger.debug(f"Creating new challenge '{title}'")
                cursor = await db.execute(
                    "INSERT INTO global_challenges (title) VALUES (?)", (title,)
                )
                challenge_id = cursor.lastrowid
                await cursor.close()
                logger.info(f"Created new challenge '{title}' (ID: {challenge_id})")
                return challenge_id
                
        except Exception as e:
            logger.error(f"Database error managing challenge: {e}", exc_info=True)
            raise

    async def _get_challenge_info(self, db: aiosqlite.Connection, challenge_id: int) -> str | None:
        """Get challenge title by ID. Returns title or None if not found."""
        try:
            logger.debug(f"Getting challenge info for ID {challenge_id}")
            cursor = await db.execute(
                "SELECT title FROM global_challenges WHERE challenge_id = ?", (challenge_id,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            
            if row:
                logger.debug(f"Challenge ID {challenge_id} found: '{row[0]}'")
                return row[0]
            else:
                logger.warning(f"Challenge ID {challenge_id} not found")
                return None
                
        except Exception as e:
            logger.error(f"Database error getting challenge info: {e}", exc_info=True)
            raise

    async def _fetch_anilist_manga_info(self, manga_id: int) -> tuple[str, int] | None:
        """Fetch manga information from AniList API. Returns (title, chapters) or None."""
        query = """
        query ($id: Int) {
          Media(id: $id, type: MANGA) {
            id
            title {
              romaji
              english
            }
            chapters
          }
        }
        """
        
        try:
            logger.debug(f"Fetching manga info from AniList for ID {manga_id}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    ANILIST_API_URL,
                    json={"query": query, "variables": {"id": manga_id}},
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"AniList API returned status {resp.status} for manga {manga_id}")
                        return None
                        
                    data = await resp.json()
                    
            media = data.get("data", {}).get("Media")
            if not media:
                logger.warning(f"Manga ID {manga_id} not found on AniList")
                return None
                
            manga_title = media["title"].get("romaji") or media["title"].get("english") or "Unknown Title"
            total_chapters = media.get("chapters") or 0
            
            logger.info(f"Successfully fetched AniList data for '{manga_title}' ({total_chapters} chapters)")
            return (manga_title, total_chapters)
            
        except aiohttp.ClientError as e:
            logger.error(f"Network error fetching AniList data for manga {manga_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching AniList data: {e}", exc_info=True)
            return None

    async def _add_manga_to_challenge(
        self, db: aiosqlite.Connection, challenge_id: int, manga_id: int, 
        manga_title: str, total_chapters: int
    ):
        """Add manga to challenge in database."""
        try:
            logger.debug(f"Adding manga '{manga_title}' (ID: {manga_id}) to challenge {challenge_id}")
            
            await db.execute(
                """
                INSERT INTO challenge_manga (challenge_id, manga_id, title, total_chapters)
                VALUES (?, ?, ?, ?)
                """,
                (challenge_id, manga_id, manga_title, total_chapters)
            )
            await db.commit()
            
            logger.info(f"Successfully added manga '{manga_title}' (ID: {manga_id}) to challenge {challenge_id}")
            
        except Exception as e:
            logger.error(f"Database error adding manga to challenge: {e}", exc_info=True)
            raise

    async def _remove_manga_from_challenge(self, db: aiosqlite.Connection, manga_id: int) -> bool:
        """Remove manga from challenge in database. Returns True if removed, False if not found."""
        try:
            logger.debug(f"Removing manga ID {manga_id} from challenge")
            
            cursor = await db.execute(
                "DELETE FROM challenge_manga WHERE manga_id = ?", (manga_id,)
            )
            rows_affected = cursor.rowcount
            await cursor.close()
            await db.commit()
            
            if rows_affected > 0:
                logger.info(f"Successfully removed manga ID {manga_id} from challenge")
                return True
            else:
                logger.warning(f"Manga ID {manga_id} not found in any challenge for removal")
                return False
                
        except Exception as e:
            logger.error(f"Database error removing manga from challenge: {e}", exc_info=True)
            raise

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="challenge-manage",
        description="🎯 Interactive challenge management - add, remove, and manage manga in challenges"
    )
    async def challenge_manage(self, interaction: discord.Interaction):
        """Interactive challenge management interface."""
        try:
            logger.info(f"Challenge-manage command invoked by {interaction.user.display_name} "
                       f"({interaction.user.id}) in {interaction.guild.name}")
            
            embed = discord.Embed(
                title="🎯 Challenge Management",
                description=f"Welcome **{interaction.user.display_name}**!\n\n"
                           f"Use the buttons below to manage global challenges:\n\n"
                           f"➕ **Add Manga** - Add manga to a challenge\n"
                           f"🗑️ **Remove Manga** - Remove manga from challenges\n"
                           f"📋 **List Challenges** - View all active challenges\n"
                           f"🔍 **Search Manga** - Get information about specific manga",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📝 Notes",
                value="• Challenges are created automatically when adding manga\n"
                      "• AniList manga information is fetched automatically\n"
                      "• All operations are logged for tracking",
                inline=False
            )
            
            embed.set_footer(text="Admin-only • Buttons expire after 2 minutes of inactivity")
            
            # Create interactive view
            view = ChallengeManagementView(interaction.user.id)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            logger.info(f"Challenge management interface sent to {interaction.user.display_name}")
            
        except Exception as e:
            logger.error(f"Unexpected error in challenge_manage command for {interaction.user.display_name} "
                        f"(ID: {interaction.user.id}): {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ An unexpected error occurred. Please try again later.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ An unexpected error occurred. Please try again later.",
                        ephemeral=True
                    )
            except Exception as follow_e:
                logger.error(f"Failed to send error message: {follow_e}", exc_info=True)


async def setup(bot: commands.Bot):
    """Set up the ChallengeManage cog."""
    try:
        await bot.add_cog(ChallengeManage(bot))
        logger.info("Challenge Management cog successfully loaded")
    except Exception as e:
        logger.error(f"Failed to load Challenge Management cog: {e}", exc_info=True)
        raise