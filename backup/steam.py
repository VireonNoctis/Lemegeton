# cogs/steam.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import aiosqlite
from config import STEAM_API_KEY, DB_PATH, GUILD_ID
from bs4 import BeautifulSoup
import logging
import math
import asyncio
import random
import io
import textwrap

# Optional Pillow for friend-grid image rendering
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

logger = logging.getLogger("steam")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
    logger.addHandler(h)


# -------------------- Helpers --------------------
async def safe_json(session, url, params=None, timeout=15):
    try:
        async with session.get(url, params=params, timeout=timeout) as resp:
            if resp.status != 200:
                logger.debug(f"safe_json - {url} returned {resp.status}")
                return None
            return await resp.json()
    except Exception:
        logger.exception("safe_json failed")
        return None


async def fetch_text(session, url, timeout=15):
    try:
        async with session.get(url, timeout=timeout) as resp:
            if resp.status != 200:
                logger.debug(f"fetch_text - {url} returned {resp.status}")
                return None
            return await resp.text()
    except Exception:
        logger.exception("fetch_text failed")
        return None


def chunk_list(lst, n):
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def random_color():
    palette = [
        discord.Color.blurple(), discord.Color.blue(), discord.Color.teal(),
        discord.Color.green(), discord.Color.gold(), discord.Color.purple(),
        discord.Color.dark_blue(), discord.Color.dark_teal()
    ]
    return random.choice(palette)


def human_hours(minutes):
    return f"{minutes // 60}h"


def safe_text(s, fallback="N/A"):
    if not s:
        return fallback
    return str(s)


# Friend grid generator using Pillow (optional). Returns BytesIO png or None.
def make_friend_grid_image(friends_slice, thumb_size=96, per_row=5):
    if not PIL_AVAILABLE:
        return None
    # friend entries should be dicts with keys: name, avatar_bytes
    cols = min(per_row, max(1, len(friends_slice)))
    rows = math.ceil(len(friends_slice) / per_row)
    padding = 12
    name_height = 20
    width = cols * (thumb_size + padding) + padding
    height = rows * (thumb_size + name_height + padding) + padding

    image = Image.new("RGBA", (width, height), (30, 30, 30, 255))
    draw = ImageDraw.Draw(image)

    # try to use a TTF font if available
    try:
        font = ImageFont.truetype("arial.ttf", 14)
    except Exception:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

    x = padding
    y = padding
    idx = 0
    for fr in friends_slice:
        avatar_bytes = fr.get("avatar_bytes")
        try:
            if avatar_bytes:
                av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                av = av.resize((thumb_size, thumb_size))
                image.paste(av, (x, y), av)
            else:
                draw.rectangle([x, y, x + thumb_size, y + thumb_size], fill=(60, 60, 60))
        except Exception:
            draw.rectangle([x, y, x + thumb_size, y + thumb_size], fill=(60, 60, 60))
        # draw name under avatar
        name = (fr.get("name") or "Unknown")[:22]
        tx = x
        ty = y + thumb_size + 4
        draw.text((tx, ty), name, fill=(240, 240, 240), font=font)
        x += thumb_size + padding
        idx += 1
        if idx % per_row == 0:
            x = padding
            y += thumb_size + name_height + padding

    out = io.BytesIO()
    image.save(out, "PNG")
    out.seek(0)
    return out


