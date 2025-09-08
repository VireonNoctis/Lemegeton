import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import aiosqlite
import asyncio
from config import GUILD_ID

API_URL = "https://graphql.anilist.co"
DB_PATH = "database.db"


class Affinity(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------
    # Fetch AniList user data with retries
    # ---------------------------------------------------------
    async def fetch_user(self, username: str):
        query = """
        query ($name: String) {
          User(name: $name) {
            id
            name
            avatar { large }
            statistics {
              anime { count meanScore episodesWatched genres { genre count } formats { format count } }
              manga { count meanScore chaptersRead genres { genre count } formats { format count } }
            }
            favourites {
              anime { nodes { id } }
              manga { nodes { id } }
              characters { nodes { id } }
            }
          }
        }
        """
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(API_URL, json={"query": query, "variables": {"name": username}}, timeout=10) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        user_data = data.get("data", {}).get("User")
                        if user_data:
                            return user_data
            except Exception as e:
                print(f"Attempt {attempt+1} failed for {username}: {e}")
            await asyncio.sleep(2)
        return None

    # ---------------------------------------------------------
    # Extensive affinity calculation (fully upgraded + rarity)
    # ---------------------------------------------------------
    def calculate_affinity(self, user1: dict, user2: dict) -> float:
        # --------------------------
        # Shared favourites with weighting & rarity
        # --------------------------
        def weighted_overlap(set1, set2, weight=1, rarity1=None, rarity2=None):
            shared = set1 & set2
            if not shared:
                return 0
            score = 0
            for item in shared:
                r1 = rarity1.get(item, 1) if rarity1 else 1
                r2 = rarity2.get(item, 1) if rarity2 else 1
                # Rarer items contribute more (inverse popularity)
                score += weight * (1 / r1 + 1 / r2) / 2
            total_items = len(set1) + len(set2)
            return score / max(total_items, 1)

        # Favourites sets
        fav_anime1 = {a["id"] for a in user1.get("favourites", {}).get("anime", {}).get("nodes", [])}
        fav_anime2 = {a["id"] for a in user2.get("favourites", {}).get("anime", {}).get("nodes", [])}
        fav_manga1 = {m["id"] for m in user1.get("favourites", {}).get("manga", {}).get("nodes", [])}
        fav_manga2 = {m["id"] for m in user2.get("favourites", {}).get("manga", {}).get("nodes", [])}
        fav_char1 = {c["id"] for c in user1.get("favourites", {}).get("characters", {}).get("nodes", [])}
        fav_char2 = {c["id"] for c in user2.get("favourites", {}).get("characters", {}).get("nodes", [])}

        # Optional rarity dictionaries (popularity counts)
        # Here we just simulate with 1 for all, replace with actual popularity if available
        rarity_anime1 = {i: 1 for i in fav_anime1}
        rarity_anime2 = {i: 1 for i in fav_anime2}
        rarity_manga1 = {i: 1 for i in fav_manga1}
        rarity_manga2 = {i: 1 for i in fav_manga2}
        rarity_char1 = {i: 1 for i in fav_char1}
        rarity_char2 = {i: 1 for i in fav_char2}

        fav_score = (
            weighted_overlap(fav_anime1, fav_anime2, 1.5, rarity_anime1, rarity_anime2) +
            weighted_overlap(fav_manga1, fav_manga2, 1.2, rarity_manga1, rarity_manga2) +
            weighted_overlap(fav_char1, fav_char2, 1.0, rarity_char1, rarity_char2)
        )

        # --------------------------
        # Stats similarity
        # --------------------------
        def similarity_score(a, b):
            if a == 0 and b == 0:
                return 1.0
            return 1 - abs(a - b) / max(a, b, 1)

        anime_stats1 = user1.get("statistics", {}).get("anime", {})
        anime_stats2 = user2.get("statistics", {}).get("anime", {})
        manga_stats1 = user1.get("statistics", {}).get("manga", {})
        manga_stats2 = user2.get("statistics", {}).get("manga", {})

        anime_count_score = similarity_score(anime_stats1.get("count", 0), anime_stats2.get("count", 0))
        anime_score_score = similarity_score(anime_stats1.get("meanScore", 0), anime_stats2.get("meanScore", 0))
        anime_episodes_score = similarity_score(anime_stats1.get("episodesWatched", 0), anime_stats2.get("episodesWatched", 0))

        manga_count_score = similarity_score(manga_stats1.get("count", 0), manga_stats2.get("count", 0))
        manga_score_score = similarity_score(manga_stats1.get("meanScore", 0), manga_stats2.get("meanScore", 0))
        manga_chapters_score = similarity_score(manga_stats1.get("chaptersRead", 0), manga_stats2.get("chaptersRead", 0))

        # --------------------------
        # Completed series overlap
        # --------------------------
        completed_anime1 = set(a["id"] for a in anime_stats1.get("completed", []))
        completed_anime2 = set(a["id"] for a in anime_stats2.get("completed", []))
        completed_manga1 = set(m["id"] for m in manga_stats1.get("completed", []))
        completed_manga2 = set(m["id"] for m in manga_stats2.get("completed", []))

        completed_score = (
            len(completed_anime1 & completed_anime2) / max(len(completed_anime1 | completed_anime2), 1) * 0.5 +
            len(completed_manga1 & completed_manga2) / max(len(completed_manga1 | completed_manga2), 1) * 0.5
        )

        # --------------------------
        # Pace similarity (watch/read speed)
        # --------------------------
        def pace_score(count1, time1, count2, time2):
            if not time1 or not time2:
                return 0.5
            pace1 = count1 / time1
            pace2 = count2 / time2
            return 1 - abs(pace1 - pace2) / max(pace1, pace2, 1)

        pace_anime_score = pace_score(anime_stats1.get("episodesWatched", 0), anime_stats1.get("daysWatched", 0),
                                    anime_stats2.get("episodesWatched", 0), anime_stats2.get("daysWatched", 0))
        pace_manga_score = pace_score(manga_stats1.get("chaptersRead", 0), manga_stats1.get("daysRead", 0),
                                    manga_stats2.get("chaptersRead", 0), manga_stats2.get("daysRead", 0))
        pace_score_final = (pace_anime_score + pace_manga_score) / 2

        # --------------------------
        # Genre overlap
        # --------------------------
        genres1 = {g["genre"] for g in anime_stats1.get("genres", [])} | {g["genre"] for g in manga_stats1.get("genres", [])}
        genres2 = {g["genre"] for g in anime_stats2.get("genres", [])} | {g["genre"] for g in manga_stats2.get("genres", [])}
        genre_score = len(genres1 & genres2) / max(len(genres1 | genres2), 1)

        # --------------------------
        # Format overlap
        # --------------------------
        formats1 = {f["format"] for f in anime_stats1.get("formats", [])} | {f["format"] for f in manga_stats1.get("formats", [])}
        formats2 = {f["format"] for f in anime_stats2.get("formats", [])} | {f["format"] for f in manga_stats2.get("formats", [])}
        format_score = len(formats1 & formats2) / max(len(formats1 | formats2), 1)

        # --------------------------
        # Weighted final affinity score
        # --------------------------
        affinity_score = round(
            fav_score * 35 +
            (anime_count_score + anime_score_score + anime_episodes_score) / 3 * 15 +
            (manga_count_score + manga_score_score + manga_chapters_score) / 3 * 15 +
            genre_score * 10 +
            format_score * 10 +
            completed_score * 7 +
            pace_score_final * 8,
            2
        )

        return min(affinity_score, 100.0)

    # ---------------------------------------------------------
    # Paginated Embed View
    # ---------------------------------------------------------
    class AffinityView(discord.ui.View):
        def __init__(self, entries, user_name):
            super().__init__(timeout=None)
            self.entries = entries
            self.page = 0
            self.user_name = user_name

        def get_embed(self):
            per_page = 10
            start = self.page * per_page
            end = start + per_page
            current_entries = self.entries[start:end]

            description = "\n".join(
                f"{i}. `{score}%` — {username}" 
                for i, (username, score) in enumerate(current_entries, start=start + 1)
            )

            if not description:
                description = "No users found."

            embed = discord.Embed(
                title=f"💞 Affinity Ranking for {self.user_name}",
                description=description,
                color=discord.Color.blurple()
            )
            embed.set_footer(text=f"Page {self.page + 1}/{(len(self.entries)-1)//per_page + 1}")
            return embed

        @discord.ui.button(label="⬅️", style=discord.ButtonStyle.blurple)
        async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.page > 0:
                self.page -= 1
                await interaction.response.edit_message(embed=self.get_embed(), view=self)

        @discord.ui.button(label="➡️", style=discord.ButtonStyle.blurple)
        async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
            if (self.page + 1) * 10 < len(self.entries):
                self.page += 1
                await interaction.response.edit_message(embed=self.get_embed(), view=self)

    # ---------------------------------------------------------
    # Slash Command: /affinity
    # ---------------------------------------------------------
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="affinity",
        description="Compare your affinity with all registered AniList users"
    )
    async def affinity(self, interaction: discord.Interaction):
        await interaction.response.defer()

        discord_id = interaction.user.id
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT anilist_username FROM users WHERE discord_id = ?", (discord_id,))
            row = await cursor.fetchone()
            if not row:
                await interaction.followup.send("❌ You are not registered in the users table.", ephemeral=True)
                return
            anilist_username = row[0]

            cursor = await db.execute("SELECT username, anilist_username FROM users WHERE discord_id != ?", (discord_id,))
            all_users = await cursor.fetchall()

        me = await self.fetch_user(anilist_username)
        if not me:
            await interaction.followup.send("❌ Could not fetch your AniList data. Make sure your profile is public.", ephemeral=True)
            return

        results = []
        for username, other_anilist in all_users:
            other_user = await self.fetch_user(other_anilist)
            if other_user:
                score = self.calculate_affinity(me, other_user)
                results.append((username, score))

        if not results:
            await interaction.followup.send("❌ No other users' data could be fetched.", ephemeral=True)
            return

        results.sort(key=lambda x: x[1], reverse=True)

        view = self.AffinityView(results, interaction.user.display_name)
        await interaction.followup.send(embed=view.get_embed(), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Affinity(bot))
