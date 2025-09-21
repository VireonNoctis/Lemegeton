# challenge_helper.py

import discord
from discord.ext import commands
from config import CHALLENGE_ROLE_IDS, GUILD_ID

# -----------------------------
# Difficulty Calculation
# -----------------------------
async def get_manga_difficulty(total_chapters: int, medium_type: str = "manga") -> float:
    """
    Calculate numeric difficulty score for a single manga based on chapters and medium type.
    Returns a float score (1-5 scale, higher for longer titles and Manga > Manhwa > Manhua).
    """
    import math
    if total_chapters <= 25:
        base_score = 1.0
    elif total_chapters <= 50:
        base_score = 1.5
    elif total_chapters <= 100:
        base_score = 2.0
    elif total_chapters <= 200:
        base_score = 2.5
    elif total_chapters <= 300:
        base_score = 3.0
    elif total_chapters <= 500:
        base_score = 3.5
    elif total_chapters <= 1000:
        base_score = 4.0
    elif total_chapters <= 1500:
        base_score = 4.3
    elif total_chapters <= 2000:
        base_score = 4.6
    else:
        base_score = 5.0

    multipliers = {"manga": 1.1, "manhwa": 1.0, "manhua": 0.9}
    multiplier = multipliers.get(medium_type.lower(), 1.0)
    adjusted_score = base_score * multiplier
    return min(5.0, adjusted_score)


async def get_challenge_difficulty(db, challenge_id: int) -> str:
    """
    Calculate overall difficulty for a challenge based on all manga in it.
    Returns a difficulty string: Easy / Medium / Hard / Very Hard / Extreme
    """
    cursor = await db.execute(
        "SELECT total_chapters, medium_type FROM challenge_manga WHERE challenge_id = ?",
        (challenge_id,)
    )
    manga_rows = await cursor.fetchall()
    await cursor.close()

    if not manga_rows:
        return "Medium"

    total_score = sum(await get_manga_difficulty(tc, mt) for tc, mt in manga_rows)
    avg_score = total_score / len(manga_rows)

    if avg_score <= 1.5:
        return "Easy"
    elif avg_score <= 2.5:
        return "Medium"
    elif avg_score <= 3.5:
        return "Hard"
    elif avg_score <= 4.5:
        return "Very Hard"
    return "Extreme"


# -----------------------------
# Points Calculation
# -----------------------------
def calculate_manga_points(
    total_chapters: int,
    chapters_read: int,
    status: str,
    difficulty: float,
    repeat_count: int = 0
) -> int:
    """
    Calculate points for a single manga based on chapters, chapters read, status,
    difficulty, and reread count.
    """
    if total_chapters < 25:
        base = 10
    elif total_chapters <= 100:
        base = 20
    elif total_chapters <= 250:
        base = 35
    elif total_chapters <= 500:
        base = 50
    elif total_chapters <= 1000:
        base = 75
    elif total_chapters <= 2000:
        base = 100
    else:
        base = 120

    status_multiplier = {
        "Completed": 1.2,
        "Caught Up": 1.2,
        "Skipped": 0.6,
        "Dropped": 0.3,
        "Paused": 0.4,
        "In Progress": 0.8,
        "Not Started": 0,
        "Reread": 1.5
    }

    multiplier = 1.5 + max(repeat_count - 1, 0) * 0.3 if status == "Reread" else status_multiplier.get(status, 0)
    points = base * multiplier * (difficulty / 3)

    if status == "In Progress" and total_chapters > 0:
        points *= min(chapters_read / total_chapters, 1)

    return max(0, round(points))


def calculate_challenge_completion_bonus(user_progress: list) -> int:
    """
    Returns bonus points if all manga in the challenge are marked as:
    Completed, Caught Up, Reread, or Skipped.
    """
    valid_statuses = {"Completed", "Caught Up", "Reread", "Skipped"}

    if not all(p.get("status") in valid_statuses for p in user_progress):
        return 0

    total_points = sum(p.get("points", 0) for p in user_progress)
    bonus_points = round(total_points * 0.1)
    return min(bonus_points, 150)


# -----------------------------
# Role Assignment
# -----------------------------
async def assign_challenge_role(bot: commands.Bot, discord_id: int, challenge_id: int, challenge_progress: list):
    """
    Assigns a role for a specific challenge based on user's progress.
    Only assigns role when all titles are completed, caught up, reread, or skipped.
    Returns a list of roles that were assigned.
    """
    assigned_roles = []

    if challenge_id not in CHALLENGE_ROLE_IDS:
        return assigned_roles

    total_titles = len(challenge_progress)
    if total_titles == 0:
        return assigned_roles

    valid_statuses = {"Completed", "Caught Up", "Reread", "Skipped"}
    completed_count = sum(1 for entry in challenge_progress if entry.get("status") in valid_statuses)
    if completed_count != total_titles:
        return assigned_roles

    thresholds = CHALLENGE_ROLE_IDS[challenge_id]
    role_to_assign = next((r for t, r in sorted(thresholds.items(), reverse=True) if 1.0 >= t), None)
    if not role_to_assign:
        return assigned_roles

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        return assigned_roles

    member = guild.get_member(discord_id)
    if not member:
        return assigned_roles

    # Remove other roles for this challenge
    roles_to_remove = [r for r in member.roles if r.id in thresholds.values() and r.id != role_to_assign]
    if roles_to_remove:
        await member.remove_roles(*roles_to_remove)

    role = guild.get_role(role_to_assign)
    if role and role not in member.roles:
        await member.add_roles(role)
        assigned_roles.append(role)
        try:
            await member.send(
                f"🎉 Congratulations! You've completed Challenge {challenge_id} and have been awarded the role **{role.name}**!"
            )
        except discord.Forbidden:
            pass

    return assigned_roles

