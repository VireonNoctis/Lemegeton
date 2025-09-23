import discord
from discord.ext import commands
import logging
import math
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from config import CHALLENGE_ROLE_IDS, GUILD_ID

# Configuration constants
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "challenge_helper.log"
VALID_COMPLETION_STATUSES = {"Completed", "Caught Up", "Reread", "Skipped"}
MAX_BONUS_POINTS = 150
BONUS_PERCENTAGE = 0.1

# Ensure logs directory exists
LOG_DIR.mkdir(exist_ok=True)

# Set up file-based logging with auto-clearing
logger = logging.getLogger("ChallengeHelper")
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

logger.info("Challenge Helper logging system initialized")

# Difficulty calculation constants
DIFFICULTY_THRESHOLDS = [
    (25, 1.0),
    (50, 1.5),
    (100, 2.0),
    (200, 2.5),
    (300, 3.0),
    (500, 3.5),
    (1000, 4.0),
    (1500, 4.3),
    (2000, 4.6),
    (float('inf'), 5.0)
]

MEDIUM_TYPE_MULTIPLIERS = {
    "manga": 1.1,
    "manhwa": 1.0,
    "manhua": 0.9
}

DIFFICULTY_LABELS = [
    (1.5, "Easy"),
    (2.5, "Medium"),
    (3.5, "Hard"),
    (4.5, "Very Hard"),
    (float('inf'), "Extreme")
]

async def get_manga_difficulty(total_chapters: int, medium_type: str = "manga") -> float:
    """
    Calculate numeric difficulty score for a single manga based on chapters and medium type.
    Returns a float score (1-5 scale, higher for longer titles and Manga > Manhwa > Manhua).
    """
    logger.debug(f"Calculating difficulty for {total_chapters} chapters, type: {medium_type}")
    
    try:
        # Validate input
        if not isinstance(total_chapters, int) or total_chapters < 0:
            logger.warning(f"Invalid total_chapters value: {total_chapters}, defaulting to 0")
            total_chapters = 0
            
        if not isinstance(medium_type, str):
            logger.warning(f"Invalid medium_type value: {medium_type}, defaulting to 'manga'")
            medium_type = "manga"
            
        # Calculate base score using threshold lookup
        base_score = 1.0
        for threshold, score in DIFFICULTY_THRESHOLDS:
            if total_chapters <= threshold:
                base_score = score
                break
                
        logger.debug(f"Base score for {total_chapters} chapters: {base_score}")
        
        # Apply medium type multiplier
        multiplier = MEDIUM_TYPE_MULTIPLIERS.get(medium_type.lower(), 1.0)
        if multiplier != MEDIUM_TYPE_MULTIPLIERS.get(medium_type.lower(), None):
            logger.debug(f"Unknown medium type '{medium_type}', using default multiplier 1.0")
            
        adjusted_score = base_score * multiplier
        final_score = min(5.0, adjusted_score)
        
        logger.info(f"Difficulty calculated: {total_chapters} {medium_type} chapters = {final_score:.2f}")
        return final_score
        
    except Exception as e:
        logger.error(f"Error calculating manga difficulty: {e}", exc_info=True)
        return 2.0  # Default fallback difficulty

