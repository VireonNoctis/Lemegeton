#!/usr/bin/env python3
"""
Script to update challenge progress for all registered users and notify them via DM.
Based on the challenge_update command functionality.
"""

import os
import sys
import asyncio
import aiosqlite
import aiohttp
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

import discord
from config import TOKEN, DB_PATH, GUILD_ID
from helpers.challenge_helper import (
    calculate_manga_points,
    calculate_challenge_completion_bonus,
    get_manga_difficulty,
    assign_challenge_role
)

# ------------------------------------------------------
# Logging setup
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "update_all_users.log"

logger = logging.getLogger("UpdateAllUsers")
logger.setLevel(logging.INFO)

# Clear existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create file handler
file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("="*60)
logger.info("STARTING BULK USER CHALLENGE UPDATE")
logger.info("="*60)

# ------------------------------------------------------
# AniList API helper (copied from challenge_update.py)
# ------------------------------------------------------
ANILIST_API = "https://graphql.anilist.co"

async def fetch_anilist_progress(anilist_id: int, manga_id: int):
    """Fetch user's progress for a specific manga from AniList API."""
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
# User update function (based on challenge_update command)
# ------------------------------------------------------
async def update_user_challenges(bot: discord.Client, user_data: dict):
    """Update challenges for a single user (based on challenge_update logic)."""
    discord_id = user_data['discord_id']
    anilist_id = user_data['anilist_id']
    anilist_username = user_data['anilist_username'] or f"User_{discord_id}"
    
    if not anilist_id:
        logger.warning(f"Skipping user {discord_id} - no AniList ID")
        return None
    
    logger.info(f"Processing user: {anilist_username} (Discord: {discord_id}, AniList: {anilist_id})")
    
    updated_count = 0
    skipped_count = 0
    challenges_summary = []
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Get all challenges
        challenges = await db.execute_fetchall("SELECT challenge_id, title, start_date FROM global_challenges")
        if not challenges:
            logger.warning("No challenges found in database")
            return None
        
        # Process each challenge
        for challenge_id, challenge_title, challenge_start_date in challenges:
            logger.info(f"Processing challenge {challenge_id}: {challenge_title}")
            
            # Get manga for this challenge
            manga_rows = await db.execute_fetchall(
                "SELECT manga_id, title, total_chapters, medium_type FROM challenge_manga WHERE challenge_id = ?",
                (challenge_id,)
            )
            
            if not manga_rows:
                logger.info(f"No manga found for challenge {challenge_id}")
                continue
            
            user_progress = []
            
            # Process each manga in the challenge
            for row in manga_rows:
                manga_id = row['manga_id']
                title = row['title']
                total_chapters = row['total_chapters']
                medium_type = row['medium_type']
                
                # Get local progress
                cursor = await db.execute(
                    "SELECT current_chapter, status, repeat, started_at FROM user_manga_progress "
                    "WHERE discord_id = ? AND manga_id = ?",
                    (discord_id, manga_id)
                )
                local_result = await cursor.fetchone()
                await cursor.close()
                
                local_chapters = local_result['current_chapter'] if local_result else 0
                local_status = local_result['status'] if local_result else "Not Started"
                local_repeat = local_result['repeat'] if local_result else 0
                local_started_at = local_result['started_at'] if local_result else None
                
                # Get AniList progress
                ani_data = await fetch_anilist_progress(anilist_id, manga_id)
                await asyncio.sleep(2)  # 2 second wait as requested
                
                ani_progress = ani_data['progress'] if ani_data else 0
                ani_status_upper = ani_data['status'].upper() if ani_data else "CURRENT"
                ani_repeat = ani_data['repeat'] if ani_data else 0
                ani_started_at = ani_data['started_at'] if ani_data else None
                
                # Determine status (simplified version of the complex logic from challenge_update)
                def _to_date(val):
                    if not val:
                        return None
                    try:
                        if isinstance(val, str):
                            return datetime.fromisoformat(val.replace('Z', '+00:00')).date()
                        return val
                    except:
                        return None
                
                status = "Not Started"
                effective_total = total_chapters if (isinstance(total_chapters, (int, float)) and total_chapters > 0) else 1
                
                # Normalize inputs
                try:
                    ani_progress_num = int(ani_progress) if ani_progress else 0
                except:
                    ani_progress_num = 0
                try:
                    ani_repeat_num = int(ani_repeat) if ani_repeat else 0
                except:
                    ani_repeat_num = 0
                
                status_upper = (ani_status_upper or "").upper()
                started_at_val = _to_date(ani_started_at) or _to_date(local_started_at)
                challenge_start_date_val = _to_date(challenge_start_date)
                pct_progress = (ani_progress_num / effective_total) if effective_total else 0.0
                
                # Status determination logic (simplified)
                if challenge_start_date_val and started_at_val and started_at_val < challenge_start_date_val and pct_progress >= 0.25:
                    status = "Skipped"
                elif status_upper in ("COMPLETED", "CURRENT") and ani_repeat_num >= 1 and ani_progress_num >= effective_total:
                    status = "Reread"
                elif status_upper == "CURRENT" and ani_progress_num >= effective_total:
                    status = "Caught Up"
                elif status_upper == "COMPLETED" and ani_progress_num >= effective_total:
                    status = "Completed"
                elif status_upper == "CURRENT" and 0 < ani_progress_num < effective_total:
                    status = "In Progress"
                elif status_upper == "PAUSED":
                    status = "Paused"
                elif status_upper == "DROPPED":
                    status = "Dropped"
                else:
                    status = "Not Started"
                
                # Update counters
                if status == "Skipped":
                    skipped_count += 1
                else:
                    updated_count += 1
                
                # Calculate points
                difficulty = await get_manga_difficulty(total_chapters, medium_type)
                points = calculate_manga_points(total_chapters, ani_progress, status, difficulty, ani_repeat)
                
                user_progress.append({
                    "manga_id": manga_id,
                    "title": title,
                    "status": status,
                    "points": points,
                    "chapters_read": ani_progress
                })
                
                logger.info(f"  {title}: {ani_progress}/{total_chapters} chapters, Status: {status}, Points: {points}")
                
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
                    (discord_id, manga_id, title, ani_progress, status, points, ani_started_at, datetime.utcnow().isoformat())
                )
                
                await db.commit()
            
            # Calculate challenge summary
            bonus_points = calculate_challenge_completion_bonus(user_progress)
            manga_points = sum(m['points'] for m in user_progress)
            total_points = manga_points + bonus_points
            
            # Try to assign roles
            try:
                assigned_roles = await assign_challenge_role(bot, discord_id, challenge_id, user_progress)
                assigned_role_names = [role.name for role in assigned_roles] if assigned_roles else []
            except Exception as e:
                logger.error(f"Error assigning roles for user {discord_id}, challenge {challenge_id}: {e}")
                assigned_role_names = []
            
            challenges_summary.append({
                "challenge_id": challenge_id,
                "challenge_title": challenge_title,
                "manga_points": manga_points,
                "bonus_points": bonus_points,
                "total_points": total_points,
                "assigned_roles": assigned_role_names,
                "manga_count": len(user_progress)
            })
    
    return {
        "discord_id": discord_id,
        "anilist_username": anilist_username,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "challenges": challenges_summary
    }

