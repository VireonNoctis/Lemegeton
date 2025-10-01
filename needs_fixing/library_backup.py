import discord
from discord import app_commands
from discord.ext import commands
import io
import csv
import json
import datetime
import xml.etree.ElementTree as ET
import yaml
import asyncio
import aiohttp
import aiosqlite
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable
from config import DB_PATH

# -----------------------------
# Logging Setup
# -----------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "library_backup.log"

logger = logging.getLogger("LibraryBackup")
logger.setLevel(logging.DEBUG)

if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(LOG_FILE)
           for h in logger.handlers):
    try:
        file_handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(logging.Formatter(fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
                                                      datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(stream_handler)

logger.info("Library backup logging initialized")

# -----------------------------
# DB Helper (placeholder)
# -----------------------------
async def get_anilist_username_from_db(discord_id: int, guild_id: Optional[int] = None) -> Optional[str]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            if guild_id:
                cursor = await db.execute(
                    "SELECT anilist_username FROM users WHERE discord_id = ? AND guild_id = ? AND anilist_username IS NOT NULL",
                    (discord_id, guild_id)
                )
                result = await cursor.fetchone()
                if result:
                    return result[0]

            cursor = await db.execute(
                "SELECT anilist_username FROM users WHERE discord_id = ? AND anilist_username IS NOT NULL LIMIT 1",
                (discord_id,)
            )
            result = await cursor.fetchone()
            if result:
                return result[0]
            return None
    except Exception as e:
        logger.error(f"DB error fetching AniList username for {discord_id}: {e}", exc_info=True)
        return None

# -----------------------------
# AniList Helpers
# -----------------------------
_STATUS_MAP = {
    "CURRENT": "watching",
    "PLANNING": "planned",
    "COMPLETED": "completed",
    "DROPPED": "dropped",
    "PAUSED": "paused",
    "REPEATING": "watching",
}

_STATUS_EMOJI = {
    "watching": "🎬",
    "completed": "🏁",
    "dropped": "❌",
    "paused": "⏸",
    "planned": "📝",
}


async def fetch_anilist_library(username: str, media_type: str, extended: bool = False):
    query = """
    query ($username: String, $type: MediaType) {
      MediaListCollection(userName: $username, type: $type) {
        lists {
          entries {
            media {
              id
              title {
                romaji
                english
                native
              }
              type
              episodes
              chapters
              genres
              averageScore
              siteUrl
            }
            status
            progress
            score
            repeat
            startedAt { year month day }
            completedAt { year month day }
            updatedAt
          }
        }
      }
    }
    """
    variables = {"username": username, "type": media_type.upper()}
    async with aiohttp.ClientSession() as session:
        async with session.post("https://graphql.anilist.co", json={"query": query, "variables": variables}) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

    if "data" not in data or not data["data"].get("MediaListCollection"):
        return []

    seen = {}
    for media_list in data["data"]["MediaListCollection"]["lists"]:
        for entry in media_list.get("entries", []):
            media = entry.get("media") or {}
            mid = media.get("id")
            if not mid:
                continue

            title_block = media.get("title") or {}
            title = title_block.get("romaji") or title_block.get("english") or title_block.get("native") or "Unknown Title"
            status_raw = (entry.get("status") or "").upper()
            normalized_status = _STATUS_MAP.get(status_raw, status_raw.lower() or "unknown")
            progress = entry.get("progress") or 0
            prog_str = f"{progress}/{media.get('chapters') or media.get('episodes') or '?'}"

            start = entry.get("startedAt") or {}
            finish = entry.get("completedAt") or {}

            item = {
                "title": title,
                "status": normalized_status,
                "progress": prog_str,
                "rating": entry.get("score"),
                "tags": [],
                "start_date": f"{start.get('year')}-{start.get('month')}-{start.get('day')}" if start.get("year") else None,
                "finish_date": f"{finish.get('year')}-{finish.get('month')}-{finish.get('day')}" if finish.get("year") else None,
                "rewatch_count": entry.get("repeat", 0),
                "last_updated": datetime.datetime.fromtimestamp(entry.get("updatedAt", int(datetime.datetime.now().timestamp()))).strftime("%Y-%m-%d"),
            }
            if extended:
                item.update({
                    "type": media.get("type"),
                    "genres": media.get("genres", []),
                    "average_score": media.get("averageScore"),
                    "site_url": media.get("siteUrl"),
                    "anilist_id": mid,
                })

            existing = seen.get(mid)
            if not existing or entry.get("updatedAt", 0) > existing.get("updatedAt", 0):
                seen[mid] = item
    return list(seen.values())

# -----------------------------
# Export Generator
# -----------------------------
ProgressCallback = Optional[Callable[[int, Optional[str]], Awaitable[None]]]


def _safe_str(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return ", ".join(map(str, v))
    return str(v)


async def generate_export_file(data: list, fmt: str, progress_cb: ProgressCallback = None):
    fmt = fmt.lower()
    filename = f"library_backup.{fmt}"
    buffer = io.BytesIO()

    if not data:
        if fmt == "json":
            buffer.write(json.dumps([], indent=4).encode())
        elif fmt == "csv":
            buffer.write("title,status,progress,rating\n".encode())
        elif fmt == "xml":
            buffer.write(b'<?xml version="1.0" encoding="utf-8"?><Library />')
        elif fmt == "yaml":
            buffer.write(yaml.dump([], default_flow_style=False).encode())
        else:
            buffer.write("No entries.\n".encode())
        buffer.seek(0)
        return buffer, filename

    if fmt == "json":
        buffer.write(json.dumps(data, indent=4, ensure_ascii=False).encode())
    elif fmt == "yaml":
        buffer.write(yaml.dump(data, sort_keys=False, allow_unicode=True).encode())
    elif fmt == "csv":
        keys = list({k for d in data for k in d.keys()})
        csv_io = io.StringIO()
        writer = csv.DictWriter(csv_io, fieldnames=keys)
        writer.writeheader()
        for row in data:
            writer.writerow({k: _safe_str(row.get(k)) for k in keys})
        buffer.write(csv_io.getvalue().encode())
    elif fmt == "xml":
        root = ET.Element("Library")
        for entry in data:
            item = ET.SubElement(root, "Entry")
            for k, v in entry.items():
                ET.SubElement(item, k).text = _safe_str(v)
        ET.ElementTree(root).write(buffer, encoding="utf-8", xml_declaration=True)
    elif fmt == "txt":
        header = "─────────────────────────────\n📚 Exported via /library_backup\n─────────────────────────────\n\n"
        buffer.write(header.encode())
        for entry in data:
            line = f"{_STATUS_EMOJI.get(entry.get('status',''), '')} {entry['title']} | {entry['status']} | {entry['progress']}\n"
            buffer.write(line.encode())
    else:
        buffer.write(json.dumps(data).encode())

    buffer.seek(0)
    return buffer, filename

# -----------------------------
# Cog
# -----------------------------
class LibraryBackup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="library_backup",
        description="📚 Export your AniList library → JSON / CSV / XML / TXT / YAML ⚡"
    )
    @app_commands.describe(
        username="AniList username (optional if linked)",
        format="Export format",
        scope="Which part of your list to export",
        media_type="Media type",
        delivery="How to deliver the file",
        extended="Include extended metadata?"
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(name="📝 JSON", value="json"),
            app_commands.Choice(name="📊 CSV", value="csv"),
            app_commands.Choice(name="📂 XML", value="xml"),
            app_commands.Choice(name="📜 TXT", value="txt"),
            app_commands.Choice(name="🐍 YAML", value="yaml"),
        ],
        scope=[
            app_commands.Choice(name="📚 Full Library", value="full"),
            app_commands.Choice(name="🏁 Completed", value="completed"),
            app_commands.Choice(name="🎬 Watching / Reading", value="watching"),
            app_commands.Choice(name="❌ Dropped", value="dropped"),
            app_commands.Choice(name="⏸ Paused", value="paused"),
            app_commands.Choice(name="📝 Planned", value="planned"),
        ],
        media_type=[
            app_commands.Choice(name="🎬 Anime", value="anime"),
            app_commands.Choice(name="📖 Manga", value="manga"),
            app_commands.Choice(name="📘 Light Novel", value="novel"),
        ],
        delivery=[
            app_commands.Choice(name="📩 DM (Private)", value="dm"),
            app_commands.Choice(name="💬 Channel (Public)", value="channel"),
        ],
        extended=[
            app_commands.Choice(name="✨ Yes (detailed)", value="yes"),
            app_commands.Choice(name="⚡ No (faster)", value="no"),
        ]
    )
    async def library_backup(
        self,
        interaction: discord.Interaction,
        format: app_commands.Choice[str],
        scope: app_commands.Choice[str],
        media_type: app_commands.Choice[str],
        delivery: app_commands.Choice[str],
        extended: app_commands.Choice[str],
        username: Optional[str] = None,
    ):
        guild_id = interaction.guild.id if interaction.guild else None
        if not username:
            username = await get_anilist_username_from_db(interaction.user.id, guild_id)
            if not username:
                embed = discord.Embed(
                    title="❌ AniList Username Required",
                    description="Link your AniList account with `/login` or provide a `username` next time.",
                    color=discord.Color.orange()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            auto = True
        else:
            auto = False

        progress = discord.Embed(title="📚✨ Generating Backup...", description="Fetching AniList data...\n\nProgress: `░░░░░░░░░░ 0%`", color=discord.Color.blurple())
        await interaction.response.send_message(embed=progress, ephemeral=True)
        msg = await interaction.original_response()

        user_library = await fetch_anilist_library(username, media_type.value, extended=(extended.value == "yes"))
        filtered = [e for e in user_library if scope.value == "full" or e["status"] == scope.value]

        if not filtered:
            await msg.edit(embed=discord.Embed(title="📝 No Data Found", description=f"No entries for **{username}** in `{scope.name}` scope.", color=discord.Color.orange()))
            return

        file_buffer, filename = await generate_export_file(filtered, format.value)

        confirm = discord.Embed(
            title="✅ Backup Ready!",
            description=(
                f"**User:** {username}\n"
                f"**File:** `{filename}`\n"
                f"**Format:** {format.name}\n"
                f"**Scope:** {scope.name}\n"
                f"**Type:** {media_type.name}\n"
                f"**Entries:** {len(filtered)}"
            ),
            color=discord.Color.green()
        )
        confirm.set_footer(text="🔗 Auto-detected username" if auto else "📝 Username provided manually")

        file = discord.File(file_buffer, filename)
        if delivery.value == "dm":
            try:
                await interaction.user.send(embed=confirm, file=file)
                await msg.edit(embed=discord.Embed(title="📬 Sent!", description="Your backup was sent via DM.", color=discord.Color.green()))
            except discord.Forbidden:
                await msg.edit(embed=discord.Embed(title="❌ DM Failed", description="Enable DMs or choose channel delivery.", color=discord.Color.red()))
        else:
            await msg.edit(embed=confirm)
            await interaction.followup.send(file=file)

# -----------------------------
# Cog Setup
# -----------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(LibraryBackup(bot))