# -------------------- Cog --------------------
class Steam(commands.Cog):
    """Steam commands with improved profile/details UI and scraping."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    steam_group = app_commands.Group(name="steam", description="Steam commands")
    steam_group = app_commands.guilds(discord.Object(id=GUILD_ID))(steam_group)

    # ---------------- Register ----------------
    @steam_group.command(name="register", description="Register your Steam vanity name")
    @app_commands.describe(vanity_name="the part after /id/ in your steam URL")
    async def register(self, interaction: discord.Interaction, vanity_name: str):
        await interaction.response.defer(ephemeral=True)
        async with aiohttp.ClientSession() as session:
            data = await safe_json(session, "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/",
                                   params={"key": STEAM_API_KEY, "vanityurl": vanity_name})
            if not data or data.get("response", {}).get("success") != 1:
                return await interaction.followup.send("❌ Could not resolve that vanity name.", ephemeral=True)
            steamid = data["response"]["steamid"]

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO steam_users (discord_id, steam_id, vanity_name)
                VALUES (?, ?, ?)
                ON CONFLICT(discord_id) DO UPDATE SET
                    steam_id=excluded.steam_id,
                    vanity_name=excluded.vanity_name
                """, (interaction.user.id, steamid, vanity_name)
            )
            await db.commit()

        await interaction.followup.send(f"✅ Registered `{vanity_name}` (SteamID: {steamid})", ephemeral=True)

    # ---------------- Profile ----------------
    @steam_group.command(name="profile", description="View a Steam profile (registered or by id/vanity)")
    @app_commands.describe(user="SteamID64 or vanity (optional if registered)")
    async def profile(self, interaction: discord.Interaction, user: str = None):
        logger.info(f"/steam profile by {interaction.user} user={user}")
        await interaction.response.defer(ephemeral=True)

        # resolve steam id
        steamid = None
        vanity = None
        if not user:
            async with aiosqlite.connect(DB_PATH) as db:
                cur = await db.execute("SELECT steam_id, vanity_name FROM steam_users WHERE discord_id = ?", (interaction.user.id,))
                row = await cur.fetchone()
                await cur.close()
                if not row:
                    return await interaction.followup.send("❌ You have not registered a Steam account. Use `/steam register <vanity>`.", ephemeral=True)
                steamid, vanity = row
                user = vanity

        async with aiohttp.ClientSession() as session:
            if user and not user.isdigit():
                res = await safe_json(session, "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/",
                                      params={"key": STEAM_API_KEY, "vanityurl": user})
                if not res or res.get("response", {}).get("success") != 1:
                    return await interaction.followup.send("❌ Could not resolve that user.", ephemeral=True)
                steamid = res["response"]["steamid"]

            # player summary
            ps = await safe_json(session, "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                                 params={"key": STEAM_API_KEY, "steamids": steamid})
            players = ps.get("response", {}).get("players", []) if ps else []
            if not players:
                return await interaction.followup.send("❌ No profile data found.", ephemeral=True)
            player = players[0]

            # level
            lv = await safe_json(session, "https://api.steampowered.com/IPlayerService/GetSteamLevel/v1/",
                                 params={"key": STEAM_API_KEY, "steamid": steamid})
            level = lv.get("response", {}).get("player_level", 0) if lv else 0

            # recently played
            recent = await safe_json(session, "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/",
                                     params={"key": STEAM_API_KEY, "steamid": steamid, "count": 5})
            recent_games = recent.get("response", {}).get("games", []) if recent else []

            # owned games
            owned = await safe_json(session, "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
                                    params={"key": STEAM_API_KEY, "steamid": steamid, "include_appinfo": 1, "include_played_free_games": 1})
            owned_games = owned.get("response", {}).get("games", []) if owned else []
            total_games = owned.get("response", {}).get("game_count", 0) if owned else 0
            top_games = sorted(owned_games, key=lambda g: g.get("playtime_forever", 0), reverse=True)

            # friends
            friends = []
            friends_json = await safe_json(session, "https://api.steampowered.com/ISteamUser/GetFriendList/v1/",
                                           params={"key": STEAM_API_KEY, "steamid": steamid, "relationship": "all"})
            friends_list = friends_json.get("friendslist", {}).get("friends", []) if friends_json else []
            friend_ids = [f["steamid"] for f in friends_list]

            # try fetch badge count (scrape badges page for count)
            badge_count = None
            try:
                badges_html = await fetch_text(session, f"https://steamcommunity.com/profiles/{steamid}/badges") or await fetch_text(session, f"https://steamcommunity.com/id/{user}/badges")
                if badges_html:
                    bs = BeautifulSoup(badges_html, "html.parser")
                    # badge count often shown in .profile_badges_count or in elements containing 'Badges'
                    # fallback: count badge tiles
                    badge_tiles = bs.find_all("div", class_=lambda c: c and "badge_row" in c or "badge" in c)
                    if badge_tiles:
                        badge_count = len(badge_tiles)
                    else:
                        # try to parse a numeric label
                        txt = bs.get_text()
                        m = None
                        import re
                        m = re.search(r"(\d+)\s+Badges", txt)
                        if m:
                            badge_count = int(m.group(1))
            except Exception:
                logger.debug("badge count scrape failed", exc_info=True)

        # format status color
        pstate = player.get("personastate", 0)
        if pstate == 1:
            color = discord.Color.green()
        elif pstate == 0:
            color = discord.Color.red()
        else:
            color = random_color()

        status_map = {
            0: "🔴 Offline",
            1: "🟢 Online",
            2: "⛔ Busy",
            3: "🌙 Away",
            4: "💤 Snooze",
            5: "🔄 Looking to trade",
            6: "🎮 Looking to play"
        }
        status_text = status_map.get(pstate, "❔ Unknown")

        # Main profile embed (aesthetic)
        embed = discord.Embed(title=f"{player.get('personaname','Unknown')} — {status_text}",
                              url=player.get("profileurl"),
                              color=color)
        avatar_url = player.get("avatarfull")
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)

        # Basic info fields
        embed.add_field(name="🆔 SteamID", value=str(steamid), inline=False)
        embed.add_field(name="⭐ Level", value=str(level), inline=True)
        embed.add_field(name="🎮 Games", value=str(total_games), inline=True)
        embed.add_field(name="👥 Friends", value=str(len(friend_ids)), inline=True)
        # badges total count on main embed
        embed.add_field(name="🏅 Badges", value=str(badge_count) if badge_count is not None else "Unknown", inline=True)

        # Real name (if present) and location (if present)
        rn = player.get("realname")
        loc = player.get("loccountrycode")
        embed.add_field(name="🧑 Real Name", value=rn or "N/A", inline=True)
        embed.add_field(name="🌍 Location", value=loc or "N/A", inline=True)

        # Bio: attempt to scrape summary text from profile page (better than "Click details")
        summary_text = None
        try:
            async with aiohttp.ClientSession() as s:
                prof_html = await fetch_text(s, f"https://steamcommunity.com/profiles/{steamid}") or await fetch_text(s, f"https://steamcommunity.com/id/{user}")
                if prof_html:
                    ssp = BeautifulSoup(prof_html, "html.parser")
                    # try common selectors
                    summary = ssp.select_one(".profile_summary") or ssp.select_one("#summary") or ssp.find("div", class_=lambda c: c and "profile_summary" in c)
                    if summary:
                        summary_text = summary.get_text(" ", strip=True)
        except Exception:
            logger.debug("bio scrape failed", exc_info=True)

        embed.add_field(name="📝 Bio", value=(summary_text[:900] + "…" if summary_text and len(summary_text) > 900 else summary_text) if summary_text else "N/A", inline=False)

        # Top games preview (3)
        if top_games:
            preview = []
            for g in top_games[:3]:
                nm = g.get("name", "Unknown")
                hours = g.get("playtime_forever", 0) // 60
                preview.append(f"**{nm}** — {hours}h")
            embed.add_field(name="🏆 Top Games (preview)", value="\n".join(preview), inline=False)

        # footer simplified
        embed.set_footer(text="ℹ️ Details • 👁 Toggle Visibility to make public")

        # View: Details button + Toggle Visibility (only if ephemeral)
        view = discord.ui.View(timeout=180)
        view.is_ephemeral = True

        details_button = discord.ui.Button(label="ℹ️ Details", style=discord.ButtonStyle.secondary)
        async def details_cb(btn_inter: discord.Interaction):
            # open a new message (do not edit original)
            await self.open_details_message(btn_inter, steamid, player, owned_games, top_games, friend_ids)
        details_button.callback = details_cb
        view.add_item(details_button)

        # Add toggle only if message will be ephemeral (default True)
        toggle_button = discord.ui.Button(label="👁 Toggle Visibility", style=discord.ButtonStyle.danger)
        async def toggle_cb(btn_inter: discord.Interaction):
            # flip ephemeral by deleting and resending a copy
            try:
                await btn_inter.message.delete()
            except Exception:
                pass
            new_ephemeral = not getattr(view, "is_ephemeral", True)
            new_view = discord.ui.View(timeout=180)
            new_view.is_ephemeral = new_ephemeral
            # re-add details
            db = discord.ui.Button(label="ℹ️ Details", style=discord.ButtonStyle.secondary)
            db.callback = details_cb
            new_view.add_item(db)
            if new_ephemeral:
                tb = discord.ui.Button(label="👁 Toggle Visibility", style=discord.ButtonStyle.danger)
                tb.callback = toggle_cb
                new_view.add_item(tb)
            try:
                await btn_inter.response.send_message(embed=embed, view=new_view, ephemeral=new_ephemeral)
                view.is_ephemeral = new_ephemeral
            except Exception:
                try:
                    await btn_inter.followup.send("⚠️ Could not toggle visibility.", ephemeral=True)
                except Exception:
                    pass
        toggle_button.callback = toggle_cb
        view.add_item(toggle_button)

        # send the main profile (ephemeral True)
        try:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception:
            try:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            except Exception:
                logger.exception("Failed sending profile message")

    # ------------------ Open Details Message ------------------
    async def open_details_message(self, interaction: discord.Interaction, steamid: str, player: dict, owned_games: list, top_games: list, friend_ids: list):
        """
        Sends a NEW message (not editing the original) that contains a dropdown of all details.
        Each selection will send new messages (keeps original profile message intact).
        """
        # build dropdown view
        view = discord.ui.View(timeout=300)
        select = discord.ui.Select(
            placeholder="Select details...",
            options=[
                discord.SelectOption(label="🏆 Top / Most Played Games", value="top_games"),
                discord.SelectOption(label="🎮 All Games", value="all_games"),
                discord.SelectOption(label="👥 Friends", value="friends"),
                discord.SelectOption(label="🏅 Badges (in profile)", value="badges"),
                discord.SelectOption(label="📷 Screenshots", value="screenshots"),
                discord.SelectOption(label="📹 Videos", value="videos"),
                discord.SelectOption(label="💬 Profile Comments", value="comments"),
                discord.SelectOption(label="👪 Groups", value="groups"),
            ],
            min_values=1, max_values=1
        )

        async def select_cb(sel_inter: discord.Interaction):
            choice = sel_inter.data["values"][0]
            # Send a short ephemeral progress message that we will edit into results (gives good UX)
            await sel_inter.response.send_message("🔎 Preparing data…", ephemeral=True)
            progress_msg = await sel_inter.original_response()

            try:
                if choice == "top_games":
                    await progress_msg.edit(content="🔎 Building Top Games pages...")
                    await self._send_paginated_games(sel_inter, top_games, title="Top / Most Played Games", progress_msg=progress_msg)
                elif choice == "all_games":
                    await progress_msg.edit(content="🔎 Building Games pages...")
                    await self._send_paginated_games(sel_inter, owned_games, title="All Games", progress_msg=progress_msg)
                elif choice == "friends":
                    await progress_msg.edit(content="🔎 Fetching friends...")
                    await self._send_friends_pages(sel_inter, friend_ids, progress_msg=progress_msg)
                elif choice == "badges":
                    # badges already displayed on main profile: tell user quickly (ephemeral)
                    await progress_msg.edit(content="🏅 Badges are shown on the main profile embed.", embed=None)
                elif choice == "screenshots":
                    await progress_msg.edit(content="🔎 Scraping screenshots...")
                    await self._send_screenshots(sel_inter, steamid, progress_msg=progress_msg)
                elif choice == "videos":
                    await progress_msg.edit(content="🔎 Scraping videos...")
                    await self._send_videos(sel_inter, steamid, progress_msg=progress_msg)
                elif choice == "comments":
                    await progress_msg.edit(content="🔎 Scraping comments...")
                    await self._send_comments(sel_inter, steamid, progress_msg=progress_msg)
                elif choice == "groups":
                    await progress_msg.edit(content="🔎 Scraping groups...")
                    await self._send_groups(sel_inter, steamid, progress_msg=progress_msg)
                else:
                    await progress_msg.edit(content="⚠️ Unknown selection.")
            except Exception:
                logger.exception("Error processing details selection")
                try:
                    await progress_msg.edit(content="⚠️ Failed to fetch details.")
                except Exception:
                    pass

        select.callback = select_cb
        view.add_item(select)

        # Add a button that makes the message public (toggle) if the initial message is ephemeral.
        # But because this is a NEW details message, we'll add a 'Return to Profile' and make no toggle here.
        back_btn = discord.ui.Button(label="↩️ Return to Profile", style=discord.ButtonStyle.secondary)
        async def back_cb(bi: discord.Interaction):
            # simply inform user to re-open profile or press original embed's details
            try:
                await bi.response.send_message("Return to the profile message (original message still exists).", ephemeral=True)
            except Exception:
                pass
        back_btn.callback = back_cb
        view.add_item(back_btn)

        # send the new details message (ephemeral)
        try:
            await interaction.response.send_message("📂 Details opened. Choose an option from the dropdown.", view=view, ephemeral=True)
        except Exception:
            try:
                await interaction.followup.send("📂 Details opened. Choose an option from the dropdown.", view=view, ephemeral=True)
            except Exception:
                logger.exception("Failed to open details message")

    # ------------------ Games pagination helper ------------------
    async def _send_paginated_games(self, interaction: discord.Interaction, games_list: list, title: str = "Games", per_page: int = 5, progress_msg=None):
        if not games_list:
            try:
                await interaction.followup.send(embed=discord.Embed(title=title, description="No games found or profile is private.", color=discord.Color.dark_gray()), ephemeral=True)
            except Exception:
                pass
            return

        pages = chunk_list(games_list, per_page)
        page_idx = 0

        def make_embed_for_page(page, idx):
            e = discord.Embed(title=f"{title} — page {idx + 1}/{len(pages)}", color=discord.Color.blurple())
            for i, g in enumerate(page, start=1):
                name = g.get("name", "Unknown")
                hours = g.get("playtime_forever", 0) // 60
                e.add_field(name=f"{i}. {name}", value=f"🕒 {hours}h", inline=False)
            return e

        # prepare first page embed
        first_embed = make_embed_for_page(pages[0], 0)
        view = discord.ui.View(timeout=300)

        # Prev / Next buttons
        prev_btn = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        next_btn = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)

        async def prev_cb(btn_inter):
            nonlocal page_idx
            if page_idx > 0:
                page_idx -= 1
            try:
                await btn_inter.response.edit_message(embed=make_embed_for_page(pages[page_idx], page_idx), view=view)
            except Exception:
                try:
                    await btn_inter.followup.send(embed=make_embed_for_page(pages[page_idx], page_idx), ephemeral=True)
                except Exception:
                    pass

        async def next_cb(btn_inter):
            nonlocal page_idx
            if page_idx < len(pages) - 1:
                page_idx += 1
            try:
                await btn_inter.response.edit_message(embed=make_embed_for_page(pages[page_idx], page_idx), view=view)
            except Exception:
                try:
                    await btn_inter.followup.send(embed=make_embed_for_page(pages[page_idx], page_idx), ephemeral=True)
                except Exception:
                    pass

        prev_btn.callback = prev_cb
        next_btn.callback = next_cb
        if len(pages) > 1:
            view.add_item(prev_btn)
            view.add_item(next_btn)

        # replace the progress_msg with the first page embed if provided, otherwise send a fresh message
        try:
            if progress_msg:
                await progress_msg.edit(content=None, embed=first_embed, view=view)
            else:
                await interaction.followup.send(embed=first_embed, view=view, ephemeral=True)
        except Exception:
            try:
                await interaction.followup.send(embed=first_embed, view=view, ephemeral=True)
            except Exception:
                pass

    # ------------------ Friends pages ------------------
    async def _send_friends_pages(self, interaction: discord.Interaction, friend_ids: list, progress_msg=None, per_page=5):
        if not friend_ids:
            try:
                if progress_msg:
                    await progress_msg.edit(content=None, embed=discord.Embed(title="Friends", description="No friends visible or profile private.", color=discord.Color.dark_gray()))
                else:
                    await interaction.followup.send(embed=discord.Embed(title="Friends", description="No friends visible or profile private.", color=discord.Color.dark_gray()), ephemeral=True)
            except Exception:
                pass
            return

        # fetch summaries in batches (100 at a time)
        friend_summaries = []
        async with aiohttp.ClientSession() as session:
            batches = chunk_list(friend_ids, 100)
            for b in batches:
                j = await safe_json(session, "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                                    params={"key": STEAM_API_KEY, "steamids": ",".join(b)})
                batch_players = j.get("response", {}).get("players", []) if j else []
                friend_summaries.extend(batch_players)
                await asyncio.sleep(0.08)

        # build pages of 5 friends each
        pages = chunk_list(friend_summaries, per_page)
        page_idx = 0

        # Build representation for a page:
        # - If Pillow available: prepare grid image and send as attachment
        # - Otherwise: create up to `per_page` small embeds each using set_author for avatar + name
        async def send_page(msg_interaction, idx):
            slice_ = pages[idx]
            if PIL_AVAILABLE:
                # fetch avatar bytes for each friend in this slice
                fetch_tasks = []
                async with aiohttp.ClientSession() as s:
                    for f in slice_:
                        avatar_url = f.get("avatarfull") or f.get("avatar")
                        if avatar_url:
                            try:
                                async with s.get(avatar_url) as r:
                                    if r.status == 200:
                                        avatar_bytes = await r.read()
                                    else:
                                        avatar_bytes = None
                            except Exception:
                                avatar_bytes = None
                        else:
                            avatar_bytes = None
                        f['_avatar_bytes'] = avatar_bytes
                # prepare friend dicts for grid helper
                to_draw = [{"name": fr.get("personaname"), "avatar_bytes": fr.get('_avatar_bytes')} for fr in slice_]
                image_io = make_friend_grid_image(to_draw, thumb_size=96, per_row=5)
                if image_io:
                    file = discord.File(fp=image_io, filename="friends_grid.png")
                    em = discord.Embed(title=f"👥 Friends — page {idx+1}/{len(pages)}", color=discord.Color.green())
                    try:
                        await msg_interaction.edit_original_response(content=None, embed=em, attachments=[file])  # if called via progress_msg
                    except Exception:
                        try:
                            await msg_interaction.response.edit_message(content=None, embed=em, attachments=[file])
                        except Exception:
                            try:
                                await msg_interaction.followup.send(embed=em, file=file, ephemeral=True)
                            except Exception:
                                pass
                    return
                # fallback to embed-list below if image couldn't be built

            # Fallback: build a single embed with fields listing friends, and show avatars as separate small embeds (or in author of multiple embeds)
            embed = discord.Embed(title=f"👥 Friends — page {idx+1}/{len(pages)}", color=discord.Color.green())
            # build numbered list with clickable names and small avatar URLs shown
            lines = []
            for i, fr in enumerate(slice_, start=1 + idx * per_page):
                name = fr.get("personaname", "Unknown")
                purl = fr.get("profileurl", "#")
                avatar = fr.get("avatar") or fr.get("avatarfull") or ""
                lines.append(f"**{i}. [{name}]({purl})** — [avatar]({avatar})")
            embed.description = "\n".join(lines)[:4096]
            # edit existing progress message or send fresh
            try:
                if progress_msg:
                    await progress_msg.edit(content=None, embed=embed)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception:
                try:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                except Exception:
                    pass

        # Create pagination view
        view = discord.ui.View(timeout=300)
        prev_btn = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        next_btn = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)
        page_label = discord.ui.Button(label=f"Page 1/{len(pages)}", style=discord.ButtonStyle.secondary, disabled=True)

        async def prev_cb(btn_inter):
            nonlocal page_idx
            page_idx = (page_idx - 1) % len(pages)
            page_label.label = f"Page {page_idx+1}/{len(pages)}"
            # edit message content
            try:
                await btn_inter.response.edit_message(content=None)
            except Exception:
                pass
            await send_page(btn_inter, page_idx)

        async def next_cb(btn_inter):
            nonlocal page_idx
            page_idx = (page_idx + 1) % len(pages)
            page_label.label = f"Page {page_idx+1}/{len(pages)}"
            try:
                await btn_inter.response.edit_message(content=None)
            except Exception:
                pass
            await send_page(btn_inter, page_idx)

        prev_btn.callback = prev_cb
        next_btn.callback = next_cb
        view.add_item(prev_btn)
        view.add_item(page_label)
        view.add_item(next_btn)

        # show first page in place of progress_msg or as new message
        try:
            if progress_msg:
                # edit original (progress_msg) into first page with view
                await progress_msg.edit(content=None)
                # then call send_page with a fake interaction wrapper for editing original response
                class MsgInteractionWrapper:
                    def __init__(self, original):
                        self._orig = original
                    async def edit_original_response(self, *args, **kwargs):
                        await self._orig.edit(*args, **kwargs)
                    # mimic interaction.response.edit_message
                    async def response_edit(self, *args, **kwargs):
                        await self._orig.edit(*args, **kwargs)
                    async def followup_send(self, *args, **kwargs):
                        await self._orig.channel.send(*args, **kwargs)
                # We'll attempt to edit using the underlying message object. Simpler: just edit the message with embed.
                await send_page(progress_msg, 0)
                try:
                    await progress_msg.edit(view=view)
                except Exception:
                    pass
            else:
                # send new message with first page and view
                # create a placeholder embed to be replaced by send_page's content
                placeholder = discord.Embed(title="👥 Friends", description="Loading...", color=discord.Color.green())
                await interaction.followup.send(embed=placeholder, view=view, ephemeral=True)
                # get original response to edit
                orig = await interaction.original_response()
                # send_page will try to edit orig via progress_msg pattern - emulate by passing orig
                await send_page(orig, 0)
        except Exception:
            # fallback: send first page as normal
            await send_page(interaction, 0)

    # ------------------ Screenshots ------------------
    async def _send_screenshots(self, interaction: discord.Interaction, steamid: str, progress_msg=None):
        # try to fetch screenshots from profile screenshot gallery or profile main page
        async with aiohttp.ClientSession() as session:
            html = await fetch_text(session, f"https://steamcommunity.com/profiles/{steamid}/screenshots/") or await fetch_text(session, f"https://steamcommunity.com/profiles/{steamid}") or await fetch_text(session, f"https://steamcommunity.com/id/{steamid}/screenshots/")
        if not html:
            try:
                await progress_msg.edit(content="⚠️ Could not fetch screenshots or profile is private.")
            except Exception:
                await interaction.followup.send("⚠️ Could not fetch screenshots or profile is private.", ephemeral=True)
            return

        soup = BeautifulSoup(html, "html.parser")
        imgs = []
        # look for gallery items
        for img in soup.select("img"):
            src = img.get("src") or img.get("data-src")
            if src and "cdn" in src:
                imgs.append(src)
        # dedupe
        imgs = list(dict.fromkeys(imgs))
        if not imgs:
            try:
                if progress_msg:
                    await progress_msg.edit(content="⚠️ No screenshots found or profile private.")
                else:
                    await interaction.followup.send("⚠️ No screenshots found or profile private.", ephemeral=True)
            except Exception:
                pass
            return

        # paginate screenshots 1 per page (with next/prev)
        pages = chunk_list(imgs, 1)
        page_idx = 0

        def make_embed_for(idx):
            e = discord.Embed(title=f"📷 Screenshots — {idx+1}/{len(pages)}", color=discord.Color.dark_gray())
            e.set_image(url=pages[idx][0])
            return e

        view = discord.ui.View(timeout=300)
        prev_btn = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        next_btn = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)

        async def prev_cb(btn_inter):
            nonlocal page_idx
            page_idx = (page_idx - 1) % len(pages)
            try:
                await btn_inter.response.edit_message(embed=make_embed_for(page_idx), view=view)
            except Exception:
                try:
                    await btn_inter.followup.send(embed=make_embed_for(page_idx), ephemeral=True)
                except Exception:
                    pass

        async def next_cb(btn_inter):
            nonlocal page_idx
            page_idx = (page_idx + 1) % len(pages)
            try:
                await btn_inter.response.edit_message(embed=make_embed_for(page_idx), view=view)
            except Exception:
                try:
                    await btn_inter.followup.send(embed=make_embed_for(page_idx), ephemeral=True)
                except Exception:
                    pass

        prev_btn.callback = prev_cb
        next_btn.callback = next_cb
        if len(pages) > 1:
            view.add_item(prev_btn)
            view.add_item(next_btn)

        try:
            if progress_msg:
                await progress_msg.edit(content=None, embed=make_embed_for(0), view=view)
            else:
                await interaction.followup.send(embed=make_embed_for(0), view=view, ephemeral=True)
        except Exception:
            try:
                await interaction.followup.send(embed=make_embed_for(0), view=view, ephemeral=True)
            except Exception:
                pass

    # ------------------ Videos ------------------
    async def _send_videos(self, interaction: discord.Interaction, steamid: str, progress_msg=None):
        async with aiohttp.ClientSession() as session:
            html = await fetch_text(session, f"https://steamcommunity.com/profiles/{steamid}/videos/") or await fetch_text(session, f"https://steamcommunity.com/profiles/{steamid}") or await fetch_text(session, f"https://steamcommunity.com/id/{steamid}/videos/")
        if not html:
            try:
                await progress_msg.edit(content="⚠️ Could not fetch videos or profile is private.")
            except Exception:
                await interaction.followup.send("⚠️ Could not fetch videos or profile is private.", ephemeral=True)
            return

        soup = BeautifulSoup(html, "html.parser")
        videos = []
        # many profiles embed videos as anchors or iframes
        for a in soup.select("a"):
            href = a.get("href")
            if href and ("youtube.com" in href or "vimeo.com" in href or "/sharedfiles/" in href or "/videos/" in href):
                videos.append(href)
        videos = list(dict.fromkeys(videos))
        if not videos:
            try:
                if progress_msg:
                    await progress_msg.edit(content="⚠️ No videos found.")
                else:
                    await interaction.followup.send("⚠️ No videos found.", ephemeral=True)
            except Exception:
                pass
            return

        # present videos as a list embed
        embed = discord.Embed(title="📹 Videos", description="\n".join(f"[Video]({v})" for v in videos[:25]), color=discord.Color.dark_red())
        try:
            if progress_msg:
                await progress_msg.edit(content=None, embed=embed)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception:
                pass

    # ------------------ Comments ------------------
    async def _send_comments(self, interaction: discord.Interaction, steamid: str, progress_msg=None):
        async with aiohttp.ClientSession() as session:
            html = await fetch_text(session, f"https://steamcommunity.com/profiles/{steamid}") or await fetch_text(session, f"https://steamcommunity.com/id/{steamid}")
        if not html:
            try:
                if progress_msg:
                    await progress_msg.edit(content="⚠️ Could not fetch profile (private?)")
                else:
                    await interaction.followup.send("⚠️ Could not fetch profile (private?)", ephemeral=True)
            except Exception:
                pass
            return

        soup = BeautifulSoup(html, "html.parser")
        # comments often are loaded dynamically; try common selectors
        comment_nodes = soup.select(".commentthread_comment") or soup.select(".profile_comment") or []
        parsed = []
        for cn in comment_nodes[:8]:
            try:
                # author link
                a = cn.select_one(".commentthread_author_link") or cn.select_one("a")
                author_name = a.get_text(" ", strip=True) if a else "Unknown"
                author_link = a["href"] if a and a.has_attr("href") else None
                # avatar
                av = cn.find("img")
                avatar_url = av["src"] if av and av.has_attr("src") else None
                # comment text
                text_el = cn.select_one(".commentthread_comment_text") or cn.find("div", class_=lambda c: c and "comment" in c)
                comment_text = text_el.get_text(" ", strip=True) if text_el else ""
                parsed.append({"author": author_name, "link": author_link, "avatar": avatar_url, "text": comment_text})
            except Exception:
                continue

        if not parsed:
            # fallback: try comments page
            comments_html = await fetch_text(session, f"https://steamcommunity.com/profiles/{steamid}/comments/") or await fetch_text(session, f"https://steamcommunity.com/id/{steamid}/comments/")
            if comments_html:
                csoup = BeautifulSoup(comments_html, "html.parser")
                comment_nodes = csoup.select(".commentthread_comment")[:8]
                for cn in comment_nodes:
                    try:
                        a = cn.select_one(".commentthread_author_link") or cn.select_one("a")
                        author_name = a.get_text(" ", strip=True) if a else "Unknown"
                        author_link = a["href"] if a and a.has_attr("href") else None
                        av = cn.find("img")
                        avatar_url = av["src"] if av and av.has_attr("src") else None
                        text_el = cn.select_one(".commentthread_comment_text")
                        comment_text = text_el.get_text(" ", strip=True) if text_el else ""
                        parsed.append({"author": author_name, "link": author_link, "avatar": avatar_url, "text": comment_text})
                    except Exception:
                        continue

        if not parsed:
            try:
                if progress_msg:
                    await progress_msg.edit(content="⚠️ No comments found or profile private.")
                else:
                    await interaction.followup.send("⚠️ No comments found or profile private.", ephemeral=True)
            except Exception:
                pass
            return

        # Build embeds: each comment -> its own small embed so we can set_author (avatar on the left)
        embeds = []
        for cm in parsed[:8]:
            e = discord.Embed(color=discord.Color.blurple())
            author_name = cm.get("author") or "Unknown"
            author_link = cm.get("link")
            avatar = cm.get("avatar")
            try:
                if author_link:
                    e.set_author(name=author_name, url=author_link, icon_url=avatar)
                else:
                    e.set_author(name=author_name, icon_url=avatar)
            except Exception:
                e.set_author(name=author_name)
            text = cm.get("text") or "*No message*"
            # prettify the text a bit
            text = textwrap.fill(text, width=900)
            e.description = text if len(text) <= 4000 else text[:3997] + "…"
            embeds.append(e)

        # Send first embed and let user page through (prev/next)
        idx = 0
        view = discord.ui.View(timeout=300)
        prev_btn = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        next_btn = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)

        async def prev_cb(btn_inter):
            nonlocal idx
            idx = (idx - 1) % len(embeds)
            try:
                await btn_inter.response.edit_message(embed=embeds[idx], view=view)
            except Exception:
                try:
                    await btn_inter.followup.send(embed=embeds[idx], ephemeral=True)
                except Exception:
                    pass

        async def next_cb(btn_inter):
            nonlocal idx
            idx = (idx + 1) % len(embeds)
            try:
                await btn_inter.response.edit_message(embed=embeds[idx], view=view)
            except Exception:
                try:
                    await btn_inter.followup.send(embed=embeds[idx], ephemeral=True)
                except Exception:
                    pass

        prev_btn.callback = prev_cb
        next_btn.callback = next_cb
        if len(embeds) > 1:
            view.add_item(prev_btn)
            view.add_item(next_btn)

        try:
            if progress_msg:
                await progress_msg.edit(content=None, embed=embeds[0], view=view)
            else:
                await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)
        except Exception:
            try:
                await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)
            except Exception:
                pass

    # ------------------ Groups ------------------
    async def _send_groups(self, interaction: discord.Interaction, steamid: str, progress_msg=None):
        async with aiohttp.ClientSession() as session:
            html = await fetch_text(session, f"https://steamcommunity.com/profiles/{steamid}/groups/") or await fetch_text(session, f"https://steamcommunity.com/profiles/{steamid}") or await fetch_text(session, f"https://steamcommunity.com/id/{steamid}/groups/")
        if not html:
            try:
                if progress_msg:
                    await progress_msg.edit(content="⚠️ Could not fetch groups.")
                else:
                    await interaction.followup.send("⚠️ Could not fetch groups.", ephemeral=True)
            except Exception:
                pass
            return

        soup = BeautifulSoup(html, "html.parser")
        groups = []
        # try group block selectors
        for g in soup.select(".groupBlock")[:60]:
            a = g.select_one("a")
            if a and a.has_attr("href"):
                groups.append({"name": a.get_text(" ", strip=True), "url": a["href"]})
        # fallback: find any /groups/ links
        if not groups:
            for a in soup.find_all("a", href=True):
                if "/groups/" in a["href"]:
                    groups.append({"name": a.get_text(" ", strip=True), "url": a["href"]})
        if not groups:
            try:
                if progress_msg:
                    await progress_msg.edit(content="⚠️ No groups found.")
                else:
                    await interaction.followup.send("⚠️ No groups found.", ephemeral=True)
            except Exception:
                pass
            return

        # Build a clean numbered list embed (up to 40)
        lines = []
        for i, g in enumerate(groups[:40], start=1):
            lines.append(f"**{i}. [{g['name']}]({g['url']})**")
        embed = discord.Embed(title="👪 Groups", description="\n\n".join(lines), color=discord.Color.teal())
        try:
            if progress_msg:
                await progress_msg.edit(content=None, embed=embed)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception:
                pass


