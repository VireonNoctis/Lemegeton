# embed.py
import re
import asyncio
from typing import Optional, Tuple
import aiohttp
from html import unescape

import discord
from discord.ext import commands

# Patterns for common social platforms (simple URL catchers)
SOCIAL_PATTERNS = {
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/[^\s]+", re.IGNORECASE),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[^\s]+", re.IGNORECASE),
    "youtube": re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s]+", re.IGNORECASE),
    "snapchat": re.compile(r"https?://(?:www\.)?snapchat\.com/[^\s]+", re.IGNORECASE),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[^\s]+", re.IGNORECASE),
    "reddit": re.compile(r"https?://(?:www\.)?reddit\.com/[^\s]+", re.IGNORECASE),
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[^\s]+", re.IGNORECASE),
    "pinterest": re.compile(r"https?://(?:www\.)?pinterest\.com/[^\s]+", re.IGNORECASE),
    "threads": re.compile(r"https?://(?:www\.)?threads\.net/[^\s]+", re.IGNORECASE),
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/[^\s]+", re.IGNORECASE),
}

NOEMBED_URL = "https://noembed.com/embed?url="  # helpful for many providers as first attempt
VIEW_TIMEOUT = 7200  # 2 hours in seconds


async def fetch_json(session: aiohttp.ClientSession, url: str, timeout: int = 10) -> Optional[dict]:
    try:
        async with session.get(url, timeout=timeout) as resp:
            if resp.status == 200:
                return await resp.json()
    except Exception:
        return None
    return None


async def fetch_text(session: aiohttp.ClientSession, url: str, timeout: int = 10) -> Optional[str]:
    try:
        async with session.get(url, timeout=timeout) as resp:
            if resp.status == 200:
                return await resp.text()
    except Exception:
        return None
    return None