# ------------------------------------------------------
# DM notification function
# ------------------------------------------------------
async def send_update_notification(bot: discord.Client, user_data: dict, update_result: dict):
    """Send DM notification to user about their updated challenge progress."""
    try:
        user = bot.get_user(user_data['discord_id'])
        if not user:
            logger.warning(f"Could not find Discord user {user_data['discord_id']}")
            return False
        
        # Create embed with update summary
        embed = discord.Embed(
            title="🎯 Challenge Progress Updated!",
            description=f"Your challenge progress has been automatically updated from AniList.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📊 Update Summary",
            value=f"• **Updated**: {update_result['updated_count']} manga\n• **Skipped**: {update_result['skipped_count']} manga",
            inline=False
        )
        
        # Add challenge details
        challenge_info = ""
        for challenge in update_result['challenges']:
            roles_text = f", Roles: {', '.join(challenge['assigned_roles'])}" if challenge['assigned_roles'] else ""
            challenge_info += f"**Challenge {challenge['challenge_id']}**: {challenge['total_points']} points{roles_text}\n"
        
        if challenge_info:
            embed.add_field(
                name="🏆 Challenge Details",
                value=challenge_info[:1024],  # Discord field limit
                inline=False
            )
        
        embed.add_field(
            name="🔍 Please Review Your Progress",
            value=(
                "Please check your challenge progress and report any inconsistencies.\n\n"
                "**If you notice any errors or missing progress:**\n"
                "Use `/feedback` to report issues with your challenge data.\n\n"
                "**Common issues to check:**\n"
                "• Missing completed manga\n"
                "• Incorrect chapter counts\n"
                "• Wrong status assignments\n"
                "• Missing role assignments"
            ),
            inline=False
        )
        
        embed.set_footer(text="This update was performed automatically • Use /feedback for any issues")
        embed.timestamp = datetime.utcnow()
        
        await user.send(embed=embed)
        logger.info(f"✅ Sent DM notification to {update_result['anilist_username']} ({user_data['discord_id']})")
        return True
        
    except discord.Forbidden:
        logger.warning(f"❌ Could not send DM to {update_result['anilist_username']} - DMs disabled")
        return False
    except Exception as e:
        logger.error(f"❌ Error sending DM to {update_result['anilist_username']}: {e}")
        return False

