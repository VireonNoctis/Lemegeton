import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import aiosqlite
from typing import List, Dict, Optional
from collections import Counter

ANILIST_API_URL = "https://graphql.anilist.co"

USER_MANGA_QUERY = """
query ($username: String) {
  MediaListCollection(userName: $username, type: MANGA) {
    lists {
      name
      entries {
        status
        score
        progress
        media {
          id
          title { romaji english native }
          siteUrl
          coverImage { large }
          genres
        }
      }
    }
  }
}
"""

USER_ANIME_QUERY = USER_MANGA_QUERY.replace("MANGA", "ANIME")

class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_anilist(self, query: str, variables: dict):
        async with aiohttp.ClientSession() as session:
            async with session.post(ANILIST_API_URL, json={"query": query, "variables": variables}) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()

    def process_entries(self, lists: List[dict]):
        all_entries: Dict[int, dict] = {}
        for group in lists:
            for entry in group.get("entries", []):
                media = entry["media"]
                media_id = media["id"]
                if media_id not in all_entries:
                    all_entries[media_id] = {
                        "title": media["title"]["romaji"] or media["title"]["english"] or media["title"]["native"],
                        "url": media["siteUrl"],
                        "cover": media["coverImage"]["large"],
                        "status": entry.get("status", "UNKNOWN"),
                        "score": entry.get("score", 0),
                        "progress": entry.get("progress", 0),
                        "genres": media.get("genres", [])
                    }
        return list(all_entries.values())

    def generate_stats(self, entries: List[dict]):
        stats = {"Completed": 0, "InProgress": 0, "Planned": 0, "Dropped": 0, "Total": len(entries), "AverageScore": 0}
        total_score = 0
        scored_count = 0
        for entry in entries:
            status = entry["status"]
            if status == "COMPLETED":
                stats["Completed"] += 1
            elif status == "CURRENT":
                stats["InProgress"] += 1
            elif status == "PLANNING":
                stats["Planned"] += 1
            elif status == "DROPPED":
                stats["Dropped"] += 1
            if entry["score"] and entry["score"] > 0:
                total_score += entry["score"]
                scored_count += 1
        stats["AverageScore"] = round(total_score / scored_count, 2) if scored_count else 0
        return stats

    async def update_user_stats(self, discord_id: int, username: str, manga_entries: List[dict], anime_entries: List[dict]):
        manga_stats = self.generate_stats(manga_entries)
        anime_stats = self.generate_stats(anime_entries)

        # Update stats in DB
        async with aiosqlite.connect("database.db") as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_stats (
                    discord_id INTEGER PRIMARY KEY,
                    username TEXT,
                    total_manga INTEGER,
                    total_anime INTEGER,
                    avg_manga_score REAL,
                    avg_anime_score REAL
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS achievements (
                    discord_id INTEGER,
                    achievement TEXT,
                    PRIMARY KEY (discord_id, achievement)
                )
            """)

            await db.execute("""
                INSERT INTO user_stats (discord_id, username, total_manga, total_anime, avg_manga_score, avg_anime_score)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(discord_id) DO UPDATE SET
                    username=excluded.username,
                    total_manga=excluded.total_manga,
                    total_anime=excluded.total_anime,
                    avg_manga_score=excluded.avg_manga_score,
                    avg_anime_score=excluded.avg_anime_score
            """, (discord_id, username, manga_stats['Total'], anime_stats['Total'],
                  manga_stats['AverageScore'], anime_stats['AverageScore']))
            await db.commit()

        # Achievements
        achievements = []

        # Completion
        if manga_stats['Completed'] >= 100: achievements.append("📚 Manga Enthusiast (100+ Manga)")
        if manga_stats['Completed'] >= 250: achievements.append("📖 Bookworm (250+ Manga)")
        if manga_stats['Completed'] >= 500: achievements.append("📚 Completionist (500+ Manga)")
        if manga_stats['Completed'] >= 1000: achievements.append("📚 Ultimate Manga Collector (1000+ Manga)")

        if anime_stats['Completed'] >= 100: achievements.append("🎬 Anime Enthusiast (100+ Anime)")
        if anime_stats['Completed'] >= 250: achievements.append("🎥 Binge Watcher (250+ Anime)")
        if anime_stats['Completed'] >= 500: achievements.append("🎬 Anime Addict (500+ Anime)")
        if anime_stats['Completed'] >= 1000: achievements.append("🎬 Anime Marathoner (1000+ Anime)")

        # High Scores
        if manga_stats['AverageScore'] >= 8: achievements.append("🏆 Manga Critic (Avg ≥ 8)")
        if manga_stats['AverageScore'] >= 9: achievements.append("🥇 Score Master (Avg ≥ 9)")
        if anime_stats['AverageScore'] >= 8: achievements.append("🎖 Anime Critic (Avg ≥ 8)")
        if anime_stats['AverageScore'] >= 9: achievements.append("🥇 Anime Score Master (Avg ≥ 9)")

        # Genre Variety / Binge
        genre_counter = Counter()
        for entry in manga_entries + anime_entries:
            genre_counter.update(entry.get("genres", []))
        if len(genre_counter) >= 10: achievements.append("🔄 Mixed Tastes (10+ genres)")
        if any(v >= 50 for v in genre_counter.values()): achievements.append("🔥 Binge Mode (50+ in one genre)")

        # Activity
        if manga_stats['Total'] >= 100 or anime_stats['Total'] >= 100: achievements.append("📝 Active User (100+ entries)")

        # Insert achievements into DB
        async with aiosqlite.connect("database.db") as db:
            for ach in achievements:
                await db.execute("INSERT OR IGNORE INTO achievements (discord_id, achievement) VALUES (?, ?)", (discord_id, ach))
            await db.commit()

        return achievements

    def create_embed(self, username: str, media_type: str, entries: List[dict]):
        stats = self.generate_stats(entries)
        embed = discord.Embed(
            title=f"{username}'s {media_type} Profile",
            color=discord.Color.blurple(),
            url=f"https://anilist.co/{media_type.lower()}/{username}"
        )
        if entries:
            embed.set_thumbnail(url=entries[0]["cover"])
        embed.add_field(
            name="📊 Stats",
            value=(
                f"Total: {stats['Total']}\n"
                f"Completed: {stats['Completed']}\n"
                f"In Progress: {stats['InProgress']}\n"
                f"Planned: {stats['Planned']}\n"
                f"Dropped: {stats['Dropped']}\n"
                f"Average Score: {stats['AverageScore']}"
            ),
            inline=False
        )
        recent = sorted(entries, key=lambda x: x["progress"], reverse=True)[:5]
        if recent:
            embed.add_field(
                name="📝 Recent Updates",
                value="\n".join([f"[{e['title']}]({e['url']}) — {e['status']} ({e['progress']})" for e in recent]),
                inline=False
            )
        return embed

    @app_commands.command(name="profile", description="View your AniList profile or another user's profile")
    @app_commands.describe(user="Optional: Discord user to view their profile")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        await interaction.response.defer()
        target = user or interaction.user

        # Fetch username
        async with aiosqlite.connect("database.db") as db:
            async with db.execute("SELECT username FROM users WHERE discord_id = ?", (target.id,)) as cursor:
                row = await cursor.fetchone()
        if not row:
            await interaction.followup.send(f"⚠️ {target.display_name} hasn't registered their AniList username yet!")
            return
        username = row[0]

        # Fetch Manga/Anime
        manga_data = await self.fetch_anilist(USER_MANGA_QUERY, {"username": username})
        manga_lists = manga_data.get("data", {}).get("MediaListCollection", {}).get("lists", [])
        manga_entries = self.process_entries(manga_lists)

        anime_data = await self.fetch_anilist(USER_ANIME_QUERY, {"username": username})
        anime_lists = anime_data.get("data", {}).get("MediaListCollection", {}).get("lists", [])
        anime_entries = self.process_entries(anime_lists)

        # Update stats & achievements
        achievements = await self.update_user_stats(target.id, username, manga_entries, anime_entries)

        # Create embeds & pagination
        embeds = [
            self.create_embed(username, "Manga", manga_entries),
            self.create_embed(username, "Anime", anime_entries)
        ]

        # Add achievements to both embeds
        if achievements:
            for embed in embeds:
                embed.add_field(name="🏅 Achievements", value="\n".join(achievements), inline=False)

        current = 0
        msg = await interaction.followup.send(embed=embeds[current])

        class Pager(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(label="◀", style=discord.ButtonStyle.grey)
            async def prev(self, interaction_: discord.Interaction, button: discord.ui.Button):
                nonlocal current
                current = (current - 1) % len(embeds)
                await interaction_.response.edit_message(embed=embeds[current])

            @discord.ui.button(label="▶", style=discord.ButtonStyle.grey)
            async def next(self, interaction_: discord.Interaction, button: discord.ui.Button):
                nonlocal current
                current = (current + 1) % len(embeds)
                await interaction_.response.edit_message(embed=embeds[current])

        await msg.edit(view=Pager())

async def setup(bot):
    await bot.add_cog(Profile(bot))
