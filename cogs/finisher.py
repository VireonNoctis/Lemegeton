import discord
from discord.ext import commands, tasks
import requests
import json
import datetime

CHANNEL_ID = 1420448966423609407
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

class MangaTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_check.start()  # start loop when cog is loaded

    def cog_unload(self):
        self.daily_check.cancel()

    # === Utility Functions ===
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

    # === Daily Task ===
    @tasks.loop(minutes=1)
    async def daily_check(self):
        now = datetime.datetime.now()
        if now.hour == 12 and now.minute == 0:  # runs every day at 12:00
            channel = self.bot.get_channel(CHANNEL_ID)
            prev_ids = self.load_previous()
            manga_list = self.fetch_manga()
            new_manga = self.filter_new_manga(manga_list, prev_ids)

            if not new_manga:
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

    @daily_check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Finisher(bot))
