import random
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

# -----------------------------
# Fetch media by title (for /search_similar)
# -----------------------------
async def fetch_media_by_title(session: aiohttp.ClientSession, title: str, media_type: str):
    """
    Fetch a single media entry from AniList by title.
    Returns the media object with relations (prequels, sequels, spin-offs, etc.)
    """
    query = '''
    query ($search: String, $type: MediaType) {
      Media(search: $search, type: $type) {
        id
        title {
          romaji
          english
          native
        }
        format
        status
        relations {
          edges {
            relationType
            node {
              id
              title {
                romaji
                english
                native
              }
              format
              status
            }
          }
        }
      }
    }
    '''
    variables = {"search": title, "type": media_type}

    url = "https://graphql.anilist.co"

    try:
        async with session.post(url, json={"query": query, "variables": variables}) as resp:
            if resp.status != 200:
                logger.warning(f"Failed to fetch media by title '{title}' ({media_type}): HTTP {resp.status}")
                return None
            data = await resp.json()
            return data.get("data", {}).get("Media")
    except aiohttp.ClientError as e:
        logger.warning(f"Client error fetching media by title '{title}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching media by title '{title}': {e}")
        return None




# -----------------------------
# Fetch AniList User Stats
# -----------------------------
async def fetch_user_stats(username: str) -> dict:
    """
    Fetch a user's overall AniList stats (anime + manga).
    Includes counts, completed, average score, and genres.
    """
    query = """
    query ($username: String) {
      User(name: $username) {
        id
        name
        statistics {
          anime {
            count
            chaptersRead
            meanScore
            genres {
              genre
              count
            }
            statuses {
              status
              count
            }
            scores {
              score
              count
            }
          }
          manga {
            count
            chaptersRead
            meanScore
            genres {
              genre
              count
            }
            statuses {
              status
              count
            }
            scores {
              score
              count
            }
          }
        }
      }
    }
    """
    variables = {"username": username}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(ANILIST_API_URL, json={"query": query, "variables": variables}) as resp:
                if resp.status != 200:
                    logger.warning(f"AniList API request failed [{resp.status}] for stats of {username}")
                    return {}
                return await resp.json()
        except aiohttp.ClientError as e:
            logger.warning(f"Client error fetching stats for {username}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching stats for {username}: {e}")
            return {}

 # -----------------------------
# Fetch AniList Media with Recommendations
# -----------------------------
async def fetch_media_with_recommendations(session: aiohttp.ClientSession, media_id: int, media_type: str):
    """
    Fetch a media entry with its recommendations from AniList.
    Returns the raw Media object (not an Embed).
    """
    query = """
    query ($id: Int, $type: MediaType) {
      Media(id: $id, type: $type) {
        id
        title {
          romaji
          english
          native
        }
        recommendations {
          edges {
            node {
              rating
              mediaRecommendation {
                id
                title {
                  romaji
                  english
                  native
                }
              }
            }
          }
        }
      }
    }
    """
    variables = {"id": media_id, "type": media_type}

    try:
        async with session.post("https://graphql.anilist.co", json={"query": query, "variables": variables}) as resp:
            if resp.status != 200:
                logger.warning(f"AniList API request failed [{resp.status}] for {media_id} ({media_type})")
                return None
            data = await resp.json()
            return data.get("data", {}).get("Media")
    except aiohttp.ClientError as e:
        logger.warning(f"Client error fetching recommendations for {media_id} ({media_type}): {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching recommendations for {media_id} ({media_type}): {e}")
        return None

