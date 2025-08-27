# auto_embed.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import asyncio
import time

class AniListAutoEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cache = {}  # {query_lower: (timestamp, result_list)}
        self.cache_duration = 300  # 5 minutes
        self.rate_limit_time = 1  # seconds between API calls
        self.last_api_call = 0
        self.session = aiohttp.ClientSession()

    async def search_anilist(self, query: str):
        now = time.time()
        if now - self.last_api_call < self.rate_limit_time:
            await asyncio.sleep(self.rate_limit_time - (now - self.last_api_call))
        self.last_api_call = time.time()

        url = "https://graphql.anilist.co"
        query_string = '''
        query ($search: String) {
          Page(perPage: 5) {
            media(search: $search, type: MANGA) {
              id
              title { romaji }
              coverImage { large }
            }
          }
        }
        '''
        variables = {"search": query}

        async with self.session.post(url, json={"query": query_string, "variables": variables}) as resp:
            if resp.status == 429:
                await asyncio.sleep(2)
                return await self.search_anilist(query)
            elif resp.status != 200:
                return []
            data = await resp.json()
            return data.get("data", {}).get("Page", {}).get("media", [])

    async def get_manga_details(self, title: str):
        url = "https://graphql.anilist.co"
        query_string = '''
        query ($search: String) {
          Media(search: $search, type: MANGA) {
            id
            title { romaji }
            description
            coverImage { large }
            chapters
          }
        }
        '''
        variables = {"search": title}

        async with self.session.post(url, json={"query": query_string, "variables": variables}) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("data", {}).get("Media", None)

    # -----------------------------
    # Slash Command
    # -----------------------------
    @app_commands.command(name="manga", description="Search for a manga")
    @app_commands.describe(query="Name of the manga to search")
    async def manga(self, interaction: discord.Interaction, query: str):
        results = await self.search_anilist(query)
        if not results:
            await interaction.response.send_message(f"No results found for `{query}`.", ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=m["title"]["romaji"][:100],
                value=str(m["id"]),
                emoji="📖"
            ) for m in results
        ]

        select = discord.ui.Select(placeholder="Select a manga to see details...", options=options)
        view = discord.ui.View()
        view.add_item(select)

        async def select_callback(interaction2: discord.Interaction):
            manga_id = int(select.values[0])
            selected = next((m for m in results if m["id"] == manga_id), None)
            if not selected:
                await interaction2.response.send_message("Manga not found.", ephemeral=True)
                return
            details = await self.get_manga_details(selected["title"]["romaji"])
            embed = discord.Embed(
                title=details["title"]["romaji"],
                description=(details.get("description") or "No description")[:500],
                color=discord.Color.blue()
            )
            if cover := details.get("coverImage", {}).get("large"):
                embed.set_thumbnail(url=cover)
            embed.add_field(name="Chapters", value=details.get("chapters", "Unknown"))
            await interaction2.response.send_message(embed=embed)

        select.callback = select_callback
        await interaction.response.send_message("Choose a manga from the list:", view=view, ephemeral=True)

    # -----------------------------
    # Autocomplete
    # -----------------------------
    @manga.autocomplete("query")
    async def manga_autocomplete(self, interaction: discord.Interaction, query: str):
        query_lower = query.lower()
        cached = self.cache.get(query_lower)
        if cached and time.time() - cached[0] < self.cache_duration:
            results = cached[1]
        else:
            results = await self.search_anilist(query)
            self.cache[query_lower] = (time.time(), results)

        return [
            app_commands.Choice(name=m["title"]["romaji"], value=m["title"]["romaji"])
            for m in results
        ]

    # -----------------------------
    # Cleanup
    # -----------------------------
    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

# -----------------------------
# Setup function for loading
# -----------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(AniListAutoEmbed(bot))
