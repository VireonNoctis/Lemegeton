# embed.py
import discord
from discord.ext import commands, tasks
from discord.ui import View, Button
import aiohttp
import yt_dlp
import os
import re
import json
import asyncio
import tempfile
import subprocess
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from typing import Optional, Tuple

# -------------------------
# Config
# -------------------------
PERSIST_FILE = os.path.join("data", "embed_delete_buttons.json")
DELETE_TIMEOUT = 7200  # seconds (2 hours)
DEFAULT_MAX_UPLOAD = int(os.getenv("DISCORD_UPLOAD_LIMIT", 8 * 1024 * 1024))  # 8MB default; you can override env
FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg")
YDL_OPTS = {"quiet": True, "no_warnings": True, "skip_download": True, "format": "bestvideo+bestaudio/best"}
NOEMBED_URL = "https://noembed.com/embed?url="

SITE_LOGOS = {
    "youtube": "https://cdn-icons-png.flaticon.com/512/1384/1384060.png",
    "tiktok": "https://cdn-icons-png.flaticon.com/512/3046/3046121.png",
    "twitter": "https://cdn-icons-png.flaticon.com/512/733/733579.png",
    "reddit": "https://cdn-icons-png.flaticon.com/512/2111/2111589.png",
    "instagram": "https://cdn-icons-png.flaticon.com/512/2111/2111463.png",
    "facebook": "https://cdn-icons-png.flaticon.com/512/733/733547.png",
    "pinterest": "https://cdn-icons-png.flaticon.com/512/2111/2111490.png",
    "threads": "https://cdn-icons-png.flaticon.com/512/565/565310.png",
    "linkedin": "https://cdn-icons-png.flaticon.com/512/174/174857.png",
    "snapchat": "https://cdn-icons-png.flaticon.com/512/2111/2111468.png",
    "generic": "https://cdn-icons-png.flaticon.com/512/565/565547.png"
}