async def get_challenge_difficulty(db, challenge_id: int) -> str:
    """
    Calculate overall difficulty for a challenge based on all manga in it with comprehensive logging.
    Returns a difficulty string: Easy / Medium / Hard / Very Hard / Extreme
    """
    logger.info(f"Calculating challenge difficulty for challenge ID: {challenge_id}")
    
    try:
        # Validate input
        if not isinstance(challenge_id, int) or challenge_id <= 0:
            logger.error(f"Invalid challenge_id: {challenge_id}")
            return "Medium"
            
        logger.debug(f"Querying database for manga in challenge {challenge_id}")
        cursor = await db.execute(
            "SELECT total_chapters, medium_type FROM challenge_manga WHERE challenge_id = ?",
            (challenge_id,)
        )
        manga_rows = await cursor.fetchall()
        await cursor.close()

        if not manga_rows:
            logger.warning(f"No manga found for challenge {challenge_id}, returning default difficulty")
            return "Medium"
            
        logger.debug(f"Found {len(manga_rows)} manga entries for challenge {challenge_id}")

        # Calculate individual difficulties
        difficulty_scores = []
        for i, (total_chapters, medium_type) in enumerate(manga_rows):
            try:
                difficulty = await get_manga_difficulty(total_chapters or 0, medium_type or "manga")
                difficulty_scores.append(difficulty)
                logger.debug(f"Manga {i+1}/{len(manga_rows)}: {total_chapters} {medium_type} = {difficulty:.2f}")
            except Exception as e:
                logger.warning(f"Error calculating difficulty for manga {i+1}: {e}")
                difficulty_scores.append(2.0)  # Default fallback
                
        # Calculate average difficulty
        if difficulty_scores:
            total_score = sum(difficulty_scores)
            avg_score = total_score / len(difficulty_scores)
            logger.debug(f"Average difficulty score: {avg_score:.2f} (from {len(difficulty_scores)} manga)")
        else:
            logger.warning("No valid difficulty scores calculated, using default")
            avg_score = 2.5
            
        # Determine difficulty label
        difficulty_label = "Medium"  # Default
        for threshold, label in DIFFICULTY_LABELS:
            if avg_score <= threshold:
                difficulty_label = label
                break
                
        logger.info(f"Challenge {challenge_id} difficulty: {difficulty_label} (avg score: {avg_score:.2f})")
        return difficulty_label
        
    except Exception as e:
        logger.error(f"Error calculating challenge difficulty for {challenge_id}: {e}", exc_info=True)
        return "Medium"  # Safe fallback


# -----------------------------
# Points Calculation
# -----------------------------
# Points calculation constants
STATUS_MULTIPLIERS = {
    "Completed": 1.2,
    "Caught Up": 1.2,
    "Skipped": 0.6,
    "Dropped": 0.3,
    "Paused": 0.4,
    "In Progress": 0.8,
    "Not Started": 0,
    "Reread": 1.5
}

CHAPTER_BASE_POINTS = {
    25: 10,
    100: 20,
    250: 35,
    500: 50,
    1000: 75,
    2000: 100,
    float('inf'): 120
}

def calculate_manga_points(
    total_chapters: int,
    chapters_read: int,
    status: str,
    difficulty: float,
    repeat_count: int = 0
) -> int:
    """
    Calculate points for a single manga based on chapters, status, difficulty, and reread count with logging.
    """
    logger.debug(f"Calculating points: {total_chapters}ch, {chapters_read} read, {status}, diff: {difficulty}, repeats: {repeat_count}")
    
    try:
        # Validate inputs
        if not isinstance(total_chapters, int) or total_chapters < 0:
            logger.warning(f"Invalid total_chapters: {total_chapters}, using 0")
            total_chapters = 0
            
        if not isinstance(chapters_read, int) or chapters_read < 0:
            logger.warning(f"Invalid chapters_read: {chapters_read}, using 0")
            chapters_read = 0
            
        if not isinstance(difficulty, (int, float)) or difficulty <= 0:
            logger.warning(f"Invalid difficulty: {difficulty}, using 3.0")
            difficulty = 3.0
            
        if not isinstance(repeat_count, int) or repeat_count < 0:
            logger.warning(f"Invalid repeat_count: {repeat_count}, using 0")
            repeat_count = 0
            
        # Determine base points from chapter count
        base_points = CHAPTER_BASE_POINTS[float('inf')]  # Default to highest
        for threshold, points in CHAPTER_BASE_POINTS.items():
            if total_chapters < threshold:
                base_points = points
                break
                
        logger.debug(f"Base points for {total_chapters} chapters: {base_points}")
        
        # Get status multiplier
        if status == "Reread":
            multiplier = 1.5 + max(repeat_count - 1, 0) * 0.3
            logger.debug(f"Reread multiplier: {multiplier} (repeat count: {repeat_count})")
        else:
            multiplier = STATUS_MULTIPLIERS.get(status, 0)
            if status not in STATUS_MULTIPLIERS:
                logger.warning(f"Unknown status '{status}', using 0 multiplier")
            logger.debug(f"Status multiplier for '{status}': {multiplier}")
        
        # Apply difficulty scaling
        difficulty_factor = difficulty / 3.0
        logger.debug(f"Difficulty factor: {difficulty_factor:.2f}")
        
        # Calculate base points
        points = base_points * multiplier * difficulty_factor
        
        # Apply partial completion for "In Progress" status
        if status == "In Progress" and total_chapters > 0:
            completion_ratio = min(chapters_read / total_chapters, 1.0)
            points *= completion_ratio
            logger.debug(f"In Progress completion ratio: {completion_ratio:.2f}")
        
        final_points = max(0, round(points))
        logger.info(f"Points calculated: {total_chapters}ch {status} (diff: {difficulty:.1f}) = {final_points} points")
        
        return final_points
        
    except Exception as e:
        logger.error(f"Error calculating manga points: {e}", exc_info=True)
        return 0

