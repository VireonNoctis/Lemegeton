import os
import re
import json
import asyncio
import aiohttp
import discord
from discord.ext import commands
from discord.ui import View, Button
from dotenv import load_dotenv

load_dotenv()
EZ_API = os.getenv("EZ_API")

# Mapping table for rewrites
REWRITE_MAP = {
    r"(?:https?://)?(?:www\.)?x\.com": "https://xeezz.com",
    r"(?:https?://)?(?:www\.)?tiktok\.com": "https://tiktokez.com",
    r"(?:https?://)?(?:www\.)?ifunny\.co": "https://ifunnyez.co",
    r"(?:https?://)?(?:www\.)?reddit\.com": "https://redditez.com",
    r"(?:https?://)?(?:www\.)?snapchat\.com": "https://snapchatez.com",
    r"(?:https?://)?(?:www\.)?bilibili\.com": "https://bilibiliez.com",
    r"(?:https?://)?(?:www\.)?imgur\.com": "https://imgurez.com",
    r"(?:https?://)?(?:www\.)?weibo\.com": "https://weiboez.com",
}


class EmbedView(View):
    """Buttons for embeds."""

    def __init__(self, user: discord.User, url: str):
        super().__init__(timeout=None)
        self.user = user
        self.url = url

        # Add View button
        self.add_item(Button(label="View", style=discord.ButtonStyle.link, url=url))

        # Add Delete button
        delete_button = Button(label="Delete", style=discord.ButtonStyle.danger)

        async def delete_callback(interaction: discord.Interaction):
            if interaction.user.id == user.id or interaction.user.guild_permissions.manage_messages:
                await interaction.message.delete()
            else:
                await interaction.response.send_message("❌ You can't delete this embed.", ephemeral=True)

        delete_button.callback = delete_callback
        self.add_item(delete_button)

        # Schedule delete button expiry after 2h
        asyncio.create_task(self._expire_delete())

    async def _expire_delete(self):
        await asyncio.sleep(7200)
        for item in list(self.children):
            if isinstance(item, Button) and item.label == "Delete":
                self.remove_item(item)
        try:
            await self.message.edit(view=self)
        except:
            pass


class EmbedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------------
    # Main listener
    # ------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        url = self._match_supported_url(message.content)
        if not url:
            return

        await message.delete()
        await self._process_embed(message, url)

    # ------------------------
    # URL matcher
    # ------------------------
    def _match_supported_url(self, content: str) -> str | None:
        for pattern in REWRITE_MAP.keys():
            match = re.search(pattern, content)
            if match:
                urls = re.findall(r"https?://[^\s]+", content)
                return urls[0] if urls else None
        return None

    # ------------------------
    # Process embed
    # ------------------------
    async def _process_embed(self, message: discord.Message, url: str):
        # Try API first
        data = await self._fetch_api(url)

        if not data:
            # fallback: rewrite domain
            for pattern, fixed in REWRITE_MAP.items():
                if re.search(pattern, url):
                    url = re.sub(pattern, fixed, url)
                    break
            data = {"url": url, "title": "Post", "author": {"name": "Unknown", "icon": None}, "stats": {}}

        embed = self._build_embed(data)
        view = EmbedView(message.author, url)
        sent = await message.channel.send(embed=embed, view=view)
        view.message = sent

    # ------------------------
    # Call EmbedEZ API
    # ------------------------
    async def _fetch_api(self, url: str) -> dict | None:
        if not EZ_API:
            return None
        api_url = f"https://embedez.com/api?url={url}&key={EZ_API}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception:
            return None
        return None

    # ------------------------
    # Build embed
    # ------------------------
    def _build_embed(self, data: dict) -> discord.Embed:
        title = data.get("title", "Untitled")
        url = data.get("url")
        description = data.get("description", "")
        author = data.get("author", {})
        stats = data.get("stats", {})
        date = data.get("date", "Unknown Date")
        site = data.get("site", "Unknown")
        logo = data.get("logo", "")

        embed = discord.Embed(
            title=title,
            url=url,
            description=description,
            color=discord.Color.blurple()
        )

        if author:
            embed.set_author(name=author.get("name", "Unknown"), icon_url=author.get("icon", ""))

        stats_line = (
            f"💬 {stats.get('comments', 'N/A')}   "
            f"❤️ {stats.get('likes', 'N/A')}   "
            f"👁️ {stats.get('views', 'N/A')}   "
            f"🔁 {stats.get('reposts', 'N/A')}"
        )
        embed.add_field(name="", value=stats_line, inline=False)

        embed.set_footer(text=f"{site} • {date}", icon_url=logo)
        return embed


async def setup(bot):
    await bot.add_cog(EmbedCog(bot))