# Fetch Completely Random Media
# -----------------------------
async def fetch_random_media(media_type: str = "ANIME") -> Optional[discord.Embed]:
    """
    Fetch a completely random Anime, Manga, or Light Novel (LN) from AniList.
    """
    async with aiohttp.ClientSession() as session:
        for _ in range(15):
            random_id = random.randint(1, 180000)

            if media_type in ["ANIME", "MANGA"]:
                embed = await fetch_media(session, media_type, random_id)
                if embed:
                    return embed

            if media_type == "LN":
                query = """
                query ($id: Int) {
                  Media(id: $id, type: MANGA) {
                    id
                    format
                    title { romaji english native }
                    description(asHtml: false)
                    coverImage { large medium }
                    siteUrl
                  }
                }
                """
                try:
                    async with session.post("https://graphql.anilist.co", json={"query": query, "variables": {"id": random_id}}) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        media = data.get("data", {}).get("Media")
                        if not media or media.get("format") != "NOVEL":
                            continue

                        title_name = media["title"].get("english") or media["title"].get("romaji") or media["title"].get("native") or "Unknown"
                        description = media.get("description") or "No description available."
                        description = re.sub(r"<br\s*/?>|</?i>|</?b>", "", description)
                        if len(description) > 500:
                            description = description[:500] + "..."

                        embed = discord.Embed(
                            title=title_name,
                            url=media.get("siteUrl"),
                            description=description,
                            color=discord.Color.blue()
                        )

                        cover_url = media.get("coverImage", {}).get("large") or media.get("coverImage", {}).get("medium")
                        if cover_url:
                            embed.set_thumbnail(url=cover_url)

                        return embed
                except Exception as e:
                    logger.error(f"Error fetching random LN: {e}")
                    continue

# -----------------------------
# Fetch AniList Watchlist (Anime + Manga)
# -----------------------------
WATCHLIST_CACHE: Dict[str, Tuple[dict, float]] = {}
WATCHLIST_CACHE_TTL = 300  # seconds

WATCHLIST_QUERY = """
query ($username: String) {
  anime: MediaListCollection(userName: $username, type: ANIME, status_in: [CURRENT, REPEATING]) {
    lists {
      entries {
        progress
        media {
          id
          title {
            romaji
            english
            native
          }
          episodes
          siteUrl
        }
      }
    }
  }
  manga: MediaListCollection(userName: $username, type: MANGA, status_in: [CURRENT, REPEATING]) {
    lists {
      entries {
        progress
        media {
          id
          title {
            romaji
            english
            native
          }
          chapters
          format
          siteUrl
        }
      }
    }
  }
}
"""

async def fetch_watchlist(username: str) -> Optional[dict]:
    """
    Fetches a user's current anime + manga watchlist from AniList.

    Args:
        username (str): AniList username.

    Returns:
        dict: {
            "anime": [ ... ],
            "manga": [ ... ]
        }
        or None if fetch failed.
    """
    now = asyncio.get_event_loop().time()

    # ✅ Use cache if available
    if username in WATCHLIST_CACHE:
        cached_data, cached_time = WATCHLIST_CACHE[username]
        if now - cached_time < WATCHLIST_CACHE_TTL:
            logger.info(f"Using cached watchlist for {username}")
            return cached_data

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                ANILIST_API_URL,
                json={"query": WATCHLIST_QUERY, "variables": {"username": username}},
            ) as resp:
                # ❌ Handle 404 (user not found)
                if resp.status == 404:
                    logger.warning(f"AniList user not found: {username}")
                    return None

                # ❌ Handle 429 (rate limit)
                if resp.status == 429:
                    logger.warning(f"Rate limited by AniList for {username}")
                    return None

                # ❌ Handle other HTTP errors
                if resp.status != 200:
                    logger.warning(f"AniList watchlist fetch failed ({resp.status}) for {username}")
                    return None

                data = await resp.json()
                result = {
                    "anime": data.get("data", {}).get("anime", {}).get("lists", []),
                    "manga": data.get("data", {}).get("manga", {}).get("lists", []),
                }

                # ✅ Cache result
                WATCHLIST_CACHE[username] = (result, now)
                return result

        except aiohttp.ClientError as e:
            logger.warning(f"Client error fetching watchlist for {username}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching watchlist for {username}: {e}")
            return None


        return None