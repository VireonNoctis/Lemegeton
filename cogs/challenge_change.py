import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import aiohttp
import logging
import os
from pathlib import Path
from config import GUILD_ID
from database import DB_PATH

# Configuration constants
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "challenge_change.log"
ANILIST_API_URL = "https://graphql.anilist.co"

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

class ChallengeChange(commands.Cog):
    """Discord cog for adding and removing manga from global challenges."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Challenge Change cog initialized")

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
        name="challenge-add",
        description="➕ Add a manga to a global challenge (creates the challenge if it doesn't exist)"
    )
    @app_commands.describe(
        title="Challenge title",
        manga_id="AniList Manga ID",
        total_chapters="Optional: total chapters (overrides AniList data)"
    )
    async def challenge_add(
        self,
        interaction: discord.Interaction,
        title: str,
        manga_id: int,
        total_chapters: int = None
    ):
        """Add a manga to a global challenge with comprehensive error handling."""
        try:
            logger.info(f"Challenge-add command invoked by {interaction.user.display_name} "
                       f"({interaction.user.id}) in {interaction.guild.name}")
            logger.debug(f"Parameters: title='{title}', manga_id={manga_id}, total_chapters={total_chapters}")
            
            await interaction.response.defer(ephemeral=True)

            async with aiosqlite.connect(DB_PATH) as db:
                # Check if manga already exists in any challenge
                existing_info = await self._check_manga_exists(db, manga_id)
                if existing_info:
                    existing_challenge_id, existing_manga_title = existing_info
                    existing_challenge_title = await self._get_challenge_info(db, existing_challenge_id)
                    await interaction.followup.send(
                        f"⚠️ Manga **{existing_manga_title}** (ID: `{manga_id}`) already exists in challenge "
                        f"**{existing_challenge_title or 'Unknown'}** (ID: {existing_challenge_id}).",
                        ephemeral=True
                    )
                    return

                # Get or create challenge
                challenge_id = await self._get_or_create_challenge(db, title)

                # Get manga information
                if total_chapters is not None:
                    manga_title = f"Manga {manga_id}"
                    logger.debug(f"Using provided chapter count: {total_chapters}")
                else:
                    anilist_info = await self._fetch_anilist_manga_info(manga_id)
                    if not anilist_info:
                        await interaction.followup.send(
                            f"⚠️ Manga ID `{manga_id}` not found on AniList or API error occurred. "
                            f"Please try again or specify total_chapters manually.",
                            ephemeral=True
                        )
                        return
                    
                    manga_title, total_chapters = anilist_info

                # Add manga to challenge
                await self._add_manga_to_challenge(db, challenge_id, manga_id, manga_title, total_chapters)

                # Success response
                await interaction.followup.send(
                    f"✅ Manga **{manga_title}** ({total_chapters} chapters) "
                    f"added to challenge **{title}**!",
                    ephemeral=True
                )
                
                logger.info(f"Successfully completed challenge-add: '{manga_title}' "
                           f"(ID: {manga_id}) added to '{title}' (ID: {challenge_id})")

        except Exception as e:
            logger.error(f"Unexpected error in challenge_add command: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
                await interaction.followup.send(
                    "⚠️ An unexpected error occurred while adding manga to the challenge. "
                    "Please try again later or contact support.",
                    ephemeral=True
                )
            except Exception as follow_e:
                logger.error(f"Failed to send error response: {follow_e}", exc_info=True)

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="challenge-remove",
        description="🗑️ Remove a manga from a global challenge"
    )
    @app_commands.describe(
        manga_id="AniList Manga ID to remove from challenge"
    )
    async def challenge_remove(
        self,
        interaction: discord.Interaction,
        manga_id: int
    ):
        """Remove a manga from a global challenge with comprehensive error handling."""
        try:
            logger.info(f"Challenge-remove command invoked by {interaction.user.display_name} "
                       f"({interaction.user.id}) in {interaction.guild.name}")
            logger.debug(f"Parameters: manga_id={manga_id}")
            
            await interaction.response.defer(ephemeral=True)

            async with aiosqlite.connect(DB_PATH) as db:
                # Check if manga exists in any challenge
                existing_info = await self._check_manga_exists(db, manga_id)
                if not existing_info:
                    await interaction.followup.send(
                        f"⚠️ Manga ID `{manga_id}` is not currently in any challenge.",
                        ephemeral=True
                    )
                    return

                existing_challenge_id, existing_manga_title = existing_info
                existing_challenge_title = await self._get_challenge_info(db, existing_challenge_id)

                # Remove manga from challenge
                removal_success = await self._remove_manga_from_challenge(db, manga_id)
                
                if removal_success:
                    # Success response
                    await interaction.followup.send(
                        f"✅ Manga **{existing_manga_title}** (ID: `{manga_id}`) "
                        f"removed from challenge **{existing_challenge_title or 'Unknown'}**!",
                        ephemeral=True
                    )
                    
                    logger.info(f"Successfully completed challenge-remove: '{existing_manga_title}' "
                               f"(ID: {manga_id}) removed from '{existing_challenge_title}' (ID: {existing_challenge_id})")
                else:
                    await interaction.followup.send(
                        f"⚠️ Failed to remove manga ID `{manga_id}` from challenge. "
                        f"It may have been removed already.",
                        ephemeral=True
                    )

        except Exception as e:
            logger.error(f"Unexpected error in challenge_remove command: {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
                await interaction.followup.send(
                    "⚠️ An unexpected error occurred while removing manga from the challenge. "
                    "Please try again later or contact support.",
                    ephemeral=True
                )
            except Exception as follow_e:
                logger.error(f"Failed to send error response: {follow_e}", exc_info=True)


async def setup(bot: commands.Bot):
    """Set up the ChallengeChange cog."""
    try:
        await bot.add_cog(ChallengeChange(bot))
        logger.info("Challenge Change cog successfully loaded")
    except Exception as e:
        logger.error(f"Failed to load Challenge Change cog: {e}", exc_info=True)
        raise