def calculate_challenge_completion_bonus(user_progress: list) -> int:
    """
    Calculate bonus points for completing a challenge with comprehensive logging.
    Returns bonus points if all manga in the challenge are marked as completed statuses.
    """
    logger.debug(f"Calculating completion bonus for {len(user_progress)} progress entries")
    
    try:
        if not user_progress:
            logger.warning("No user progress data provided")
            return 0
            
        if not isinstance(user_progress, list):
            logger.error(f"Invalid user_progress type: {type(user_progress)}")
            return 0
        
        # Check completion status for all entries
        completed_entries = []
        incomplete_entries = []
        
        for i, entry in enumerate(user_progress):
            if not isinstance(entry, dict):
                logger.warning(f"Entry {i} is not a dict: {type(entry)}")
                continue
                
            status = entry.get("status", "Unknown")
            if status in VALID_COMPLETION_STATUSES:
                completed_entries.append(entry)
            else:
                incomplete_entries.append((i, status))
                
        logger.debug(f"Completed entries: {len(completed_entries)}, Incomplete: {len(incomplete_entries)}")
        
        if incomplete_entries:
            logger.debug(f"Incomplete statuses found: {[status for _, status in incomplete_entries]}")
            return 0
            
        # Calculate total points from completed entries
        total_points = 0
        for entry in completed_entries:
            entry_points = entry.get("points", 0)
            if isinstance(entry_points, (int, float)):
                total_points += entry_points
            else:
                logger.warning(f"Invalid points value in entry: {entry_points}")
                
        logger.debug(f"Total points from entries: {total_points}")
        
        if total_points <= 0:
            logger.warning("No valid points found in progress entries")
            return 0
            
        # Calculate bonus (10% of total points, capped at 150)
        bonus_percentage = 0.1
        bonus_points = round(total_points * bonus_percentage)
        final_bonus = min(bonus_points, MAX_BONUS_POINTS)
        
        logger.info(f"Challenge completion bonus: {final_bonus} points ({bonus_percentage*100}% of {total_points}, capped at {MAX_BONUS_POINTS})")
        return final_bonus
        
    except Exception as e:
        logger.error(f"Error calculating challenge completion bonus: {e}", exc_info=True)
        return 0


