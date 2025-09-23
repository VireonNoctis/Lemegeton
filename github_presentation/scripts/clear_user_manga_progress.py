import asyncio
import aiosqlite
from config import DB_PATH


async def clear_user_manga_progress():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM user_manga_progress")
        await db.commit()
        print("[INFO] Cleared all entries from user_manga_progress table.")

if __name__ == "__main__":
    asyncio.run(clear_user_manga_progress())