# -------------------------
# Persistence helpers
# -------------------------
def _load_persist() -> dict:
    if os.path.exists(PERSIST_FILE):
        try:
            with open(PERSIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_persist(d: dict):
    with open(PERSIST_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)

# -------------------------
# Web helpers
# -------------------------
async def fetch_text(session: aiohttp.ClientSession, url: str, timeout: int = 15) -> Optional[str]:
    try:
        async with session.get(url, timeout=timeout, headers={"User-Agent":"Mozilla/5.0"}) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception:
        return None
    return None

def parse_og(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    data = {}
    def get_meta(name):
        tag = soup.find("meta", property=f"og:{name}") or soup.find("meta", attrs={"name": f"og:{name}"})
        return tag["content"] if tag and tag.get("content") else None
    data["title"] = get_meta("title") or (soup.title.string if soup.title else None)
    data["description"] = get_meta("description")
    data["image"] = get_meta("image")
    data["site_name"] = get_meta("site_name")
    return data

# -------------------------
# yt_dlp scraping wrapper (synchronous)
# -------------------------
def scrape_with_yt_dlp(url: str) -> Optional[dict]:
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return None

    out = {}
    out["title"] = info.get("title")
    out["description"] = info.get("description")
    out["uploader"] = info.get("uploader") or info.get("creator") or info.get("author")
    out["uploader_url"] = None
    if info.get("channel_id"):
        out["uploader_url"] = f"https://www.youtube.com/channel/{info.get('channel_id')}"
    elif info.get("uploader_id"):
        out["uploader_url"] = f"https://www.youtube.com/user/{info.get('uploader_id')}"
    out["thumbnail"] = info.get("thumbnail")
    out["pfp"] = info.get("channel_favicon") or info.get("uploader_thumbnail") or info.get("thumbnail")
    # published
    if info.get("upload_date"):
        d = info.get("upload_date")
        try:
            out["published"] = datetime.strptime(d, "%Y%m%d").replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            out["published"] = None
    elif info.get("timestamp"):
        try:
            out["published"] = datetime.fromtimestamp(int(info.get("timestamp")), tz=timezone.utc).isoformat()
        except Exception:
            out["published"] = None
    else:
        out["published"] = info.get("release_date") or info.get("created_at") or None
    out["view_count"] = info.get("view_count")
    out["like_count"] = info.get("like_count") or info.get("likeCount")
    out["comment_count"] = info.get("comment_count")
    out["repost_count"] = info.get("repost_count") or info.get("share_count") or info.get("retweet_count")
    # direct media selection: prefer a direct MP4/webm/best format
    direct = info.get("url")
    if not direct and info.get("formats"):
        # pick best progressive format (has both audio+video) or bestvideo+audio fallback is complex
        for f in reversed(info.get("formats")):
            if f.get("acodec") != "none" and f.get("vcodec") != "none" and f.get("url"):
                direct = f.get("url")
                break
        if not direct:
            # fallback: last format's url
            direct = info.get("formats")[-1].get("url")
    out["direct_url"] = direct
    out["webpage_url"] = info.get("webpage_url") or url
    return out

# -------------------------
# Media download & optional transcode to fit limit
# -------------------------
async def download_media_bytes(url: str, timeout: int = 60) -> Optional[bytes]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout, headers={"User-Agent":"Mozilla/5.0"}) as resp:
                if resp.status == 200:
                    return await resp.read()
    except Exception:
        return None
    return None

def transcode_to_limit(input_path: str, output_path: str, max_bytes: int) -> bool:
    """
    Use ffmpeg to re-encode to fit a target size (best-effort).
    Strategy: try re-encoding at progressively lower bitrates.
    Returns True on success (output <= max_bytes).
    """
    # try a few bitrate targets (kbps)
    bitrates = [1500, 1200, 800, 600, 400]  # kbps
    for kbps in bitrates:
        # build ffmpeg command to re-encode with target bitrate
        cmd = [
            FFMPEG_BINARY, "-y", "-i", input_path,
            "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{kbps}k",
            "-c:a", "aac", "-b:a", "96k",
            "-movflags", "+faststart",
            output_path
        ]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(output_path) and os.path.getsize(output_path) <= max_bytes:
                return True
        except Exception:
            continue
    return False

# -------------------------
# Build view helper (View + Delete)
# -------------------------
def make_control_view(link_url: str, author_id: int) -> Tuple[View, str]:
    view = View(timeout=None)
    view.add_item(Button(label="View", style=discord.ButtonStyle.link, url=link_url))
    custom_id = f"embed_delete:{author_id}:{int(datetime.now(tz=timezone.utc).timestamp())}"
    # delete button will be registered through DeleteView so we don't add callback here
    btn = Button(label="Delete", style=discord.ButtonStyle.danger, custom_id=custom_id)
    view.add_item(btn)
    return view, custom_id

# -------------------------
# Per-site processors (use yt_dlp + fallback)
# -------------------------
# All processors return (embed, file_path_or_None, view, custom_id)
# file_path is path on disk to uploaded file (caller will convert to discord.File and cleanup)

async def _process_youtube(url: str, author: discord.User) -> Tuple[discord.Embed, Optional[str], View, str]:
    scraped = scrape_with_yt_dlp(url)
    if not scraped:
        # fallback generic
        return await _process_generic(url, author, "youtube")

    title = scraped.get("title") or "Untitled"
    description = scraped.get("description") or ""
    uploader = scraped.get("uploader") or "Unknown"
    uploader_url = scraped.get("uploader_url")
    pfp = scraped.get("pfp")
    thumbnail = scraped.get("thumbnail")
    published = scraped.get("published")
    comments = scraped.get("comment_count") or 0
    likes = scraped.get("like_count") or 0
    views = scraped.get("view_count") or 0
    reposts = scraped.get("repost_count") or 0

    embed = discord.Embed(title=title, url=scraped.get("webpage_url"), description=(description[:800] + "...") if len(description) > 800 else description, color=discord.Color.red())
    embed.set_author(name=uploader, url=uploader_url, icon_url=pfp or discord.Embed.Empty)
    embed.add_field(name="", value=f"💬 {comments}   ❤️ {likes}   👁️ {views}   🔁 {reposts}", inline=False)
    # footer
    footer_date = "Unknown Date"
    if published:
        try:
            dt = datetime.fromisoformat(published)
            footer_date = dt.strftime("%b %d, %Y")
        except Exception:
            footer_date = str(published).split("T")[0]
    embed.set_footer(text=f"YouTube • {footer_date}", icon_url=SITE_LOGOS["youtube"])

    # try to download direct media
    file_path = None
    direct = scraped.get("direct_url")
    if direct:
        data = await download_media_bytes(direct)
        if data:
            # write to tmp file
            suffix = ".mp4"
            tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp_in.write(data)
            tmp_in.flush()
            tmp_in.close()
            # check size
            size = os.path.getsize(tmp_in.name)
            # Attempt to fit within DEFAULT_MAX_UPLOAD
            limit = DEFAULT_MAX_UPLOAD
            # If guild's limit is higher we will adjust later in caller based on channel
            if size <= limit:
                file_path = tmp_in.name
            else:
                # try to transcode to fit
                tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                tmp_out.close()
                ok = transcode_to_limit(tmp_in.name, tmp_out.name, limit)
                if ok:
                    file_path = tmp_out.name
                    try:
                        os.remove(tmp_in.name)
                    except Exception:
                        pass
                else:
                    # keep thumbnail fallback, cleanup files
                    try:
                        os.remove(tmp_in.name)
                    except Exception:
                        pass
                    try:
                        os.remove(tmp_out.name)
                    except Exception:
                        pass
                    file_path = None

    # set image if no file
    if not file_path and thumbnail:
        embed.set_image(url=thumbnail)

    view, custom_id = make_control_view(scraped.get("webpage_url") or url, author.id)
    return embed, file_path, view, custom_id

async def _process_tiktok(url: str, author: discord.User) -> Tuple[discord.Embed, Optional[str], View, str]:
    scraped = scrape_with_yt_dlp(url)
    if not scraped:
        return await _process_generic(url, author, "tiktok")
    title = scraped.get("title") or ""
    desc = scraped.get("description") or ""
    uploader = scraped.get("uploader") or "Unknown"
    pfp = scraped.get("pfp")
    thumb = scraped.get("thumbnail")
    published = scraped.get("published")
    comments = scraped.get("comment_count") or 0
    likes = scraped.get("like_count") or 0
    views = scraped.get("view_count") or 0
    reposts = scraped.get("repost_count") or 0

    embed = discord.Embed(title=title, url=scraped.get("webpage_url"), description=(desc[:800] + "...") if len(desc) > 800 else desc, color=discord.Color.dark_teal())
    embed.set_author(name=uploader, url=scraped.get("uploader_url"), icon_url=pfp or discord.Embed.Empty)
    embed.add_field(name="", value=f"💬 {comments}   ❤️ {likes}   👁️ {views}   🔁 {reposts}", inline=False)
    footer_date = "Unknown Date"
    if published:
        try:
            dt = datetime.fromisoformat(published)
            footer_date = dt.strftime("%b %d, %Y")
        except Exception:
            footer_date = str(published).split("T")[0]
    embed.set_footer(text=f"TikTok • {footer_date}", icon_url=SITE_LOGOS["tiktok"])

    # download media
    file_path = None
    direct = scraped.get("direct_url")
    if direct:
        data = await download_media_bytes(direct)
        if data:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tmp.write(data); tmp.flush(); tmp.close()
            if os.path.getsize(tmp.name) <= DEFAULT_MAX_UPLOAD:
                file_path = tmp.name
            else:
                tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4"); tmp_out.close()
                ok = transcode_to_limit(tmp.name, tmp_out.name, DEFAULT_MAX_UPLOAD)
                if ok:
                    file_path = tmp_out.name
                    os.remove(tmp.name)
                else:
                    os.remove(tmp.name); os.remove(tmp_out.name); file_path = None

    if not file_path and thumb:
        embed.set_image(url=thumb)

    view, custom_id = make_control_view(scraped.get("webpage_url") or url, author.id)
    return embed, file_path, view, custom_id

async def _process_twitter(url: str, author: discord.User) -> Tuple[discord.Embed, Optional[str], View, str]:
    scraped = scrape_with_yt_dlp(url)
    if not scraped:
        return await _process_generic(url, author, "twitter")
    title = scraped.get("title") or ""
    desc = scraped.get("description") or ""
    uploader = scraped.get("uploader") or "Unknown"
    pfp = scraped.get("pfp")
    thumb = scraped.get("thumbnail")
    published = scraped.get("published")
    comments = scraped.get("comment_count") or 0
    likes = scraped.get("like_count") or 0
    views = scraped.get("view_count") or 0
    reposts = scraped.get("repost_count") or 0

    embed = discord.Embed(title=title, url=scraped.get("webpage_url"), description=(desc[:800] + "...") if len(desc) > 800 else desc, color=discord.Color.blue())
    embed.set_author(name=uploader, url=scraped.get("uploader_url"), icon_url=pfp or discord.Embed.Empty)
    embed.add_field(name="", value=f"💬 {comments}   ❤️ {likes}   👁️ {views}   🔁 {reposts}", inline=False)
    footer_date = "Unknown Date"
    if published:
        try:
            dt = datetime.fromisoformat(published)
            footer_date = dt.strftime("%b %d, %Y")
        except Exception:
            footer_date = str(published).split("T")[0]
    embed.set_footer(text=f"Twitter • {footer_date}", icon_url=SITE_LOGOS["twitter"])

    # media download logic (same general approach)
    file_path = None
    direct = scraped.get("direct_url")
    if direct:
        data = await download_media_bytes(direct)
        if data:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4"); tmp.write(data); tmp.flush(); tmp.close()
            if os.path.getsize(tmp.name) <= DEFAULT_MAX_UPLOAD:
                file_path = tmp.name
            else:
                tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4"); tmp_out.close()
                ok = transcode_to_limit(tmp.name, tmp_out.name, DEFAULT_MAX_UPLOAD)
                if ok:
                    file_path = tmp_out.name
                    os.remove(tmp.name)
                else:
                    os.remove(tmp.name); os.remove(tmp_out.name); file_path = None

    if not file_path and thumb:
        embed.set_image(url=thumb)

    view, custom_id = make_control_view(scraped.get("webpage_url") or url, author.id)
    return embed, file_path, view, custom_id

async def _process_instagram(url: str, author: discord.User) -> Tuple[discord.Embed, Optional[str], View, str]:
    scraped = scrape_with_yt_dlp(url)
    if not scraped:
        return await _process_generic(url, author, "instagram")
    title = scraped.get("title") or ""
    desc = scraped.get("description") or ""
    uploader = scraped.get("uploader") or "Unknown"
    pfp = scraped.get("pfp")
    thumb = scraped.get("thumbnail")
    published = scraped.get("published")
    comments = scraped.get("comment_count") or 0
    likes = scraped.get("like_count") or 0
    views = scraped.get("view_count") or 0
    reposts = scraped.get("repost_count") or 0

    embed = discord.Embed(title=title, url=scraped.get("webpage_url"), description=(desc[:800] + "...") if len(desc) > 800 else desc, color=discord.Color.purple())
    embed.set_author(name=uploader, url=scraped.get("uploader_url"), icon_url=pfp or discord.Embed.Empty)
    embed.add_field(name="", value=f"💬 {comments}   ❤️ {likes}   👁️ {views}   🔁 {reposts}", inline=False)
    footer_date = "Unknown Date"
    if published:
        try:
            dt = datetime.fromisoformat(published); footer_date = dt.strftime("%b %d, %Y")
        except Exception: footer_date = str(published).split("T")[0]
    embed.set_footer(text=f"Instagram • {footer_date}", icon_url=SITE_LOGOS["instagram"])

    file_path = None
    direct = scraped.get("direct_url")
    if direct:
        data = await download_media_bytes(direct)
        if data:
            ext = ".mp4" if re.search(r"\.(mp4|webm|mov)", direct, re.IGNORECASE) else ".jpg"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext); tmp.write(data); tmp.flush(); tmp.close()
            if os.path.getsize(tmp.name) <= DEFAULT_MAX_UPLOAD:
                file_path = tmp.name
            else:
                if ext in [".mp4", ".webm", ".mov"]:
                    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=ext); tmp_out.close()
                    ok = transcode_to_limit(tmp.name, tmp_out.name, DEFAULT_MAX_UPLOAD)
                    if ok:
                        file_path = tmp_out.name
                        os.remove(tmp.name)
                    else:
                        os.remove(tmp.name); os.remove(tmp_out.name); file_path = None
                else:
                    # image too large: leave as external thumbnail
                    os.remove(tmp.name); file_path = None

    if not file_path and thumb:
        embed.set_image(url=thumb)

    view, custom_id = make_control_view(scraped.get("webpage_url") or url, author.id)
    return embed, file_path, view, custom_id