# -----------------------------
# Role Assignment
# -----------------------------
async def assign_challenge_role(bot: commands.Bot, discord_id: int, challenge_id: int, challenge_progress: list):
    """
    Assign role for a specific challenge based on user's progress with comprehensive logging.
    Only assigns role when all titles are completed, caught up, reread, or skipped.
    Returns a list of roles that were assigned.
    """
    logger.info(f"Assigning challenge role for user {discord_id}, challenge {challenge_id}")
    assigned_roles = []
    
    try:
        # Validate inputs
        if not isinstance(discord_id, int) or discord_id <= 0:
            logger.error(f"Invalid discord_id: {discord_id}")
            return assigned_roles
            
        if not isinstance(challenge_id, int) or challenge_id <= 0:
            logger.error(f"Invalid challenge_id: {challenge_id}")
            return assigned_roles
            
        if not isinstance(challenge_progress, list):
            logger.error(f"Invalid challenge_progress type: {type(challenge_progress)}")
            return assigned_roles
            
        # Check if challenge has role assignments configured
        if challenge_id not in CHALLENGE_ROLE_IDS:
            logger.debug(f"No role configuration found for challenge {challenge_id}")
            return assigned_roles

        total_titles = len(challenge_progress)
        logger.debug(f"Total titles in challenge: {total_titles}")
        
        if total_titles == 0:
            logger.warning(f"No titles found in challenge progress for challenge {challenge_id}")
            return assigned_roles

        # Check completion status
        completed_entries = []
        incomplete_entries = []
        
        for i, entry in enumerate(challenge_progress):
            if not isinstance(entry, dict):
                logger.warning(f"Progress entry {i} is not a dict: {type(entry)}")
                continue
                
            status = entry.get("status", "Unknown")
            if status in VALID_COMPLETION_STATUSES:
                completed_entries.append(entry)
                logger.debug(f"Entry {i}: {status} (completed)")
            else:
                incomplete_entries.append((i, status))
                logger.debug(f"Entry {i}: {status} (incomplete)")
        
        completed_count = len(completed_entries)
        logger.debug(f"Completion status: {completed_count}/{total_titles} completed")
        
        if completed_count != total_titles:
            logger.info(f"Challenge {challenge_id} not fully completed by user {discord_id} ({completed_count}/{total_titles})")
            return assigned_roles

        # Determine role to assign
        thresholds = CHALLENGE_ROLE_IDS[challenge_id]
        completion_percentage = 1.0  # 100% completion
        
        role_to_assign = None
        for threshold in sorted(thresholds.keys(), reverse=True):
            if completion_percentage >= threshold:
                role_to_assign = thresholds[threshold]
                logger.debug(f"Role selected: {role_to_assign} for threshold {threshold}")
                break
                
        if not role_to_assign:
            logger.warning(f"No role found for completion percentage {completion_percentage}")
            return assigned_roles

        # Get Discord guild and member
        logger.debug(f"Getting guild {GUILD_ID}")
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            logger.error(f"Guild {GUILD_ID} not found")
            return assigned_roles

        logger.debug(f"Getting member {discord_id}")
        member = guild.get_member(discord_id)
        if not member:
            logger.warning(f"Member {discord_id} not found in guild {GUILD_ID}")
            return assigned_roles

        # Remove other challenge roles first
        existing_challenge_roles = [r for r in member.roles if r.id in thresholds.values() and r.id != role_to_assign]
        if existing_challenge_roles:
            logger.debug(f"Removing {len(existing_challenge_roles)} existing challenge roles")
            try:
                await member.remove_roles(*existing_challenge_roles, reason=f"Challenge {challenge_id} role update")
                logger.info(f"Removed roles: {[r.name for r in existing_challenge_roles]}")
            except Exception as e:
                logger.error(f"Failed to remove existing roles: {e}")

        # Add new role
        role = guild.get_role(role_to_assign)
        if not role:
            logger.error(f"Role {role_to_assign} not found in guild")
            return assigned_roles
            
        if role in member.roles:
            logger.debug(f"User {discord_id} already has role {role.name}")
            return assigned_roles

        try:
            await member.add_roles(role, reason=f"Completed Challenge {challenge_id}")
            assigned_roles.append(role)
            logger.info(f"Assigned role '{role.name}' to user {discord_id} for challenge {challenge_id}")
            
            # Send congratulatory message
            try:
                await member.send(
                    f"🎉 Congratulations! You've completed Challenge {challenge_id} and have been awarded the role **{role.name}**!"
                )
                logger.debug(f"Sent congratulatory message to user {discord_id}")
            except discord.Forbidden:
                logger.debug(f"Could not send DM to user {discord_id} (DMs disabled)")
            except Exception as dm_error:
                logger.warning(f"Failed to send congratulatory message: {dm_error}")
                
        except Exception as e:
            logger.error(f"Failed to assign role {role.name} to user {discord_id}: {e}")

        return assigned_roles
        
    except Exception as e:
        logger.error(f"Error in assign_challenge_role: {e}", exc_info=True)
        return assigned_roles

