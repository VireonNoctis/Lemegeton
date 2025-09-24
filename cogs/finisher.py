import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests
import json
import datetime

Embed_ID = 1420448966423609407
MOD_ROLE_ID = 1420451296304959641
ANILIST_URL = "https://graphql.anilist.co"
SAVE_FILE = "manga_scan.json"

query = """
query {
  Page(page: 1, perPage: 25) {
    media(type: MANGA, sort: END_DATE_DESC, status_in: [FINISHED, CANCELLED]) {
      id
      title { romaji english }
      status
      chapters
      format
      endDate { year month day }
      coverImage { large }
      siteUrl
    }
  }
}
"""

class Finisher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_check.start()

    def cog_unload(self):
        self.daily_check.cancel()

    # === Utilities ===
    def fetch_manga(self):
        response = requests.post(ANILIST_URL, json={"query": query})
        return response.json()["data"]["Page"]["media"]

    def load_previous(self):
        try:
            with open(SAVE_FILE, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def save_current(self, data):
        with open(SAVE_FILE, "w") as f:
            json.dump([m["id"] for m in data], f)

    def filter_new_manga(self, manga_list, prev_ids):
        today = datetime.date.today()
        new_manga = []
        for m in manga_list:
            if m["format"] == "ONE_SHOT":
                continue
            if not m["chapters"] or m["chapters"] < 40:
                continue
            if m["id"] not in prev_ids:
                new_manga.append(m)
            if (m["endDate"]["year"], m["endDate"]["month"], m["endDate"]["day"]) == (today.year, today.month, today.day):
                new_manga.append(m)
        return new_manga

    async def post_updates(self, channel):
        prev_ids = self.load_previous()
        manga_list = self.fetch_manga()
        new_manga = self.filter_new_manga(manga_list, prev_ids)

        if not new_manga:
            await channel.send("📭 No new manga updates today!")
            return

        for m in new_manga:
            title = m["title"]["english"] or m["title"]["romaji"]
            end_date = f"{m['endDate']['day']}/{m['endDate']['month']}/{m['endDate']['year']}"
            status_emoji = "✅" if m["status"] == "FINISHED" else "❌"
            color = 0x00FF00 if m["status"] == "FINISHED" else 0xFF0000

            embed = discord.Embed(
                title=f"{status_emoji} {title}",
                url=m["siteUrl"],
                description=f"**📖 Chapters:** {m['chapters']}\n**📌 Status:** {m['status']}\n**📅 End Date:** {end_date}",
                color=color
            )
            embed.set_thumbnail(url=m["coverImage"]["large"])
            embed.set_footer(text=f"📅 Daily Manga Update | {datetime.date.today()}")

            await channel.send(embed=embed)

        self.save_current(manga_list)

    # === Daily Scheduled Task ===
    @tasks.loop(minutes=1)
    async def daily_check(self):
        now = datetime.datetime.now()
        if now.hour == 12 and now.minute == 0:  # runs daily at 12:00
            channel = self.bot.get_channel(CHANNEL_ID)
            await self.post_updates(channel)

    @daily_check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # === Slash Command for Mods Only ===
    @app_commands.command(name="forceupdate", description="Force a manga completion update (Mod Only)")
    @app_commands.checks.has_role(MOD_ROLE_ID)
    async def forceupdate(self, interaction: discord.Interaction):
        # Step 1: Start
        await interaction.response.send_message(
            "⏳ (1) **Starting Update** → `[0%]` Preparing request to AniList...",
            ephemeral=True
        )

        # Step 2: Fetch Data
        manga_list = self.fetch_manga()
        await interaction.edit_original_response(
            content=f"📡 (2) **Fetching Data** → `[25%]` Retrieved **{len(manga_list)}** manga entries from AniList."
        )

        # Step 3: Load Previous
        prev_ids = self.load_previous()
        await interaction.edit_original_response(
            content=f"🗂 (3) **Comparing Data** → `[50%]` Found **{len(prev_ids)}** previously tracked manga."
        )

        # Step 4: Filter
        new_manga = self.filter_new_manga(manga_list, prev_ids)
        await interaction.edit_original_response(
            content=f"⚖️ (4) **Filtering Results** → `[75%]` After filtering ➝ **{len(new_manga)}** new manga updates."
        )

        # Step 5: Post Updates
        channel = self.bot.get_channel(CHANNEL_ID)
        if new_manga:
            await self.post_updates(channel)
            await interaction.edit_original_response(
                content=f"✅ (5) **Completed!** → `[100%]` Successfully posted **{len(new_manga)}** manga updates to <#{CHANNEL_ID}> 🎉"
            )
        else:
            await interaction.edit_original_response(
                content=f"📭 (5) **Completed!** → `[100%]` No new manga updates to post today."
            )


    @forceupdate.error
    async def forceupdate_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingRole):
            await interaction.response.send_message("❌ You don’t have permission to use this command.", ephemeral=True)
        else:
            raise error

async def setup(bot):
    await bot.add_cog(Finisher(bot))