# ------------------------------------------------------
# Main execution function
# ------------------------------------------------------
async def main():
    """Main function to update all users and send notifications."""
    logger.info("Starting bulk user update process")
    
    # Initialize bot
    intents = discord.Intents.default()
    intents.message_content = True
    bot = discord.Client(intents=intents)
    
    @bot.event
    async def on_ready():
        logger.info(f"Bot connected as {bot.user}")
        
        try:
            # Get all users with AniList IDs
            async with aiosqlite.connect(DB_PATH) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    "SELECT discord_id, username, anilist_username, anilist_id FROM users WHERE anilist_id IS NOT NULL"
                )
                users = await cursor.fetchall()
                await cursor.close()
            
            if not users:
                logger.warning("No users with AniList IDs found in database")
                await bot.close()
                return
            
            logger.info(f"Found {len(users)} users with AniList IDs to update")
            
            successful_updates = 0
            successful_notifications = 0
            failed_updates = 0
            failed_notifications = 0
            
            # Process each user
            for i, user_data in enumerate(users, 1):
                logger.info(f"\n{'='*50}")
                logger.info(f"Processing user {i}/{len(users)}: {user_data['username']} (ID: {user_data['discord_id']})")
                logger.info(f"{'='*50}")
                
                try:
                    # Update user's challenge progress
                    update_result = await update_user_challenges(bot, dict(user_data))
                    
                    if update_result:
                        successful_updates += 1
                        logger.info(f"✅ Successfully updated {user_data['username']}")
                        
                        # Send DM notification
                        dm_sent = await send_update_notification(bot, dict(user_data), update_result)
                        if dm_sent:
                            successful_notifications += 1
                        else:
                            failed_notifications += 1
                        
                        # 2 second wait between each user as requested
                        await asyncio.sleep(2)
                        
                    else:
                        failed_updates += 1
                        logger.warning(f"❌ Failed to update {user_data['username']}")
                        
                except Exception as e:
                    failed_updates += 1
                    logger.error(f"❌ Error processing {user_data['username']}: {e}")
            
            # Final summary
            logger.info(f"\n{'='*60}")
            logger.info("BULK UPDATE COMPLETE")
            logger.info(f"{'='*60}")
            logger.info(f"Total users processed: {len(users)}")
            logger.info(f"Successful updates: {successful_updates}")
            logger.info(f"Failed updates: {failed_updates}")
            logger.info(f"Successful DM notifications: {successful_notifications}")
            logger.info(f"Failed DM notifications: {failed_notifications}")
            logger.info(f"{'='*60}")
            
        except Exception as e:
            logger.error(f"Fatal error in main process: {e}")
        finally:
            await bot.close()
    
    # Start the bot
    try:
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")