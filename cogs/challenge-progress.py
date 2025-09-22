import asyncio
from typing import Optional
import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from config import CHALLENGE_ROLE_IDS, GUILD_ID
from database import DB_PATH, set_user_manga_progress, get_challenge_rules, upsert_user_manga_progress
import aiohttp
import os
import logging
from datetime import datetime
from helpers.challenge_helper import assign_challenge_role, get_manga_difficulty, get_challenge_difficulty, calculate_manga_points, calculate_challenge_completion_bonus


logger = logging.getLogger("ChallengeProgress")
file_handler = logging.FileHandler("logs/challenge_update.log")
file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(file_handler)
logger.setLevel(logging.INFO)
user_progress_cache = {}  # {(user_id, manga_id): (chapters_read, status)}

# AniList API
ANILIST_API = "https://graphql.anilist.co"

async def fetch_anilist_progress(anilist_id: int, manga_id: int):
    """Fetch AniList progress for a specific manga - same logic as challenge_update.py"""
    query = """
    query ($userId: Int, $mediaId: Int) {
      MediaList(userId: $userId, mediaId: $mediaId) {
        progress
        status
        repeat
        startedAt { year month day }
      }
    }
    """
    variables = {"userId": anilist_id, "mediaId": manga_id}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ANILIST_API, json={"query": query, "variables": variables}) as resp:
                if resp.status != 200:
                    logger.error(f"AniList API returned status {resp.status} for user {anilist_id}, manga {manga_id}")
                    return {"progress": 0, "status": "CURRENT", "repeat": 0, "started_at": None}

                data = await resp.json()
                media_list = data.get("data", {}).get("MediaList")
                if not media_list:
                    logger.warning(f"No media list entry for user {anilist_id}, manga {manga_id}")
                    return {"progress": 0, "status": "CURRENT", "repeat": 0, "started_at": None}

                progress = media_list.get("progress", 0)
                status = media_list.get("status", "CURRENT")
                repeat = media_list.get("repeat", 0)
                started = media_list.get("startedAt")
                started_at = None
                if started and started.get("year"):
                    started_at = f"{started['year']:04}-{started.get('month',1):02}-{started.get('day',1):02}"

                return {"progress": progress, "status": status, "repeat": repeat, "started_at": started_at}

    except Exception as e:
        logger.error(f"AniList fetch failed for user {anilist_id}, manga {manga_id}: {e}")
        return {"progress": 0, "status": "CURRENT", "repeat": 0, "started_at": None}

