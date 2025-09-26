import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import datetime
import os
import asyncio
import logging
import aiohttp

from config import CHANNEL_ID, MOD_ROLE_ID
ANILIST_URL = "https://graphql.anilist.co"
SAVE_FILE = "data/manga_scan.json"
CHANNEL_SAVE_FILE = "data/manga_channel.json"  # stores mapping {guild_id: channel_id}
LAST_RUN_FILE = "data/manga_scan_meta.json"  # stores metadata like last run timestamp

# ---------------- Logging ----------------
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "finisher.log")

logger = logging.getLogger("Finisher")
logger.setLevel(logging.INFO)

# Avoid duplicate file handlers on reload
if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == os.path.abspath(LOG_FILE)
           for h in logger.handlers):
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
    logger.addHandler(file_handler)

# Console output
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(stream_handler)

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


def mod_only():
    """App command check that allows only users with the configured MOD_ROLE_ID
    or users with administrative/manage permissions as a fallback.
    Use as: @mod_only() on an app command.
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        try:
            # Prefer configured role id if present
            if MOD_ROLE_ID:
                member = interaction.user if isinstance(interaction.user, discord.Member) else await interaction.guild.fetch_member(interaction.user.id)
                for r in getattr(member, 'roles', []):
                    if getattr(r, 'id', None) == MOD_ROLE_ID:
                        return True
                return False

            # Fallback to permission checks
            member = interaction.user if isinstance(interaction.user, discord.Member) else await interaction.guild.fetch_member(interaction.user.id)
            perms = getattr(member, 'guild_permissions', None)
            if perms:
                return perms.manage_roles or perms.manage_guild or perms.administrator
        except Exception:
            return False
        return False

    return app_commands.check(predicate)


class Finisher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # use module-level logger configured above
        self.logger = logger
        self.logger.info("Finisher cog initialized")
        # Ensure data directory exists when saving
        os.makedirs(os.path.dirname(SAVE_FILE) or '.', exist_ok=True)
        os.makedirs(os.path.dirname(CHANNEL_SAVE_FILE) or '.', exist_ok=True)

    def cog_unload(self):
        self.daily_check.cancel()

    # === Utilities ===
    async def fetch_manga(self):
        """Async fetch from AniList with timeout and basic error handling."""
        timeout = aiohttp.ClientTimeout(total=15)
        try:
            self.logger.info("Fetching manga list from AniList")
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(ANILIST_URL, json={"query": query}) as resp:
                    if resp.status != 200:
                        self.logger.warning(f"AniList returned status {resp.status}")
                        return []
                    data = await resp.json()
                    media = data.get("data", {}).get("Page", {}).get("media", [])
                    self.logger.info(f"AniList returned {len(media)} media entries")
                    return media
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.exception(f"Error fetching AniList data: {e}")
            return []

    async def load_previous(self):
        """Load previous saved IDs (runs in thread to avoid blocking)."""
        def _read():
            try:
                with open(SAVE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except FileNotFoundError:
                return []
            except Exception:
                return []

        result = await asyncio.to_thread(_read)
        try:
            self.logger.debug(f"Loaded {len(result)} previous manga ids from {SAVE_FILE}")
        except Exception:
            self.logger.debug("Loaded previous manga ids (unable to calculate length)")
        return result

    async def save_current(self, data):
        """Save current IDs atomically (runs in thread to avoid blocking)."""
        def _write():
            temp = SAVE_FILE + ".tmp"
            try:
                with open(temp, "w", encoding="utf-8") as f:
                    json.dump([m.get("id") for m in data], f)
                os.replace(temp, SAVE_FILE)
            finally:
                try:
                    if os.path.exists(temp):
                        os.remove(temp)
                except Exception:
                    pass

        await asyncio.to_thread(_write)
        try:
            self.logger.info(f"Saved {len(data)} current manga ids to {SAVE_FILE}")
        except Exception:
            self.logger.info("Saved current manga ids")

    def filter_new_manga(self, manga_list, prev_ids):
        """Filter list: exclude one-shots, short series, and prefer newly finished today or not seen before."""
        today = datetime.date.today()
        try:
            self.logger.debug(f"Filtering {len(manga_list)} manga entries against {len(prev_ids)} previous ids")
        except Exception:
            self.logger.debug("Filtering manga entries")
        new_manga = []
        for m in manga_list:
            try:
                if m.get("format") == "ONE_SHOT":
                    continue
                chapters = m.get("chapters") or 0
                if chapters < 40:
                    continue
                mid = m.get("id")
                # Add if unseen
                if mid not in prev_ids:
                    new_manga.append(m)
                    continue
                # Also add if ended today (guard missing endDate)
                end = m.get("endDate") or {}
                if all(k in end and isinstance(end[k], int) for k in ("year", "month", "day")):
                    if (end["year"], end["month"], end["day"]) == (today.year, today.month, today.day):
                        new_manga.append(m)
            except Exception:
                # Don't let one bad entry break the loop
                self.logger.exception("Error filtering manga entry")
                continue
        return new_manga

    # === Channel configuration persistence ===
    async def load_defined_channel(self, guild_id: int):
        """Return configured channel_id for a specific guild (or None)."""
        def _read(gid: int):
            try:
                if os.path.exists(CHANNEL_SAVE_FILE):
                    with open(CHANNEL_SAVE_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                        cid = data.get(str(gid))
                        return int(cid) if cid else None
                return None
            except Exception:
                return None

        result = await asyncio.to_thread(_read, guild_id)
        try:
            if result:
                self.logger.info(f"Loaded configured channel {result} for guild {guild_id}")
            else:
                self.logger.info(f"No configured channel for guild {guild_id}")
        except Exception:
            self.logger.debug("Loaded defined channel (unable to log details)")
        return result

    async def load_all_defined_channels(self) -> dict:
        """Return the full mapping of guild_id -> channel_id (strings) or empty dict."""
        def _read_all():
            try:
                if os.path.exists(CHANNEL_SAVE_FILE):
                    with open(CHANNEL_SAVE_FILE, "r", encoding="utf-8") as f:
                        return json.load(f) or {}
                return {}
            except Exception:
                return {}

        result = await asyncio.to_thread(_read_all)
        try:
            self.logger.info(f"Loaded channel mapping for {len(result)} guild(s)")
        except Exception:
            self.logger.debug("Loaded channel mapping")
        return result

    async def save_defined_channel(self, guild_id: int, channel_id: int):
        """Persist a guild -> channel mapping atomically."""
        def _write(gid: int, ch_id: int):
            temp = CHANNEL_SAVE_FILE + ".tmp"
            try:
                data = {}
                if os.path.exists(CHANNEL_SAVE_FILE):
                    try:
                        with open(CHANNEL_SAVE_FILE, "r", encoding="utf-8") as f:
                            data = json.load(f) or {}
                    except Exception:
                        data = {}

                data[str(gid)] = int(ch_id)
                with open(temp, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                os.replace(temp, CHANNEL_SAVE_FILE)
            finally:
                try:
                    if os.path.exists(temp):
                        os.remove(temp)
                except Exception:
                    pass

        await asyncio.to_thread(_write, guild_id, channel_id)
        try:
            self.logger.info(f"Saved configured channel {channel_id} for guild {guild_id} to {CHANNEL_SAVE_FILE}")
        except Exception:
            self.logger.debug("Saved configured channel mapping")

    # === Last-run persistence (to ensure runs are once-per-24h) ===
    async def load_last_run(self) -> datetime.datetime | None:
        """Return the last run datetime or None."""
        def _read():
            try:
                if os.path.exists(LAST_RUN_FILE):
                    with open(LAST_RUN_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f) or {}
                        s = data.get("last_run")
                        if s:
                            return datetime.datetime.fromisoformat(s)
                return None
            except Exception:
                return None

        return await asyncio.to_thread(_read)

    async def save_last_run(self, dt: datetime.datetime):
        """Persist the last run datetime atomically."""
        def _write(ts: str):
            temp = LAST_RUN_FILE + ".tmp"
            try:
                with open(temp, "w", encoding="utf-8") as f:
                    json.dump({"last_run": ts}, f)
                os.replace(temp, LAST_RUN_FILE)
            finally:
                try:
                    if os.path.exists(temp):
                        os.remove(temp)
                except Exception:
                    pass

        await asyncio.to_thread(_write, dt.isoformat())
        try:
            self.logger.info(f"Saved last run timestamp {dt.isoformat()} to {LAST_RUN_FILE}")
        except Exception:
            self.logger.debug("Saved last run timestamp")

    async def _user_is_mod(self, interaction: discord.Interaction) -> bool:
        """Return True if the invoking user should be considered a moderator.

        Priority:
        - If MOD_ROLE_ID configured: user must have that role.
        - Else: fall back to guild permissions (manage_roles/manage_guild/administrator).
        """
        try:
            if interaction.guild is None:
                return False

            # Prefer configured role id if present
            if MOD_ROLE_ID:
                try:
                    member = interaction.user if isinstance(interaction.user, discord.Member) else await interaction.guild.fetch_member(interaction.user.id)
                    for r in getattr(member, 'roles', []):
                        if getattr(r, 'id', None) == MOD_ROLE_ID:
                            return True
                except Exception:
                    return False

            # Fallback to permission checks
            member = interaction.user if isinstance(interaction.user, discord.Member) else await interaction.guild.fetch_member(interaction.user.id)
            perms = getattr(member, 'guild_permissions', None)
            if perms:
                return perms.manage_roles or perms.manage_guild or perms.administrator

        except Exception:
            self.logger.exception("Failed to determine mod permissions")
        return False

    # === Admin commands to configure channel ===
    @mod_only()
    @app_commands.command(name="set_manga_channel", description="Set channel to receive manga updates (Mod only)")
    async def set_manga_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        self.logger.info(f"/set_manga_channel invoked by {interaction.user} in guild {interaction.guild.id} -> channel {channel.id}")
        # Permission check
        if not await self._user_is_mod(interaction):
            await interaction.response.send_message("❌ You don’t have permission to use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            # Check bot can send messages in channel
            bot_member = interaction.guild.me
            perms = channel.permissions_for(bot_member) if bot_member else None
            if perms and not perms.send_messages:
                await interaction.followup.send("I don't have permission to send messages in that channel.", ephemeral=True)
                return

            await self.save_defined_channel(interaction.guild.id, channel.id)
            self.logger.info(f"Configured manga updates for guild {interaction.guild.id} -> channel {channel.id}")
            await interaction.followup.send(f"✅ Manga updates will be sent to {channel.mention}", ephemeral=True)
        except Exception:
            self.logger.exception("Failed to set manga channel")
            try:
                await interaction.followup.send("❌ Failed to set channel.", ephemeral=True)
            except Exception:
                pass

    @app_commands.command(name="show_manga_channel", description="Show currently configured manga update channel")
    async def show_manga_channel(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        self.logger.info(f"/show_manga_channel invoked by {interaction.user} in guild {interaction.guild.id}")
        cid = await self.load_defined_channel(interaction.guild.id)
        if cid:
            ch = self.bot.get_channel(cid)
            if ch:
                await interaction.response.send_message(f"Current manga updates channel: {ch.mention}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Configured channel id {cid} is not visible to the bot.", ephemeral=True)
        else:
            await interaction.response.send_message("No channel configured for this server.", ephemeral=True)

    async def post_updates(self, channel):
        if channel is None:
            self.logger.warning("post_updates called with None channel")
            return

        self.logger.info(f"Posting updates to channel {getattr(channel, 'name', getattr(channel, 'id', 'unknown'))}")
        prev_ids = await self.load_previous()
        manga_list = await self.fetch_manga()
        new_manga = self.filter_new_manga(manga_list, prev_ids)

        self.logger.info(f"Found {len(new_manga)} new manga updates after filtering")

        if not new_manga:
            await channel.send("📭 No new manga updates today!")
            # Still update saved state to prevent repeated alerts for the same list
            await self.save_current(manga_list)
            return

        for m in new_manga:
            title = (m.get("title") or {}).get("english") or (m.get("title") or {}).get("romaji") or "Unknown Title"
            self.logger.info(f"Posting update for manga id={m.get('id')} title={title} status={m.get('status')}")
            end = m.get("endDate") or {}
            end_date = f"{end.get('day','?')}/{end.get('month','?')}/{end.get('year','?')}"
            status_emoji = "✅" if m.get("status") == "FINISHED" else "❌"
            color = 0x00FF00 if m.get("status") == "FINISHED" else 0xFF0000

            embed = discord.Embed(
                title=f"{status_emoji} {title}",
                url=m.get("siteUrl"),
                description=f"**📖 Chapters:** {m.get('chapters','?')}\n**📌 Status:** {m.get('status','?')}\n**📅 End Date:** {end_date}",
                color=color
            )
            cover = (m.get("coverImage") or {}).get("large")
            if cover:
                embed.set_thumbnail(url=cover)
            embed.set_footer(text=f"📅 Daily Manga Update | {datetime.date.today()}")

            await channel.send(embed=embed)
            self.logger.debug(f"Sent embed for manga {m.get('id')} to channel {getattr(channel,'id',None)}")

        # after sending all new updates, persist the latest fetched list
        await self.save_current(manga_list)
        try:
            self.logger.info("Post updates complete and state saved")
        except Exception:
            self.logger.debug("Post updates complete (unable to log details)")

    # === Daily Scheduled Task ===
    @tasks.loop(minutes=1)
    async def daily_check(self):
        # Enforce an at-most-once-per-24-hour run using a persisted timestamp.
        now = datetime.datetime.utcnow()
        try:
            last_run = await self.load_last_run()
        except Exception:
            last_run = None

        should_run = False
        if last_run is None:
            should_run = True
        else:
            elapsed = now - last_run
            if elapsed.total_seconds() >= 24 * 3600:
                should_run = True

        if not should_run:
            self.logger.debug("Skipping daily_check; last run was within 24 hours")
            return

        self.logger.info("Running daily_check scheduled task (24h interval reached)")
        # Load mapping and post to each configured guild channel
        try:
            mapping = await self.load_all_defined_channels()
            if mapping:
                for gid, cid in mapping.items():
                    try:
                        channel = self.bot.get_channel(int(cid)) if cid else None
                        if channel:
                            await self.post_updates(channel)
                        else:
                            self.logger.warning(f"Configured channel {cid} for guild {gid} not visible to bot")
                    except Exception:
                        self.logger.exception(f"Failed to post updates for guild {gid}")
            else:
                # No per-guild mapping; try global fallback once
                channel = self.bot.get_channel(CHANNEL_ID)
                if channel:
                    await self.post_updates(channel)
                else:
                    self.logger.warning("No configured channels found and global CHANNEL_ID not available to bot")
        except Exception:
            self.logger.exception("Failed to load configured channels for daily_check")

        # Persist the run timestamp so we don't run again for 24h
        try:
            await self.save_last_run(now)
        except Exception:
            self.logger.exception("Failed to save last run timestamp after daily_check")

    @daily_check.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    # === Slash Command for Mods Only ===
    @mod_only()
    @app_commands.command(name="forceupdate", description="Force a manga completion update (Mod Only)")
    async def forceupdate(self, interaction: discord.Interaction):
        # Use defer to acknowledge interaction and update progress via edit_original_response
        # Permission check
        if not await self._user_is_mod(interaction):
            await interaction.response.send_message("❌ You don’t have permission to use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.edit_original_response(content="⏳ (1) **Starting Update** → `[0%]` Preparing request to AniList...")

            # Step 2: Fetch Data
            manga_list = await self.fetch_manga()
            await interaction.edit_original_response(content=f"📡 (2) **Fetching Data** → `[25%]` Retrieved **{len(manga_list)}** manga entries from AniList.")

            # Step 3: Load Previous
            prev_ids = await self.load_previous()
            await interaction.edit_original_response(content=f"🗂 (3) **Comparing Data** → `[50%]` Found **{len(prev_ids)}** previously tracked manga.")

            # Step 4: Filter
            new_manga = self.filter_new_manga(manga_list, prev_ids)
            await interaction.edit_original_response(content=f"⚖️ (4) **Filtering Results** → `[75%]` After filtering ➝ **{len(new_manga)}** new manga updates.")

            # Step 5: Post Updates (prefer configured channel)
            cid = await self.load_defined_channel(interaction.guild.id)
            channel = self.bot.get_channel(cid) if cid else self.bot.get_channel(CHANNEL_ID)
            await self.post_updates(channel)

            # Record that we just ran a manual/forced update
            try:
                await self.save_last_run(datetime.datetime.utcnow())
            except Exception:
                self.logger.exception("Failed to persist last_run after forceupdate")

            if new_manga:
                target = channel.mention if channel else f"<#{CHANNEL_ID}>"
                await interaction.edit_original_response(content=f"✅ (5) **Completed!** → `[100%]` Successfully posted **{len(new_manga)}** manga updates to {target} 🎉")
            else:
                await interaction.edit_original_response(content=f"📭 (5) **Completed!** → `[100%]` No new manga updates to post today.")

            await interaction.followup.send("✅ Update posted!", ephemeral=True)

        except Exception as e:
            self.logger.exception("Error running forceupdate command")
            # Try to inform the user if possible
            try:
                await interaction.followup.send("❌ An error occurred while running the update.", ephemeral=True)
            except Exception:
                pass
            raise


    @forceupdate.error
    async def forceupdate_error(self, interaction: discord.Interaction, error):
        # Check for permission errors from app_commands checks
        from discord import app_commands as _app
        if isinstance(error, (_app.MissingRole, _app.MissingPermissions, _app.CheckFailure)):
            try:
                await interaction.response.send_message("❌ You don’t have permission to use this command.", ephemeral=True)
            except Exception:
                # If response already sent, try followup
                try:
                    await interaction.followup.send("❌ You don’t have permission to use this command.", ephemeral=True)
                except Exception:
                    pass
        else:
            raise error

async def setup(bot):
    cog = Finisher(bot)
    await bot.add_cog(cog)
    # Start the scheduled task after the cog is added so the bot client is initialized.
    try:
        cog.daily_check.start()
    except RuntimeError:
        # If the loop is already running or can't be started, log and continue.
        logger.exception("Failed to start daily_check loop for Finisher cog")
