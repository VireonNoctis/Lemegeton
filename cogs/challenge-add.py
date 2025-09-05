import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import aiohttp
import logging
from config import GUILD_ID
from database import DB_PATH  # Ensure DB_PATH is exported from your database.py

logger = logging.getLogger("ChallengeAdd")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

class ChallengeAdd(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
        await interaction.response.defer(ephemeral=True)

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                # 1️⃣ Ensure manga ID is unique across all challenges
                cursor = await db.execute(
                    "SELECT challenge_id FROM challenge_manga WHERE manga_id = ?", (manga_id,)
                )
                row = await cursor.fetchone()
                await cursor.close()
                if row:
                    await interaction.followup.send(
                        f"⚠️ Manga ID `{manga_id}` already exists in a challenge (ID: {row[0]}).",
                        ephemeral=True
                    )
                    logger.warning(f"Manga ID {manga_id} already exists in challenge ID {row[0]}")
                    return

                # 2️⃣ Check if challenge exists
                cursor = await db.execute(
                    "SELECT challenge_id FROM global_challenges WHERE title = ?", (title,)
                )
                row = await cursor.fetchone()
                await cursor.close()
                if row:
                    challenge_id = row[0]
                    logger.info(f"Challenge '{title}' exists (ID: {challenge_id})")
                else:
                    cursor = await db.execute(
                        "INSERT INTO global_challenges (title) VALUES (?)", (title,)
                    )
                    challenge_id = cursor.lastrowid
                    logger.info(f"Created new challenge '{title}' (ID: {challenge_id})")

                # 3️⃣ Fetch manga info from AniList if total_chapters not provided
                if not total_chapters:
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
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            "https://graphql.anilist.co",
                            json={"query": query, "variables": {"id": manga_id}}
                        ) as resp:
                            data = await resp.json()
                    media = data.get("data", {}).get("Media")
                    if not media:
                        await interaction.followup.send(
                            f"⚠️ Manga ID `{manga_id}` not found on AniList.", ephemeral=True
                        )
                        logger.warning(f"Manga ID {manga_id} not found on AniList")
                        return
                    manga_title = media["title"].get("romaji") or media["title"].get("english") or "Unknown Title"
                    total_chapters = media.get("chapters") or 0
                else:
                    manga_title = f"Manga {manga_id}"

                # 4️⃣ Insert into challenge_manga table
                await db.execute(
                    """
                    INSERT INTO challenge_manga (challenge_id, manga_id, title, total_chapters)
                    VALUES (?, ?, ?, ?)
                    """,
                    (challenge_id, manga_id, manga_title, total_chapters)
                )
                await db.commit()
                await interaction.followup.send(
                    f"✅ Manga **{manga_title}** added to challenge **{title}**!", ephemeral=True
                )
                logger.info(f"Added manga '{manga_title}' (ID: {manga_id}) to challenge '{title}'")

        except Exception as e:
            await interaction.followup.send(
                f"⚠️ An error occurred while adding manga to the challenge.", ephemeral=True
            )
            logger.error(f"Error adding manga to challenge: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ChallengeAdd(bot))
