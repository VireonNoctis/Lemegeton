# anilist_site_embed.py
import re
import aiohttp
import asyncio
import discord
from discord.ext import commands
from discord import ui
import math
import logging
from typing import Optional, Dict, Any, List, Tuple
from database import (
    get_all_users,
    get_all_paginator_states,
    set_paginator_state,
    delete_paginator_state,
    get_paginator_state
)
from datetime import datetime, timedelta
from enum import Enum
import json

logger = logging.getLogger("AniListCog")
logger.setLevel(logging.INFO)

ANILIST_API = "https://graphql.anilist.co"
ACTIVITY_URL_RE = re.compile(r"https?://anilist\.co/activity/(\d+)", re.IGNORECASE)
ANIME_URL_RE = re.compile(r"https?://anilist\.co/anime/(\d+)(?:/[^/\s]+)?/?", re.IGNORECASE)
MANGA_URL_RE = re.compile(r"https?://anilist\.co/manga/(\d+)(?:/[^/\s]+)?/?", re.IGNORECASE)
REVIEW_URL_RE = re.compile(r"https?://anilist\.co/review/(\d+)", re.IGNORECASE)
CHARACTER_URL_RE = re.compile(r"https?://anilist\.co/character/(\d+)(?:/[^/\s]+)?/?", re.IGNORECASE)
STAFF_URL_RE = re.compile(r"https?://anilist\.co/staff/(\d+)(?:/[^/\s]+)?/?", re.IGNORECASE)

REPLIES_PER_PAGE = 5
HTML_TIMEOUT = 20  # seconds for parsing fallback HTTP requests
DEFAULT_REVIEW_COLOR = 0x0F1720

class ProgressFilter(Enum):
    ALL = "all"
    ACTIVE_ONLY = "active_only"
    COMPLETED_ONLY = "completed_only"
    HIGH_SCORERS = "high_scorers"
    RECENT_ACTIVITY = "recent_activity"
    CUSTOM_RANGE = "custom_range"
    WATCHING_NOW = "watching_now"
    DROPPED = "dropped"

PROGRESS_FILTER_OPTIONS = {
    ProgressFilter.ALL: {"label": "🌟 All Users", "description": "Show all registered users", "emoji": "🌟"},
    ProgressFilter.ACTIVE_ONLY: {"label": "⚡ Active Users", "description": "Users with progress > 0", "emoji": "⚡"},
    ProgressFilter.COMPLETED_ONLY: {"label": "✅ Completed Only", "description": "Users who finished the series", "emoji": "✅"},
    ProgressFilter.HIGH_SCORERS: {"label": "⭐ High Scorers", "description": "Users with 8+ ratings", "emoji": "⭐"},
    ProgressFilter.WATCHING_NOW: {"label": "📺 Currently Active", "description": "Users actively watching/reading", "emoji": "📺"},
    ProgressFilter.DROPPED: {"label": "❌ Dropped", "description": "Users who dropped the series", "emoji": "❌"}
}

# small helpers (regex for images/markdown)
IMG_MD_RE = re.compile(r'!\[.*?\]\(\s*(https?://[^\s)]+)\s*\)', re.I)
IMG_HTML_RE = re.compile(r'<img[^>]+src=["\'](https?://[^"\']+)["\'][^>]*>', re.I)
IMG_CUSTOM_RE = re.compile(r'imgx\(\s*(https?://[^\s)]+)\s*\)', re.I)
URL_RE = re.compile(r'(https?://[^\s)>\]]+)')

def _split_into_segments(text: Optional[str]) -> List[Dict[str, str]]:
    if not text:
        return []
    s = text
    try:
        s = re.sub(r'<img[^>]+src=["\'](https?://[^"\']+)["\'][^>]*>', r' imgx(\1) ', s, flags=re.I)
    except Exception:
        pass
    segments = []
    idx = 0
    L = len(s)
    while idx < L:
        m_md = IMG_MD_RE.search(s, idx)
        m_cus = IMG_CUSTOM_RE.search(s, idx)
        matches = [m for m in (m_md, m_cus) if m]
        if not matches:
            rem = s[idx:].strip()
            if rem:
                segments.append({"type": "text", "content": rem})
            break
        m = min(matches, key=lambda mm: mm.start())
        start, end = m.start(), m.end()
        if start > idx:
            pre = s[idx:start].strip()
            if pre:
                segments.append({"type": "text", "content": pre})
        url = None
        try:
            url = m.group(1)
        except Exception:
            u = URL_RE.search(m.group(0))
            if u:
                url = u.group(1)
        if url:
            segments.append({"type": "image", "url": url})
        idx = end
    # merge adjacent texts
    out = []
    for seg in segments:
        if out and seg["type"] == "text" and out[-1]["type"] == "text":
            out[-1]["content"] += "\n\n" + seg["content"]
        else:
            out.append(seg)
    return out

def _chunk_text(text: str, limit: int = 2000) -> List[str]:
    if not text:
        return []
    chunks = []
    cur = text
    while cur:
        if len(cur) <= limit:
            chunks.append(cur)
            break
        cut = cur.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(cur[:cut].strip())
        cur = cur[cut:].lstrip("\n")
    return chunks

class AniListCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self._views_restored = False

    async def cog_unload(self):
        await self.session.close()

    # ---------------------
    # Utility text helpers
    # ---------------------
    def clean_text(self, text: Optional[str]) -> str:
        if not text:
            return ""
        t = text
        t = re.sub(r'<br\s*/?>', '\n', t)
        t = re.sub(r'<script[^>]*>.*?</script>', '', t, flags=re.S|re.I)
        t = re.sub(r'<style[^>]*>.*?</style>', '', t, flags=re.S|re.I)
        t = re.sub(r'<[^>]+>', '', t)
        t = t.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
        t = re.sub(r"\r\n", "\n", t)
        return t.strip()

    def extract_media(self, text: Optional[str]) -> Tuple[List[str], str]:
        if not text:
            return [], ""
        media_links = []
        for m in re.finditer(r'(?:imgx|img)\((https?://[^\s)]+)\)', text):
            media_links.append(m.group(1))
        for m in re.finditer(r'(https?://[^\s]+(?:\.png|\.jpg|\.jpeg|\.gif|\.webp|\.mp4|\.webm))', text):
            u = m.group(1)
            if u not in media_links:
                media_links.append(u)
        cleaned = re.sub(r'(?:imgx|img)\((https?://[^\s)]+)\)', '', text)
        cleaned = re.sub(r'(https?://[^\s]+(?:\.png|\.jpg|\.jpeg|\.gif|\.webp|\.mp4|\.webm))', '', cleaned)
        return media_links, cleaned.strip()

    def _fmt_date(self, d: Dict[str, Any]) -> str:
        if not d:
            return "Unknown"
        y = d.get("year")
        m = d.get("month")
        day = d.get("day")
        if not y:
            return "Unknown"
        if not m:
            return f"{y}"
        if not day:
            return f"{y}-{m:02d}"
        return f"{y}-{m:02d}-{day:02d}"

    # ---------------------
    # MEDIA GraphQL + parse fallback (kept intact, deep fallback)
    # ---------------------
    async def fetch_media_api(self, media_id: int, media_type: str) -> Optional[dict]:
        query = """
        query($id: Int, $type: MediaType) {
          Media(id: $id, type: $type) {
            id
            siteUrl
            type
            title { romaji english native }
            description(asHtml: false)
            coverImage { large extraLarge color }
            bannerImage
            episodes
            chapters
            volumes
            status
            startDate { year month day }
            endDate { year month day }
            studios(isMain: true) { nodes { id name siteUrl } }
            popularity
            favourites
            source
            tags { id name isAdult rank isMediaSpoiler }
            staff(perPage:50) { edges { role node { id name { full native alternative } siteUrl image { large } } } }
            characters(perPage:50) { edges { role node { id name { full native alternative } siteUrl image { large } } } }
            relations { edges { relationType node { id type siteUrl title { romaji english native } coverImage { large } } } }
            stats { scoreDistribution { score amount } statusDistribution { status amount } }
            recommendations { edges { node { mediaRecommendation { id title { romaji english } coverImage { large } siteUrl } } } }
          }
        }
        """
        variables = {"id": media_id, "type": media_type}
        try:
            async with self.session.post(ANILIST_API, json={"query": query, "variables": variables}, timeout=30) as resp:
                text = await resp.text()
                try:
                    js = await resp.json()
                except Exception:
                    js = None
                if resp.status != 200:
                    logger.error("AniList media API error %s: %s", resp.status, text)
                    return None
                if not js or "data" not in js or js["data"].get("Media") is None:
                    logger.warning("AniList API returned no Media for id %s. Response: %s", media_id, text)
                    return None
                return js["data"]["Media"]
        except Exception:
            logger.exception("AniList media API fetch failed (exception).")
            return None

    async def fetch_media_parse_fallback(self, media_id: int, media_type: str) -> Optional[dict]:
        base = "anime" if media_type.upper().startswith("ANIME") else "manga"
        url = f"https://anilist.co/{base}/{media_id}"
        logger.info("Parsing mode started: 0% — attempting HTML fallback for %s", url)
        progress = 0
        try:
            progress = 10
            async with self.session.get(url, timeout=HTML_TIMEOUT, headers={"User-Agent": "AniListBot/1.0"}) as resp:
                html = await resp.text()
        except Exception:
            logger.exception("Parsing fetch failed at 10%%")
            return None
        progress = 30
        try:
            og_title = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html)
            og_desc = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html)
            og_image = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
            title = og_title.group(1).strip() if og_title else None
            description = og_desc.group(1).strip() if og_desc else None
            banner = og_image.group(1).strip() if og_image else None
        except Exception:
            title = description = banner = None
        progress = 50
        cover = None
        try:
            m_cover = re.search(r'coverImage["\']:\s*{\s*["\']large["\']:\s*["\']([^"\']+)["\']', html)
            if not m_cover:
                m_cover = re.search(r'<meta\s+property=["\']og:image:secure_url["\']\s+content=["\']([^"\']+)["\']', html)
            if m_cover:
                cover = m_cover.group(1).strip()
        except Exception:
            cover = None
        progress = 65
        episodes = chapters = volumes = None
        status = None
        popularity = None
        favourites = None
        source = None
        try:
            m_eps = re.search(r'Episodes</dt>\s*<dd[^>]*>\s*([0-9,]+)\s*</dd>', html)
            if m_eps:
                episodes = int(m_eps.group(1).replace(",", ""))
            m_ch = re.search(r'Chapters</dt>\s*<dd[^>]*>\s*([0-9,]+)\s*</dd>', html)
            if m_ch:
                chapters = int(m_ch.group(1).replace(",", ""))
            m_vol = re.search(r'Volumes</dt>\s*<dd[^>]*>\s*([0-9,]+)\s*</dd>', html)
            if m_vol:
                volumes = int(m_vol.group(1).replace(",", ""))
            m_status = re.search(r'Status</dt>\s*<dd[^>]*>\s*([^<]+)</dd>', html)
            if m_status:
                status = m_status.group(1).strip()
            m_pop = re.search(r'Popularity</dt>\s*<dd[^>]*>\s*([0-9,]+)\s*</dd>', html)
            if m_pop:
                popularity = int(m_pop.group(1).replace(",", ""))
            m_fav = re.search(r'Favorites</dt>\s*<dd[^>]*>\s*([0-9,]+)\s*</dd>', html)
            if m_fav:
                favourites = int(m_fav.group(1).replace(",", ""))
            m_src = re.search(r'Source</dt>\s*<dd[^>]*>\s*([^<]+)</dd>', html)
            if m_src:
                source = m_src.group(1).strip()
        except Exception:
            logger.exception("Parsing stats extraction failed (non-fatal)")
        studios = []
        try:
            for m in re.finditer(r'<a[^>]+href=["\']https?://anilist.co/[^"\']*studio/[^"\']+["\'][^>]*>([^<]+)</a>', html):
                name = m.group(1).strip()
                if name and name not in studios:
                    studios.append({"name": name})
        except Exception:
            pass
        media = {
            "id": media_id,
            "siteUrl": url,
            "title": {"romaji": title or f"Media {media_id}", "english": None, "native": None},
            "description": description or "",
            "coverImage": {"large": cover} if cover else {},
            "bannerImage": banner or None,
            "episodes": episodes,
            "chapters": chapters,
            "volumes": volumes,
            "status": status,
            "startDate": {"year": None, "month": None, "day": None},
            "endDate": {"year": None, "month": None, "day": None},
            "studios": {"nodes": studios},
            "popularity": popularity,
            "favourites": favourites,
            "source": source,
            "tags": [],
            "relations": {"edges": []},
            "characters": {"edges": []},
            "staff": {"edges": []},
            "stats": {},
            "recommendations": {"edges": []},
        }
        progress = 100
        logger.info("Parsing fallback completed for %s", url)
        return media

    async def fetch_media(self, media_id: int, media_type: str) -> Optional[dict]:
        api_resp = await self.fetch_media_api(media_id, media_type)
        if api_resp:
            return api_resp
        logger.warning("AniList API failed for media %s %s — starting parsing fallback", media_type, media_id)
        parsed = await self.fetch_media_parse_fallback(media_id, media_type)
        if parsed:
            logger.info("Parsing fallback succeeded for media %s %s", media_type, media_id)
        else:
            logger.error("Parsing fallback failed for media %s %s", media_type, media_id)
        return parsed

    # ---------------------
    # Media embed builders (kept intact but ensure dropdown persistence)
    # ---------------------
    def build_media_embed(self, media: dict) -> discord.Embed:
        title_romaji = (media.get("title") or {}).get("romaji")
        title_eng = (media.get("title") or {}).get("english")
        title_native = (media.get("title") or {}).get("native")
        title_line = title_romaji or title_eng or title_native or "Unknown Title"
        if title_eng and title_eng != title_romaji:
            title_line += f" ({title_eng})"
        if title_native and title_native not in (title_romaji, title_eng):
            title_line += f" | {title_native}"
        desc_raw = media.get("description") or ""
        desc = self.clean_text(desc_raw)
        short_desc = (desc[:800] + "...") if len(desc) > 800 else desc
        embed = discord.Embed(title=title_line, url=media.get("siteUrl"), description=short_desc or "*No synopsis available*", color=discord.Color.blurple())
        cover = (media.get("coverImage") or {}).get("large")
        banner = media.get("bannerImage")
        if cover:
            embed.set_thumbnail(url=cover)
        if banner:
            embed.set_image(url=banner)
        meta_lines = []
        if media.get("type"):
            meta_lines.append(f"**Type:** {media.get('type')}")
        if media.get("status"):
            meta_lines.append(f"**Status:** {media.get('status')}")
        if media.get("episodes") is not None:
            meta_lines.append(f"🎬 Episodes: {media.get('episodes')}")
        if media.get("chapters") is not None:
            meta_lines.append(f"📖 Chapters: {media.get('chapters')}")
        if media.get("volumes") is not None:
            meta_lines.append(f"📚 Volumes: {media.get('volumes')}")
        if media.get("startDate"):
            meta_lines.append(f"Start: {self._fmt_date(media.get('startDate'))}")
        if media.get("endDate"):
            meta_lines.append(f"End: {self._fmt_date(media.get('endDate'))}")
        if meta_lines:
            embed.add_field(name="Info", value="\n".join(meta_lines), inline=False)
        studios_nodes = (media.get("studios") or {}).get("nodes") or []
        if studios_nodes:
            studios_str = ", ".join(n.get("name") for n in studios_nodes if n.get("name"))
            embed.add_field(name="Studio", value=studios_str or "—", inline=True)
        stats_lines = []
        if media.get("popularity") is not None:
            stats_lines.append(f"🔥 Popularity: {media['popularity']}")
        if media.get("favourites") is not None:
            stats_lines.append(f"❤️ Favourites: {media['favourites']}")
        if media.get("source"):
            stats_lines.append(f"🔗 Source: {media['source']}")
        if stats_lines:
            embed.add_field(name="Stats", value="\n".join(stats_lines), inline=True)
        char_edges = (media.get("characters") or {}).get("edges") or []
        main_chars = [e for e in char_edges if (e.get("role") or "").upper() == "MAIN"] or char_edges
        if main_chars:
            lines = []
            for e in main_chars[:6]:
                node = e.get("node") or {}
                name = (node.get("name") or {}).get("full") or "Unknown"
                cid = node.get("id")
                char_url = f"https://anilist.co/character/{cid}" if cid else ""
                lines.append(f"[{name}]({char_url})")
            embed.add_field(name="Main Characters", value=" • ".join(lines), inline=False)
        embed.set_footer(text="AniList Media")
        return embed

    def render_media_pages(self, media: dict, page: int, total_pages: int) -> List[discord.Embed]:
        embeds: List[discord.Embed] = []
        if not media:
            return [discord.Embed(description="Media not found.", color=discord.Color.red())]
        if page == 1:
            embeds.append(self.build_media_embed(media))
        else:
            raw = self.clean_text(media.get("description") or "")
            if not raw:
                embeds.append(discord.Embed(description="No description available.", color=discord.Color.greyple()))
                return embeds
            chunk_size = 1000
            chunks = [raw[i:i + chunk_size] for i in range(0, len(raw), chunk_size)]
            for idx, c in enumerate(chunks, start=1):
                em = discord.Embed(title=f"{(media.get('title') or {}).get('romaji', 'Description')} — Part {idx}", description=c, url=media.get("siteUrl"), color=discord.Color.green())
                embeds.append(em)
        return embeds

    # relations/characters/staff/stats/recs/tags (kept same but adjusted tags spoiler rendering)
    def build_relations_embed(self, media: dict) -> List[discord.Embed]:
        relations = (media.get("relations") or {}).get("edges") or []
        if not relations:
            return [discord.Embed(description="No relations found.", color=discord.Color.greyple())]
        embeds = []
        chunk_size = 6
        for i in range(0, len(relations), chunk_size):
            chunk = relations[i:i + chunk_size]
            em = discord.Embed(title="Relations", color=discord.Color.dark_blue())
            for edge in chunk:
                rel_type = edge.get("relationType") or ""
                node = edge.get("node") or {}
                node_title = (node.get("title") or {}).get("romaji") or (node.get("title") or {}).get("english") or "Unknown"
                url = node.get("siteUrl")
                value = f"[{node_title}]({url})" if url else node_title
                field_name = rel_type or node.get("type") or "Related"
                em.add_field(name=field_name, value=value, inline=False)
            first_cover = (chunk[0].get("node") or {}).get("coverImage", {}).get("large")
            if first_cover:
                em.set_thumbnail(url=first_cover)
            embeds.append(em)
        return embeds

    def build_characters_embed(self, media: dict, support: bool = False) -> List[discord.Embed]:
        char_edges = (media.get("characters") or {}).get("edges") or []
        if not char_edges:
            return [discord.Embed(description="No characters found.", color=discord.Color.greyple())]
        if support:
            selected = [e for e in char_edges if (e.get("role") or "").upper() != "MAIN"]
            title = "Support Cast"
        else:
            selected = [e for e in char_edges if (e.get("role") or "").upper() == "MAIN"]
            title = "Main Characters"
        if not selected:
            selected = char_edges[:10]
        embeds = []
        chunk_size = 6
        for i in range(0, len(selected), chunk_size):
            chunk = selected[i:i + chunk_size]
            em = discord.Embed(title=title, color=discord.Color.blurple())
            for e in chunk:
                node = e.get("node") or {}
                name = (node.get("name") or {}).get("full") or "Unknown"
                cid = node.get("id")
                url = f"https://anilist.co/character/{cid}" if cid else None
                # alt names placed in value under name
                alt = (node.get("name") or {}).get("alternative") or []
                # add spoilers if flagged? AniList char alt doesn't flag spoilers in API; we show raw names
                alt_text = ""
                if alt:
                    alt_text = "Other names: " + ", ".join(alt[:6])
                value = f"{alt_text}\n[AniList]({url})" if url else (alt_text or "—")
                em.add_field(name=name, value=value, inline=False)
            first_img = (chunk[0].get("node") or {}).get("image", {}).get("large")
            if first_img:
                em.set_thumbnail(url=first_img)
            embeds.append(em)
        return embeds

    def build_staff_embed(self, media: dict) -> List[discord.Embed]:
        staff_edges = (media.get("staff") or {}).get("edges") or []
        if not staff_edges:
            return [discord.Embed(description="No staff info found.", color=discord.Color.greyple())]
        embeds = []
        chunk_size = 8
        for i in range(0, len(staff_edges), chunk_size):
            chunk = staff_edges[i:i + chunk_size]
            em = discord.Embed(title="Staff", color=discord.Color.dark_teal())
            for edge in chunk:
                role = edge.get("role") or "Staff"
                node = edge.get("node") or {}
                name = (node.get("name") or {}).get("full") or "Unknown"
                sid = node.get("id")
                url = f"https://anilist.co/staff/{sid}" if sid else None
                value = f"{role}\n" + (f"[AniList]({url})" if url else "")
                em.add_field(name=name, value=value, inline=False)
            first_img = (chunk[0].get("node") or {}).get("image", {}).get("large")
            if first_img:
                em.set_thumbnail(url=first_img)
            embeds.append(em)
        return embeds

    def build_stats_embed(self, media: dict) -> discord.Embed:
        stats = media.get("stats") or {}
        em = discord.Embed(title="Stats Distribution", color=discord.Color.green())
        status_dist = stats.get("statusDistribution") or []
        if status_dist:
            lines = []
            for s in status_dist:
                st = s.get("status") or "Unknown"
                amt = s.get("amount") or 0
                lines.append(f"**{st.title()}** — {amt} users")
            em.add_field(name="Status Distribution", value="\n".join(lines), inline=False)
        score_dist = stats.get("scoreDistribution") or []
        if score_dist:
            sd_lines = []
            for s in sorted(score_dist, key=lambda x: int(x.get("score", 0))):
                sc = s.get("score")
                amt = s.get("amount")
                sd_lines.append(f"{sc}: {amt}")
            em.add_field(name="Score Distribution", value=" | ".join(sd_lines), inline=False)
        if not em.fields:
            em.description = "No statistical distribution data available."
        return em

    def build_recommendations_embed(self, media: dict, max_items: int = 5) -> discord.Embed:
        recs = (media.get("recommendations") or {}).get("edges") or []
        em = discord.Embed(title="🎯 Recommendations", description="Top recommendations from AniList", color=discord.Color.gold())
        count = 0
        for e in recs:
            node = e.get("node") or {}
            rec = node.get("mediaRecommendation") or {}
            title = (rec.get("title") or {}).get("romaji") or (rec.get("title") or {}).get("english") or "Unknown"
            url = rec.get("siteUrl") or ""
            cover = (rec.get("coverImage") or {}).get("large")
            em.add_field(name=title, value=f"[AniList]({url})", inline=False)
            if cover:
                em.set_thumbnail(url=cover)
            count += 1
            if count >= max_items:
                break
        if count == 0:
            em.description = "No recommendations found."
        em.set_footer(text="AniList Recommendations")
        return em

    def build_tags_embed(self, media: dict) -> discord.Embed:
        tags = media.get("tags") or []
        if not tags:
            return discord.Embed(description="No tags found.", color=discord.Color.greyple())
        em = discord.Embed(title="Tags", color=discord.Color.dark_purple())
        lines = []
        for t in tags:
            name = t.get("name") or "Unknown"
            rank = t.get("rank")
            is_spoiler = t.get("isMediaSpoiler")
            disp = f"||{name}||" if is_spoiler else name
            if rank is not None:
                disp += f" — #{rank}"
            lines.append(disp)
        em.description = "  \n".join(lines)
        return em

    # ---------------------
    # NEW: Review GraphQL + deep HTML fallback + builder
    # ---------------------
    async def fetch_review_api(self, review_id: int) -> Optional[dict]:
        query = """
        query($id: Int) {
          Review(id: $id) {
            id summary body rating ratingAmount score siteUrl likeCount user { id name siteUrl avatar { large } }
            media { id title { romaji english } coverImage { large } siteUrl }
            createdAt
          }
        }
        """
        try:
            async with self.session.post(ANILIST_API, json={"query": query, "variables": {"id": review_id}}, timeout=25) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.debug("Review API status %s: %s", resp.status, text)
                    return None
                j = await resp.json()
                return j.get("data", {}).get("Review")
        except Exception:
            logger.exception("fetch_review_api failed")
            return None

    async def fetch_review_parse_fallback(self, review_id: int) -> Optional[dict]:
        url = f"https://anilist.co/review/{review_id}"
        logger.info("Review HTML fallback for %s", url)
        try:
            async with self.session.get(url, timeout=HTML_TIMEOUT, headers={"User-Agent": "AniListBot/1.0"}) as resp:
                html = await resp.text()
        except Exception:
            logger.exception("fetch_review_parse_fallback: http fetch failed")
            return None
        # attempt JSON-LD / structured data first
        body = ""
        summary = None
        score = None
        rating = None
        ratingAmount = None
        user = {"name": None, "siteUrl": None, "avatar": {"large": None}}
        siteUrl = url
        # og tags
        m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            summary = m.group(1).strip()
        m = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            body = m.group(1).strip()
        # look for review body block
        mbody = re.search(r'(<div[^>]+class=["\']review-body[^"\']*["\'][^>]*>.*?</div>)', html, re.I|re.S)
        if mbody:
            s = mbody.group(1)
            s = re.sub(r'<img[^>]+src=["\'](https?://[^"\']+)["\'][^>]*>', r' imgx(\1) ', s, flags=re.I)
            body = re.sub(r'<[^>]+>', '', s).strip()
        # find score / ratings
        mscore = re.search(r'(\d{1,3})\s*/\s*100', html)
        if mscore:
            try:
                score = int(mscore.group(1))
            except:
                score = None
        m_rat = re.search(r'(\d+)\s*\/\s*(\d+)\s*(?:found|users|voted)?', html)
        if m_rat:
            try:
                rating = int(m_rat.group(1))
                ratingAmount = int(m_rat.group(2))
            except:
                rating = ratingAmount = None
        # user
        m_user = re.search(r'<a[^>]+href=["\'](https?://anilist\.co/user/[^"\']+)["\'][^>]*>([^<]+)</a>', html, re.I)
        if m_user:
            user["siteUrl"] = m_user.group(1).strip()
            user["name"] = re.sub(r'<[^>]+>', '', m_user.group(2)).strip()
        m_img = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.I)
        if m_img:
            # og:image may be media cover — use if needed
            pass
        # try JSON embedded
        jmatch = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S|re.I)
        if jmatch:
            try:
                jd = json.loads(jmatch.group(1))
                if isinstance(jd, dict):
                    summary = summary or jd.get("name")
                    if not body:
                        body = jd.get("description") or body
            except Exception:
                pass
        return {"id": review_id, "summary": summary, "body": body, "score": score, "rating": rating, "ratingAmount": ratingAmount, "user": user, "siteUrl": siteUrl}

    async def fetch_review(self, review_id: int) -> Optional[dict]:
        api = await self.fetch_review_api(review_id)
        if api:
            return api
        return await self.fetch_review_parse_fallback(review_id)

    async def build_review_embeds(self, review_id: int) -> List[discord.Embed]:
        rv = await self.fetch_review(review_id)
        if not rv:
            return [discord.Embed(description="❌ Review not found or fetch failed.", color=discord.Color.red())]
        embeds: List[discord.Embed] = []
        title = rv.get("summary") or f"Review #{rv.get('id')}"
        base_url = rv.get("siteUrl")
        author_name = (rv.get("user") or {}).get("name") or ""
        author_url = (rv.get("user") or {}).get("siteUrl")
        # header
        header = discord.Embed(title=title, url=base_url, color=discord.Color.from_rgb((DEFAULT_REVIEW_COLOR>>16)&255, (DEFAULT_REVIEW_COLOR>>8)&255, DEFAULT_REVIEW_COLOR&255))
        if author_name:
            header.set_author(name=author_name, url=author_url)
        score = rv.get("score") or rv.get("rating") or 0
        # ensure out-of-100
        try:
            sc = int(score)
            if sc <= 10:
                sc = sc * 10
        except:
            sc = 0
        header.add_field(name="Rating", value=f"{sc}/100", inline=True)
        rating = rv.get("rating") or 0
        ratingAmount = rv.get("ratingAmount") or 0
        if ratingAmount:
            ratio = f"{rating}/{ratingAmount}"
            perc = f"{(rating / ratingAmount) * 100:.1f}%"
        else:
            ratio = "N/A"
            perc = "N/A"
        header.add_field(name="👍 Ratio", value=ratio, inline=True)
        header.add_field(name="✅ Positive %", value=perc, inline=True)
        embeds.append(header)
        body = rv.get("body") or ""
        segments = _split_into_segments(body)
        if not segments:
            for chunk in _chunk_text(self.clean_text(body), limit=2048):
                embeds.append(discord.Embed(description=chunk, color=discord.Color.from_rgb((DEFAULT_REVIEW_COLOR>>16)&255, (DEFAULT_REVIEW_COLOR>>8)&255, DEFAULT_REVIEW_COLOR&255)))
            return embeds
        for seg in segments:
            if seg["type"] == "text":
                txt = self.clean_text(seg["content"])
                for chunk in _chunk_text(txt, limit=2048):
                    embeds.append(discord.Embed(description=chunk, color=discord.Color.from_rgb((DEFAULT_REVIEW_COLOR>>16)&255, (DEFAULT_REVIEW_COLOR>>8)&255, DEFAULT_REVIEW_COLOR&255)))
            else:
                e = discord.Embed(color=discord.Color.from_rgb((DEFAULT_REVIEW_COLOR>>16)&255, (DEFAULT_REVIEW_COLOR>>8)&255, DEFAULT_REVIEW_COLOR&255))
                e.set_image(url=seg["url"])
                embeds.append(e)
        return embeds

    # ---------------------
    # CHARACTER GraphQL + deep fallback + builder
    # ---------------------
    async def fetch_character_api(self, char_id: int) -> Optional[dict]:
        query = """
        query($id: Int) {
          Character(id: $id) {
            id name { full native alternative } image { large medium } favourites description(asHtml: true) siteUrl
            media { edges { node { id title { romaji english } coverImage { large } siteUrl type } } }
          }
        }
        """
        try:
            async with self.session.post(ANILIST_API, json={"query": query, "variables": {"id": char_id}}, timeout=25) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.debug("Character API status %s: %s", resp.status, text)
                    return None
                j = await resp.json()
                return j.get("data", {}).get("Character")
        except Exception:
            logger.exception("fetch_character_api failed")
            return None

    async def fetch_character_parse_fallback(self, char_id: int) -> Optional[dict]:
        url = f"https://anilist.co/character/{char_id}"
        logger.info("Character HTML fallback for %s", url)
        try:
            async with self.session.get(url, timeout=HTML_TIMEOUT, headers={"User-Agent": "AniListBot/1.0"}) as resp:
                html = await resp.text()
        except Exception:
            logger.exception("fetch_character_parse_fallback: http fetch failed")
            return None
        name = None
        native = None
        alts = []
        image = None
        favourites = 0
        desc = ""
        m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html, re.I)
        if m:
            name = m.group(1).strip()
        m2 = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.I)
        if m2:
            image = m2.group(1).strip()
        m_fav = re.search(r'Favorites</dt>\s*<dd[^>]*>\s*([0-9,]+)\s*</dd>', html, re.I)
        if m_fav:
            try:
                favourites = int(m_fav.group(1).replace(",", ""))
            except:
                favourites = 0
        mdesc = re.search(r'<div[^>]+class=["\']description[^"\']*["\'][^>]*>(.*?)</div>', html, re.I|re.S)
        if mdesc:
            desc = re.sub(r'<[^>]+>', '', mdesc.group(1)).strip()
        # alt names parsing: find other names list
        for malt in re.finditer(r'Other names(?:.*?)</dt>\s*<dd[^>]*>(.*?)</dd>', html, re.I|re.S):
            txt = re.sub(r'<[^>]+>', '', malt.group(1)).strip()
            for n in re.split(r',\s*', txt):
                if n:
                    alts.append(n.strip())
        return {
            "id": char_id,
            "name": {"full": name or f"Character {char_id}", "native": native, "alternative": alts},
            "image": {"large": image} if image else {},
            "favourites": favourites or 0,
            "description": desc,
            "siteUrl": url
        }

    async def fetch_character(self, char_id: int) -> Optional[dict]:
        api = await self.fetch_character_api(char_id)
        if api:
            return api
        return await self.fetch_character_parse_fallback(char_id)

    async def build_character_embed(self, char_id: int) -> discord.Embed:
        ch = await self.fetch_character(char_id)
        if not ch:
            return discord.Embed(description="❌ Character not found.", color=discord.Color.red())
        name_obj = ch.get("name") or {}
        name = name_obj.get("full") or "Unknown"
        native = name_obj.get("native")
        alts = name_obj.get("alternative") or []
        desc_html = ch.get("description") or ""
        desc = self.clean_text(desc_html)
        # Title plain, description has bold name for rendering
        desc_top = f"**{name}**"
        if native and native not in (name,):
            desc_top += f" | *{native}*"
        final_desc = desc_top + ("\n\n" + (desc[:1400] + "...") if len(desc) > 1400 else ("\n\n" + desc if desc else ""))
        embed = discord.Embed(title=name, url=ch.get("siteUrl"), description=final_desc, colour=discord.Color.blue())
        # show other names under title as a field
        if alts:
            # if any spoiler-like names (we can't detect AniList spoiler flags easily in fallback), keep it raw
            def format_alt(n):
                if n.startswith("||") and n.endswith("||"):
                    return n
                return n
            embed.add_field(name="Other Names", value=", ".join(format_alt(a) for a in alts[:12]), inline=False)
        # favourites under the thumbnail/pfp section - put as a field to show near thumbnail
        favs = ch.get("favourites", 0)
        embed.add_field(name="❤️ Favorites", value=str(favs), inline=True)
        img = (ch.get("image") or {}).get("large") or (ch.get("image") or {}).get("medium")
        if img:
            # set both author icon (left) and thumbnail (right)
            embed.set_author(name=name, icon_url=img, url=ch.get("siteUrl"))
            embed.set_thumbnail(url=img)
        return embed

    # ---------------------
    # STAFF GraphQL + deep fallback + builder + pager
    # ---------------------
    async def fetch_staff_api(self, staff_id: int) -> Optional[dict]:
        query = """
        query($id: Int) {
          Staff(id: $id) {
            id name { full native alternative } image { large medium } favourites description(asHtml: true) siteUrl
            staffMedia(perPage: 100) {
              edges { role node { id title { romaji english } coverImage { large medium } siteUrl type startDate { year month day } } }
            }
          }
        }
        """
        try:
            async with self.session.post(ANILIST_API, json={"query": query, "variables": {"id": staff_id}}, timeout=30) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.debug("Staff API status %s: %s", resp.status, text)
                    return None
                j = await resp.json()
                return j.get("data", {}).get("Staff")
        except Exception:
            logger.exception("fetch_staff_api failed")
            return None

    async def fetch_staff_parse_fallback(self, staff_id: int) -> Optional[dict]:
        url = f"https://anilist.co/staff/{staff_id}"
        logger.info("Staff HTML fallback for %s", url)
        try:
            async with self.session.get(url, timeout=HTML_TIMEOUT, headers={"User-Agent": "AniListBot/1.0"}) as resp:
                html = await resp.text()
        except Exception:
            logger.exception("fetch_staff_parse_fallback: http fetch failed")
            return None
        name = None
        native = None
        alts = []
        img = None
        favs = 0
        desc = ""
        for m in re.finditer(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', html, re.I):
            name = m.group(1).strip()
            break
        mimg = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.I)
        if mimg:
            img = mimg.group(1).strip()
        mfav = re.search(r'Favorites</dt>\s*<dd[^>]*>\s*([0-9,]+)\s*</dd>', html, re.I)
        if mfav:
            try:
                favs = int(mfav.group(1).replace(",", ""))
            except:
                favs = 0
        mdesc = re.search(r'<div[^>]+class=["\']description[^"\']*["\'][^>]*>(.*?)</div>', html, re.I|re.S)
        if mdesc:
            desc = re.sub(r'<[^>]+>', '', mdesc.group(1)).strip()
        # parse roles (deep): look for links to anime/manga with small role text nearby
        roles = []
        for m in re.finditer(r'<a[^>]+href=["\']https?://anilist\.co/(anime|manga)/(\d+)[^"\']*["\'][^>]*>(.*?)</a>(?:.*?)<small[^>]*>(.*?)</small>', html, re.I|re.S):
            typ = m.group(1).upper()
            mid = m.group(2)
            title = re.sub(r'<[^>]+>', '', m.group(3)).strip()
            role_text = re.sub(r'<[^>]+>', '', m.group(4)).strip()
            roles.append({"role": role_text, "node": {"title": {"romaji": title}, "coverImage": {"large": None}, "siteUrl": f"https://anilist.co/{typ.lower()}/{mid}", "type": typ}})
        # fallback if none found: try script JSON
        jmatch = re.search(r'window\.__APOLLO_STATE__\s*=\s*({.+?});\s*</script>', html, re.S)
        if jmatch:
            try:
                data = json.loads(jmatch.group(1))
                # rough pass: find staffMedia entries
            except Exception:
                pass
        return {"id": staff_id, "name": {"full": name or f"Staff {staff_id}", "native": native, "alternative": alts}, "image": {"large": img} if img else {}, "favourites": favs or 0, "description": desc, "siteUrl": url, "staffMedia": {"edges": roles}}

    async def fetch_staff(self, staff_id: int) -> Optional[dict]:
        api = await self.fetch_staff_api(staff_id)
        if api:
            return api
        return await self.fetch_staff_parse_fallback(staff_id)

    # Staff pager view (Anime/Manga selector + Prev/Counter/Next)
    class StaffPager(ui.View):
        def __init__(self, staff_id: int, anime_pages: List[discord.Embed], manga_pages: List[discord.Embed], message_id: Optional[int] = None):
            super().__init__(timeout=None)
            self.staff_id = int(staff_id)
            self.anime_pages = anime_pages or []
            self.manga_pages = manga_pages or []
            self.current_pages = []
            self.index = 0
            self.message_id = message_id
            # Top selector buttons
            self.add_item(ui.Button(label="🎬 Anime Staff Role", style=discord.ButtonStyle.success, custom_id=f"staff:{self.staff_id}:anime"))
            self.add_item(ui.Button(label="📚 Manga/Novel Staff Role", style=discord.ButtonStyle.primary, custom_id=f"staff:{self.staff_id}:manga"))
            # Navigation row: prev, counter (disabled), next
            self.prev_btn = ui.Button(label="⬅ Prev", style=discord.ButtonStyle.secondary, custom_id=f"staff:{self.staff_id}:prev")
            self.counter_btn = ui.Button(label=f"Page 0/0", style=discord.ButtonStyle.secondary, disabled=True, custom_id=f"staff:{self.staff_id}:counter")
            self.next_btn = ui.Button(label="Next ➡", style=discord.ButtonStyle.secondary, custom_id=f"staff:{self.staff_id}:next")
            # add on second row
            self.add_item(self.prev_btn)
            self.add_item(self.counter_btn)
            self.add_item(self.next_btn)
            # assign callbacks
            self.prev_btn.callback = self._prev
            self.next_btn.callback = self._next
            # dynamic callbacks for top buttons
            self.children[0].callback = self._set_anime  # first top element
            self.children[1].callback = self._set_manga  # second top element

        async def _set_anime(self, interaction: discord.Interaction):
            self.current_pages = self.anime_pages or []
            self.index = 0
            await self._update(interaction)

        async def _set_manga(self, interaction: discord.Interaction):
            self.current_pages = self.manga_pages or []
            self.index = 0
            await self._update(interaction)

        async def _prev(self, interaction: discord.Interaction):
            if not self.current_pages:
                return await interaction.response.defer()
            self.index = (self.index - 1) % len(self.current_pages)
            await self._update(interaction)

        async def _next(self, interaction: discord.Interaction):
            if not self.current_pages:
                return await interaction.response.defer()
            self.index = (self.index + 1) % len(self.current_pages)
            await self._update(interaction)

        async def _update(self, interaction: discord.Interaction):
            if not self.current_pages:
                em = discord.Embed(description="No pages available.", color=discord.Color.greyple())
                await interaction.response.edit_message(embed=em, view=self)
                return
            current = self.current_pages[self.index]
            total = len(self.current_pages)
            self.counter_btn.label = f"Page {self.index+1}/{total}"
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=current, view=self)
            else:
                await interaction.followup.edit_message(interaction.message.id, embed=current, view=self)

    async def build_staff_embeds_and_view(self, staff_id: int) -> Tuple[List[discord.Embed], Optional[ui.View]]:
        st = await self.fetch_staff(staff_id)
        if not st:
            return [discord.Embed(description="❌ Staff not found.", color=discord.Color.red())], None
        name_obj = st.get("name") or {}
        name = name_obj.get("full") or f"Staff {staff_id}"
        native = name_obj.get("native")
        alts = name_obj.get("alternative") or []
        desc = self.clean_text(st.get("description") or "")
        base = discord.Embed(title=name, url=st.get("siteUrl"), description=(desc[:1200] + "...") if len(desc) > 1200 else desc, color=discord.Color.dark_teal())
        # show native and alt names under title fields
        if native:
            base.add_field(name="Native", value=native, inline=True)
        if alts:
            base.add_field(name="Other Names", value=", ".join(alts[:10]), inline=False)
        base.add_field(name="❤️ Favorites", value=str(st.get("favourites", 0)), inline=True)
        img = (st.get("image") or {}).get("large")
        if img:
            base.set_author(name=name, icon_url=img, url=st.get("siteUrl"))
            base.set_thumbnail(url=img)
        # Build per-role pages: 1 per page, include cover, title (linked), and role
        edges = (st.get("staffMedia") or {}).get("edges") or []
        anime_pages = []
        manga_pages = []
        for e in edges:
            role = e.get("role") or ""
            node = e.get("node") or {}
            title = (node.get("title") or {}).get("romaji") or (node.get("title") or {}).get("english") or "Unknown"
            site = node.get("siteUrl") or None
            cover = (node.get("coverImage") or {}).get("large") or (node.get("coverImage") or {}).get("medium")
            typ = (node.get("type") or "").upper() or node.get("type") or ""
            em = discord.Embed(title=title, url=site, description=f"**Role:** {role}", color=discord.Color.blurple())
            if cover:
                em.set_thumbnail(url=cover)
            em.set_footer(text=f"{typ or 'Unknown'}")
            if typ == "ANIME":
                anime_pages.append(em)
            else:
                manga_pages.append(em)
        # If there are no pages for a type, put a placeholder
        if not anime_pages:
            anime_pages = [discord.Embed(description="No anime roles found.", color=discord.Color.greyple())]
        if not manga_pages:
            manga_pages = [discord.Embed(description="No manga/novel roles found.", color=discord.Color.greyple())]
        view = self.StaffPager(staff_id, anime_pages, manga_pages)
        return [base], view

    # ---------------------
    # Media paginator view & helpers (restore persistence functions)
    # ---------------------
    class MediaPaginator(ui.View):
        def __init__(self, cog: "AniListCog", message_id: int, channel_id: int, media_id: int, media_type: str, total_pages: int, current_page: int = 1):
            super().__init__(timeout=None)
            self.cog = cog
            self.message_id = str(message_id)
            self.channel_id = int(channel_id)
            self.media_id = int(media_id)
            self.media_type = media_type
            self.total_pages = max(1, int(total_pages))
            self.current_page = max(1, int(current_page))
            # Buttons
            self.desc_btn = ui.Button(label="📖 Description", style=discord.ButtonStyle.primary, custom_id=f"media:{self.message_id}:desc")
            self.recs_btn = ui.Button(label="🎯 Recommendations", style=discord.ButtonStyle.success, custom_id=f"media:{self.message_id}:recs")
            self.char_btn = ui.Button(label="🎭 Characters", style=discord.ButtonStyle.secondary, custom_id=f"media:{self.message_id}:chars")
            self.staff_btn = ui.Button(label="🛠 Staff", style=discord.ButtonStyle.secondary, custom_id=f"media:{self.message_id}:staff")
            self.back_btn = ui.Button(label="⬅ Back", style=discord.ButtonStyle.secondary, custom_id=f"media:{self.message_id}:back")
            # Add items
            self.add_item(self.desc_btn)
            self.add_item(self.recs_btn)
            self.add_item(self.char_btn)
            self.add_item(self.staff_btn)
            self.add_item(self.back_btn)
            # Wire callbacks
            self.desc_btn.callback = self.show_description
            self.recs_btn.callback = self.show_recommendations
            self.char_btn.callback = self.show_characters
            self.staff_btn.callback = self.show_staff
            self.back_btn.callback = self.show_main

            # Select dropdown for relations/stats/tags (persisted)
            options = [
                discord.SelectOption(label="🔗 Relations", value="relations", description="Show related media"),
                discord.SelectOption(label="🎭 Characters (Main)", value="characters_main", description="Main characters"),
                discord.SelectOption(label="🌟 Support Cast", value="characters_support", description="Support characters"),
                discord.SelectOption(label="🛡️ Staff", value="staff", description="Media staff"),
                discord.SelectOption(label="📊 Stats", value="stats", description="Stats distribution"),
                discord.SelectOption(label="🎯 Recommendations", value="recommendations", description="Top recommendations"),
                discord.SelectOption(label="🏷 Tags", value="tags", description="Media tags"),
            ]
            self.select = ui.Select(placeholder="More ...", options=options, custom_id=f"media:{self.message_id}:select")
            self.select.callback = self.handle_select
            self.add_item(self.select)

        async def show_main(self, interaction: discord.Interaction):
            try:
                media = await self.cog.fetch_media(self.media_id, self.media_type)
                embeds = self.cog.render_media_pages(media, page=1, total_pages=self.total_pages)
                await interaction.response.edit_message(embeds=embeds, view=self)
            except Exception:
                logger.exception("show_main failed")
                await interaction.response.send_message("Failed to show main page.", ephemeral=True)

        async def show_description(self, interaction: discord.Interaction):
            try:
                media = await self.cog.fetch_media(self.media_id, self.media_type)
                embeds = self.cog.render_media_pages(media, page=2, total_pages=self.total_pages)
                await interaction.response.edit_message(embeds=embeds, view=self)
            except Exception:
                logger.exception("show_description failed")
                await interaction.response.send_message("Failed to show description.", ephemeral=True)

        async def show_recommendations(self, interaction: discord.Interaction):
            try:
                media = await self.cog.fetch_media(self.media_id, self.media_type)
                em = self.cog.build_recommendations_embed(media)
                await interaction.response.edit_message(embeds=[em], view=self)
            except Exception:
                logger.exception("show_recommendations failed")
                await interaction.response.send_message("Failed to show recommendations.", ephemeral=True)

        async def show_characters(self, interaction: discord.Interaction):
            try:
                media = await self.cog.fetch_media(self.media_id, self.media_type)
                ems = self.cog.build_characters_embed(media, support=False)
                await interaction.response.edit_message(embeds=ems, view=self)
            except Exception:
                logger.exception("show_characters failed")
                await interaction.response.send_message("Failed to show characters.", ephemeral=True)

        async def show_staff(self, interaction: discord.Interaction):
            try:
                media = await self.cog.fetch_media(self.media_id, self.media_type)
                ems = self.cog.build_staff_embed(media)
                await interaction.response.edit_message(embeds=ems, view=self)
            except Exception:
                logger.exception("show_staff failed")
                await interaction.response.send_message("Failed to show staff.", ephemeral=True)

        async def handle_select(self, interaction: discord.Interaction):
            try:
                value = interaction.data.get("values", [None])[0]
                media = await self.cog.fetch_media(self.media_id, self.media_type)
                if value == "relations":
                    embeds = self.cog.build_relations_embed(media)
                    await interaction.response.edit_message(embeds=embeds, view=self)
                elif value == "characters_main":
                    embeds = self.cog.build_characters_embed(media, support=False)
                    await interaction.response.edit_message(embeds=embeds, view=self)
                elif value == "characters_support":
                    embeds = self.cog.build_characters_embed(media, support=True)
                    await interaction.response.edit_message(embeds=embeds, view=self)
                elif value == "staff":
                    embeds = self.cog.build_staff_embed(media)
                    await interaction.response.edit_message(embeds=embeds, view=self)
                elif value == "stats":
                    emb = self.cog.build_stats_embed(media)
                    await interaction.response.edit_message(embeds=[emb], view=self)
                elif value == "recommendations":
                    emb = self.cog.build_recommendations_embed(media)
                    await interaction.response.edit_message(embeds=[emb], view=self)
                elif value == "tags":
                    emb = self.cog.build_tags_embed(media)
                    await interaction.response.edit_message(embeds=[emb], view=self)
                else:
                    await interaction.response.send_message("Unknown option.", ephemeral=True)
            except Exception:
                logger.exception("Media select callback failed")
                try:
                    await interaction.response.send_message("Failed to handle option.", ephemeral=True)
                except:
                    pass

    async def _add_media_persistence(self, message_id: int, channel_id: int, media_id: int, media_type: str, total_pages: int, current_page: int = 1):
        try:
            view = self.MediaPaginator(self, message_id, channel_id, media_id, media_type, total_pages, current_page)
            # persist to DB if available
            try:
                # store a simple dict as JSON string
                set_paginator_state(str(message_id), {"type": "media", "media_id": media_id, "media_type": media_type, "total_pages": total_pages, "current_page": current_page})
            except Exception:
                logger.exception("set_paginator_state failed (non-fatal)")
            # register persistent view
            try:
                self.bot.add_view(view, message_id=message_id)
            except Exception:
                logger.exception("bot.add_view failed for media paginator")
            return view
        except Exception:
            logger.exception("Failed to create media persistence view")
            return None

    async def _add_paginator_persistence(self, message_id: int, channel_id: int, activity_id: int, total_pages: int, current_page: int = 1):
        # Simple compatibility for activity paginator usage in your existing code:
        try:
            # We reuse MediaPaginator for generic paginator needs if desired
            view = self.MediaPaginator(self, message_id, channel_id, activity_id, "ACTIVITY", total_pages, current_page)
            try:
                set_paginator_state(str(message_id), {"type": "activity", "activity_id": activity_id, "total_pages": total_pages, "current_page": current_page})
            except Exception:
                logger.exception("set_paginator_state failed for activity (non-fatal)")
            try:
                self.bot.add_view(view, message_id=message_id)
            except Exception:
                logger.exception("bot.add_view failed for activity paginator")
            return view
        except Exception:
            logger.exception("Failed to create activity persistence view")
            return None

    # ---------------------
    # Small wrappers for API fetchers not included above (activity)
    # Keep original functions if exist in your file
    # ---------------------
    async def fetch_activity(self, activity_id: int) -> Optional[dict]:
        query = """
        query($id: Int) {
          Activity(id: $id) {
            __typename
            ... on TextActivity {
              id
              text
              likeCount
              replyCount
              siteUrl
              user { id name siteUrl avatar { large } }
              replies { id text likeCount user { id name siteUrl avatar { large } } }
            }
            ... on MessageActivity {
              id
              message
              likeCount
              replyCount
              siteUrl
              messenger { id name siteUrl avatar { large } }
              recipient { id name siteUrl avatar { large } }
              replies { id text likeCount user { id name siteUrl avatar { large } } }
            }
            ... on ListActivity {
              id
              status
              progress
              likeCount
              replyCount
              siteUrl
              user { id name siteUrl avatar { large } }
              media { id siteUrl title { romaji } coverImage { large } bannerImage }
              replies { id text likeCount user { id name siteUrl avatar { large } } }
            }
          }
        }
        """
        try:
            async with self.session.post(ANILIST_API, json={"query": query, "variables": {"id": activity_id}}, timeout=25) as resp:
                text = await resp.text()
                try:
                    js = await resp.json()
                except Exception:
                    js = None
                if resp.status != 200:
                    logger.error("AniList API error %s: %s", resp.status, text)
                    return None
                if not js or "data" not in js or js["data"].get("Activity") is None:
                    logger.warning("AniList returned no Activity for id %s. Response: %s", activity_id, text)
                    return None
                return js["data"]["Activity"]
        except Exception:
            logger.exception("AniList activity fetch failed.")
            return None

    async def render_page(self, activity: Optional[dict], page: int):
        embeds: List[discord.Embed] = []
        if not activity:
            e = discord.Embed(title="❌ Activity not found", description="This AniList activity is missing, deleted, or could not be retrieved.", color=discord.Color.red())
            embeds.append(e)
            return embeds
        activity_type = activity.get("__typename", "Unknown")
        if activity_type == "MessageActivity":
            user = activity.get("messenger") or {}
            text = activity.get("message") or ""
        else:
            user = activity.get("user") or {}
            text = activity.get("text") or activity.get("status") or ""
        if page == 1:
            media_links, cleaned = self.extract_media(text)
            likes = activity.get("likeCount", 0)
            comments = activity.get("replyCount", 0)
            embed = self.build_embed(activity, activity_type, user, text, media_links, likes, comments)
            embeds.append(embed)
            return embeds
        else:
            # replies page logic (kept succinct)
            replies = activity.get("replies") or []
            start = (page - 2) * REPLIES_PER_PAGE
            for r in replies[start:start + REPLIES_PER_PAGE]:
                u = r.get("user") or {}
                txt = r.get("text") or ""
                e = discord.Embed(description=self.clean_text(txt), color=discord.Color.greyple())
                e.set_author(name=u.get("name"), url=u.get("siteUrl"), icon_url=(u.get("avatar") or {}).get("large"))
                e.set_footer(text=f"Likes: {r.get('likeCount', 0)}")
                embeds.append(e)
            if not embeds:
                embeds.append(discord.Embed(description="No replies.", color=discord.Color.greyple()))
            return embeds

    def build_embed(self, activity: dict, activity_type: str, user: dict, text: str, media_links: list, likes: int, comments: int = 0):
        embed = discord.Embed(color=discord.Color.blurple())
        clean = self.clean_text(text)
        embed.set_author(name=(user or {}).get("name", "Unknown"), url=(user or {}).get("siteUrl", ""), icon_url=((user or {}).get("avatar") or {}).get("large"))
        embed.description = clean or "*No content*"
        # add media links inline as fields and first image as embed image if present
        if media_links:
            first = media_links[0]
            if any(first.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                embed.set_image(url=first)
            else:
                embed.add_field(name="🔗 Media", value=f"[Click here]({first})", inline=False)
            for extra in media_links[1:]:
                embed.add_field(name="🔗 Media", value=f"[Click here]({extra})", inline=False)
        embed.set_footer(text="Powered by AniList")
        return embed

    # ---------------------
    # Listener (integrates activity + anime + manga + review + char + staff)
    # ---------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # REVIEW
        m = REVIEW_URL_RE.search(message.content or "")
        if m:
            review_id = int(m.group(1))
            try:
                embeds = await self.build_review_embeds(review_id)
                for e in embeds:
                    await message.channel.send(embed=e)
            except Exception:
                logger.exception("Failed to send review message")
            return

        # CHARACTER
        m = CHARACTER_URL_RE.search(message.content or "")
        if m:
            char_id = int(m.group(1))
            try:
                embed = await self.build_character_embed(char_id)
                await message.channel.send(embed=embed)
            except Exception:
                logger.exception("Failed to send character message")
            return

        # STAFF
        m = STAFF_URL_RE.search(message.content or "")
        if m:
            staff_id = int(m.group(1))
            try:
                embeds, view = await self.build_staff_embeds_and_view(staff_id)
                if embeds:
                    sent = await message.channel.send(embed=embeds[0], view=view)
                    try:
                        self.bot.add_view(view, message_id=sent.id)
                        set_paginator_state(str(sent.id), {"type": "staff", "staff_id": staff_id})
                    except Exception:
                        logger.exception("Failed to persist staff view")
            except Exception:
                logger.exception("Failed to send staff message")
            return

        # Activity link handling
        m = ACTIVITY_URL_RE.search(message.content or "")
        if m:
            activity_id = int(m.group(1))
            activity = await self.fetch_activity(activity_id)
            if not activity:
                await message.channel.send("❌ Failed to fetch activity.")
                return
            total_replies = len(activity.get("replies") or [])
            total_pages = 1 + math.ceil(max(0, total_replies) / REPLIES_PER_PAGE)
            embeds = await self.render_page(activity, page=1)
            try:
                sent = await message.channel.send(embeds=embeds)
            except Exception:
                logger.exception("Failed to send activity message")
                return
            try:
                view = await self._add_paginator_persistence(sent.id, sent.channel.id, activity_id, total_pages, current_page=1)
                try:
                    await sent.edit(view=view)
                except Exception:
                    logger.exception("Failed to attach paginator view to activity message (message.edit failed).")
            except Exception:
                logger.exception("Failed to persist activity paginator.")
            return

        # Anime link
        m = ANIME_URL_RE.search(message.content or "")
        if m:
            media_id = int(m.group(1))
            media = await self.fetch_media(media_id, "ANIME")
            if not media:
                await message.channel.send("❌ Failed to fetch anime info.")
                return
            total_pages = 2
            embeds = self.render_media_pages(media, page=1, total_pages=total_pages)
            try:
                sent = await message.channel.send(embeds=embeds)
            except Exception:
                logger.exception("Failed to send anime message")
                return
            try:
                view = await self._add_media_persistence(sent.id, sent.channel.id, media_id, "ANIME", total_pages, current_page=1)
                try:
                    await sent.edit(view=view)
                except Exception:
                    logger.exception("Failed to attach media view to anime message (message.edit failed).")
            except Exception:
                logger.exception("Failed to persist media paginator for anime.")
            return

        # Manga link
        m = MANGA_URL_RE.search(message.content or "")
        if m:
            media_id = int(m.group(1))
            media = await self.fetch_media(media_id, "MANGA")
            if not media:
                await message.channel.send("❌ Failed to fetch manga info.")
                return
            total_pages = 2
            embeds = self.render_media_pages(media, page=1, total_pages=total_pages)
            try:
                sent = await message.channel.send(embeds=embeds)
            except Exception:
                logger.exception("Failed to send manga message")
                return
            try:
                view = await self._add_media_persistence(sent.id, sent.channel.id, media_id, "MANGA", total_pages, current_page=1)
                try:
                    await sent.edit(view=view)
                except Exception:
                    logger.exception("Failed to attach media view to manga message (message.edit failed).")
            except Exception:
                logger.exception("Failed to persist media paginator for manga.")
            return

# setup
async def setup(bot: commands.Bot):
    cog = AniListCog(bot)
    await bot.add_cog(cog)
