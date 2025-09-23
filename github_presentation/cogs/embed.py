import discord
from discord.ext import commands
from discord.ui import View, Button
import re
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ------------------------------
# Helpers
# ------------------------------

PLATFORM_MAP = {
    "x.com": ("xeezz.com", "Twitter", "https://cdn-icons-png.flaticon.com/512/733/733579.png"),
    "tiktok.com": ("tiktokez.com", "TikTok", "https://cdn-icons-png.flaticon.com/512/3046/3046120.png"),
    "ifunny.co": ("ifunnyez.co", "iFunny", "https://cdn-icons-png.flaticon.com/512/2111/2111589.png"),
    "reddit.com": ("redditez.com", "Reddit", "https://cdn-icons-png.flaticon.com/512/2111/2111589.png"),
    "snapchat.com": ("snapchatez.com", "Snapchat", "https://cdn-icons-png.flaticon.com/512/2111/2111628.png"),
    "bilibili.com": ("bilibiliez.com", "Bilibili", "https://cdn-icons-png.flaticon.com/512/3670/3670227.png"),
    "imgur.com": ("imgurez.com", "Imgur", "https://cdn-icons-png.flaticon.com/512/2111/2111370.png"),
    "weibo.com": ("weiboez.com", "Weibo", "https://cdn-icons-png.flaticon.com/512/2111/2111664.png"),
}


def rewrite_url(url: str):
    for base, (new, _, _) in PLATFORM_MAP.items():
        if base in url:
            return url.replace(base, new)
    return url


async def fetch_meta(url: str):
    """Scrape OpenGraph/Meta tags from a URL."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return {}
                text = await resp.text()
                soup = BeautifulSoup(text, "html.parser")
                meta = {
                    "description": None,
                    "author": None,
                    "pfp": None,
                    "date": None,
                }
                if (desc := soup.find("meta", property="og:description")):
                    meta["description"] = desc.get("content")
                elif (desc := soup.find("meta", attrs={"name": "description"})):
                    meta["description"] = desc.get("content")

                if (auth := soup.find("meta", property="og:site_name")):
                    meta["author"] = auth.get("content")

                if (img := soup.find("meta", property="og:image")):
                    meta["pfp"] = img.get("content")

                if (date := soup.find("meta", property="article:published_time")):
                    meta["date"] = date.get("content").split("T")[0]

                return meta
        except Exception:
            return {}


# ------------------------------
# Delete/View Buttons
# ------------------------------

class EmbedView(View):
    def __init__(self, url: str, author_id: int):
        super().__init__(timeout=7200)  # 2 hours
        self.add_item(Button(label="View", url=url, style=discord.ButtonStyle.link))
        self.author_id = author_id
        self.message = None

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ You can’t delete this embed.", ephemeral=True)
            return
        if self.message:
            await self.message.delete()
        else:
            await interaction.message.delete()

    async def on_timeout(self):
        self.clear_items()
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass


# ------------------------------
# Cog
# ------------------------------

class EmbedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.url_pattern = re.compile(r"(https?://[^\s]+)")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        urls = self.url_pattern.findall(message.content)
        for url in urls:
            for base, (new, sitename, logo) in PLATFORM_MAP.items():
                if base in url:
                    await self._process(message, url, base, new, sitename, logo)
                    break

    async def _process(self, message, url, base, new, sitename, logo):
        rewritten = url.replace(base, new)
        meta = await fetch_meta(url)

        description = meta.get("description") or "No description available."
        author = meta.get("author") or "Unknown"
        pfp = meta.get("pfp") or message.author.avatar.url if message.author.avatar else None
        date = meta.get("date") or datetime.utcnow().strftime("%Y-%m-%d")

        files = []
        if message.attachments:
            for att in message.attachments:
                files.append(await att.to_file())

        embed = discord.Embed(description=description, color=discord.Color.blurple())
        embed.set_author(name=author, icon_url=pfp)
        embed.set_footer(text=f"{sitename} • {date}", icon_url=logo)

        view = EmbedView(rewritten, message.author.id)

        try:
            sent = await message.channel.send(content=rewritten, embed=embed, files=files, view=view)
            view.message = sent
            await message.delete()
        except Exception as e:
            print(f"Error sending embed: {e}")


async def setup(bot):
    await bot.add_cog(EmbedCog(bot))