def extract_og(html: str) -> dict:
    """Very small OG/meta parser (not foolproof, but works for many sites)."""
    data = {}
    # og:title
    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        data["title"] = unescape(m.group(1))
    # og:description
    m = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        data["description"] = unescape(m.group(1))
    # og:image
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        data["thumbnail_url"] = m.group(1)
    # twitter:creator or author
    m = re.search(r'<meta[^>]+name=["\']twitter:creator["\'][^>]*content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        data["author_name"] = m.group(1)
    # canonical / author link hints
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if m:
        data.setdefault("author_url", m.group(1))
    return data


async def get_metadata(session: aiohttp.ClientSession, url: str) -> dict:
    """
    Attempt to retrieve metadata for the URL:
    1) Try noembed
    2) Fallback to fetching page HTML and parsing OG tags
    Returns a dict with possible keys: title, author_name, author_url, thumbnail_url, description
    """
    # 1) Try noembed
    try:
        js = await fetch_json(session, NOEMBED_URL + aiohttp.helpers.quote(url, safe=""))
        if js:
            # Normalize keys
            data = {}
            if "title" in js:
                data["title"] = js.get("title")
            if "author_name" in js:
                data["author_name"] = js.get("author_name")
            if "author_url" in js:
                data["author_url"] = js.get("author_url")
            if "thumbnail_url" in js:
                data["thumbnail_url"] = js.get("thumbnail_url")
            if "html" in js and not data.get("title"):
                # try short title from noembed html
                title_m = re.search(r'<meta[^>]+name=["\']title["\'][^>]*content=["\']([^"\']+)["\']', js.get("html", ""), re.IGNORECASE)
                if title_m:
                    data["title"] = title_m.group(1)
            if data:
                return data
    except Exception:
        pass

    # 2) Fallback to OG tags
    try:
        html = await fetch_text(session, url)
        if html:
            og = extract_og(html)
            if og:
                return og
    except Exception:
        pass

    # 3) Minimal fallback
    return {"title": None, "author_name": None, "author_url": None, "thumbnail_url": None, "description": None}


class DeleteView(discord.ui.View):
    def __init__(self, original_author_id: int, *, timeout: int = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.original_author_id = original_author_id
        self.message_ref: Optional[discord.Message] = None

    async def on_timeout(self) -> None:
        # disable all children (buttons) and edit the message to disable them
        for item in self.children:
            item.disabled = True
        if self.message_ref:
            try:
                await self.message_ref.edit(view=self)
            except Exception:
                pass

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # allow the original author or those with manage_messages to delete
        can_delete = (interaction.user.id == self.original_author_id) or (
            interaction.permissions.manage_messages if hasattr(interaction, "permissions") else False
        )
        if not can_delete:
            await interaction.response.send_message("You cannot delete this embed. (Only the original poster or moderators can.)", ephemeral=True)
            return
        try:
            await self.message_ref.delete()
            # optionally inform the user
            await interaction.response.send_message("Embed deleted.", ephemeral=True)
        except Exception:
            try:
                await interaction.response.send_message("Failed to delete message (missing permissions?).", ephemeral=True)
            except Exception:
                pass


class EmbedCog(commands.Cog):
    """Background cog: detects social links and replaces them with a styled embed message + delete button."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()

    def cog_unload(self):
        # cleanup aiohttp session
        try:
            asyncio.create_task(self.session.close())
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots and webhooks
        if message.author.bot or message.webhook_id:
            return

        # find first social URL in message
        found = None
        for platform, pattern in SOCIAL_PATTERNS.items():
            m = pattern.search(message.content)
            if m:
                found = (platform, m.group(0))
                break

        if not found:
            return

        platform, url = found

        # Try to remove the original message to keep channel clean (best-effort)
        try:
            await message.delete()
        except Exception:
            # if cannot delete, continue (we still post the embed)
            pass

        # Build a default/fallback embed so we always have something pretty
        embed = discord.Embed(color=discord.Color.blurple(), description=f"[View Original Post]({url})")
        embed.set_footer(text=f"{platform.capitalize()} • Shared via embed cog")

        # fetch metadata (noembed -> OG)
        meta = {}
        try:
            meta = await get_metadata(self.session, url)
        except Exception:
            meta = {}

        title = meta.get("title") or None
        author_name = meta.get("author_name") or None
        author_url = meta.get("author_url") or None
        thumbnail = meta.get("thumbnail_url") or None
        description = meta.get("description") or None

        # set fields based on metadata
        if title:
            # make author clickable like screenshot: Author/Username as title redirecting to X account if present
            # We set embed.title to title and set author to author_name linking to author_url (if available)
            embed.title = title if isinstance(title, str) else None

        if author_name:
            try:
                embed.set_author(name=author_name, url=author_url or None)
            except Exception:
                embed.set_author(name=author_name)

        if thumbnail:
            # put the thumbnail as large image if it's a video thumbnail
            try:
                embed.set_image(url=thumbnail)
            except Exception:
                try:
                    embed.set_thumbnail(url=thumbnail)
                except Exception:
                    pass

        if description and not embed.description:
            embed.description = description[:2048]

        # Add soft-fail "bedding" fields (keeps embed attractive even when metadata missing)
        embed.add_field(name="💬 Comments", value="N/A", inline=True)
        embed.add_field(name="❤️ Likes", value="N/A", inline=True)
        embed.add_field(name="👁️ Views", value="N/A", inline=True)

        # Create delete view (2 hours). original_author_id is the user who posted original message
        view = DeleteView(original_author_id=message.author.id, timeout=VIEW_TIMEOUT)

        sent = None
        try:
            sent = await message.channel.send(embed=embed, view=view)
            # attach a ref so the view can edit/delete the sent message later
            view.message_ref = sent
        except Exception:
            # fallback: send embed without view if we don't have permissions
            try:
                sent = await message.channel.send(embed=embed)
            except Exception:
                # as last resort, send a plain link
                try:
                    await message.channel.send(f"<{url}>")
                except Exception:
                    pass

    # optional manual cleanup command (owner-only) to close aiohttp nicely if needed
    @commands.is_owner()
    @commands.command(hidden=True)
    async def closeembed(self, ctx: commands.Context):
        await self.session.close()
        await ctx.send("Embed cog session closed.")


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCog(bot))

