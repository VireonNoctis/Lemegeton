# cogs/challenge_update.py
import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from datetime import datetime
import logging
import asyncio
import aiohttp
import os

from config import DB_PATH
from helpers.challenge_helper import (
    calculate_manga_points,
    calculate_challenge_completion_bonus,
    get_manga_difficulty,
    assign_challenge_role
)

# ------------------------------------------------------
# Logging setup
# ------------------------------------------------------
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "challenge_update.log")

logger = logging.getLogger("ChallengeUpdate")
logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == os.path.abspath(LOG_FILE)
           for h in logger.handlers):
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
        logger.addHandler(stream_handler)

# ------------------------------------------------------
# AniList API helper
# ------------------------------------------------------
ANILIST_API = "https://graphql.anilist.co"

async def fetch_anilist_progress(anilist_id: int, manga_id: int):
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

# ------------------------------------------------------
# Challenge Update Cog
# ------------------------------------------------------
class ChallengeUpdate(commands.Cog):
    """Admin cog to update a user's manga challenge points and roles."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cancel_flags = {}

    @commands.has_permissions(administrator=True)
    @app_commands.command(
        name="challenge-update",
        description="Update a user's points and roles for all manga challenges"
    )
    @app_commands.describe(user="Discord member to update")
    async def challenge_update(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.send_message(f"🔄 Challenge update started for {user.mention}. You will receive a summary once complete.", ephemeral=True)
        user_id = user.id
        self.cancel_flags[user_id] = False
        updated_count = 0
        skipped_count = 0

        # --- Clear and re-create log file/handler for this command run ---
        try:
            # Remove and close existing handlers
            for h in list(logger.handlers):
                logger.removeHandler(h)
                try:
                    h.close()
                except Exception:
                    pass

            # Truncate the log file
            open(LOG_FILE, "w", encoding="utf-8").close()

            # Recreate file handler so new session writes to a fresh file
            file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
            formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception:
            # If clearing logs fails, continue without raising (logging will still work if possible)
            pass

        # Helper to update the ephemeral progress message (throttled)
        last_update = 0.0
        async def _edit_progress(text: str, force: bool = False):
            nonlocal last_update
            now = asyncio.get_event_loop().time()
            # Throttle updates to avoid spamming edits (0.5s default)
            if not force and now - last_update < 0.5:
                return
            last_update = now
            try:
                await interaction.edit_original_response(content=text)
            except Exception:
                # ignore editing errors (user might have closed interaction or rate limit)
                pass

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row

            # Get AniList ID and username
            cursor = await db.execute(
                "SELECT anilist_id, anilist_username FROM users WHERE discord_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            await cursor.close()

            if not row or not row['anilist_id']:
                await interaction.followup.send(f"⚠️ No AniList ID found for {user.mention}.", ephemeral=True)
                logger.warning(f"No AniList ID for user {user}")
                return

            anilist_id = row['anilist_id']
            anilist_username = row['anilist_username'] or str(user)
            logger.info(f"Starting challenge update for {anilist_username} (Discord ID: {user_id})")

            # Fetch challenges
            challenges = await db.execute_fetchall("SELECT challenge_id, title, start_date FROM global_challenges")
            if not challenges:
                await interaction.followup.send("⚠️ No challenges found in the database.", ephemeral=True)
                logger.warning("No challenges found in the database")
                return

            # --- Main loop over challenges ---
            final_summary = []  # Collect data for embed at the end
            total_challenges = len(challenges)
            processed_challenges = 0

            for idx, (challenge_id, title, challenge_start_date) in enumerate(challenges, start=1):
                processed_challenges += 1
                manga_rows = await db.execute_fetchall(
                    "SELECT manga_id, title, total_chapters, medium_type FROM challenge_manga WHERE challenge_id = ?",
                    (challenge_id,)
                )
                if not manga_rows:
                    logger.info(f"No manga found for challenge {challenge_id}")
                    continue

                user_progress = []
                total_manga = len(manga_rows)
                processed_manga = 0

                for row in manga_rows:
                    processed_manga += 1

                    # allow cancellation from elsewhere
                    if self.cancel_flags.get(user_id):
                        await _edit_progress("❌ Challenge update cancelled.", force=True)
                        logger.info("Challenge update cancelled by user")
                        return

                    manga_id = row['manga_id']
                    title = row['title']
                    total_chapters = row['total_chapters']
                    medium_type = row['medium_type']

                    # Local progress
                    cursor = await db.execute(
                        "SELECT current_chapter, status, repeat, started_at FROM user_manga_progress "
                        "WHERE discord_id = ? AND manga_id = ?",
                        (user_id, manga_id)
                    )
                    local_result = await cursor.fetchone()
                    await cursor.close()

                    local_chapters = local_result['current_chapter'] if local_result else 0
                    local_status = local_result['status'] if local_result else "Not Started"
                    local_repeat = local_result['repeat'] if local_result else 0
                    local_started_at = local_result['started_at'] if local_result else None

                    # AniList progress
                    ani_data = await fetch_anilist_progress(anilist_id, manga_id)
                    await asyncio.sleep(2)

                    ani_progress = ani_data['progress'] if ani_data else 0
                    ani_status_upper = ani_data['status'].upper() if ani_data else "CURRENT"
                    ani_repeat = ani_data['repeat'] if ani_data else 0
                    ani_started_at = ani_data['started_at'] if ani_data else None

                    # ------------------------------
                    # Determine Status (priority-based)
                    # ------------------------------
                    def _to_date(val):
                        """Safe parser for date-like values. Returns a datetime.date or None."""
                        if not val:
                            return None
                        if isinstance(val, datetime):
                            return val.date()
                        try:
                            return datetime.fromisoformat(str(val)).date()
                        except Exception:
                            try:
                                return datetime.strptime(str(val), "%Y-%m-%d").date()
                            except Exception:
                                return None

                    status = "Not Started"

                    # baseline total
                    effective_total = total_chapters if (isinstance(total_chapters, (int, float)) and total_chapters > 0) else 1

                    # normalize numeric / text inputs
                    try:
                        ani_progress_num = float(ani_progress or 0)
                    except Exception:
                        ani_progress_num = 0.0
                    try:
                        ani_repeat_num = int(ani_repeat or 0)
                    except Exception:
                        ani_repeat_num = 0
                    try:
                        local_chapters_num = float(local_chapters or 0)
                    except Exception:
                        local_chapters_num = 0.0

                    status_upper = (ani_status_upper or "").upper()

                    # parse dates for skipped-check
                    started_at_val = _to_date(ani_started_at) or _to_date(local_started_at)
                    challenge_start_date_val = _to_date(challenge_start_date)

                    pct_progress = (ani_progress_num / effective_total) if effective_total else 0.0

                    # Priority order (non-overlapping):
                    # 1) Skipped: started before challenge and already had meaningful progress
                    if challenge_start_date_val and started_at_val and started_at_val < challenge_start_date_val and pct_progress >= 0.25:
                        status = "Skipped"
                        logger.info(
                            f"[STATUS] Skipped: {anilist_username} | {title} | "
                            f"{ani_progress_num}/{total_chapters} ({pct_progress*100:.1f}%) progress before challenge start "
                            f"(started_at={started_at_val}, challenge_start_date={challenge_start_date_val})"
                        )

                    # 2) Reread: repeats and at/over total
                    elif status_upper in ("COMPLETED", "CURRENT") and ani_repeat_num >= 1 and ani_progress_num >= effective_total:
                        status = "Reread"
                        logger.info(
                            f"[STATUS] Reread: {anilist_username} | {title} | ani_status={status_upper}, "
                            f"repeats={ani_repeat_num}, progress={ani_progress_num}, total_chapters={effective_total}"
                        )

                    # 3) Caught Up: user still marked CURRENT but has reached/exceeded total -> treat differently from Completed
                    elif status_upper == "CURRENT" and ani_progress_num >= effective_total:
                        status = "Caught Up"
                        logger.info(
                            f"[STATUS] Caught Up: {anilist_username} | {title} | status=CURRENT but progress={ani_progress_num} >= total={effective_total}"
                        )

                    # 4) Completed: explicitly completed (prefer COMPLETED state)
                    elif status_upper == "COMPLETED" and ani_progress_num >= effective_total:
                        status = "Completed"
                        logger.info(
                            f"[STATUS] Completed: {anilist_username} | {title} | progress={ani_progress_num}, total_chapters={effective_total}"
                        )

                    # 5) In Progress: marked CURRENT with progress less than total (or fallback to any positive progress)
                    elif status_upper == "CURRENT" and 0 < ani_progress_num < effective_total:
                        status = "In Progress"
                        logger.info(
                            f"[STATUS] In Progress: {anilist_username} | {title} | progress={ani_progress_num}, total_chapters={effective_total}"
                        )

                    # 6) Paused
                    elif status_upper == "PAUSED":
                        status = "Paused"
                        logger.info(f"[STATUS] Paused: {anilist_username} | {title} | ani_status=PAUSED")

                    # 7) Dropped
                    elif status_upper == "DROPPED":
                        status = "Dropped"
                        logger.info(f"[STATUS] Dropped: {anilist_username} | {title} | ani_status=DROPPED")

                    # 8) Fallbacks:
                    else:
                        # If progress meets/exceeds total, mark Completed as a safe fallback
                        if ani_progress_num >= effective_total:
                            status = "Completed"
                            logger.info(
                                f"[STATUS] Completed (fallback): {anilist_username} | {title} | progress={ani_progress_num}, total_chapters={effective_total}"
                            )
                        # any positive progress -> In Progress
                        elif ani_progress_num > 0 or local_chapters_num > 0:
                            status = "In Progress"
                            logger.info(
                                f"[STATUS] In Progress (fallback): {anilist_username} | {title} | progress={ani_progress_num or local_chapters_num}, total_chapters={effective_total}"
                            )
                        else:
                            status = "Not Started"
                            logger.info(
                                f"[STATUS] Not Started: {anilist_username} | {title} | ani_status={status_upper}, progress={ani_progress_num}, total_chapters={effective_total}"
                            )

                    # update counters
                    if status == "Skipped":
                        skipped_count += 1
                    else:
                        updated_count += 1

                    # Points
                    difficulty = await get_manga_difficulty(total_chapters, medium_type)
                    points = calculate_manga_points(total_chapters, ani_progress, status, difficulty, ani_repeat)

                    user_progress.append({
                        "manga_id": manga_id,
                        "title": title,
                        "status": status,
                        "points": points,
                        "chapters_read": ani_progress
                    })

                    # Log per-manga
                    logger.info(f"{anilist_username} | {title} | Chapters: {ani_progress}/{total_chapters} | Status: {status} | Points: {points}")

                    # Upsert into DB
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
                        (user_id, manga_id, title, ani_progress, status, points, ani_started_at, datetime.utcnow().isoformat())
                    )

                    # Commit per-manga to persist progress and keep memory low
                    await db.commit()

                    # Edit ephemeral progress message
                    progress_text = (
                        f"🔄 Updating {user.mention}\n"
                        f"Challenge {processed_challenges}/{total_challenges}: {title}\n"
                        f"Manga {processed_manga}/{total_manga} — {manga_id}\n"
                        f"Processed: {updated_count} updated, {skipped_count} skipped"
                    )
                    await _edit_progress(progress_text)

                # End manga loop -> per-challenge summary calculations
                bonus_points = calculate_challenge_completion_bonus(user_progress)
                manga_points = sum(m['points'] for m in user_progress)
                total_points = manga_points + bonus_points

                # Build summary string for this challenge
                manga_summary = ""
                for m in user_progress:
                    t = m['title']
                    if len(t) > 50:
                        t = t[:47] + "…"
                    manga_summary += f"{t} | {m['status']} | Points: {m['points']}\n"

                # Attempt to assign challenge role rewards (if criteria met)
                try:
                    assigned_roles = await assign_challenge_role(self.bot, user_id, challenge_id, user_progress)
                    assigned_role_names = [r.name for r in assigned_roles] if assigned_roles else []
                    if assigned_role_names:
                        logger.info(f"Assigned roles for user {anilist_username} on challenge {challenge_id}: {', '.join(assigned_role_names)}")
                except Exception as e:
                    logger.exception(f"Role assignment failed for user {anilist_username}, challenge {challenge_id}: {e}")
                    assigned_role_names = []

                # Append to final_summary
                final_summary.append({
                    "challenge_id": challenge_id,
                    "updated": updated_count,
                    "skipped": skipped_count,
                    "manga_points": manga_points,
                    "bonus_points": bonus_points,
                    "total_points": total_points,
                    "manga_summary": manga_summary
                    , "assigned_roles": assigned_role_names
                })

            # Final progress update (force)
            await _edit_progress("✅ Challenge update complete. Preparing summary...", force=True)

            # Send final summary as a followup (ephemeral)
            summary_lines = []
            for s in final_summary:
                roles_part = ", ".join(s.get("assigned_roles") or []) or "None"
                summary_lines.append(
                    f"Challenge {s['challenge_id']}: Updated {s['updated']}, Skipped {s['skipped']}, "
                    f"Points {s['total_points']} | Roles assigned: {roles_part}"
                )
            summary_text = "Challenge update finished.\n\n" + "\n".join(summary_lines)
            # Send ephemeral summary to the command user
            await interaction.followup.send(summary_text, ephemeral=True)
            # Send detailed summary via DM instead of public message
            try:
                dm_embed = discord.Embed(
                    title="📊 Challenge Update Summary",
                    description="Your challenge progress has been updated!",
                    color=discord.Color.green()
                )
                for s in final_summary:
                    roles_part = ", ".join(s.get("assigned_roles") or []) or "None"
                    dm_embed.add_field(
                        name=f"Challenge {s['challenge_id']}",
                        value=f"Updated: {s['updated']}\nSkipped: {s['skipped']}\nPoints: {s['total_points']}\nRoles: {roles_part}",
                        inline=False
                    )
                dm_embed.set_footer(text="Challenge Update Complete")
                await user.send(embed=dm_embed)
                logger.info(f"Sent DM summary to {user}")
            except discord.Forbidden:
                # User has DMs disabled, log but don't error
                logger.warning(f"Could not send DM to {user} - DMs may be disabled")
            except Exception as e:
                # Log any other DM sending errors but don't crash
                logger.error(f"Failed to send DM summary to {user}: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ChallengeUpdate(bot))
