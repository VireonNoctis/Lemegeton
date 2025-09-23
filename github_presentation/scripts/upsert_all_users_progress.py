import asyncio
import aiohttp
import aiosqlite
import logging

DB_PATH = "database.db"
ANILIST_API = "https://graphql.anilist.co"

logger = logging.getLogger("AllUsersUpdater")
logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------
# Setup checkpoint table if not exists
# ---------------------------------------------------
async def init_checkpoint_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_progress_checkpoint (
                discord_id INTEGER PRIMARY KEY,
                last_manga_id INTEGER
            )
        """)
        await db.commit()

# ---------------------------------------------------
# Fetch all registered users
# ---------------------------------------------------
async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT discord_id, anilist_username FROM users")
        users = await cursor.fetchall()
        await cursor.close()
        return users

# ---------------------------------------------------
# Fetch AniList manga progress
# ---------------------------------------------------
async def fetch_user_manga_progress(session, anilist_username: str, manga_id: int):
    query = """
    query ($username: String, $id: Int) {
      MediaList(userName: $username, mediaId: $id, type: MANGA) {
        progress
        status
      }
    }
    """
    try:
        async with session.post(
            ANILIST_API,
            json={"query": query, "variables": {"username": anilist_username, "id": manga_id}},
            timeout=10
        ) as resp:
            data = await resp.json()
            media_list = data.get("data", {}).get("MediaList")
            if media_list:
                return media_list.get("progress", 0), media_list.get("status", "Not Started")
            return 0, "Not Started"
    except Exception as e:
        logger.error(f"❌ AniList fetch failed for {anilist_username}, manga {manga_id}: {e}")
        return 0, "Not Started"

# ---------------------------------------------------
# Upsert manga progress in DB (with status)
# ---------------------------------------------------
async def upsert_user_manga_progress(discord_id, manga_id, manga_title, chapters_read, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_manga_progress (discord_id, manga_id, title, current_chapter, rating, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(discord_id, manga_id) DO UPDATE SET
                title = excluded.title,
                current_chapter = excluded.current_chapter,
                rating = excluded.rating,
                status = excluded.status
        """, (discord_id, manga_id, manga_title, chapters_read, 0, status))
        await db.commit()

# ---------------------------------------------------
# Get last checkpoint for user
# ---------------------------------------------------
async def get_user_checkpoint(discord_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT last_manga_id FROM user_progress_checkpoint WHERE discord_id = ?", (discord_id,))
        row = await cursor.fetchone()
        await cursor.close()
        return row[0] if row else None

# ---------------------------------------------------
# Update user checkpoint
# ---------------------------------------------------
async def set_user_checkpoint(discord_id, manga_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO user_progress_checkpoint (discord_id, last_manga_id)
            VALUES (?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                last_manga_id = excluded.last_manga_id
        """, (discord_id, manga_id))
        await db.commit()

# ---------------------------------------------------
# Update challenge progress for a single user
# ---------------------------------------------------
async def update_single_user(discord_id: int, anilist_username: str, session):
    # Get all challenges & manga
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT challenge_id FROM global_challenges")
        challenges = await cursor.fetchall()
        await cursor.close()

        challenge_manga_map = {}
        for challenge_id, in challenges:
            cursor = await db.execute(
                "SELECT manga_id, title, total_chapters FROM challenge_manga WHERE challenge_id = ?",
                (challenge_id,)
            )
            challenge_manga_map[challenge_id] = await cursor.fetchall()
            await cursor.close()

    last_checkpoint = await get_user_checkpoint(discord_id)
    logger.info(f"🔄 Updating {anilist_username} (Discord: {discord_id})")

    for challenge_id, manga_list in challenge_manga_map.items():
        manga_list.sort(key=lambda x: x[1].lower())

        start_index = 0
        if last_checkpoint:
            for i, (manga_id, _, _) in enumerate(manga_list):
                if manga_id == last_checkpoint:
                    start_index = i + 1
                    break

        for manga_id, manga_title, total_chapters in manga_list[start_index:]:
            chapters_read, status = await fetch_user_manga_progress(session, anilist_username, manga_id)
            await upsert_user_manga_progress(discord_id, manga_id, manga_title, chapters_read, status)
            await set_user_checkpoint(discord_id, manga_id)

            logger.info(f"    ➜ {manga_title}: {chapters_read}/{total_chapters or '?'} ({status})")
            await asyncio.sleep(2)

    logger.info(f"✅ Finished updating {anilist_username}")

# ---------------------------------------------------
# Update all users
# ---------------------------------------------------
async def update_all_users():
    await init_checkpoint_table()
    users = await get_all_users()

    async with aiohttp.ClientSession() as session:
        for discord_id, anilist_username in users:
            if not anilist_username:
                logger.warning(f"⚠️ Skipping Discord ID {discord_id} — no AniList username set.")
                continue

            try:
                await update_single_user(discord_id, anilist_username, session)
            except Exception as e:
                logger.error(f"❌ Failed to update user {anilist_username} ({discord_id}): {e}")
                continue

    logger.info("🎉 Finished updating all users!")

# ---------------------------------------------------
# Run script
# ---------------------------------------------------
if __name__ == "__main__":
    asyncio.run(update_all_users())
