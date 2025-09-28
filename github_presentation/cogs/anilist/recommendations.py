import os
import json
import re
import time
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from typing import Dict, Tuple, List, Optional, Callable, Awaitable, Any
import random

from config import CHANNEL_ID
from database import get_user_guild_aware

logger = logging.getLogger("Recommendations")
logger.setLevel(logging.INFO)

# Ensure logs directory exi
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "recommendations.log")

# Avoid adding duplicate handlers on reloads
# Avoid duplicate file handlers on reload; try file handler, fallback to stream
if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == os.path.abspath(LOG_FILE)
           for h in logger.handlers):
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
        logger.addHandler(file_handler)
    except Exception:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
        logger.addHandler(stream_handler)
    logger.info("File handler added for logging.")
else:
    logger.info("File handler already exists, skipping addition.")
# Also keep console output
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(stream_handler)

ANILIST_API_URL = "https://graphql.anilist.co"

# Persistent cache configuration
RECOMMENDATION_CACHE_FILE = "data/recommendation_cache.json"
POPULAR_TITLES_CACHE_FILE = "data/popular_titles_cache.json"

# Global cache for recommendation totals (id -> count, timestamp)
RECOMMENDATION_CACHE = {}
CACHE_DURATION = 86400  # 24 hour cache (increased from 1 hour)

# Popular titles cache - tracks commonly recommended titles
POPULAR_TITLES_CACHE = set()
CACHE_UPDATE_THRESHOLD = 100  # Update popular cache every 100 recommendations

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

def load_recommendation_cache():
    """Load recommendation cache from persistent storage"""
    global RECOMMENDATION_CACHE
    try:
        if os.path.exists(RECOMMENDATION_CACHE_FILE):
            with open(RECOMMENDATION_CACHE_FILE, "r", encoding="utf-8") as f:
                cache_data = json.load(f)
                # Convert string keys back to integers and validate timestamps
                current_time = time.time()
                for str_key, (count, timestamp) in cache_data.items():
                    # Only load non-expired entries
                    if current_time - timestamp < CACHE_DURATION:
                        RECOMMENDATION_CACHE[int(str_key)] = (count, timestamp)
                logger.info(f"Loaded {len(RECOMMENDATION_CACHE)} valid cache entries from persistent storage")
        else:
            logger.info("No existing recommendation cache file found, starting fresh")
    except Exception as e:
        logger.error(f"Failed to load recommendation cache: {e}")
        RECOMMENDATION_CACHE = {}

def save_recommendation_cache():
    """Save recommendation cache to persistent storage"""
    try:
        # Clean expired entries before saving
        current_time = time.time()
        cleaned_cache = {
            str(media_id): (count, timestamp) 
            for media_id, (count, timestamp) in RECOMMENDATION_CACHE.items()
            if current_time - timestamp < CACHE_DURATION
        }
        
        # Atomic write using temporary file
        temp_file = RECOMMENDATION_CACHE_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(cleaned_cache, f, indent=2)
        os.replace(temp_file, RECOMMENDATION_CACHE_FILE)
        logger.debug(f"Saved {len(cleaned_cache)} cache entries to persistent storage")
    except Exception as e:
        logger.error(f"Failed to save recommendation cache: {e}")

def load_popular_titles_cache():
    """Load popular titles cache from persistent storage"""
    global POPULAR_TITLES_CACHE
    try:
        if os.path.exists(POPULAR_TITLES_CACHE_FILE):
            with open(POPULAR_TITLES_CACHE_FILE, "r", encoding="utf-8") as f:
                popular_list = json.load(f)
                POPULAR_TITLES_CACHE = set(popular_list)
                logger.info(f"Loaded {len(POPULAR_TITLES_CACHE)} popular titles from persistent storage")
        else:
            logger.info("No existing popular titles cache file found, starting fresh")
    except Exception as e:
        logger.error(f"Failed to load popular titles cache: {e}")
        POPULAR_TITLES_CACHE = set()

def save_popular_titles_cache():
    """Save popular titles cache to persistent storage"""
    try:
        # Convert set to list for JSON serialization
        popular_list = list(POPULAR_TITLES_CACHE)
        
        # Atomic write using temporary file
        temp_file = POPULAR_TITLES_CACHE_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(popular_list, f, indent=2)
        os.replace(temp_file, POPULAR_TITLES_CACHE_FILE)
        logger.debug(f"Saved {len(popular_list)} popular titles to persistent storage")
    except Exception as e:
        logger.error(f"Failed to save popular titles cache: {e}")

# Load persistent cache data on module import
load_recommendation_cache()
load_popular_titles_cache()

