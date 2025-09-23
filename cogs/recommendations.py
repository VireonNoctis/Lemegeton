import os
import json
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import logging
from typing import Dict, Tuple, List, Optional, Callable, Awaitable, Any
import random

from config import CHANNEL_ID
from database import get_user

logger = logging.getLogger("Recommendations")
logger.setLevel(logging.INFO)

# Ensure logs directory exi
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "recommendations.log")

# Avoid adding duplicate handlers on reloads
if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == os.path.abspath(LOG_FILE)
           for h in logger.handlers):
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)
# Also keep console output
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(stream_handler)

ANILIST_API_URL = "https://graphql.anilist.co"

# Global cache for recommendation totals (id -> count, timestamp)
RECOMMENDATION_CACHE = {}
CACHE_DURATION = 3600  # 1 hour cache

class Recommendations(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
                        logger.warning(f"AniList API returned {resp.status} for user '{username}': {body}")
                        return []

                    try:
                        data = json.loads(text)
                    except Exception as e:
                        logger.exception(f"Failed to decode AniList JSON response for '{username}': {e}")
                        return []

                    if "errors" in data:
                        logger.warning(f"AniList GraphQL errors for '{username}': {data['errors']}")
                        return []

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
        # enforce channel-specific usage
        if interaction.channel is None or interaction.channel.id != CHANNEL_ID:
            await interaction.response.send_message(f"⚠️ This command can only be used in <#{CHANNEL_ID}>.", ephemeral=True)
            return
        await interaction.response.defer()
        target = member or interaction.user

        user_row = await get_user(target.id)
        if not user_row:
            await interaction.followup.send(f"⚠️ No AniList linked for {target.mention}.", ephemeral=True)
            return
        anilist_username = None
        try:
            anilist_username = user_row["anilist_username"]
        except Exception:
            try:
                anilist_username = user_row[3]
            except Exception:
                anilist_username = None

        if not anilist_username:
            await interaction.followup.send(f"⚠️ No AniList username set for {target.mention}.", ephemeral=True)
            return

        logger.info(f"Recommendations command invoked for Discord user {target} -> AniList '{anilist_username}'")
        await interaction.followup.send(f"🔎 Fetching rated manga for {anilist_username}...", ephemeral=True)

        entries = await self._fetch_user_manga_with_recs(anilist_username)
        if entries is None:
            await interaction.followup.send("⚠️ Error fetching the user's manga list.", ephemeral=True)
            return
        if not entries:
            await interaction.followup.send("⚠️ Could not fetch the user's manga list or no entries found.", ephemeral=True)
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

        # Tally recommendations using only the top_entries
        tally: Dict[int, Dict[str, object]] = {}  # id -> {"occurrences": int, "votes": int, "title": str, "country": str}
        total_recs_considered = 0
        for e in top_entries:
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

        logger.info(f"Considered {total_recs_considered} recommendation entries across top {len(top_entries)} titles.")
        logger.info(f"Unique recommended titles after excluding user's list: {len(tally)}")

        if not tally:
            await interaction.followup.send("No recommendations found from rated manga (after excluding titles already on the user's list).", ephemeral=True)
            return

        # PRE-FILTER: Only fetch global totals for titles with multiple occurrences (saves API calls)
        min_occurrences = 2
        filtered_tally = {mid: info for mid, info in tally.items() if info["occurrences"] >= min_occurrences}
        logger.info(f"Pre-filtered to {len(filtered_tally)} candidates with >= {min_occurrences} occurrences (from {len(tally)} total)")

        if not filtered_tally:
            # Fallback: use top candidates by occurrence count if pre-filter removes too many
            candidates_by_occ = sorted(tally.items(), key=lambda kv: kv[1]["occurrences"], reverse=True)[:50]
            filtered_tally = dict(candidates_by_occ)
            logger.info(f"Fallback: using top {len(filtered_tally)} candidates by occurrence count")

        # Fetch global recommendation totals for filtered candidates with caching
        candidate_ids = list(filtered_tally.keys())
        
        # Check cache first to reduce API calls
        import time
        current_time = time.time()
        cached_ids = []
        api_fetch_ids = []
        
        for mid in candidate_ids:
            if mid in RECOMMENDATION_CACHE:
                cached_count, cached_time = RECOMMENDATION_CACHE[mid]
                if current_time - cached_time < CACHE_DURATION:
                    filtered_tally[mid]["votes"] = cached_count
                    cached_ids.append(mid)
                else:
                    api_fetch_ids.append(mid)
            else:
                api_fetch_ids.append(mid)
        
        logger.info(f"Using cached data for {len(cached_ids)} candidates, fetching {len(api_fetch_ids)} from API")

        # Fetch global recommendation totals for remaining candidates
        candidate_ids = api_fetch_ids

        # live progress message for global totals
        progress_msg = await interaction.followup.send(
            f"🔎 Fetching global recommendation totals for {len(candidate_ids)} candidates...",
            ephemeral=True
        )

        async def _progress_cb(processed: int, total: int):
            # safe best-effort edit
            try:
                pct = (processed / total * 100) if total else 100.0
                await interaction.followup.edit_message(progress_msg.id, content=f"🔎 Fetching global totals: {processed}/{total} ({pct:.1f}%)")
            except Exception:
                # ignore edit errors (rate limits / missing perms)
                pass

        # fetch global totals with reduced batch size to avoid rate limiting
        if candidate_ids:
            global_votes_map = await self._fetch_global_votes_for_candidates(
                candidate_ids,
                batch_size=2,  # Reduced to avoid rate limiting
                interval=3.0,  # Increased to 3.0 seconds for safety
                progress_cb=_progress_cb
            )

            # Cache the results for future use
            current_time = time.time()
            for mid, votes in global_votes_map.items():
                RECOMMENDATION_CACHE[mid] = (votes, current_time)
        else:
            global_votes_map = {}

        # finalise progress message
        try:
            await interaction.followup.edit_message(progress_msg.id, content=f"✅ Fetched global totals for {len(global_votes_map)} candidates.")
        except Exception:
            pass

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

        # Build embeds for each page
        def build_embed_for(title_prefix: str, items: List[tuple]) -> discord.Embed:
            embed = discord.Embed(
                title=f"{title_prefix} recommendations based on {anilist_username}'s ratings",
                description=f"Top {len(items)} {title_prefix.lower()}by {anilist_username})",
                color=discord.Color.blurple()
            )
            if not items:
                embed.add_field(name="None found", value="No recommendations in this category.", inline=False)
                return embed
            for idx, (mid, info) in enumerate(items, start=1):
                url = f"https://anilist.co/manga/{mid}"
                embed.add_field(
                    name=f"{idx}. {info['title']}",
                    value=f"[View on AniList]({url}) — Votes: {info.get('votes', 0)} (occurrences: {info.get('occurrences', 0)})",
                    inline=False
                )
            return embed

        pages = [
            ("Manga", build_embed_for("Manga", top_manga)),
            ("Manhwa", build_embed_for("Manhwa", top_manhwa)),
            ("Manhua", build_embed_for("Manhua", top_manhua)),
        ]

        # Simple paginator view (3 pages)
        class RecPaginator(discord.ui.View):
            def __init__(self, pages):
                super().__init__(timeout=200)
                self.pages = pages
                self.index = 0

            async def update_message(self, message: discord.Message):
                title, embed = self.pages[self.index]
                # include page indicator in footer
                embed.set_footer(text=f"{title} — Page {self.index + 1}/{len(self.pages)}")
                await message.edit(embed=embed, view=self)

            @discord.ui.button(label="◀️ Prev", style=discord.ButtonStyle.secondary)
            async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.index > 0:
                    self.index -= 1
                    await self.update_message(interaction.message)
                await interaction.response.defer()

            @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary)
            async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                if self.index < len(self.pages) - 1:
                    self.index += 1
                    await self.update_message(interaction.message)
                await interaction.response.defer()

            @discord.ui.button(label="Close", style=discord.ButtonStyle.red)
            async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                try:
                    await interaction.message.delete()
                except Exception:
                    pass
                await interaction.response.defer()

        # Send first page with view
        first_title, first_embed = pages[0]
        msg = await interaction.followup.send(embed=first_embed, view=RecPaginator(pages), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Recommendations(bot))