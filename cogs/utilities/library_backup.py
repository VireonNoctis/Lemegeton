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


# -----------------------------
# AniList API Helper
# -----------------------------
async def fetch_anilist_library(username: str, media_type: str):
    """
    Fetch user library from AniList API.
    Replace with DB integration later if needed.
    """
    query = """
    query ($username: String, $type: MediaType) {
      MediaListCollection(userName: $username, type: $type) {
        lists {
          name
          entries {
            media {
              title {
                romaji
              }
              type
              episodes
              chapters
            }
            status
            progress
            score
            repeat
            startedAt {
              year
              month
              day
            }
            completedAt {
              year
              month
              day
            }
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

    entries = []
    for media_list in data["data"]["MediaListCollection"]["lists"]:
        for entry in media_list["entries"]:
            title = entry["media"]["title"]["romaji"]
            status = entry["status"]
            progress = entry["progress"]
            episodes = entry["media"].get("episodes")
            chapters = entry["media"].get("chapters")

            # Dates
            start = entry["startedAt"]
            start_date = f"{start['year']}-{start['month']}-{start['day']}" if start["year"] else None
            finish = entry["completedAt"]
            finish_date = f"{finish['year']}-{finish['month']}-{finish['day']}" if finish["year"] else None

            entries.append({
                "title": title,
                "status": status,
                "progress": f"{progress}/{episodes or chapters or '?'}",
                "rating": entry.get("score", None),
                "tags": [],  # DB placeholder
                "start_date": start_date,
                "finish_date": finish_date,
                "rewatch_count": entry.get("repeat", 0),
                "last_updated": datetime.datetime.fromtimestamp(entry["updatedAt"]).strftime("%Y-%m-%d"),
            })
    return entries


# -----------------------------
# Cog
# -----------------------------
class LibraryBackup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Slash Command with extended options
    @app_commands.command(name="library_backup", description="Export your tracked library from AniList.")
    @app_commands.describe(
        username="Your AniList username",
        format="Choose the export format",
        scope="Choose the scope of export",
        media_type="Choose media type (anime/manga/lightnovel)",
        delivery="Choose how you want the file delivered",
        extended="Include extended metadata?"
    )
    @app_commands.choices(
        format=[
            app_commands.Choice(name="JSON", value="json"),
            app_commands.Choice(name="CSV", value="csv"),
            app_commands.Choice(name="XML", value="xml"),
            app_commands.Choice(name="TXT", value="txt"),
            app_commands.Choice(name="YAML", value="yaml"),
        ],
        scope=[
            app_commands.Choice(name="Full Library", value="full"),
            app_commands.Choice(name="Completed", value="completed"),
            app_commands.Choice(name="Watching/Reading", value="watching"),
            app_commands.Choice(name="Dropped", value="dropped"),
            app_commands.Choice(name="Paused", value="paused"),
            app_commands.Choice(name="Planned", value="planned"),
        ],
        media_type=[
            app_commands.Choice(name="Anime", value="anime"),
            app_commands.Choice(name="Manga", value="manga"),
            app_commands.Choice(name="Light Novel", value="novel"),
        ],
        delivery=[
            app_commands.Choice(name="Direct Message (Private)", value="dm"),
            app_commands.Choice(name="Channel Drop (Public)", value="channel"),
        ],
        extended=[
            app_commands.Choice(name="Yes", value="yes"),
            app_commands.Choice(name="No", value="no"),
        ]
    )
    async def library_backup(
        self,
        interaction: discord.Interaction,
        username: str,
        format: app_commands.Choice[str],
        scope: app_commands.Choice[str],
        media_type: app_commands.Choice[str],
        delivery: app_commands.Choice[str],
        extended: app_commands.Choice[str],
    ):
        # Initial progress embed
        progress_embed = discord.Embed(
            title="📚✨ Generating Library Backup...",
            description="Fetching data from AniList...\n\nProgress: `░░░░░░░░░░ 0%`",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=progress_embed, ephemeral=True)
        msg = await interaction.original_response()

        # Step 1: Fetch AniList Data
        user_library = await fetch_anilist_library(username, media_type.value)
        if not user_library:
            await msg.edit(embed=discord.Embed(
                title="❌ Error",
                description="Could not fetch AniList data. Check your username.",
                color=discord.Color.red()
            ))
            return

        # Step 2: Simulated progress
        for percent in [25, 55, 85]:
            await asyncio.sleep(1.5)
            bar = "▓" * (percent // 10) + "░" * (10 - percent // 10)
            await msg.edit(embed=discord.Embed(
                title="📚✨ Generating Library Backup...",
                description=f"Processing data...\n\nProgress: `{bar} {percent}%`",
                color=discord.Color.blurple()
            ))

        # Step 3: Apply filters
        filtered_data = []
        for entry in user_library:
            if scope.value != "full" and entry["status"].lower() != scope.value:
                continue
            filtered_data.append(entry)

        # Step 4: Export file
        file_buffer, filename = await generate_export_file(filtered_data, format.value)

        # Step 5: Send file
        confirm_embed = discord.Embed(
            title="✅ Backup Generated Successfully!",
            description=(
                f"**User:** {username}\n"
                f"**File:** `{filename}`\n"
                f"**Format:** {format.name}\n"
                f"**Scope:** {scope.name}\n"
                f"**Type:** {media_type.name}\n\n"
                f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • Safe & Sound"
            ),
            color=discord.Color.green()
        )

        file = discord.File(fp=file_buffer, filename=filename)

        if delivery.value == "dm":
            try:
                await interaction.user.send(embed=confirm_embed, file=file)
                await msg.edit(embed=discord.Embed(
                    title="📬 Backup Sent!",
                    description="Your backup was sent to your DMs.",
                    color=discord.Color.green()
                ))
            except discord.Forbidden:
                await msg.edit(embed=discord.Embed(
                    title="❌ DM Failed",
                    description="I couldn't send the DM. Please allow direct messages.",
                    color=discord.Color.red()
                ))
        else:
            await msg.edit(embed=confirm_embed)
            await interaction.followup.send(file=file, ephemeral=False)


# -----------------------------
# Export File Generator
# -----------------------------
async def generate_export_file(data, fmt):
    buffer = io.BytesIO()
    filename = f"library_backup.{fmt.lower()}"

    if fmt == "json":
        buffer.write(json.dumps(data, indent=4).encode())

    elif fmt == "csv":
        writer = csv.DictWriter(buffer := io.StringIO(), fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
        buffer = io.BytesIO(buffer.getvalue().encode())

    elif fmt == "xml":
        root = ET.Element("Library")
        for entry in data:
            item = ET.SubElement(root, "Entry")
            for k, v in entry.items():
                ET.SubElement(item, k).text = str(v)
        tree = ET.ElementTree(root)
        tree.write(buffer, encoding="utf-8", xml_declaration=True)

    elif fmt == "txt":
        txt_export = "─────────────────────────────\nExported via /library_backup\nStay organized. Stay inspired.\n─────────────────────────────\n\n"
        for entry in data:
            txt_export += f"📖 {entry['title']} | Status: {entry['status']} | Progress: {entry['progress']}\n"
        buffer.write(txt_export.encode())

    elif fmt == "yaml":
        buffer.write(yaml.dump(data, sort_keys=False, allow_unicode=True).encode())

    buffer.seek(0)
    return buffer, filename


# -----------------------------
# Cog Setup
# -----------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(LibraryBackup(bot))
