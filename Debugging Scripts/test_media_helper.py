import asyncio
import aiohttp
from media_helper import fetch_user_progress, fetch_media, progress_cache, CACHE_TTL
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Test users (discord username, some dummy fields)
test_users = [
    (1, 111, "TestUser1"),
    (2, 222, "TestUser2"),
]

async def test_fetch_user_progress():
    async with aiohttp.ClientSession() as session:
        media_id = 16498  # Example media ID
        logger.info("Testing first fetch (should call API)...")
        results1 = await asyncio.gather(*(fetch_user_progress(session, user[2], media_id) for user in test_users))
        for res in results1:
            logger.info("Result: %s", res)

        logger.info("Testing second fetch (should use cache)...")
        results2 = await asyncio.gather(*(fetch_user_progress(session, user[2], media_id) for user in test_users))
        for res in results2:
            logger.info("Result (cached): %s", res)

        # Ensure cache keys exist
        logger.debug("Cache contents: %s", progress_cache)

async def test_fetch_media():
    async with aiohttp.ClientSession() as session:
        # Test Anime
        anime_embed = await fetch_media(session, "ANIME", "Attack on Titan", test_users)
        if anime_embed:
            logger.info("✅ ANIME fetched successfully!")
            logger.info("Title: %s", anime_embed.title)
            logger.info("Fields: %s", [(f.name, f.value) for f in anime_embed.fields])
        else:
            logger.warning("❌ Failed to fetch ANIME")

        # Test Manga
        manga_embed = await fetch_media(session, "MANGA", "One Piece", test_users)
        if manga_embed:
            logger.info("✅ MANGA fetched successfully!")
            logger.info("Title: %s", manga_embed.title)
            logger.info("Fields: %s", [(f.name, f.value) for f in manga_embed.fields])
        else:
            logger.warning("❌ Failed to fetch MANGA")

async def main():
    await test_fetch_user_progress()
    await test_fetch_media()

if __name__ == "__main__":
    asyncio.run(main())