# -----------------------------------------
# Fetch AniList info for a Discord user
# -----------------------------------------
async def get_anilist_info(discord_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT anilist_id, anilist_username FROM users WHERE discord_id = ?", (discord_id,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return None
        anilist_id, anilist_username = row
        if not anilist_id and not anilist_username:
            return None
        return {"id": anilist_id, "username": anilist_username}

async def fetch_user_manga_progress(anilist_username: str, manga_id: int, db=None):
    query = """
    query ($username: String, $mediaId: Int) {
        MediaList(userName: $username, mediaId: $mediaId, type: MANGA) {
            progress
            status
            repeat
            startedAt {
                year
                month
                day
            }
            media {
                format
            }
        }
    }
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://graphql.anilist.co",
                json={"query": query, "variables": {"username": anilist_username, "mediaId": manga_id}},
                timeout=10
            ) as resp:

                if resp.status != 200:
                    logger.warning(f"AniList API returned {resp.status} for {anilist_username} / {manga_id}")
                    return None, "Fetch Failed", 0, {}, None

                data = await resp.json()
                media_list = data.get("data", {}).get("MediaList")

                if media_list is None:
                    # User hasn't added this manga
                    return 0, "Not in List", 0, {}, None

                progress = media_list.get("progress", 0)
                status = media_list.get("status", "Not Started")
                repeat = media_list.get("repeat", 0)
                started_at = media_list.get("startedAt") or {}

                media_data = media_list.get("media", {})
                medium_type = media_data.get("format", "MANGA")
                if medium_type == "MANHWA":
                    medium_type = "Manhwa"
                elif medium_type == "MANHUA":
                    medium_type = "Manhua"
                else:
                    medium_type = "Manga"

                # ✅ Pull title from local DB instead of AniList
                title_to_use = None
                if db:
                    cursor = await db.execute(
                        "SELECT title FROM challenge_manga WHERE manga_id = ?",
                        (manga_id,)
                    )
                    row = await cursor.fetchone()
                    await cursor.close()
                    if row:
                        title_to_use = row[0]

                return progress, status, repeat, started_at, title_to_use

    except Exception as e:
        logger.error(f"Failed to fetch AniList progress for {anilist_username} / {manga_id}: {e}")
        return None, "Fetch Failed", 0, {}, None


# -----------------------------------------
# Manga Challenges Cog
# -----------------------------------------
class MangaChallenges(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="challenge-progress",
        description="📚 View your progress in all global manga challenges (optionally for another user)"
    )
    @app_commands.describe(member="Discord member to view progress for (optional)")
    async def manga_challenges(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        await interaction.response.defer(ephemeral=True)

        # Allow viewing another user's progress by passing a member; defaults to the invoking user
        target = member or interaction.user
        target_id = target.id

        anilist_info = await get_anilist_info(target_id)
        if not anilist_info:
            if member:
                await interaction.followup.send(
                    f"⚠️ {target.mention} has not linked their AniList account.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "⚠️ You have not linked your AniList account. Use `/link_anilist` first.",
                    ephemeral=True
                )
            return

        anilist_username = anilist_info.get("username")
        anilist_id = anilist_info.get("id")

        # Fetch challenges
        async with aiosqlite.connect(DB_PATH) as db:
            challenges = await db.execute_fetchall(
                "SELECT challenge_id, title FROM global_challenges"
            )
        if not challenges:
            await interaction.followup.send("⚠️ No global challenges found.", ephemeral=True)
            return

        # Sort challenges alphabetically by title
        challenges.sort(key=lambda x: x[1].lower())

        embeds = []
        options = []
        embed_page_map = {}  # {embed_index: (challenge_id, start_idx, end_idx)}
        all_manga_data = {}  # {challenge_id: [(manga_id, title, total_chapters, medium_type), ...]}

        async with aiosqlite.connect(DB_PATH) as db:
            for challenge_id, title in challenges:

                manga_rows = await db.execute_fetchall(
                    "SELECT manga_id, title, total_chapters, medium_type FROM challenge_manga WHERE challenge_id = ?",
                    (challenge_id,)
                )
                manga_rows.sort(key=lambda x: x[1].lower())
                
                # Store manga data for updates
                all_manga_data[challenge_id] = manga_rows

                chunk_size = 10
                chunk_index = 0
                for i in range(0, len(manga_rows), chunk_size):
                    description_lines = []
                    for manga_id, manga_title, total_chapters, medium_type in manga_rows[i:i + chunk_size]:
                        cache_key = (target_id, manga_id)
                        if cache_key in user_progress_cache:
                            cache = user_progress_cache.get(cache_key)
                            if cache:
                                manga_title = cache["title"]
                                chapters_read = cache["chapters_read"]
                                status = cache["status"]
                        else:
                            cursor = await db.execute(
                                "SELECT current_chapter, rating, status FROM user_manga_progress WHERE discord_id = ? AND manga_id = ?",
                                (target_id, manga_id)
                            )
                            result = await cursor.fetchone()
                            await cursor.close()

                            if result:
                                chapters_read = result[0]
                                status = result[2] if result[2] else ("Not Started" if chapters_read == 0 else "In Progress")
                            else:
                                chapters_read = 0
                                status = "Not Started"

                            user_progress_cache[cache_key] = {
                                "title": manga_title,
                                "chapters_read": chapters_read,
                                "status": status,
                                "medium_type": medium_type 
                            }

                        description_lines.append(
                            f"[{manga_title}](https://anilist.co/manga/{manga_id}) - `{chapters_read}/{total_chapters}` • Status: `{status}`"
                        )

                    description = "\n\n".join(description_lines) if description_lines else "_No manga added to this challenge yet._"
                    embed = discord.Embed(
                        title=f"📖 Challenge: {title}",
                        description=description,
                        color=discord.Color.random()
                    )
                    # Indicate whose progress is being shown
                    embed.set_author(name=f"Progress for {target.display_name} ({anilist_username})")
                    embeds.append(embed)
                    embed_index = len(embeds) - 1
                    embed_page_map[embed_index] = (challenge_id, i, i + chunk_size)
                    options.append(discord.SelectOption(label=f"{title} - Page {chunk_index + 1}", value=str(embed_index)))
                    chunk_index += 1

        # -----------------------------------------
        # Challenge View with pagination and update button
        # -----------------------------------------
        class ChallengeView(discord.ui.View):
            def __init__(self, bot, embeds, options, page_to_challenge_id, target_id, anilist_username, anilist_id, all_manga_data):
                super().__init__(timeout=None)
                self.bot = bot
                self.embeds = embeds
                self.options = options
                self.page_to_challenge_id = page_to_challenge_id
                self.target_id = target_id
                self.anilist_username = anilist_username
                self.anilist_id = anilist_id
                self.all_manga_data = all_manga_data  # {challenge_id: [(manga_id, title, total_chapters, medium_type), ...]}
                self.current_page = 0
                self.message: Optional[discord.Message] = None

                # Dropdown
                self.select = discord.ui.Select(
                    placeholder="Select Challenge",
                    options=self.options
                )
                self.select.callback = self.select_callback
                self.add_item(self.select)

            def determine_status(self, ani_progress, ani_status, ani_repeat, total_chapters, ani_started_at, challenge_start_date):
                """Same status logic as challenge_update.py"""
                def _to_date(val):
                    if not val:
                        return None
                    try:
                        from datetime import datetime
                        if isinstance(val, str) and len(val) >= 10:
                            return datetime.strptime(val[:10], "%Y-%m-%d").date()
                    except Exception:
                        pass
                    return None

                # baseline total
                effective_total = total_chapters if (isinstance(total_chapters, (int, float)) and total_chapters > 0) else 1

                # normalize numeric / text inputs
                try:
                    ani_progress_num = max(0, int(ani_progress or 0))
                except Exception:
                    ani_progress_num = 0
                try:
                    ani_repeat_num = max(0, int(ani_repeat or 0))
                except Exception:
                    ani_repeat_num = 0

                status_upper = (ani_status or "").upper()

                # parse dates for skipped-check
                started_at_val = _to_date(ani_started_at)
                challenge_start_date_val = _to_date(challenge_start_date)

                pct_progress = (ani_progress_num / effective_total) if effective_total else 0.0

                # Priority order (same as challenge_update.py):
                # 1) Skipped: started before challenge and already had meaningful progress
                if challenge_start_date_val and started_at_val and started_at_val < challenge_start_date_val and pct_progress >= 0.25:
                    return "Skipped"
                # 2) Reread: completed/current + repeat >= 1 + progress >= total
                elif status_upper in ("COMPLETED", "CURRENT") and ani_repeat_num >= 1 and ani_progress_num >= effective_total:
                    return "Reread"
                # 3) Caught Up: current + progress >= total
                elif status_upper == "CURRENT" and ani_progress_num >= effective_total:
                    return "Caught Up"
                # 4) Completed: completed status + progress >= total
                elif status_upper == "COMPLETED" and ani_progress_num >= effective_total:
                    return "Completed"
                # 5) In Progress: current status + 0 < progress < total
                elif status_upper == "CURRENT" and 0 < ani_progress_num < effective_total:
                    return "In Progress"
                # 6) Paused
                elif status_upper == "PAUSED":
                    return "Paused"
                # 7) Dropped
                elif status_upper == "DROPPED":
                    return "Dropped"
                # 8) Fallback
                else:
                    return "Not Started"

            async def update_current_page(self, interaction: discord.Interaction):
                """Update only the manga on the current page"""
                await interaction.response.defer()

                if self.current_page not in self.page_to_challenge_id:
                    await interaction.followup.send("❌ Unable to determine current page data.", ephemeral=True)
                    return

                challenge_id, start_idx, end_idx = self.page_to_challenge_id[self.current_page]
                
                # Get challenge info
                async with aiosqlite.connect(DB_PATH) as db:
                    cursor = await db.execute("SELECT start_date FROM global_challenges WHERE challenge_id = ?", (challenge_id,))
                    challenge_row = await cursor.fetchone()
                    await cursor.close()
                    challenge_start_date = challenge_row[0] if challenge_row else None

                    # Get manga for this page
                    manga_data = self.all_manga_data.get(challenge_id, [])
                    page_manga = manga_data[start_idx:end_idx]

                    updated_count = 0
                    description_lines = []

                    for manga_id, manga_title, total_chapters, medium_type in page_manga:
                        # Fetch from AniList
                        ani_data = await fetch_anilist_progress(self.anilist_id, manga_id)
                        await asyncio.sleep(1)  # Rate limiting

                        ani_progress = ani_data['progress']
                        ani_status = ani_data['status']
                        ani_repeat = ani_data['repeat']
                        ani_started_at = ani_data['started_at']

                        # Determine status using same logic as challenge_update
                        status = self.determine_status(
                            ani_progress, ani_status, ani_repeat, 
                            total_chapters, ani_started_at, challenge_start_date
                        )

                        # Calculate points
                        difficulty = await get_manga_difficulty(total_chapters, medium_type)
                        points = calculate_manga_points(total_chapters, ani_progress, status, difficulty, ani_repeat)

                        # Update database
                        await db.execute(
                            """
                            INSERT INTO user_manga_progress (discord_id, manga_id, title, current_chapter, status, points, started_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(discord_id, manga_id) DO UPDATE SET
                                title=excluded.title,
                                current_chapter=excluded.current_chapter,
                                status=excluded.status,
                                points=excluded.points,
                                started_at=excluded.started_at,
                                updated_at=excluded.updated_at
                            """,
                            (self.target_id, manga_id, manga_title, ani_progress, status, points, ani_started_at, datetime.utcnow().isoformat())
                        )

                        # Update cache
                        cache_key = (self.target_id, manga_id)
                        user_progress_cache[cache_key] = {
                            "title": manga_title,
                            "chapters_read": ani_progress,
                            "status": status,
                            "medium_type": medium_type
                        }

                        # Add to description
                        description_lines.append(
                            f"[{manga_title}](https://anilist.co/manga/{manga_id}) - `{ani_progress}/{total_chapters}` • Status: `{status}`"
                        )
                        updated_count += 1

                    await db.commit()

                    # Update embed
                    description = "\n\n".join(description_lines) if description_lines else "_No manga added to this challenge yet._"
                    
                    cursor = await db.execute("SELECT title FROM global_challenges WHERE challenge_id = ?", (challenge_id,))
                    challenge_title_row = await cursor.fetchone()
                    await cursor.close()
                    challenge_title = challenge_title_row[0] if challenge_title_row else f"Challenge {challenge_id}"

                    # Update the embed in our list
                    updated_embed = discord.Embed(
                        title=f"📖 Challenge: {challenge_title}",
                        description=description,
                        color=discord.Color.green()
                    )
                    target = self.bot.get_user(self.target_id) or f"User {self.target_id}"
                    updated_embed.set_author(name=f"Progress for {target.display_name if hasattr(target, 'display_name') else target} ({self.anilist_username})")
                    updated_embed.set_footer(
                        text=f"Page {self.current_page + 1} of {len(self.embeds)} | "
                            f"ChallengeID: {challenge_id} | Updated {updated_count} manga"
                    )
                    
                    self.embeds[self.current_page] = updated_embed

                    # Update the message
                    await interaction.followup.edit_message(
                        message_id=self.message.id, embed=updated_embed, view=self
                    )

                await interaction.followup.send(f"✅ Updated {updated_count} manga on this page!", ephemeral=True)

            async def update_message(self, interaction: discord.Interaction):
                embed = self.embeds[self.current_page]
                embed.set_footer(
                    text=f"Page {self.current_page + 1} of {len(self.embeds)} | "
                        f"ChallengeID: {self.page_to_challenge_id[self.current_page][0]}"
                )
                try:
                    await interaction.response.edit_message(embed=embed, view=self)
                except discord.errors.InteractionResponded:
                    await interaction.followup.edit_message(
                        message_id=self.message.id, embed=embed, view=self
                    )

            @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.secondary, row=1)
            async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page = (self.current_page - 1) % len(self.embeds)
                await self.update_message(interaction)

            @discord.ui.button(label="➡️ Next", style=discord.ButtonStyle.secondary, row=1)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                self.current_page = (self.current_page + 1) % len(self.embeds)
                await self.update_message(interaction)

            @discord.ui.button(label="🔄 Update Page", style=discord.ButtonStyle.primary, row=1)
            async def update_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                await self.update_current_page(interaction)

            async def select_callback(self, interaction: discord.Interaction):
                self.current_page = int(self.select.values[0])
                await self.update_message(interaction)


        # -----------------------------------------
        # Send the view
        # -----------------------------------------
        view = ChallengeView(
            self.bot,
            embeds,
            options,
            embed_page_map,  # page_to_challenge_id
            target_id,
            anilist_username,
            anilist_id,
            all_manga_data
        )
        msg = await interaction.followup.send(embed=embeds[0], view=view)
        view.message = msg


async def setup(bot: commands.Bot):
    await bot.add_cog(MangaChallenges(bot))