async def _process_reddit(url: str, author: discord.User) -> Tuple[discord.Embed, Optional[str], View, str]:
    scraped = scrape_with_yt_dlp(url)
    if not scraped:
        return await _process_generic(url, author, "reddit")
    title = scraped.get("title") or ""
    desc = scraped.get("description") or ""
    uploader = scraped.get("uploader") or "Unknown"
    pfp = scraped.get("pfp")
    thumb = scraped.get("thumbnail")
    published = scraped.get("published")
    comments = scraped.get("comment_count") or 0
    likes = scraped.get("like_count") or 0
    views = scraped.get("view_count") or 0
    reposts = scraped.get("repost_count") or 0

    embed = discord.Embed(title=title, url=scraped.get("webpage_url"), description=(desc[:800] + "...") if len(desc) > 800 else desc, color=discord.Color.orange())
    embed.set_author(name=uploader, url=scraped.get("uploader_url"), icon_url=pfp or discord.Embed.Empty)
    embed.add_field(name="", value=f"💬 {comments}   ❤️ {likes}   👁️ {views}   🔁 {reposts}", inline=False)
    footer_date = "Unknown Date"
    if published:
        try:
            dt = datetime.fromisoformat(published); footer_date = dt.strftime("%b %d, %Y")
        except Exception: footer_date = str(published).split("T")[0]
    embed.set_footer(text=f"Reddit • {footer_date}", icon_url=SITE_LOGOS["reddit"])

    file_path = None
    direct = scraped.get("direct_url")
    if direct:
        data = await download_media_bytes(direct)
        if data:
            ext = ".mp4" if re.search(r"\.(mp4|webm|mov)", direct, re.IGNORECASE) else ".jpg"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext); tmp.write(data); tmp.flush(); tmp.close()
            if os.path.getsize(tmp.name) <= DEFAULT_MAX_UPLOAD:
                file_path = tmp.name
            else:
                if ext in [".mp4", ".webm", ".mov"]:
                    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=ext); tmp_out.close()
                    ok = transcode_to_limit(tmp.name, tmp_out.name, DEFAULT_MAX_UPLOAD)
                    if ok:
                        file_path = tmp_out.name
                        os.remove(tmp.name)
                    else:
                        os.remove(tmp.name); os.remove(tmp_out.name); file_path = None
                else:
                    os.remove(tmp.name); file_path = None

    if not file_path and thumb:
        embed.set_image(url=thumb)

    view, custom_id = make_control_view(scraped.get("webpage_url") or url, author.id)
    return embed, file_path, view, custom_id