# -------------------- Game search command (kept) --------------------
    @steam_group.command(name="game", description="Search a game on Steam")
    @app_commands.describe(game_name="Name of the game")
    async def game(self, interaction: discord.Interaction, game_name: str):
        await interaction.response.defer()
        search_url = f"https://store.steampowered.com/api/storesearch/?term={game_name}&l=en&cc=us"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(search_url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send(f"❌ Failed to search for '{game_name}'")
                    search_data = await resp.json()
            except Exception:
                return await interaction.followup.send("❌ Failed to search Steam.")

        items = search_data.get("items", [])
        if not items:
            return await interaction.followup.send(f"❌ No results found for '{game_name}'")

        top_items = items[:3]
        view = discord.ui.View(timeout=60)

        async def make_button(item):
            label = (item["name"][:80]) if item.get("name") else "Game"
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)

            async def button_callback(button_inter: discord.Interaction):
                await button_inter.response.defer(ephemeral=True)
                appid = item["id"]
                url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=us&l=en"
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(url) as resp:
                            data = await resp.json()
                    except Exception:
                        return await button_inter.followup.send(f"❌ No data found for '{item['name']}'", ephemeral=True)
                app_data = data.get(str(appid), {}).get("data")
                if not app_data:
                    return await button_inter.followup.send(f"❌ No data found for '{item['name']}'", ephemeral=True)

                name = app_data.get("name", "Unknown")
                description = app_data.get("short_description", "No description available.")
                description = (description[:400] + "…") if len(description) > 400 else description
                header_image = app_data.get("header_image")
                genres = [g["description"] for g in app_data.get("genres", [])]
                main_genre = genres[0] if genres else "Other"
                platforms = [k for k, v in app_data.get("platforms", {}).items() if v]
                price_info = app_data.get("price_overview")
                metacritic = app_data.get("metacritic", {}).get("score")
                tags = app_data.get("categories", [])
                is_free = app_data.get("is_free", False)
                release_date = app_data.get("release_date", {}).get("date", "Unknown")

                genre_colors = {"Action": 0xE74C3C, "Adventure": 0x3498DB, "RPG": 0x9B59B6, "Strategy": 0xF1C40F, "Simulation": 0x1ABC9C, "Sports": 0xE67E22, "Other": 0x95A5A6}
                color = genre_colors.get(main_genre, 0x95A5A6)
                if is_free:
                    price_str = "Free"
                elif price_info:
                    final = price_info.get("final_formatted", "Unknown")
                    initial = price_info.get("initial_formatted", "")
                    discount = price_info.get("discount_percent", 0)
                    price_str = f"~~{initial}~~ → **{final}** ({discount}% off)" if discount > 0 else final
                else:
                    price_str = "N/A"

                badge_list = []
                if metacritic:
                    badge_list.append(f"⭐ Metacritic: {metacritic}")
                if tags:
                    top_tags = [t["description"] for t in tags[:5]]
                    badge_list.append(" | ".join(top_tags))
                badge_text = " | ".join(badge_list) if badge_list else "No badges"

                embed = discord.Embed(title=name, description=description, color=color)
                embed.set_thumbnail(url=header_image)
                embed.add_field(name="Price", value=price_str, inline=True)
                embed.add_field(name="Release Date", value=release_date, inline=True)
                embed.add_field(name="Platforms", value=", ".join(platforms) if platforms else "Unknown", inline=True)
                embed.add_field(name="Tags & Ratings", value=badge_text, inline=False)

                result_view = discord.ui.View()
                result_view.add_item(discord.ui.Button(label="View on Steam", url=f"https://store.steampowered.com/app/{appid}", style=discord.ButtonStyle.link))
                await button_inter.followup.send(embed=embed, view=result_view, ephemeral=True)

            button.callback = button_callback
            view.add_item(button)

        for it in top_items:
            await make_button(it)

        try:
            await interaction.followup.send(content=f"Select a game from the top {len(top_items)} results:", view=view, ephemeral=True)
        except Exception:
            try:
                await interaction.response.send_message(content=f"Select a game from the top {len(top_items)} results:", view=view, ephemeral=True)
            except Exception:
                pass


# -------------------- Setup --------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Steam(bot))