class Recommendations(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Recommendations cog initialized with persistent cache system")

    def cog_unload(self):
        """Save caches when cog is unloaded"""
        logger.info("Saving recommendation caches before cog unload...")
        save_recommendation_cache()
        save_popular_titles_cache()
        logger.info("Recommendation caches saved successfully")

    def _format_description(self, description: str) -> str:
        """Format description text for embed"""
        if not description or description == "No description available.":
            return "No description available."
        
        # Remove HTML tags and truncate
        clean_desc = re.sub('<[^<]+?>', '', description)
        return clean_desc[:500] + "..." if len(clean_desc) > 500 else clean_desc
    
    def _get_category_color(self, category: str) -> discord.Color:
        """Get color for category"""
        colors = {
            'Manga': discord.Color.blue(),
            'Manhwa': discord.Color.red(), 
            'Manhua': discord.Color.gold()
        }
        return colors.get(category, discord.Color.blurple())

    async def _check_anilist_user_exists(self, username: str) -> bool:
        """Check if an AniList user exists using a simple query."""
        query = """
        query ($username: String) {
          User(name: $username) {
            id
            name
          }
        }
        """
        variables = {"username": username}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(ANILIST_API_URL, json={"query": query, "variables": variables}) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        user_data = data.get("data", {}).get("User")
                        return user_data is not None
                    else:
                        logger.debug(f"User existence check returned {resp.status} for '{username}'")
                        return False
        except Exception as e:
            logger.error(f"Error checking if user '{username}' exists: {e}")
            return False

    async def _fetch_user_manga_with_recs(self, username: str, per_page: int = 50) -> List[dict]:
        """
        Fetch user's manga list entries including media.recommendations.
        Returns list of entries: {score, status, media:{id, title:{romaji,english}, recommendations:{edges:[{node:{mediaRecommendation:{...}, votes?}}]}}}
        Uses MediaListCollection to avoid Page-based replies/perPage issues and logs detailed errors.
        """
        results = []
        query = """
        query ($username: String) {
          MediaListCollection(userName: $username, type: MANGA) {
            lists {
              entries {
                score
                status
                media {
                  id
                  title { romaji english }
                  countryOfOrigin
                  recommendations {
                    edges {
                      node {
                        mediaRecommendation {
                          id
                          title { romaji english }
                          countryOfOrigin
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        variables = {"username": username}
        async with aiohttp.ClientSession() as session:
            logger.info(f"Fetching MediaListCollection for AniList user '{username}'")
            try:
                async with session.post(ANILIST_API_URL, json={"query": query, "variables": variables}) as resp:
                    text = await resp.text()
                    if resp.status != 200:
                        try:
                            body = json.loads(text)
                        except Exception:
                            body = text
                        
                        # Special handling for 404 user not found
                        if resp.status == 404:
                            logger.warning(f"AniList user '{username}' not found (404): {body}")
                        else:
                            logger.warning(f"AniList API returned {resp.status} for user '{username}': {body}")
                        return None  # Signal that user doesn't exist or API error occurred

                    try:
                        data = json.loads(text)
                    except Exception as e:
                        logger.exception(f"Failed to decode AniList JSON response for '{username}': {e}")
                        return []

                    if "errors" in data:
                        errors = data.get("errors", [])
                        # Check if it's a "User not found" error
                        user_not_found = any(
                            error.get("message", "").lower() == "user not found" or 
                            error.get("status") == 404 
                            for error in errors
                        )
                        
                        if user_not_found:
                            logger.warning(f"AniList user '{username}' not found: {errors}")
                            return None  # Signal user doesn't exist
                        else:
                            logger.warning(f"AniList GraphQL errors for '{username}': {errors}")
                            return []  # Signal API error but user might exist

                    collection = data.get("data", {}).get("MediaListCollection", {})
                    lists = collection.get("lists", []) or []
                    total_entries = 0
                    total_with_recs = 0
                    for group in lists:
                        for entry in group.get("entries", []):
                            total_entries += 1
                            media = entry.get("media", {}) or {}
                            recs = []
                            for edge in (media.get("recommendations", {}).get("edges") or []):
                                node = edge.get("node") or {}
                                mr = node.get("mediaRecommendation")
                                if mr:
                                    # capture countryOfOrigin for categorisation (may be None)
                                    recs.append({"media": mr, "country": mr.get("countryOfOrigin")})
                            if recs:
                                total_with_recs += 1
                            results.append({
                                "score": entry.get("score") or 0,
                                "status": (entry.get("status") or "").upper(),
                                "media": {
                                    "id": media.get("id"),
                                    "title": media.get("title") or {},
                                    "recommendations": {"nodes": recs}
                                }
                            })
                    logger.info(f"Fetched {len(results)} entries for '{username}' (raw entries: {total_entries}, with recommendations: {total_with_recs})")
            except aiohttp.ClientError as e:
                logger.exception(f"HTTP error fetching AniList data for '{username}': {e}")
            except Exception as e:
                logger.exception(f"Unexpected error fetching AniList data for '{username}': {e}")

        return results

    async def _fetch_global_rec_count_for_media(self, session: aiohttp.ClientSession, media_id: int) -> int:
        """
        Query AniList Media(id){ recommendations.pageInfo.total } with robust retry/backoff.
        Logs rate-limit (429) events and uses Retry-After when present. Returns 0 on permanent failure.
        """
        query = """
        query ($id: Int) {
          Media(id: $id, type: MANGA) {
            id
            recommendations {
              pageInfo { total }
            }
          }
        }
        """
        variables = {"id": media_id}
        max_retries = 6
        backoff_base = 1.5

        for attempt in range(1, max_retries + 1):
            try:
                async with session.post(ANILIST_API_URL, json={"query": query, "variables": variables}) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        try:
                            data = json.loads(text)
                        except Exception as e:
                            logger.debug(f"JSON decode error for media {media_id}: {e}")
                            return 0
                        media = data.get("data", {}).get("Media")
                        if not media:
                            return 0
                        page_info = media.get("recommendations", {}).get("pageInfo", {})
                        total = page_info.get("total") or 0
                        return int(total)

                    # Rate limited -> use Retry-After header if provided, otherwise exponential backoff + jitter
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                wait = float(retry_after)
                            except Exception:
                                wait = backoff_base * (2 ** (attempt - 1))
                        else:
                            # exponential backoff with jitter
                            base_wait = backoff_base * (2 ** (attempt - 1))
                            jitter = random.uniform(0, base_wait * 0.25)
                            wait = base_wait + jitter
                        logger.warning(f"Rate limited (429) fetching rec count for {media_id}. Attempt {attempt}/{max_retries}. Waiting {wait:.1f}s before retry.")
                        await asyncio.sleep(wait)
                        continue

                    # 5xx server errors -> retry with backoff
                    if 500 <= resp.status < 600 and attempt < max_retries:
                        base_wait = backoff_base * (2 ** (attempt - 1))
                        jitter = random.uniform(0, base_wait * 0.25)
                        wait = base_wait + jitter
                        logger.debug(f"Server error {resp.status} for media {media_id}. Attempt {attempt}/{max_retries}. Retrying after {wait:.1f}s.")
                        await asyncio.sleep(wait)
                        continue

                    # Non-retryable or exhausted
                    try:
                        body = json.loads(text)
                    except Exception:
                        body = text
                    logger.debug(f"Failed to fetch global rec count for {media_id}: HTTP {resp.status} {body}")
                    return 0

            except aiohttp.ClientError as e:
                if attempt < max_retries:
                    base_wait = backoff_base * (2 ** (attempt - 1))
                    jitter = random.uniform(0, base_wait * 0.25)
                    wait = base_wait + jitter
                    logger.debug(f"HTTP client error for {media_id}: {e}. Attempt {attempt}/{max_retries}. Retrying after {wait:.1f}s.")
                    await asyncio.sleep(wait)
                    continue
                logger.debug(f"HTTP client error for {media_id} (final): {e}")
                return 0
            except Exception as e:
                logger.debug(f"Unexpected error fetching rec count for {media_id}: {e}")
                return 0

        logger.debug(f"Exhausted retries fetching rec count for {media_id}")
        return 0

    async def _fetch_global_votes_for_candidates(
        self,
        candidate_ids: List[int],
        batch_size: int = 3,
        interval: float = 2.0,
        progress_cb: Optional[Callable[[int, int], Awaitable[Any]]] = None
    ) -> Dict[int, int]:
        """
        Fetch global recommendation counts for candidate media IDs in batches.
        - Sends up to `batch_size` requests concurrently, then waits `interval` seconds before the next batch.
        - Ensures a steady rate of requests (e.g. 3 requests every 2 seconds).
        - Calls progress_cb(processed, total) after each completed fetch (if provided).
        """
        results: Dict[int, int] = {}
        ids_to_fetch = list(candidate_ids)
        total = len(ids_to_fetch)
        logger.info(f"Fetching global recommendation totals for {total} candidates (batch_size={batch_size}, interval={interval}s).")

        processed = 0

        async with aiohttp.ClientSession() as session:
            for start in range(0, total, batch_size):
                batch = ids_to_fetch[start:start + batch_size]
                logger.debug(f"Processing batch {start // batch_size + 1}: {len(batch)} candidates.")
                # Launch batch requests concurrently
                tasks = [asyncio.create_task(self._fetch_global_rec_count_for_media(session, mid)) for mid in batch]
                try:
                    results_list = await asyncio.gather(*tasks)
                except Exception as e:
                    # if a batch-level failure occurs, mark those ids with 0 and continue
                    logger.debug(f"Batch fetch error: {e}")
                    results_list = [0] * len(batch)

                # Store results and update progress
                for mid, val in zip(batch, results_list):
                    results[mid] = val or 0
                    if results[mid] == 0:
                        logger.debug(f"No global rec total returned for {mid} (0).")
                    processed += 1
                    if progress_cb:
                        try:
                            await progress_cb(processed, total)
                        except Exception as e:
                            logger.debug(f"Progress callback error: {e}")

                # If there are more batches to process, wait the configured interval
                if start + batch_size < total:
                    logger.debug(f"Sleeping for {interval}s before next batch to respect rate limits.")
                    await asyncio.sleep(interval)

        logger.info(f"Fetched global rec totals for {len(results)} candidates (requested {len(candidate_ids)}). Rate-limited/exhausted hits may be reflected as 0 totals.")
        return results

    @app_commands.command(name="recommendations", description="Top recommendations based on a user's highly-rated manga (>=7/10)")
    @app_commands.describe(member="Discord member (defaults to you)")
    async def recommendations(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        # Send ephemeral message with wait time estimate
        await interaction.response.send_message(
            "🔄 **Generating your recommendations...**\n\n"
            "📊 Analyzing your highly-rated manga (8.0+ scores)\n"
            "🌐 Fetching global recommendation data from AniList\n"
            "🎯 Building personalized suggestions\n\n"
            "⏰ **Please wait up to 30 seconds** - High-quality recommendations take time!",
            ephemeral=True
        )
        target = member or interaction.user

        user_row = await get_user_guild_aware(target.id, interaction.guild_id)
        if not user_row:
            await interaction.followup.send(f"⚠️ No AniList linked for {target.mention}.")
            return
        anilist_username = None
        try:
            # Try dictionary access first (if using Row objects)
            anilist_username = user_row["anilist_username"]
        except (TypeError, KeyError):
            try:
                # Fallback to index access - anilist_username is at index 4
                anilist_username = user_row[4]  # Fixed: was [3], should be [4]
            except (IndexError, TypeError):
                anilist_username = None

        if not anilist_username:
            await interaction.followup.send(f"⚠️ No AniList username set for {target.mention}.")
            return

        logger.info(f"Recommendations command invoked for Discord user {target} -> AniList '{anilist_username}'")

        entries = await self._fetch_user_manga_with_recs(anilist_username)
        if entries is None:
            # Check if it's a user not found error by trying a simple user existence check
            user_exists = await self._check_anilist_user_exists(anilist_username)
            if not user_exists:
                embed = discord.Embed(
                    title="❌ AniList User Not Found",
                    description=f"The AniList user **{anilist_username}** could not be found.\n\n"
                               f"**Possible reasons:**\n"
                               f"• Username doesn't exist on AniList\n"
                               f"• Username spelling/capitalization is incorrect\n"
                               f"• Profile is private or deactivated\n\n"
                               f"**Solutions:**\n"
                               f"• Check the spelling of your AniList username\n"
                               f"• Make sure your profile is public\n"
                               f"• Use `/login` to update your AniList username",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="📝 Update Username",
                    value="Use the `/login` command to register or update your AniList username.",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send("⚠️ Error fetching the user's manga list. Please try again later.")
            return
        if not entries:
            embed = discord.Embed(
                title="📭 Empty Manga List",
                description=f"No manga entries found for **{anilist_username}**.\n\n"
                           f"**To get recommendations:**\n"
                           f"• Add some manga to your AniList\n"
                           f"• Rate them (7+ out of 10 for best results)\n"
                           f"• Make sure your list is public",
                color=discord.Color.orange()
            )
            embed.add_field(
                name="🔗 AniList Profile",
                value=f"[Visit your profile](https://anilist.co/user/{anilist_username})",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return

        logger.info(f"Total entries received from AniList for '{anilist_username}': {len(entries)}")

        # Build quick map of user's current media ids/status for exclusion checks
        user_media_ids = set()
        user_media_status = {}
        for e in entries:
            media = e.get("media") or {}
            mid = media.get("id")
            if mid:
                user_media_ids.add(mid)
                user_media_status[mid] = (e.get("status") or "").upper()
        logger.info(f"User '{anilist_username}' has {len(user_media_ids)} titles on their list (includes Planning).")

        # Select the user's top-rated entries (normalize 0-10 -> 0-100 by multiplying <=10 scores by 10)
        def _normalize_score(raw):
            try:
                f = float(raw)
            except Exception:
                return 0.0
            # treat scores <= 10 as 0-10 scale, convert to 0-100
            return f * 10.0 if f <= 10.0 else f

        scored_entries = [e for e in entries if (e.get("score") is not None and str(e.get("score")).strip() != "")]
        scored_entries = [e for e in scored_entries if _normalize_score(e.get("score")) > 0]
        scored_entries.sort(key=lambda x: _normalize_score(x.get("score")), reverse=True)
        top_n = 100
        top_entries = scored_entries[:top_n]
        logger.info(f"Selected top {len(top_entries)} rated entries (by normalized score) out of {len(scored_entries)} scored entries.")

        # AGGRESSIVE PRE-FILTER: Multiple criteria to drastically reduce API calls
        min_occurrences = 3  # Increased from 2 - only highly recommended titles
        min_score_threshold = 80  # Only from manga rated 8.0+ (80/100)
        
        # Filter by minimum score threshold first
        high_rated_entries = [e for e in top_entries if _normalize_score(e.get("score")) >= min_score_threshold]
        logger.info(f"Using {len(high_rated_entries)} high-rated entries (>= {min_score_threshold/10}) out of {len(top_entries)} top entries")
        
        # Use high-rated entries for recommendation tally
        tally: Dict[int, Dict[str, object]] = {}
        total_recs_considered = 0
        for e in high_rated_entries:  # Changed from top_entries to high_rated_entries
            media = e.get("media") or {}
            recs = (media.get("recommendations") or {}).get("nodes") or []
            for node in recs:
                rec_media = node.get("media") or {}
                rec_id = rec_media.get("id")
                if not rec_id:
                    continue
                # Allow titles on the user's list only if status == PLANNING
                if rec_id in user_media_ids and user_media_status.get(rec_id) != "PLANNING":
                    logger.debug(f"Skipping rec {rec_id} because it's already on {anilist_username}'s list (status={user_media_status.get(rec_id)})")
                    continue
                title_obj = rec_media.get("title") or {}
                title = title_obj.get("english") or title_obj.get("romaji") or f"#{rec_id}"
                country = rec_media.get("countryOfOrigin")

                total_recs_considered += 1
                if rec_id not in tally:
                    tally[rec_id] = {"occurrences": 0, "votes": 0, "title": title, "country": country}
                tally[rec_id]["occurrences"] += 1
                # votes will be filled by global lookup later (placeholder 0 for now)
                tally[rec_id]["votes"] += 0

        logger.info(f"Considered {total_recs_considered} recommendation entries across top {len(high_rated_entries)} high-rated titles.")
        logger.info(f"Unique recommended titles after excluding user's list: {len(tally)}")

        if not tally:
            await interaction.followup.send("No recommendations found from highly-rated manga (8.0+). Try rating more manga!")
            return

        # MULTI-STAGE FILTERING: Apply multiple filters to reduce API calls
        
        # Stage 1: Minimum occurrences filter
        filtered_tally = {mid: info for mid, info in tally.items() if info["occurrences"] >= min_occurrences}
        logger.info(f"Stage 1 - Occurrence filter: {len(filtered_tally)} candidates with >= {min_occurrences} occurrences")
        
        # Stage 2: Limit by popularity (top 50 by occurrences)
        if len(filtered_tally) > 50:
            sorted_by_occ = sorted(filtered_tally.items(), key=lambda kv: kv[1]["occurrences"], reverse=True)[:50]
            filtered_tally = dict(sorted_by_occ)
            logger.info(f"Stage 2 - Limited to top 50 by occurrence count: {len(filtered_tally)} candidates")
        
        # Stage 3: Country-based sampling (ensure variety)
        candidate_ids = list(filtered_tally.keys())
        if len(candidate_ids) > 30:
            # Sample evenly across countries to ensure variety
            manga_candidates = [mid for mid, info in filtered_tally.items() 
                              if (info.get("country") or "").upper() not in ("KOREA", "CHINA")]
            manhwa_candidates = [mid for mid, info in filtered_tally.items() 
                               if (info.get("country") or "").upper() in ("KOREA", "KR")]
            manhua_candidates = [mid for mid, info in filtered_tally.items() 
                               if (info.get("country") or "").upper() in ("CHINA", "CN")]
            
            # Take top 10 from each category (or all if less than 10)
            final_candidates = (
                manga_candidates[:10] + 
                manhwa_candidates[:10] + 
                manhua_candidates[:10]
            )
            
            # If still too many, take top by occurrences
            if len(final_candidates) > 30:
                final_sorted = sorted(final_candidates, 
                                    key=lambda mid: filtered_tally[mid]["occurrences"], 
                                    reverse=True)[:30]
                final_candidates = final_sorted
            
            # Update filtered_tally to only include final candidates
            filtered_tally = {mid: filtered_tally[mid] for mid in final_candidates if mid in filtered_tally}
            candidate_ids = final_candidates
            logger.info(f"Stage 3 - Country-balanced sampling: {len(candidate_ids)} final candidates")

        if not filtered_tally:
            # Emergency fallback: use top candidates by occurrence count
            candidates_by_occ = sorted(tally.items(), key=lambda kv: kv[1]["occurrences"], reverse=True)[:30]
            filtered_tally = dict(candidates_by_occ)
            candidate_ids = list(filtered_tally.keys())
            logger.info(f"Emergency fallback: using top {len(filtered_tally)} candidates by occurrence count")
        
        # Check cache first to reduce API calls + prioritize popular titles
        global POPULAR_TITLES_CACHE, RECOMMENDATION_CACHE
        import time
        current_time = time.time()
        cached_ids = []
        api_fetch_ids = []
        
        # Prioritize titles that are commonly recommended (likely to be cached)
        popular_candidates = [mid for mid in candidate_ids if mid in POPULAR_TITLES_CACHE]
        regular_candidates = [mid for mid in candidate_ids if mid not in POPULAR_TITLES_CACHE]
        
        # Process popular titles first (more likely to be cached)
        prioritized_candidates = popular_candidates + regular_candidates
        
        popular_cache_updated = False
        for mid in prioritized_candidates:
            if mid in RECOMMENDATION_CACHE:
                cached_count, cached_time = RECOMMENDATION_CACHE[mid]
                if current_time - cached_time < CACHE_DURATION:
                    filtered_tally[mid]["votes"] = cached_count
                    cached_ids.append(mid)
                    # Add to popular titles if high vote count
                    if cached_count > 10 and mid not in POPULAR_TITLES_CACHE:
                        POPULAR_TITLES_CACHE.add(mid)
                        popular_cache_updated = True
                else:
                    api_fetch_ids.append(mid)
            else:
                api_fetch_ids.append(mid)
        
        # Save popular titles cache if updated during cache hits
        if popular_cache_updated:
            save_popular_titles_cache()
        
        logger.info(f"Cache performance: {len(cached_ids)} cached, {len(api_fetch_ids)} need API calls")
        
        # SMART LIMIT: If still too many API calls, take only the most promising candidates
        if len(api_fetch_ids) > 20:
            # Sort API candidates by occurrence count and take top 20
            api_candidates_sorted = sorted(
                [(mid, filtered_tally[mid]["occurrences"]) for mid in api_fetch_ids],
                key=lambda x: x[1], 
                reverse=True
            )[:20]
            api_fetch_ids = [mid for mid, _ in api_candidates_sorted]
            logger.info(f"Limited API calls to top 20 candidates by occurrence: {len(api_fetch_ids)}")

        # Fetch global recommendation totals for remaining candidates
        candidate_ids = api_fetch_ids

        # fetch global totals with reduced batch size to avoid rate limiting
        if candidate_ids:
            global_votes_map = await self._fetch_global_votes_for_candidates(
                candidate_ids,
                batch_size=2,  # Reduced to avoid rate limiting
                interval=3.0,  # Increased to 3.0 seconds for safety
            )

            # Cache the results for future use and update popular titles
            current_time = time.time()
            cache_updated = False
            for mid, votes in global_votes_map.items():
                RECOMMENDATION_CACHE[mid] = (votes, current_time)
                cache_updated = True
                # Track popular titles for future prioritization
                if votes > 15:  # Highly recommended titles
                    POPULAR_TITLES_CACHE.add(mid)
            
            # Save caches to persistent storage if updated
            if cache_updated:
                save_recommendation_cache()
                save_popular_titles_cache()
            
            # Limit popular cache size to prevent memory bloat
            if len(POPULAR_TITLES_CACHE) > 1000:
                # Keep only the most popular titles
                popular_with_votes = [(mid, RECOMMENDATION_CACHE.get(mid, (0, 0))[0]) 
                                     for mid in POPULAR_TITLES_CACHE 
                                     if mid in RECOMMENDATION_CACHE]
                popular_sorted = sorted(popular_with_votes, key=lambda x: x[1], reverse=True)
                POPULAR_TITLES_CACHE = set(mid for mid, _ in popular_sorted[:800])
                logger.debug(f"Trimmed popular titles cache to {len(POPULAR_TITLES_CACHE)} entries")
                # Save after trimming
                save_popular_titles_cache()
        else:
            global_votes_map = {}

        # apply fetched global totals (fallback to occurrences when missing)
        # Merge filtered_tally results with original tally and apply global votes
        for mid, info in filtered_tally.items():
            if mid not in tally:
                tally[mid] = info
        
        # Apply global votes to all items
        for mid, info in tally.items():
            gv = global_votes_map.get(mid, 0)
            info["votes"] = gv if gv and gv > 0 else info["occurrences"]

        # sort by votes (global) then occurrences
        sorted_recs = sorted(tally.items(), key=lambda kv: (kv[1].get("votes", 0), kv[1].get("occurrences", 0)), reverse=True)[:10]

        logger.info("Top recommendations (top 10):")
        for idx, (mid, info) in enumerate(sorted_recs, start=1):
            logger.info(f"#{idx}: {info['title']} (id={mid}) — Votes: {info.get('votes',0)}, occurrences: {info.get('occurrences',0)}")

        # Split into categories by countryOfOrigin:
        manga_bucket = []   # Japan / unspecified -> Manga
        manhwa_bucket = []  # Korea -> Manhwa
        manhua_bucket = []  # China -> Manhua

        for mid, info in tally.items():
            country = (info.get("country") or "").upper()
            entry = (mid, info)
            if country in ("KOREA", "KR"):
                manhwa_bucket.append(entry)
            elif country in ("CHINA", "CN"):
                manhua_bucket.append(entry)
            else:
                # treat JAPAN and unknown as Manga
                manga_bucket.append(entry)

        # sort each bucket by votes then occurrences
        def sort_bucket(bucket):
            return sorted(bucket, key=lambda kv: (kv[1].get("votes", 0), kv[1].get("occurrences", 0)), reverse=True)[:10]

        top_manga = sort_bucket(manga_bucket)
        top_manhwa = sort_bucket(manhwa_bucket)
        top_manhua = sort_bucket(manhua_bucket)

        logger.info(f"Top sizes -> Manga: {len(top_manga)}, Manhwa: {len(top_manhwa)}, Manhua: {len(top_manhua)}")

        # Fetch detailed media information for each recommendation
        async def fetch_media_details(media_id: int) -> Dict:
            """Fetch detailed media information from AniList API for rich embeds"""
            query = """
            query ($id: Int) {
              Media(id: $id, type: MANGA) {
                id
                title { romaji english }
                description(asHtml: false)
                averageScore
                siteUrl
                status
                chapters
                volumes
                startDate { year month day }
                endDate { year month day }
                genres
                coverImage { large medium }
                bannerImage
                format
                countryOfOrigin
              }
            }
            """
            variables = {"id": media_id}
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(ANILIST_API_URL, json={"query": query, "variables": variables}) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data.get("data", {}).get("Media", {})
                        else:
                            logger.warning(f"Failed to fetch media details for ID {media_id}: HTTP {resp.status}")
                            return {}
            except Exception as e:
                logger.error(f"Error fetching media details for ID {media_id}: {e}")
                return {}

        # Enhanced recommendation data with media details
        async def enrich_recommendations(recommendations: List[tuple]) -> List[Dict]:
            """Enrich recommendation data with detailed media information"""
            enriched = []
            for idx, (media_id, info) in enumerate(recommendations):
                # Add delay between requests to prevent rate limiting
                if idx > 0:  # Skip delay for first request
                    await asyncio.sleep(2.0)
                
                media_details = await fetch_media_details(media_id)
                
                # Merge recommendation info with media details
                enriched_item = {
                    'id': media_id,
                    'votes': info.get('votes', 0),
                    'occurrences': info.get('occurrences', 0),
                    'title': info.get('title', 'Unknown'),
                    'details': media_details
                }
                enriched.append(enriched_item)
            
            return enriched

        # Create recommendation data without enriching details (lazy loading)
        def create_recommendation_data(recommendations: List[tuple]) -> List[Dict]:
            """Create recommendation data structure without fetching media details"""
            items = []
            for media_id, info in recommendations:
                item = {
                    'id': media_id,
                    'votes': info.get('votes', 0),
                    'occurrences': info.get('occurrences', 0),
                    'title': info.get('title', 'Unknown'),
                    'details': None  # Will be loaded on-demand
                }
                items.append(item)
            return items

        # Create lightweight recommendation data for all categories
        manga_data = create_recommendation_data(top_manga)
        manhwa_data = create_recommendation_data(top_manhwa)  
        manhua_data = create_recommendation_data(top_manhua)

        logger.info(f"Created recommendation data -> Manga: {len(manga_data)}, Manhwa: {len(manhwa_data)}, Manhua: {len(manhua_data)}")

        # Build browse-style embed for a single recommendation
        async def build_recommendation_embed(item: Dict, category: str, index: int, total: int, fetch_details_func) -> discord.Embed:
            """Build a rich embed for a single recommendation in browse style"""
            try:
                details = item.get('details', {})
                media_id = item.get('id')
                
                # If no details loaded yet, show loading embed first
                if not details:
                    # Category emoji mapping
                    category_emojis = {
                        'Manga': '📖',
                        'Manhwa': '🇰🇷', 
                        'Manhua': '🇨🇳'
                    }
                    
                    embed = discord.Embed(
                        title=f"{category_emojis.get(category, '📖')} Loading...",
                        description="🔄 Fetching detailed information...",
                        color=self._get_category_color(category)
                    )
                    
                    # Add basic recommendation stats
                    embed.add_field(
                        name="🔥 Recommendation Score", 
                        value=f"**Global votes:** {item.get('votes', 0)}\n**From {item.get('occurrences', 0)} similar tastes**",
                        inline=True
                    )
                    
                    # Footer with page info
                    embed.set_footer(
                        text=f"{category} Recommendation {index + 1} of {total} • Loading details...",
                        icon_url="https://anilist.co/img/icons/android-chrome-512x512.png"
                    )
                    
                    return embed
                
                # Build full embed with details
                title_obj = details.get('title', {})
                title = title_obj.get('english') or title_obj.get('romaji') or item.get('title', f'Unknown #{media_id}')
                
                # Category emoji mapping
                category_emojis = {
                    'Manga': '📖',
                    'Manhwa': '🇰🇷', 
                    'Manhua': '🇨🇳'
                }
                
                embed = discord.Embed(
                    title=f"{category_emojis.get(category, '📖')} {title}",
                    url=f"https://anilist.co/manga/{media_id}",
                    description=self._format_description(details.get('description', 'No description available.')),
                    color=self._get_category_color(category)
                )
                
                # Set cover image as thumbnail
                cover_url = details.get('coverImage', {}).get('large') or details.get('coverImage', {}).get('medium')
                if cover_url:
                    embed.set_thumbnail(url=cover_url)
                
                # Set banner image  
                banner_url = details.get('bannerImage')
                if banner_url:
                    embed.set_image(url=banner_url)
                
                # Add recommendation stats
                embed.add_field(
                    name="🔥 Recommendation Score", 
                    value=f"**Global votes:** {item.get('votes', 0)}\n**From {item.get('occurrences', 0)} similar tastes**",
                    inline=True
                )
                
                # Add AniList score
                avg_score = details.get('averageScore')
                if avg_score:
                    embed.add_field(name="⭐ Average Score", value=f"{avg_score}%", inline=True)
                
                # Add status
                status = details.get('status', 'Unknown')
                embed.add_field(name="📌 Status", value=status, inline=True)
                
                # Add chapters/volumes
                chapters = details.get('chapters', '?')
                volumes = details.get('volumes', '?')
                embed.add_field(name="📚 Chapters", value=str(chapters), inline=True)
                embed.add_field(name="📖 Volumes", value=str(volumes), inline=True)
                
                # Add format
                format_type = details.get('format', 'Unknown')
                embed.add_field(name="📑 Format", value=format_type, inline=True)
                
                # Add genres
                genres = details.get('genres', [])
                if genres:
                    genre_text = ", ".join(genres[:6])  # Limit to 6 genres to avoid overflow
                    if len(genres) > 6:
                        genre_text += f" (+{len(genres) - 6} more)"
                    embed.add_field(name="🎭 Genres", value=genre_text, inline=False)
                
                # Add publication dates
                start_date = details.get('startDate', {})
                end_date = details.get('endDate', {})
                if start_date and start_date.get('year'):
                    start_str = f"{start_date.get('year', '?')}-{start_date.get('month', '?')}-{start_date.get('day', '?')}"
                    end_str = "Ongoing"
                    if end_date and end_date.get('year'):
                        end_str = f"{end_date.get('year', '?')}-{end_date.get('month', '?')}-{end_date.get('day', '?')}"
                    
                    embed.add_field(name="📅 Published", value=f"**Start:** {start_str}\n**End:** {end_str}", inline=False)
                
                # Footer with page info
                embed.set_footer(
                    text=f"{category} Recommendation {index + 1} of {total} • Powered by AniList",
                    icon_url="https://anilist.co/img/icons/android-chrome-512x512.png"
                )
                
                return embed
                
            except Exception as e:
                logger.error(f"Error building recommendation embed: {e}")
                # Fallback embed
                embed = discord.Embed(
                    title=f"❌ Error loading {category} recommendation",
                    description="An error occurred while loading this recommendation.",
                    color=discord.Color.red()
                )
                embed.set_footer(text=f"{category} Recommendation {index + 1} of {total}")
                return embed

        # Recommendation navigation view with category buttons and lazy loading
        class RecommendationView(discord.ui.View):
            def __init__(self, manga_data: List[Dict], manhwa_data: List[Dict], manhua_data: List[Dict], username: str, fetch_details_func):
                super().__init__(timeout=300)  # 5 minute timeout
                self.manga_data = manga_data
                self.manhwa_data = manhwa_data
                self.manhua_data = manhua_data
                self.username = username
                self.fetch_details_func = fetch_details_func
                self.current_category = "Manga"
                self.current_index = 0
                
                # Set initial category to first non-empty category
                if not manga_data and manhwa_data:
                    self.current_category = "Manhwa"
                elif not manga_data and not manhwa_data and manhua_data:
                    self.current_category = "Manhua"
                
                self.update_buttons()
            
            def get_current_data(self) -> List[Dict]:
                if self.current_category == "Manga":
                    return self.manga_data
                elif self.current_category == "Manhwa":
                    return self.manhwa_data
                else:
                    return self.manhua_data
            
            async def ensure_details_loaded(self, item: Dict) -> Dict:
                """Ensure media details are loaded for the given item"""
                if item.get('details') is None:
                    # Fetch details on-demand
                    media_details = await self.fetch_details_func(item['id'])
                    item['details'] = media_details
                return item
            
            def update_buttons(self):
                """Update button states based on current category and available data"""
                self.clear_items()
                
                # Category selection buttons
                manga_style = discord.ButtonStyle.primary if self.current_category == "Manga" else discord.ButtonStyle.secondary
                manhwa_style = discord.ButtonStyle.primary if self.current_category == "Manhwa" else discord.ButtonStyle.secondary
                manhua_style = discord.ButtonStyle.primary if self.current_category == "Manhua" else discord.ButtonStyle.secondary
                
                manga_btn = discord.ui.Button(
                    label=f"📖 Manga ({len(self.manga_data)})",
                    style=manga_style,
                    disabled=len(self.manga_data) == 0,
                    row=0
                )
                manhwa_btn = discord.ui.Button(
                    label=f"🇰🇷 Manhwa ({len(self.manhwa_data)})",
                    style=manhwa_style,
                    disabled=len(self.manhwa_data) == 0,
                    row=0
                )
                manhua_btn = discord.ui.Button(
                    label=f"🇨🇳 Manhua ({len(self.manhua_data)})",
                    style=manhua_style,
                    disabled=len(self.manhua_data) == 0,
                    row=0
                )
                
                async def manga_callback(interaction):
                    self.current_category = "Manga"
                    self.current_index = 0
                    self.update_buttons()
                    current_data = self.get_current_data()
                    if current_data:
                        # Show loading embed first, then fetch details
                        loading_embed = await build_recommendation_embed(current_data[0], "Manga", 0, len(current_data), self.fetch_details_func)
                        await interaction.response.edit_message(embed=loading_embed, view=self)
                        
                        # Fetch details and update embed
                        await self.ensure_details_loaded(current_data[0])
                        final_embed = await build_recommendation_embed(current_data[0], "Manga", 0, len(current_data), self.fetch_details_func)
                        try:
                            await interaction.edit_original_response(embed=final_embed, view=self)
                        except Exception:
                            # If edit_original_response fails, try edit_message as fallback
                            try:
                                await interaction.response.edit_message(embed=final_embed, view=self)
                            except Exception:
                                pass
                    else:
                        await interaction.response.defer()
                
                async def manhwa_callback(interaction):
                    self.current_category = "Manhwa" 
                    self.current_index = 0
                    self.update_buttons()
                    current_data = self.get_current_data()
                    if current_data:
                        # Show loading embed first, then fetch details
                        loading_embed = await build_recommendation_embed(current_data[0], "Manhwa", 0, len(current_data), self.fetch_details_func)
                        await interaction.response.edit_message(embed=loading_embed, view=self)
                        
                        # Fetch details and update embed
                        await self.ensure_details_loaded(current_data[0])
                        final_embed = await build_recommendation_embed(current_data[0], "Manhwa", 0, len(current_data), self.fetch_details_func)
                        try:
                            await interaction.edit_original_response(embed=final_embed, view=self)
                        except Exception:
                            # If edit_original_response fails, try edit_message as fallback
                            try:
                                await interaction.response.edit_message(embed=final_embed, view=self)
                            except Exception:
                                pass
                    else:
                        await interaction.response.defer()
                
                async def manhua_callback(interaction):
                    self.current_category = "Manhua"
                    self.current_index = 0 
                    self.update_buttons()
                    current_data = self.get_current_data()
                    if current_data:
                        # Show loading embed first, then fetch details
                        loading_embed = await build_recommendation_embed(current_data[0], "Manhua", 0, len(current_data), self.fetch_details_func)
                        await interaction.response.edit_message(embed=loading_embed, view=self)
                        
                        # Fetch details and update embed
                        await self.ensure_details_loaded(current_data[0])
                        final_embed = await build_recommendation_embed(current_data[0], "Manhua", 0, len(current_data), self.fetch_details_func)
                        try:
                            await interaction.edit_original_response(embed=final_embed, view=self)
                        except Exception:
                            # If edit_original_response fails, try edit_message as fallback
                            try:
                                await interaction.response.edit_message(embed=final_embed, view=self)
                            except Exception:
                                pass
                    else:
                        await interaction.response.defer()
                
                manga_btn.callback = manga_callback
                manhwa_btn.callback = manhwa_callback 
                manhua_btn.callback = manhua_callback
                
                self.add_item(manga_btn)
                self.add_item(manhwa_btn)
                self.add_item(manhua_btn)
                
                # Navigation buttons (if more than 1 item in current category)
                current_data = self.get_current_data()
                if len(current_data) > 1:
                    prev_btn = discord.ui.Button(
                        label="◀️ Previous",
                        style=discord.ButtonStyle.secondary,
                        disabled=self.current_index == 0,
                        row=1
                    )
                    next_btn = discord.ui.Button(
                        label="Next ▶️",
                        style=discord.ButtonStyle.secondary,
                        disabled=self.current_index >= len(current_data) - 1,
                        row=1
                    )
                    
                    async def prev_callback(interaction):
                        self.current_index = max(0, self.current_index - 1)
                        self.update_buttons()
                        current_data = self.get_current_data()
                        
                        # Show loading embed first, then fetch details
                        loading_embed = await build_recommendation_embed(current_data[self.current_index], self.current_category, self.current_index, len(current_data), self.fetch_details_func)
                        await interaction.response.edit_message(embed=loading_embed, view=self)
                        
                        # Fetch details and update embed
                        await self.ensure_details_loaded(current_data[self.current_index])
                        final_embed = await build_recommendation_embed(current_data[self.current_index], self.current_category, self.current_index, len(current_data), self.fetch_details_func)
                        try:
                            await interaction.edit_original_response(embed=final_embed, view=self)
                        except Exception:
                            # If edit_original_response fails, try edit_message as fallback
                            try:
                                await interaction.response.edit_message(embed=final_embed, view=self)
                            except Exception:
                                pass
                    
                    async def next_callback(interaction):
                        current_data = self.get_current_data()
                        self.current_index = min(len(current_data) - 1, self.current_index + 1)
                        self.update_buttons()
                        
                        # Show loading embed first, then fetch details
                        loading_embed = await build_recommendation_embed(current_data[self.current_index], self.current_category, self.current_index, len(current_data), self.fetch_details_func)
                        await interaction.response.edit_message(embed=loading_embed, view=self)
                        
                        # Fetch details and update embed
                        await self.ensure_details_loaded(current_data[self.current_index])
                        final_embed = await build_recommendation_embed(current_data[self.current_index], self.current_category, self.current_index, len(current_data), self.fetch_details_func)
                        try:
                            await interaction.edit_original_response(embed=final_embed, view=self)
                        except Exception:
                            # If edit_original_response fails, try edit_message as fallback
                            try:
                                await interaction.response.edit_message(embed=final_embed, view=self)
                            except Exception:
                                pass
                    
                    prev_btn.callback = prev_callback
                    next_btn.callback = next_callback
                    
                    self.add_item(prev_btn)
                    self.add_item(next_btn)
                
                # Close button
                close_btn = discord.ui.Button(
                    label="❌ Close",
                    style=discord.ButtonStyle.red,
                    row=2
                )
                
                async def close_callback(interaction):
                    embed = discord.Embed(
                        title="✅ Recommendations Closed",
                        description=f"Hope you found some great {self.current_category.lower()} to read, {self.username}!",
                        color=discord.Color.green()
                    )
                    await interaction.response.edit_message(embed=embed, view=None)
                
                close_btn.callback = close_callback
                self.add_item(close_btn)
            
            async def on_timeout(self):
                """Handle view timeout"""
                for item in self.children:
                    item.disabled = True

        # Determine which category to show first
        if manga_data:
            initial_category = "Manga"
            initial_data = manga_data
        elif manhwa_data:
            initial_category = "Manhwa" 
            initial_data = manhwa_data
        elif manhua_data:
            initial_category = "Manhua"
            initial_data = manhua_data
        else:
            # No recommendations found
            embed = discord.Embed(
                title="❌ No Recommendations Found",
                description=f"No recommendations could be generated for {anilist_username}. Try rating more manga on AniList!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)
            return

        # Build initial embed and view
        initial_embed = await build_recommendation_embed(initial_data[0], initial_category, 0, len(initial_data), fetch_media_details)
        view = RecommendationView(manga_data, manhwa_data, manhua_data, anilist_username, fetch_media_details)
        
        # Send the recommendation interface as a single message
        recommendation_message = await interaction.followup.send(embed=initial_embed, view=view)
        
        # Load details for first item and update embed in the background
        try:
            await view.ensure_details_loaded(initial_data[0])
            final_embed = await build_recommendation_embed(initial_data[0], initial_category, 0, len(initial_data), fetch_media_details)
            await recommendation_message.edit(embed=final_embed, view=view)
        except Exception as e:
            logger.error(f"Error loading initial recommendation details: {e}")
        # /check_anilist command removed — the Login UI now provides an equivalent check via the
        # Check AniList button which calls `_check_anilist_user_exists`.

async def setup(bot: commands.Bot):
    await bot.add_cog(Recommendations(bot))