# For facebook / pinterest / threads / linkedin / snapchat we reuse generic processor which already handles via yt_dlp or OG
async def _process_facebook(url: str, author: discord.User): return await _process_generic(url, author, "facebook")
async def _process_pinterest(url: str, author: discord.User): return await _process_generic(url, author, "pinterest")
async def _process_threads(url: str, author: discord.User): return await _process_generic(url, author, "threads")
async def _process_linkedin(url: str, author: discord.User): return await _process_generic(url, author, "linkedin")
async def _process_snapchat(url: str, author: discord.User): return await _process_generic(url, author, "snapchat")
async def _process_generic(url: str, author: discord.User, site_key: str = "generic") -> Tuple[discord.Embed, Optional[str], View, str]:
    # Try noembed -> OG -> minimal link embed
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(NOEMBED_URL + aiohttp.helpers.quote(url, safe="")) as r:
                if r.status == 200:
                    j = await r.json()
                    title = j.get("title") or j.get("author_name") or "Shared link"
                    desc = j.get("description") or ""
                    thumb = j.get("thumbnail_url")
                    embed = discord.Embed(title=title, url=url, description=(desc[:800] + "...") if len(desc) > 800 else desc)
                    embed.set_author(name=j.get("author_name") or j.get("provider_name") or site_key.capitalize(), url=j.get("author_url"), icon_url=thumb or SITE_LOGOS.get(site_key, SITE_LOGOS["generic"]))
                    embed.set_footer(text=f"{site_key.capitalize()} • Unknown", icon_url=SITE_LOGOS.get(site_key, SITE_LOGOS["generic"]))
                    view, custom_id = make_control_view(url, author.id)
                    if thumb:
                        embed.set_image(url=thumb)
                    return embed, None, view, custom_id
        except Exception:
            pass

        # OG fallback
        html = await fetch_text(session, url)
        if html:
            og = parse_og(html)
            title = og.get("title") or "Shared link"
            desc = og.get("description") or ""
            img = og.get("image")
            embed = discord.Embed(title=title, url=url, description=(desc[:800] + "...") if len(desc) > 800 else desc)
            embed.set_author(name=og.get("site_name") or site_key.capitalize(), icon_url=SITE_LOGOS.get(site_key, SITE_LOGOS["generic"]))
            if img:
                embed.set_image(url=img)
            embed.set_footer(text=f"{site_key.capitalize()} • Unknown", icon_url=SITE_LOGOS.get(site_key, SITE_LOGOS["generic"]))
            view, custom_id = make_control_view(url, author.id)
            return embed, None, view, custom_id

    # minimal fallback
    embed = discord.Embed(title="Shared link", url=url, description=url)
    embed.set_footer(text=site_key.capitalize(), icon_url=SITE_LOGOS.get(site_key, SITE_LOGOS["generic"]))
    view, custom_id = make_control_view(url, author.id)
    return embed, None, view, custom_id

