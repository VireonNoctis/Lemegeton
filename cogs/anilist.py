# anilist.py
import re
import json
import os
import aiohttp
import discord
from discord.ext import commands
from discord import ui
import math
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("AniListCog")

ANILIST_API = "https://graphql.anilist.co"
ACTIVITY_URL_RE = re.compile(r"https?://anilist\.co/activity/(\d+)", re.IGNORECASE)
REPLIES_PER_PAGE = 5
STATE_FILE = "anilist_paginator_state.json"


class AniListCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        self._views_restored = False

    async def cog_unload(self):
        await self.session.close()

    # -------------------------
    # Persistence helpers
    # -------------------------
    def _load_state(self) -> Dict[str, Any]:
        try:
            if not os.path.exists(STATE_FILE):
                return {"messages": {}}
            with open(STATE_FILE, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            logger.exception("Failed to load paginator state file, starting fresh.")
            return {"messages": {}}

    def _save_state(self, state: Dict[str, Any]):
        try:
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(state, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, STATE_FILE)
        except Exception:
            logger.exception("Failed to save paginator state file.")

    async def _add_paginator_persistence(self, message_id: int, channel_id: int, activity_id: int, total_pages: int, current_page: int = 1):
        state = self._load_state()
        state.setdefault("messages", {})
        state["messages"][str(message_id)] = {
            "channel_id": int(channel_id),
            "activity_id": int(activity_id),
            "total_pages": int(total_pages),
            "current_page": int(current_page),
        }
        self._save_state(state)

        # Create view instance and register it as persistent (tied to message_id)
        view = self.Paginator(self, message_id, channel_id, activity_id, total_pages, current_page)
        try:
            # Register persistent view for the specific message
            self.bot.add_view(view, message_id=int(message_id))
        except Exception:
            logger.exception("Failed to add_view for new paginator (non-fatal).")
        return view

    async def _remove_paginator_persistence(self, message_id: int):
        state = self._load_state()
        if "messages" in state and str(message_id) in state["messages"]:
            del state["messages"][str(message_id)]
            self._save_state(state)

    async def restore_persistent_views(self):
        # Called on_ready to re-register views for existing persisted messages
        state = self._load_state()
        msgs = state.get("messages", {})
        for mid, info in list(msgs.items()):
            try:
                view = self.Paginator(
                    self,
                    int(mid),
                    int(info.get("channel_id", 0)),
                    int(info.get("activity_id", 0)),
                    int(info.get("total_pages", 1)),
                    int(info.get("current_page", 1)),
                )
                # tie view back to its message id
                self.bot.add_view(view, message_id=int(mid))
            except Exception:
                logger.exception("Failed to restore persistent paginator for message %s", mid)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._views_restored:
            await self.restore_persistent_views()
            self._views_restored = True

    # -------------------------
    # Text cleaning / media extraction
    # -------------------------
    def clean_text(self, text: str) -> str:
        if not text:
            return ""

        # ~~~text~~~ → text (any content inside triple tildes)
        text = re.sub(r"~{3}(.*?)~{3}", r"\1", text, flags=re.DOTALL)

        # Remove wrapping ~ around img/vid placeholders
        text = re.sub(r"~+imgx?\((https?://[^\s)]+)\)~+", r"img(\1)", text)
        text = re.sub(r"~+vid\((https?://[^\s)]+)\)~+", r"vid(\1)", text)

        # Remove media placeholders and raw media links (keep inline non-media links)
        text = re.sub(r"(?:imgx?|vid)\((https?://[^\s)]+)\)", "", text)
        text = re.sub(r"https?://[^\s]+(?:\.png|\.jpg|\.jpeg|\.gif|\.mp4|\.webm|\.webp)", "", text)

        # Spoilers: ~!text!~ → Discord spoilers
        text = re.sub(r"~!(.*?)!~", r"||\1||", text)

        # Headers (#, ##, ###)
        text = re.sub(r"^# (.+)$", r"__**\1**__", text, flags=re.MULTILINE)
        text = re.sub(r"^## (.+)$", r"**\1**", text, flags=re.MULTILINE)
        text = re.sub(r"^### (.+)$", r"_\1_", text, flags=re.MULTILINE)

        return text.strip()

    def extract_media(self, text: str):
        if not text:
            return [], text

        media_links = []

        # wrapped media: img(...), imgx(...), vid(...)
        for m in re.finditer(r"(?:imgx?|vid)\((https?://[^\s)]+)\)", text):
            media_links.append(m.group(1))

        # direct media links
        for m in re.finditer(r"(https?://[^\s]+(?:\.png|\.jpg|\.jpeg|\.gif|\.webp|\.mp4|\.webm))", text):
            url = m.group(1)
            if url not in media_links:
                media_links.append(url)

        # remove media placeholders & links from text
        cleaned = re.sub(r"(?:imgx?|vid)\((https?://[^\s)]+)\)", "", text)
        cleaned = re.sub(r"https?://[^\s]+(?:\.png|\.jpg|\.jpeg|\.gif|\.mp4|\.webm|\.webp)", "", cleaned)
        cleaned = cleaned.strip()

        return media_links, cleaned

    # -------------------------
    # Embed building
    # -------------------------
    def build_embed(self, activity: dict, activity_type: str, user: dict, text: str, media_links: list, likes: int, comments: int = 0):
        embed = discord.Embed(color=discord.Color.blurple())
        clean = self.clean_text(text)

        # TextActivity: author + description = content
        if activity_type == "TextActivity":
            embed.set_author(
                name=(user or {}).get("name", "Unknown"),
                url=(user or {}).get("siteUrl", ""),
                icon_url=((user or {}).get("avatar") or {}).get("large")
            )
            embed.description = clean or "*No content*"

        # MessageActivity: messenger as author, show recipient + message in description
        elif activity_type == "MessageActivity":
            recipient = activity.get("recipient") or {}
            rec_name = recipient.get("name", "Unknown")
            embed.set_author(
                name=(user or {}).get("name", "Unknown"),
                url=(user or {}).get("siteUrl", ""),
                icon_url=((user or {}).get("avatar") or {}).get("large")
            )
            # show as: "Recipient\n\nmessage body" (messenger shown as author)
            embed.description = f"To **{rec_name}**\n\n{clean or '*No message text*'}"

        # ListActivity: author shown, description should be "Read Chapter <progress> <title>"
        elif activity_type == "ListActivity":
            media = activity.get("media") or {}
            progress = activity.get("progress") or activity.get("status") or ""
            title = (media.get("title") or {}).get("romaji", "Unknown")
            cover = (media.get("coverImage") or {}).get("large")

            embed.set_author(
                name=(user or {}).get("name", "Unknown"),
                url=(user or {}).get("siteUrl", ""),
                icon_url=((user or {}).get("avatar") or {}).get("large")
            )

            # Put the readable activity into the description (user is in author)
            if progress:
                embed.description = f"Read Chapter {progress} {title}"
            else:
                embed.description = f"{title}"

            if cover:
                embed.set_thumbnail(url=cover)

        # Reply: show as reply embed (author is replier)
        elif activity_type == "Reply":
            embed.set_author(
                name=f"💬 {(user or {}).get('name', 'Unknown')}",
                url=(user or {}).get("siteUrl", ""),
                icon_url=((user or {}).get("avatar") or {}).get("large")
            )
            embed.description = clean or "*No reply text*"

        # Fallback generic
        else:
            embed.set_author(
                name=(user or {}).get("name", "Unknown"),
                url=(user or {}).get("siteUrl", ""),
                icon_url=((user or {}).get("avatar") or {}).get("large")
            )
            embed.description = clean or "*No content*"

        # Compact stats
        stats = f"❤️ {likes or 0}"
        if comments:
            stats += f" | 💬 {comments}"
        embed.add_field(name="Stats", value=stats, inline=True)

        # Media handling (attach first image as embed image)
        if media_links:
            first = media_links[0]
            if any(first.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                embed.set_image(url=first)
            else:
                embed.add_field(name="🔗 Media", value=f"[Click here]({first})", inline=False)
            for extra in media_links[1:]:
                embed.add_field(name="🔗 Media", value=f"[Click here]({extra})", inline=False)

        embed.set_footer(text="Powered by AniList")
        return embed

    # -------------------------
    # Fetch activity from AniList (robust)
    # -------------------------
    async def fetch_activity(self, activity_id: int) -> Optional[dict]:
        query = """
        query($id: Int) {
          Activity(id: $id) {
            __typename

            ... on TextActivity {
              id
              text
              likeCount
              replyCount
              siteUrl
              user { id name siteUrl avatar { large } }
              replies { id text likeCount user { id name siteUrl avatar { large } } }
            }

            ... on MessageActivity {
              id
              message
              likeCount
              replyCount
              siteUrl
              messenger { id name siteUrl avatar { large } }
              recipient { id name siteUrl avatar { large } }
              replies { id text likeCount user { id name siteUrl avatar { large } } }
            }

            ... on ListActivity {
              id
              status
              progress
              likeCount
              replyCount
              siteUrl
              user { id name siteUrl avatar { large } }
              media { id siteUrl title { romaji } coverImage { large } }
              replies { id text likeCount user { id name siteUrl avatar { large } } }
            }
          }
        }
        """
        try:
            async with self.session.post(ANILIST_API, json={"query": query, "variables": {"id": activity_id}}) as resp:
                text = await resp.text()
                try:
                    js = await resp.json()
                except Exception:
                    js = None

                if resp.status != 200:
                    logger.error("AniList API error %s: %s", resp.status, text)
                    return None

                if not js or "data" not in js or js["data"].get("Activity") is None:
                    logger.warning("AniList returned no Activity for id %s. Response: %s", activity_id, text)
                    return None

                return js["data"]["Activity"]
        except Exception:
            logger.exception("AniList API fetch failed.")
            return None

    # -------------------------
    # Render page
    # -------------------------
    async def render_page(self, activity: Optional[dict], page: int):
        embeds = []
        if not activity:
            e = discord.Embed(
                title="❌ Activity not found",
                description="This AniList activity is missing, deleted, or could not be retrieved.",
                color=discord.Color.red()
            )
            embeds.append(e)
            return embeds

        activity_type = activity.get("__typename", "Unknown")

        # select correct user & text field per type
        if activity_type == "MessageActivity":
            user = activity.get("messenger") or {}
            text = activity.get("message") or ""
        else:
            user = activity.get("user") or {}
            text = activity.get("text") or activity.get("status") or ""

        # Page 1: show only the main activity/message/text
        if page == 1:
            media, _ = self.extract_media(text)
            likes = activity.get("likeCount", 0)
            comments = activity.get("replyCount", 0)
            embed = self.build_embed(activity, activity_type, user, text, media, likes, comments)
            embeds.append(embed)
            return embeds

        # Page >=2: show replies pages (page 2 => first batch of replies)
        replies = activity.get("replies") or []
        # page 2 should show replies[0:REPLIES_PER_PAGE], page 3 -> replies[REPLIES_PER_PAGE:2*REPLIES_PER_PAGE], etc.
        start = (page - 2) * REPLIES_PER_PAGE
        end = start + REPLIES_PER_PAGE
        sliced = replies[start:end]

        for reply in sliced:
            r_user = reply.get("user") or {}
            r_text = reply.get("text") or ""
            media, _ = self.extract_media(r_text)
            r_likes = reply.get("likeCount", 0)
            reply_embed = self.build_embed(activity, "Reply", r_user, r_text, media, r_likes)
            embeds.append(reply_embed)

        # If no replies on this page, show a notice
        if not embeds:
            embeds.append(discord.Embed(description="No replies on this page.", color=discord.Color.greyple()))

        return embeds

    # -------------------------
    # Persistent paginator view
    # -------------------------
    class Paginator(ui.View):
        def __init__(self, cog: "AniListCog", message_id: int, channel_id: int, activity_id: int, total_pages: int, current_page: int = 1):
            super().__init__(timeout=None)  # persistent view
            self.cog = cog
            self.message_id = str(message_id)
            self.channel_id = int(channel_id)
            self.activity_id = int(activity_id)
            self.total_pages = max(1, int(total_pages))
            self.current_page = max(1, int(current_page))

            # Buttons: custom_id includes message id so Discord recognizes them per-message
            self.prev_btn = ui.Button(label="⬅ Prev", style=discord.ButtonStyle.primary, custom_id=f"anilist:prev:{self.message_id}")
            self.next_btn = ui.Button(label="Next ➡", style=discord.ButtonStyle.primary, custom_id=f"anilist:next:{self.message_id}")

            self.prev_btn.disabled = (self.current_page <= 1)
            self.next_btn.disabled = (self.current_page >= self.total_pages)

            self.prev_btn.callback = self.prev_page
            self.next_btn.callback = self.next_page

            self.add_item(self.prev_btn)
            self.add_item(self.next_btn)

        async def _load_message_state(self):
            state = self.cog._load_state()
            return state.get("messages", {}).get(self.message_id)

        async def _save_message_state(self, new_state: Dict[str, Any]):
            state = self.cog._load_state()
            state.setdefault("messages", {})
            state["messages"][self.message_id] = new_state
            self.cog._save_state(state)

        def _update_buttons_disabled(self):
            self.prev_btn.disabled = (self.current_page <= 1)
            self.next_btn.disabled = (self.current_page >= self.total_pages)

        async def prev_page(self, interaction: discord.Interaction):
            try:
                msg_state = await self._load_message_state()
                if not msg_state:
                    await interaction.response.send_message("⚠️ Paginator state missing (cannot change page).", ephemeral=True)
                    return

                current = int(msg_state.get("current_page", self.current_page))
                if current <= 1:
                    await interaction.response.send_message("You are already on the first page.", ephemeral=True)
                    return

                new_page = current - 1
                activity = await self.cog.fetch_activity(self.activity_id)
                if not activity:
                    await interaction.response.send_message("⚠️ Could not fetch AniList activity.", ephemeral=True)
                    return

                embeds = await self.cog.render_page(activity, new_page)

                # persist new page
                msg_state["current_page"] = new_page
                await self._save_message_state(msg_state)

                # update local state & button states
                self.current_page = new_page
                self._update_buttons_disabled()

                try:
                    await interaction.response.edit_message(embeds=embeds, view=self)
                except discord.HTTPException:
                    # message deleted or not editable
                    await interaction.response.send_message("⚠️ Could not update the message (it may have been deleted).", ephemeral=True)
                    await self.cog._remove_paginator_persistence(int(self.message_id))
            except Exception:
                logger.exception("Paginator prev_page failure")
                try:
                    await interaction.response.send_message("⚠️ Failed to change page.", ephemeral=True)
                except Exception:
                    pass

        async def next_page(self, interaction: discord.Interaction):
            try:
                msg_state = await self._load_message_state()
                if not msg_state:
                    await interaction.response.send_message("⚠️ Paginator state missing (cannot change page).", ephemeral=True)
                    return

                current = int(msg_state.get("current_page", self.current_page))
                if current >= int(msg_state.get("total_pages", self.total_pages)):
                    await interaction.response.send_message("You are already on the last page.", ephemeral=True)
                    return

                new_page = current + 1
                activity = await self.cog.fetch_activity(self.activity_id)
                if not activity:
                    await interaction.response.send_message("⚠️ Could not fetch AniList activity.", ephemeral=True)
                    return

                embeds = await self.cog.render_page(activity, new_page)

                # persist new page
                msg_state["current_page"] = new_page
                await self._save_message_state(msg_state)

                # update local state & button states
                self.current_page = new_page
                self._update_buttons_disabled()

                try:
                    await interaction.response.edit_message(embeds=embeds, view=self)
                except discord.HTTPException:
                    await interaction.response.send_message("⚠️ Could not update the message (it may have been deleted).", ephemeral=True)
                    await self.cog._remove_paginator_persistence(int(self.message_id))
            except Exception:
                logger.exception("Paginator next_page failure")
                try:
                    await interaction.response.send_message("⚠️ Failed to change page.", ephemeral=True)
                except Exception:
                    pass

    # -------------------------
    # Listener for AniList links
    # -------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # ignore bots (including ourselves)
        if message.author.bot:
            return

        m = ACTIVITY_URL_RE.search(message.content)
        if not m:
            return

        activity_id = int(m.group(1))
        activity = await self.fetch_activity(activity_id)
        if not activity:
            await message.channel.send("❌ Failed to fetch activity (it may be deleted or AniList returned an error).")
            return

        total_replies = len(activity.get("replies") or [])
        total_pages = 1 + math.ceil(max(0, total_replies) / REPLIES_PER_PAGE)

        # Render page 1 (main activity only)
        embeds = await self.render_page(activity, page=1)

        # Send message first (we need the message id for per-message custom_id)
        try:
            sent = await message.channel.send(embeds=embeds)
        except Exception:
            logger.exception("Failed to send AniList message")
            return

        # Persist paginator state and register view for this message
        try:
            view = await self._add_paginator_persistence(sent.id, sent.channel.id, activity_id, total_pages, current_page=1)
            try:
                await sent.edit(view=view)
            except Exception:
                # editing view might fail if missing permissions - state is still persisted
                logger.exception("Failed to attach paginator view to message (message.edit failed).")
        except Exception:
            logger.exception("Failed to create/attach persistent paginator view.")


# setup entrypoint for cogs
async def setup(bot: commands.Bot):
    cog = AniListCog(bot)
    await bot.add_cog(cog)
