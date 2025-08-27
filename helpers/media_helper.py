import discord
import aiohttp
import asyncio
import re
import logging
from typing import Optional, List, Tuple, Dict

# -----------------------------
# Logging setup
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger("MediaHelper")

# -----------------------------
# User progress caching
# -----------------------------
# Cache: key=(username, media_id), value=(username, status, progress, timestamp)
progress_cache: Dict[Tuple[str, int], Tuple[str, str, int, float]] = {}
CACHE_TTL = 300  # seconds


async def fetch_user_progress(session: aiohttp.ClientSession, username: str, media_id: int) -> Optional[Tuple[str, str, int]]:
    """Fetch individual user's progress for a media ID. Uses cache."""
    now = asyncio.get_event_loop().time()
    key = (username, media_id)

    # Use cache if recent
    if key in progress_cache:
        cached = progress_cache[key]
        if now - cached[3] < CACHE_TTL:
            logger.info(f"Using cached progress for {username} (media {media_id})")
            return cached[:3]

    query = """
    query ($username: String, $mediaId: Int) {
        MediaList(userName: $username, mediaId: $mediaId) {
            status
            progress
        }
    }
    """
    variables = {"username": username, "mediaId": media_id}

    try:
        async with session.post("https://graphql.anilist.co", json={"query": query, "variables": variables}) as resp:
            if resp.status != 200:
                logger.warning(f"Failed to fetch progress for {username} (media {media_id}): HTTP {resp.status}")
                return None
            data = await resp.json()
            media_list = data.get("data", {}).get("MediaList")
            if media_list and media_list.get("status"):
                result = (username, media_list["status"], media_list.get("progress", "N/A"))
                progress_cache[key] = (*result, now)
                return result
    except aiohttp.ClientError as e:
        logger.warning(f"Client error fetching progress for {username} (media {media_id}): {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching progress for {username} (media {media_id}): {e}")

    return None


async def fetch_media(
    session: aiohttp.ClientSession,
    media_type: str,
    query: str | int,
    users: Optional[List[Tuple[int, str, str]]] = None,
    max_description: int = 500
) -> Optional[discord.Embed]:
    """Fetch Anime/Manga from AniList API and return a Discord Embed with user progress."""

    variables = {"id": int(query)} if isinstance(query, int) or (isinstance(query, str) and query.isdigit()) else {"search": query}
    graphql_query = """
    query ($search: String, $id: Int, $type: MediaType) {
        Media(search: $search, id: $id, type: $type) {
            id
            title { romaji english native }
            description(asHtml: false)
            chapters
            volumes
            episodes
            status
            genres
            averageScore
            siteUrl
            source
            coverImage { large medium }
        }
    }
    """

    try:
        async with session.post(
            "https://graphql.anilist.co",
            json={"query": graphql_query, "variables": {**variables, "type": media_type}},
        ) as resp:
            if resp.status != 200:
                logger.warning(f"Failed to fetch {media_type} '{query}': HTTP {resp.status}")
                return None

            data = await resp.json()
            media = data.get("data", {}).get("Media")
            if not media:
                logger.warning(f"No {media_type} found for query '{query}'")
                return None

            # Clean description
            description = media.get("description") or "No description available."
            description = re.sub(r"<br\s*/?>|</?i>|</?b>", "", description)
            if len(description) > max_description:
                description = description[:max_description] + "..."

            title_name = media["title"].get("english") or media["title"].get("romaji") or media["title"].get("native") or "Unknown"

            embed = discord.Embed(
                title=title_name,
                url=media.get("siteUrl"),
                description=f"{description}\n\n**Source:** {media.get('source', 'Unknown')}",
                color=discord.Color.blue()
            )

            # Add fields
            if media_type.upper() == "ANIME":
                embed.add_field(name="Episodes", value=media.get("episodes") or "Unknown", inline=True)
            else:
                embed.add_field(name="Chapters", value=media.get("chapters") or "Unknown", inline=True)
                embed.add_field(name="Volumes", value=media.get("volumes") or "Unknown", inline=True)

            embed.add_field(name="Status", value=media.get("status") or "Unknown", inline=True)
            embed.add_field(name="Genres", value=", ".join(media.get("genres") or []) or "Unknown", inline=False)
            embed.add_field(name="Average Score", value=media.get("averageScore") or "N/A", inline=True)

            cover_url = media.get("coverImage", {}).get("large") or media.get("coverImage", {}).get("medium")
            if cover_url:
                embed.set_thumbnail(url=cover_url)

            # Fetch user progress
            if users:
                tasks = [fetch_user_progress(session, user[2], media["id"]) for user in users]
                progress_results = await asyncio.gather(*tasks)

                progress_label = "ep" if media_type.upper() == "ANIME" else "chap"
                status_groups: Dict[str, List[str]] = {}
                for item in progress_results:
                    if not item:
                        continue
                    username, user_status, user_prog = item
                    if user_status.upper() == "COMPLETED":
                        continue
                    status_groups.setdefault(user_status, []).append(f"`{username}`: {progress_label} `{user_prog}`")

                grouped_text = ""
                for s, user_list in status_groups.items():
                    grouped_text += f"`{s}`:\n" + "\n".join(user_list) + "\n\n"

                if grouped_text:
                    if len(grouped_text) > 1024:
                        grouped_text = grouped_text[:1020] + "…"
                    embed.add_field(name="AniList Progress", value=grouped_text.strip(), inline=False)

            return embed

    except Exception as e:
        logger.error(f"Error fetching {media_type}: {e}")
        return None


# -----------------------------
# Fetch AniList User Media Entries
# -----------------------------
ANILIST_API_URL = "https://graphql.anilist.co"

USER_MANGA_QUERY = """
query ($username: String) {
  MediaListCollection(userName: $username, type: MANGA) {
    lists {
      entries {
        mediaId
        status
        score
        progress
        media { chapters }
      }
    }
  }
}
"""

USER_ANIME_QUERY = USER_MANGA_QUERY.replace("MANGA", "ANIME")


async def fetch_anilist_entries(username: str, media_type: str) -> List[Dict]:
    """
    Fetches all media entries for a user from AniList.
    
    Args:
        username: The AniList username.
        media_type: Either "MANGA" or "ANIME".

    Returns:
        A list of dicts containing mediaId, status, score, progress, chapters.
    """
    query = USER_MANGA_QUERY if media_type.upper() == "MANGA" else USER_ANIME_QUERY
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(ANILIST_API_URL, json={"query": query, "variables": {"username": username}}) as resp:
                if resp.status != 200:
                    logger.warning(f"AniList API request failed [{resp.status}] for {username} ({media_type})")
                    return []

                data = await resp.json()
                entries = []
                for group in data.get("data", {}).get("MediaListCollection", {}).get("lists", []):
                    for entry in group.get("entries", []):
                        chapters = entry.get("media", {}).get("chapters") or 0
                        entries.append({
                            "id": entry.get("mediaId"),
                            "status": entry.get("status"),
                            "score": entry.get("score") or 0,
                            "progress": entry.get("progress") or 0,
                            "chapters": chapters
                        })
                return entries

        except aiohttp.ClientError as e:
            logger.warning(f"Client error fetching entries for {username} ({media_type}): {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching entries for {username} ({media_type}): {e}")
            return []