# -------------------------
# Delete view persistence & handler
# -------------------------
class DeleteView(View):
    def __init__(self, author_id: int, custom_id: str):
        super().__init__(timeout=None)
        self.author_id = int(author_id) if author_id is not None else None
        self.custom_id = custom_id
        # add delete button with same custom_id so it matches interactions
        btn = Button(label="Delete", style=discord.ButtonStyle.danger, custom_id=custom_id)
        self.add_item(btn)
        btn.callback = self._on_delete_click

    async def _on_delete_click(self, interaction: discord.Interaction):
        try:
            if interaction.user.id == self.author_id or interaction.user.guild_permissions.manage_messages:
                await interaction.message.delete()
                # remove persisted entry
                persist = _load_persist()
                persist.pop(str(interaction.message.id), None)
                _save_persist(persist)
                try:
                    await interaction.response.send_message("✅ Embed deleted.", ephemeral=True)
                except Exception:
                    pass
            else:
                await interaction.response.send_message("❌ Only the original poster or mods can delete this.", ephemeral=True)
        except Exception:
            try:
                await interaction.response.send_message("❌ Failed to delete (missing permissions?).", ephemeral=True)
            except Exception:
                pass

# -------------------------
# Main Cog
# -------------------------
class EmbedCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._persist = _load_persist()
        self._cleanup = self._expired_cleanup.start()

    def cog_unload(self):
        if self._cleanup:
            self._cleanup.cancel()

    async def cog_load(self):
        # re-register persisted DeleteViews so buttons survive restart
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        changed = False
        for msg_id_str, info in list(self._persist.items()):
            try:
                expires_at = info.get("expires_at", 0)
                author_id = info.get("author_id")
                custom_id = info.get("custom_id")
                if expires_at <= now_ts:
                    # expired, remove
                    self._persist.pop(msg_id_str, None)
                    changed = True
                    continue
                if custom_id and author_id:
                    dv = DeleteView(author_id=author_id, custom_id=custom_id)
                    try:
                        self.bot.add_view(dv, message_id=int(msg_id_str))
                    except Exception:
                        self.bot.add_view(dv)
            except Exception:
                continue
        if changed:
            _save_persist(self._persist)

    # detect platform and dispatch
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.webhook_id:
            return
        content = (message.content or "").strip()
        if not content:
            return
        low = content.lower()
        try:
            if "youtube.com/watch" in low or "youtu.be/" in low:
                await self._handle_dispatch(message, _process_youtube)
                return
            if "tiktok.com" in low or "vm.tiktok.com" in low:
                await self._handle_dispatch(message, _process_tiktok)
                return
            if "twitter.com" in low or "x.com" in low:
                await self._handle_dispatch(message, _process_twitter)
                return
            if "instagram.com" in low:
                await self._handle_dispatch(message, _process_instagram)
                return
            if "reddit.com" in low:
                await self._handle_dispatch(message, _process_reddit)
                return
            if "facebook.com" in low:
                await self._handle_dispatch(message, _process_facebook)
                return
            if "pinterest.com" in low:
                await self._handle_dispatch(message, _process_pinterest)
                return
            if "threads.net" in low:
                await self._handle_dispatch(message, _process_threads)
                return
            if "linkedin.com" in low:
                await self._handle_dispatch(message, _process_linkedin)
                return
            if "snapchat.com" in low:
                await self._handle_dispatch(message, _process_snapchat)
                return
            # fallback generic if contains known domain
            if re.search(r"(youtube\.com|youtu\.be|tiktok\.com|twitter\.com|x\.com|reddit\.com|instagram\.com|facebook\.com|pinterest\.com|threads\.net|linkedin\.com|snapchat\.com)", low):
                await self._handle_dispatch(message, _process_generic)
                return
        except Exception as e:
            print(f"[embed cog] error dispatching: {e}")

    async def _handle_dispatch(self, message: discord.Message, processor):
        """
        processor: coroutine function(url, author) -> (embed, file_path_or_none, view, custom_id)
        """
        url = (message.content or "").strip()
        try:
            embed, file_path, view, custom_id = await processor(url, message.author)
        except Exception:
            # fallback to generic
            embed, file_path, view, custom_id = await _process_generic(url, message.author, "generic")

        # send embed and optional file
        sent = None
        try:
            if file_path:
                # ensure we send as discord.File, but choose filename
                fname = os.path.basename(file_path)
                try:
                    sent = await message.channel.send(embed=embed, file=discord.File(file_path, filename=fname))
                except discord.HTTPException as he:
                    # if file too large even after transcode, fallback to embed only
                    sent = await message.channel.send(embed=embed)
                # cleanup file afterwards
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            else:
                sent = await message.channel.send(embed=embed)
        except discord.Forbidden:
            try:
                sent = await message.channel.send(url)
            except Exception:
                return
        except Exception:
            try:
                sent = await message.channel.send(embed=embed)
            except Exception:
                sent = await message.channel.send(url)

        # delete original message (best-effort)
        try:
            await message.delete()
        except Exception:
            pass

        # Now attach persistent delete button: create DeleteView and re-edit message to include it
        try:
            # Build a DeleteView bound to author and custom_id
            expires_at = int(datetime.now(tz=timezone.utc).timestamp()) + DELETE_TIMEOUT
            persist_info = {"author_id": message.author.id, "expires_at": expires_at, "custom_id": custom_id}
            self._persist[str(sent.id)] = persist_info
            _save_persist(self._persist)

            dv = DeleteView(author_id=message.author.id, custom_id=custom_id)
            # Add also a View (link) button so final view includes both controls
            try:
                dv.add_item(Button(label="View", style=discord.ButtonStyle.link, url=embed.url or url))
            except Exception:
                pass
            # add view to bot (bind to message)
            try:
                self.bot.add_view(dv, message_id=sent.id)
            except Exception:
                self.bot.add_view(dv)
            # finally edit message to add the dv (so buttons show)
            try:
                await sent.edit(view=dv)
            except Exception:
                # if edit fails, send a small control message with view
                try:
                    await message.channel.send("Controls:", view=dv)
                except Exception:
                    pass
        except Exception:
            pass

    @tasks.loop(seconds=60)
    async def _expired_cleanup(self):
        """
        Remove expired delete buttons visually and purge persistence.
        """
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        changed = False
        for msg_id_str, info in list(self._persist.items()):
            try:
                if info.get("expires_at", 0) <= now_ts:
                    msg_id = int(msg_id_str)
                    # attempt to fetch message anywhere and edit view to remove Delete button
                    for guild in self.bot.guilds:
                        for ch in guild.text_channels + guild.threads:
                            try:
                                msg = None
                                try:
                                    msg = await ch.fetch_message(msg_id)
                                except Exception:
                                    continue
                                if not msg:
                                    continue
                                # build new view with only the View link (if we can read embed)
                                new_view = View(timeout=None)
                                url = None
                                if msg.embeds and msg.embeds[0].url:
                                    url = msg.embeds[0].url
                                if not url and msg.content:
                                    url = msg.content.strip().split()[0]
                                if url:
                                    new_view.add_item(Button(label="View", style=discord.ButtonStyle.link, url=url))
                                try:
                                    await msg.edit(view=new_view)
                                except Exception:
                                    pass
                                break
                            except Exception:
                                continue
                    # remove persist entry
                    self._persist.pop(msg_id_str, None)
                    changed = True
            except Exception:
                continue
        if changed:
            _save_persist(self._persist)

    @_expired_cleanup.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()

# -------------------------
# Cog setup
# -------------------------
async def setup(bot: commands.Bot):
    cog = EmbedCog(bot)
    await bot.add_cog(cog)
    # Re-register persisted delete views so they work immediately
    persist = cog._persist
    for msg_id_str, info in list(persist.items()):
        try:
            if info.get("expires_at", 0) <= int(datetime.now(tz=timezone.utc).timestamp()):
                persist.pop(msg_id_str, None)
                continue
            dv = DeleteView(author_id=info.get("author_id"), custom_id=info.get("custom_id"))
            try:
                bot.add_view(dv, message_id=int(msg_id_str))
            except Exception:
                bot.add_view(dv)
        except Exception:
            continue
    _save_persist(persist)
