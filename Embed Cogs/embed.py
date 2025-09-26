import discord
from discord.ext import commands
from discord.ui import View, Button
import re

# ------------------------------
# Platforms (rewrites)
# ------------------------------

PLATFORM_MAP = {
    "x.com": "xeezz.com",
    "tiktok.com": "tiktokez.com",
    "ifunny.co": "ifunnyez.co",
    "reddit.com": "redditez.com",
    "snapchat.com": "snapchatez.com",
    "bilibili.com": "bilibiliez.com",
    "imgur.com": "imgurez.com",
    "weibo.com": "weiboez.com",
}


def rewrite_url(url: str):
    if "vm.tiktok.com" in url:
        # Normalize TikTok short links
        return re.sub(r"vm\.tiktok\.com", "tiktokez.com", url)
    for base, new in PLATFORM_MAP.items():
        if base in url:
            return url.replace(base, new)
    return url


# ------------------------------
# Buttons
# ------------------------------

class SimpleView(View):
    def __init__(self, url: str, author_id: int):
        super().__init__(timeout=7200)  # 2 hours
        self.add_item(Button(label="View", url=url, style=discord.ButtonStyle.link))
        self.author_id = author_id
        self.message = None

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(":x: You can’t delete this.", ephemeral=True)
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
            for base in PLATFORM_MAP.keys():
                if base in url or "vm.tiktok.com" in url:
                    await self._process(message, url)
                    break

    async def _process(self, message, url):
        rewritten = rewrite_url(url)
        view = SimpleView(rewritten, message.author.id)

        try:
            sent = await message.channel.send(content=rewritten, view=view)
            view.message = sent
            await message.delete()
        except Exception as e:
            print(f"Error reposting link: {e}")


async def setup(bot):
    await bot.add_cog(EmbedCog(bot))
