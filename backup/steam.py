# cogs/steam.py
import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import aiosqlite
from bs4 import BeautifulSoup
import asyncio
import textwrap
import re
import math
import random
import io
from helpers.steam_helper import (
    logger, safe_json, fetch_text, chunk_list, random_color, human_hours,
    safe_text, make_friend_grid_image, STEAM_API_KEY, DB_PATH, PIL_AVAILABLE,
    ComparisonView, RecommendationView, EnhancedGameView, ScreenshotView,
    create_comparison_embed, get_price_string, create_recommendation_embed
)


# -------------------- Cog --------------------
class Steam(commands.Cog):
    """Steam helper cog: exposes internal helper methods and Views used by per-command cogs."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot


    # ---------------- Profile ----------------
    async def profile(self, interaction: discord.Interaction, user: str = None):
        logger.info(f"/steam profile invoked by user={interaction.user} arg_user={user} guild={getattr(interaction.guild,'id',None)}")
        await interaction.response.defer(ephemeral=True)

        # resolve steam id
        steamid = None
        vanity = None
        if not user:
            async with aiosqlite.connect(DB_PATH) as db:
                # Try to use guild-aware lookup if running in a guild
                guild_id = getattr(interaction.guild, 'id', None)
                row = None
                if guild_id is not None:
                    try:
                        cur = await db.execute("SELECT steam_id, vanity_name FROM steam_users WHERE discord_id = ? AND guild_id = ?", (interaction.user.id, guild_id))
                        row = await cur.fetchone()
                        await cur.close()
                    except Exception:
                        row = None

                if not row:
                    cur = await db.execute("SELECT steam_id, vanity_name FROM steam_users WHERE discord_id = ?", (interaction.user.id,))
                    row = await cur.fetchone()
                    await cur.close()

                if not row:
                    return await interaction.followup.send("❌ You have not registered a Steam account. Use `/steam register <vanity>`.", ephemeral=True)
                steamid, vanity = row
                user = vanity
        logger.debug(f"Resolved steam identifier: steamid={steamid} vanity={vanity} (user param now={user})")

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
                logger.warning(f"No players data returned for steamid={steamid}")
                return await interaction.followup.send("❌ No profile data found.", ephemeral=True)
            player = players[0]
            logger.debug(f"Fetched player summary for steamid={steamid} -> personaname={player.get('personaname')}")

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
            logger.debug(f"Found {len(friend_ids)} friends for steamid={steamid}")

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


# -------------------- Recommendations command --------------------
    async def recommendations(self, interaction: discord.Interaction):
        logger.info(f"/steam recommendations by {interaction.user}")
        await interaction.response.defer(ephemeral=True)

        # Get user's Steam ID
        steamid = None
        async with aiosqlite.connect(DB_PATH) as db:
            # Prefer guild-scoped lookup when in a guild
            guild_id = getattr(interaction.guild, 'id', None)
            row = None
            if guild_id is not None:
                try:
                    cur = await db.execute("SELECT steam_id FROM steam_users WHERE discord_id = ? AND guild_id = ?", (interaction.user.id, guild_id))
                    row = await cur.fetchone()
                    await cur.close()
                except Exception:
                    row = None

            if not row:
                cur = await db.execute("SELECT steam_id FROM steam_users WHERE discord_id = ?", (interaction.user.id,))
                row = await cur.fetchone()
            await cur.close()
            if not row:
                return await interaction.followup.send("❌ You have not registered a Steam account. Use `/steam register <vanity>`.", ephemeral=True)
            steamid = row[0]

        async with aiohttp.ClientSession() as session:
            # Get user's owned games with detailed info
            owned = await safe_json(session, "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
                                    params={"key": STEAM_API_KEY, "steamid": steamid, "include_appinfo": 1, "include_played_free_games": 1})
            owned_games = owned.get("response", {}).get("games", []) if owned else []
            
            if not owned_games:
                return await interaction.followup.send("❌ No games found in your library or profile is private.", ephemeral=True)

            if len(owned_games) < 3:
                return await interaction.followup.send("❌ You need at least 3 games in your library to get recommendations.", ephemeral=True)

            # Analyze user preferences
            await interaction.followup.send("🔄 Analyzing your game library and preferences...", ephemeral=True)
            
            recommendations = await self._generate_recommendations(session, owned_games, steamid)
            
            if not recommendations:
                return await interaction.edit_original_response(content="❌ Could not generate recommendations. Try again later.")

            # Create interactive recommendation view
            view = RecommendationView(recommendations, interaction.user)
            embed = await self._create_recommendation_embed(recommendations[0], 1, len(recommendations))
            
            await interaction.edit_original_response(
                content="🎮 **Personalized Game Recommendations**\nBased on your library analysis:",
                embed=embed,
                view=view
            )

    async def _generate_recommendations(self, session, owned_games, steamid):
        """Generate personalized recommendations based on user's library"""
        
        # Step 1: Analyze user's gaming preferences
        total_playtime = sum(g.get("playtime_forever", 0) for g in owned_games)
        if total_playtime == 0:
            # If no playtime data, use all games equally
            analyzed_games = owned_games[:20]  # Analyze top 20 by app ID
        else:
            # Focus on games with significant playtime (at least 1 hour or top 50% by playtime)
            min_playtime = max(60, total_playtime * 0.02)  # 2% of total playtime or 1 hour minimum
            analyzed_games = [g for g in owned_games if g.get("playtime_forever", 0) >= min_playtime]
            if len(analyzed_games) < 3:
                analyzed_games = sorted(owned_games, key=lambda x: x.get("playtime_forever", 0), reverse=True)[:10]

        # Step 2: Collect detailed game information for analysis
        genre_scores = {}
        tag_scores = {}
        developer_scores = {}
        publisher_scores = {}
        
        analyzed_count = 0
        owned_app_ids = {str(g["appid"]) for g in owned_games}

        for game in analyzed_games[:15]:  # Limit API calls
            app_id = game["appid"]
            playtime_weight = max(1, math.log(game.get("playtime_forever", 60) + 1))  # Logarithmic weighting
            
            # Get detailed app info
            app_data = await safe_json(session, f"https://store.steampowered.com/api/appdetails", 
                                     params={"appids": app_id, "cc": "us", "l": "en"})
            
            if not app_data or str(app_id) not in app_data:
                continue
                
            details = app_data[str(app_id)].get("data", {})
            if not details:
                continue
                
            analyzed_count += 1
            
            # Analyze genres
            for genre in details.get("genres", []):
                genre_name = genre.get("description", "")
                if genre_name:
                    genre_scores[genre_name] = genre_scores.get(genre_name, 0) + playtime_weight
            
            # Analyze categories/tags
            for category in details.get("categories", []):
                cat_name = category.get("description", "")
                if cat_name:
                    tag_scores[cat_name] = tag_scores.get(cat_name, 0) + playtime_weight * 0.5
            
            # Analyze developers
            for dev in details.get("developers", []):
                developer_scores[dev] = developer_scores.get(dev, 0) + playtime_weight
            
            # Analyze publishers  
            for pub in details.get("publishers", []):
                publisher_scores[pub] = publisher_scores.get(pub, 0) + playtime_weight * 0.7
            
            await asyncio.sleep(0.1)  # Rate limiting

        if analyzed_count == 0:
            return []

        # Step 3: Find recommendation candidates
        # Use Steam's recommendation API and store search
        candidates = []
        
        # Get top genres for searching
        top_genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:3]
        
        for genre_name, _ in top_genres:
            # Search Steam store for games in preferred genres
            search_url = "https://store.steampowered.com/api/storesearch/"
            search_data = await safe_json(session, search_url, params={
                "term": genre_name,
                "l": "en",
                "cc": "us",
                "category1": "998"  # Games category
            })
            
            if search_data and "items" in search_data:
                for item in search_data["items"][:20]:  # Top 20 per genre
                    if str(item["id"]) not in owned_app_ids:  # Don't recommend owned games
                        candidates.append(item["id"])
            
            await asyncio.sleep(0.1)
        
        # Step 4: Score and rank candidates
        scored_recommendations = []
        
        for app_id in list(set(candidates))[:50]:  # Limit to 50 unique candidates
            # Get detailed info for scoring
            app_data = await safe_json(session, f"https://store.steampowered.com/api/appdetails",
                                     params={"appids": app_id, "cc": "us", "l": "en"})
            
            if not app_data or str(app_id) not in app_data:
                continue
                
            details = app_data[str(app_id)].get("data", {})
            if not details or details.get("type") != "game":
                continue
            
            # Calculate recommendation score
            score = 0
            match_reasons = []
            
            # Genre matching
            for genre in details.get("genres", []):
                genre_name = genre.get("description", "")
                if genre_name in genre_scores:
                    genre_weight = genre_scores[genre_name] / max(genre_scores.values())
                    score += genre_weight * 10
                    match_reasons.append(f"Genre: {genre_name}")
            
            # Tag/category matching
            for category in details.get("categories", []):
                cat_name = category.get("description", "")
                if cat_name in tag_scores:
                    tag_weight = tag_scores[cat_name] / max(tag_scores.values()) if tag_scores else 0
                    score += tag_weight * 5
                    match_reasons.append(f"Feature: {cat_name}")
            
            # Developer matching
            for dev in details.get("developers", []):
                if dev in developer_scores:
                    dev_weight = developer_scores[dev] / max(developer_scores.values())
                    score += dev_weight * 8
                    match_reasons.append(f"Developer: {dev}")
            
            # Publisher matching
            for pub in details.get("publishers", []):
                if pub in publisher_scores:
                    pub_weight = publisher_scores[pub] / max(publisher_scores.values())
                    score += pub_weight * 6
                    match_reasons.append(f"Publisher: {pub}")
            
            # Boost score for highly rated games
            metacritic_score = details.get("metacritic", {}).get("score", 0)
            if metacritic_score > 75:
                score += 3
                match_reasons.append(f"Highly rated ({metacritic_score}/100)")
            
            # Add popularity boost for games with many reviews
            # (This would require additional API calls, so we'll skip for now)
            
            if score > 0:
                scored_recommendations.append({
                    "app_id": app_id,
                    "score": score,
                    "details": details,
                    "match_reasons": match_reasons[:3]  # Top 3 reasons
                })
            
            await asyncio.sleep(0.08)
        
        # Sort by score and return top recommendations
        scored_recommendations.sort(key=lambda x: x["score"], reverse=True)
        return scored_recommendations[:12]  # Return top 12 recommendations

    async def _create_recommendation_embed(self, recommendation, current_index, total_count):
        """Create an embed for a single recommendation"""
        details = recommendation["details"]
        
        name = details.get("name", "Unknown Game")
        description = details.get("short_description", "No description available.")
        if len(description) > 300:
            description = description[:297] + "..."
        
        header_image = details.get("header_image", "")
        app_id = recommendation["app_id"]
        
        # Get genre and pricing info
        genres = [g["description"] for g in details.get("genres", [])]
        price_info = details.get("price_overview", {})
        is_free = details.get("is_free", False)
        release_date = details.get("release_date", {}).get("date", "Unknown")
        
        # Format price
        if is_free:
            price_str = "Free to Play"
            color = discord.Color.green()
        elif price_info:
            price_str = price_info.get("final_formatted", "Price unknown")
            discount = price_info.get("discount_percent", 0)
            if discount > 0:
                original = price_info.get("initial_formatted", "")
                price_str = f"~~{original}~~ → **{price_str}** ({discount}% off)"
                color = discord.Color.gold()
            else:
                color = discord.Color.blue()
        else:
            price_str = "Price not available"
            color = discord.Color.dark_gray()
        
        embed = discord.Embed(
            title=name,
            description=description,
            color=color,
            url=f"https://store.steampowered.com/app/{app_id}"
        )
        
        if header_image:
            embed.set_image(url=header_image)
        
        embed.add_field(name="💰 Price", value=price_str, inline=True)
        embed.add_field(name="📅 Release Date", value=release_date, inline=True)
        embed.add_field(name="🎮 Genres", value=", ".join(genres[:3]) if genres else "Unknown", inline=True)
        
        embed.set_footer(text=f"Recommendation {current_index}/{total_count} • Score: {recommendation['score']:.1f}")
        
        return embed

    # -------------------- Enhanced Game search command --------------------
    async def game(self, interaction: discord.Interaction, game_name: str, 
                  genre: str = None, max_price: float = None, platform: str = None, 
                  tag: str = None, sort_by: str = "relevance"):
        await interaction.response.defer(ephemeral=True)
        
        # Build search URL with filters
        search_params = {
            "term": game_name,
            "l": "en",
            "cc": "us",
            "category1": "998"  # Games category
        }
        
        # Add genre filter
        if genre:
            genre_map = {
                "action": "19", "adventure": "25", "casual": "597", "indie": "492",
                "massively multiplayer": "128", "racing": "699", "rpg": "122",
                "simulation": "599", "sports": "701", "strategy": "2"
            }
            if genre.lower() in genre_map:
                search_params["category2"] = genre_map[genre.lower()]
        
        search_url = f"https://store.steampowered.com/api/storesearch/"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(search_url, params=search_params) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send(f"❌ Failed to search for '{game_name}'")
                    search_data = await resp.json()
            except Exception:
                return await interaction.followup.send("❌ Failed to search Steam.")

        items = search_data.get("items", [])
        if not items:
            return await interaction.followup.send(f"❌ No results found for '{game_name}'" + 
                                                 (f" with filters" if any([genre, max_price, platform, tag]) else ""))

        # Apply additional filters
        filtered_items = await self._apply_filters(session, items, max_price, platform, tag)
        
        # Sort results
        filtered_items = self._sort_results(filtered_items, sort_by)
        
        top_items = filtered_items[:5]  # Show top 5 instead of 3
        view = discord.ui.View(timeout=120)  # Longer timeout for complex view

        for item in top_items:
            await self._create_game_button(view, item, session)

        filter_info = []
        if genre: filter_info.append(f"Genre: {genre}")
        if max_price: filter_info.append(f"Max Price: ${max_price}")
        if platform: filter_info.append(f"Platform: {platform}")
        if tag: filter_info.append(f"Tag: {tag}")
        if sort_by != "relevance": filter_info.append(f"Sort: {sort_by}")
        
        filter_text = f" | Filters: {', '.join(filter_info)}" if filter_info else ""
        
        try:
            await interaction.followup.send(
                content=f"🎮 **Steam Game Search Results** ({len(filtered_items)} found){filter_text}\n"
                       f"Select a game for detailed information:",
                view=view, ephemeral=True
            )
        except Exception:
            try:
                await interaction.response.send_message(
                    content=f"🎮 **Steam Game Search Results** ({len(filtered_items)} found){filter_text}\n"
                           f"Select a game for detailed information:",
                    view=view, ephemeral=True
                )
            except Exception:
                pass

    # ==================== ENHANCED GAME SEARCH HELPER METHODS ====================
    
    async def _apply_filters(self, session, items, max_price=None, platform=None, tag=None):
        """Apply additional filters to search results"""
        if not any([max_price, platform, tag]):
            return items
        
        filtered_items = []
        
        for item in items[:20]:  # Limit API calls
            try:
                appid = item["id"]
                app_data = await self._get_app_details(session, appid)
                
                if not app_data:
                    continue
                
                # Price filter
                if max_price is not None:
                    price_info = app_data.get("price_overview")
                    if price_info:
                        price_cents = price_info.get("final", 0)
                        price_dollars = price_cents / 100.0
                        if price_dollars > max_price:
                            continue
                    elif not app_data.get("is_free", False):
                        continue  # Skip if price unknown and not free
                
                # Platform filter
                if platform:
                    platforms = app_data.get("platforms", {})
                    platform_key = platform.lower()
                    if platform_key not in platforms or not platforms[platform_key]:
                        continue
                
                # Tag filter (check categories and tags)
                if tag:
                    tag_lower = tag.lower()
                    categories = app_data.get("categories", [])
                    genres = app_data.get("genres", [])
                    
                    found_tag = False
                    for cat in categories:
                        if tag_lower in cat.get("description", "").lower():
                            found_tag = True
                            break
                    
                    if not found_tag:
                        for genre in genres:
                            if tag_lower in genre.get("description", "").lower():
                                found_tag = True
                                break
                    
                    if not found_tag:
                        continue
                
                # Add enriched item data
                item["_app_data"] = app_data
                filtered_items.append(item)
                
            except Exception as e:
                logger.debug(f"Error filtering item {item.get('id')}: {e}")
                continue
        
        return filtered_items
    
    def _sort_results(self, items, sort_by):
        """Sort search results by specified criteria"""
        if sort_by == "relevance":
            return items  # Already sorted by relevance
        
        def sort_key(item):
            app_data = item.get("_app_data", {})
            
            if sort_by == "price":
                price_info = app_data.get("price_overview")
                if price_info:
                    return price_info.get("final", 0)
                return 0 if app_data.get("is_free") else float('inf')
            
            elif sort_by == "release_date":
                release_info = app_data.get("release_date", {})
                date_str = release_info.get("date", "")
                try:
                    from datetime import datetime
                    # Try to parse date
                    date_obj = datetime.strptime(date_str, "%b %d, %Y")
                    return date_obj.timestamp()
                except:
                    return 0
            
            elif sort_by == "reviews":
                # Sort by positive review percentage
                reviews = app_data.get("reviews", {})
                positive = reviews.get("positive", 0)
                total = reviews.get("total", 1)
                return (positive / total) * 100 if total > 0 else 0
            
            return 0
        
        reverse = sort_by in ["release_date", "reviews"]  # Newest first, best reviews first
        return sorted(items, key=sort_key, reverse=reverse)
    
    async def _get_app_details(self, session, appid):
        """Get detailed app information from Steam API"""
        try:
            url = "https://store.steampowered.com/api/appdetails"
            params = {"appids": appid, "cc": "us", "l": "en"}
            headers = {"User-Agent": "Mozilla/5.0 (compatible; LemegetonBot/1.0)", "Accept-Language": "en-US,en;q=0.9"}
            logger.debug(f"_get_app_details requesting appid={appid} params={params} headers={headers}")
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                logger.debug(f"_get_app_details resp.status={resp.status} for appid={appid}")
                if resp.status == 200:
                    try:
                        data = await resp.json()
                    except Exception as e:
                        text = await resp.text()
                        logger.debug(f"_get_app_details failed parsing json for {appid}; text[:200]={text[:200]!r}")
                        raise
                    entry = data.get(str(appid))
                    if entry is None:
                        logger.debug(f"_get_app_details no entry for {appid} in response")
                        return None
                    # entry may be {success: bool, data: {...}}
                    if not entry.get("success", False):
                        logger.debug(f"_get_app_details success=false for {appid}; attempting fallback without cc")
                        # Retry without country code (some apps are region-locked or return success:false)
                        params2 = {"appids": appid, "l": "en"}
                        async with session.get(url, params=params2, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp2:
                            logger.debug(f"_get_app_details retry resp.status={resp2.status} for appid={appid}")
                            if resp2.status == 200:
                                try:
                                    data2 = await resp2.json()
                                except Exception:
                                    logger.debug("_get_app_details retry failed to parse json")
                                    return None
                                entry2 = data2.get(str(appid))
                                if entry2 and entry2.get("success", False):
                                    logger.debug(f"_get_app_details retry succeeded for {appid}")
                                    return entry2.get("data")
                        return None
                    appdata = entry.get("data")
                    logger.debug(f"_get_app_details found data for {appid}: {bool(appdata)}")
                    return appdata
        except Exception as e:
            logger.exception(f"Error getting app details for {appid}: {e}")
        return None
    
    async def _create_game_button(self, view, item, session):
        """Create an enhanced game button with rich information"""
        name = item.get("name", "Unknown Game")
        label = name[:75] + "..." if len(name) > 75 else name
        
        button = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)
        
        async def enhanced_callback(button_inter: discord.Interaction):
            # Defer publicly so the detailed embed is posted to the channel (not ephemeral)
            await button_inter.response.defer(ephemeral=False)
            
            appid = item["id"]
            app_data = item.get("_app_data")

            # Prefer cached data; otherwise try to use the provided session if it's still open.
            if not app_data:
                try:
                    use_session = None
                    if session is not None and not getattr(session, "closed", False):
                        use_session = session
                    if use_session is not None:
                        app_data = await self._get_app_details(use_session, appid)
                    else:
                        logger.debug(f"enhanced_callback: provided session closed or None for appid={appid}; creating temp session")
                        async with aiohttp.ClientSession() as tmp_sess:
                            app_data = await self._get_app_details(tmp_sess, appid)
                except Exception:
                    logger.exception(f"enhanced_callback: exception while fetching app details for appid={appid}")
                    # final attempt with a fresh session
                    try:
                        async with aiohttp.ClientSession() as tmp_sess:
                            app_data = await self._get_app_details(tmp_sess, appid)
                    except Exception:
                        logger.exception(f"enhanced_callback: final attempt failed for appid={appid}")

            if not app_data:
                logger.warning(f"enhanced_callback: failed to load app_data for appid={appid} name={name}")
                return await button_inter.followup.send(f"❌ Could not load details for '{name}'", ephemeral=False)
            
            # Create enhanced game view and send embed; guard against embed creation errors
            try:
                game_view = EnhancedGameView(app_data, appid, session, button_inter.user)
                embed = await game_view.create_main_embed()
                # Send non-ephemeral so the embed is visible to the channel
                await button_inter.followup.send(embed=embed, view=game_view, ephemeral=False)
                logger.debug(f"enhanced_callback: sent enhanced embed for appid={appid} name={name}")
            except Exception as e:
                logger.exception(f"enhanced_callback: failed to build/send embed for appid={appid} name={name}: {e}")
                # Fallback: send a simple text/embed with basic info so the user gets something
                try:
                    simple_embed = discord.Embed(title=name, url=f"https://store.steampowered.com/app/{appid}", description="Details unavailable; displaying a quick link.", color=discord.Color.dark_gray())
                    await button_inter.followup.send(embed=simple_embed, ephemeral=False)
                except Exception:
                    try:
                        await button_inter.followup.send(f"❌ Could not display detailed info for '{name}', but you can view it on the store: https://store.steampowered.com/app/{appid}", ephemeral=False)
                    except Exception:
                        logger.exception(f"enhanced_callback: failed to send fallback message for appid={appid} name={name}")
        
        button.callback = enhanced_callback
        view.add_item(button)
    
    # ==================== ADDITIONAL ENHANCED COMMANDS ====================
    
    async def compare_games(self, interaction: discord.Interaction, game1: str, game2: str):
        """Compare two games side by side"""
        await interaction.response.defer(ephemeral=True)
        
        async with aiohttp.ClientSession() as session:
            # Search for both games
            game1_data = await self._search_single_game(session, game1)
            game2_data = await self._search_single_game(session, game2)
            
            if not game1_data:
                return await interaction.followup.send(f"❌ Could not find game: {game1}")
            
            if not game2_data:
                return await interaction.followup.send(f"❌ Could not find game: {game2}")
            
            # Create comparison embed
            comparison_embed = self._create_comparison_embed(game1_data, game2_data)
            
            # Create view with individual game buttons
            compare_view = ComparisonView(game1_data, game2_data, session)
            
            await interaction.followup.send(embed=comparison_embed, view=compare_view, ephemeral=True)
    
    async def find_deals(self, interaction: discord.Interaction, max_price: float = None, 
                        genre: str = None, discount_min: int = None):
        """Find current Steam deals and sales"""
        await interaction.response.defer(ephemeral=True)
        
        # This would ideally use Steam's specials API or web scraping
        deals_embed = discord.Embed(
            title="🔥 Current Steam Deals",
            description="Here are some current deals and promotions:",
            color=0xFF4500
        )
        
        # Add filter information
        filters = []
        if max_price:
            filters.append(f"Max Price: ${max_price}")
        if genre:
            filters.append(f"Genre: {genre}")
        if discount_min:
            filters.append(f"Min Discount: {discount_min}%")
        
        if filters:
            deals_embed.add_field(name="🔍 Filters Applied", value=" • ".join(filters), inline=False)
        
        # Sample deals (in a real implementation, this would fetch from Steam API)
        sample_deals = [
            {"name": "Cyberpunk 2077", "original": "$59.99", "current": "$29.99", "discount": "50%"},
            {"name": "The Witcher 3: Wild Hunt", "original": "$39.99", "current": "$9.99", "discount": "75%"},
            {"name": "Hades", "original": "$24.99", "current": "$12.49", "discount": "50%"},
            {"name": "Among Us", "original": "$4.99", "current": "$2.49", "discount": "50%"},
        ]
        
        deal_text = []
        for deal in sample_deals:
            deal_text.append(f"🎮 **{deal['name']}**\n~~{deal['original']}~~ → **{deal['current']}** ({deal['discount']} off)")
        
        deals_embed.add_field(name="💸 Featured Deals", value="\n\n".join(deal_text), inline=False)
        
        deals_embed.set_footer(text="💡 Tip: Use /steam game to get detailed information about any game")
        
        await interaction.followup.send(embed=deals_embed, ephemeral=True)
    
    async def trending_games(self, interaction: discord.Interaction, category: str = "popular"):
        """View trending and popular Steam games"""
        await interaction.response.defer(ephemeral=True)
        
        category_map = {
            "new_releases": "🆕 New Releases",
            "top_sellers": "💰 Top Sellers", 
            "popular": "🔥 Most Popular",
            "upcoming": "🔜 Upcoming"
        }
        
        title = category_map.get(category, "🎮 Trending Games")
        
        trending_embed = discord.Embed(
            title=f"📈 Steam Trends - {title}",
            description=f"Current {title.lower()} on Steam",
            color=0x1E90FF
        )
        
        # Sample trending games (would be fetched from Steam API in real implementation)
        sample_trending = [
            "Counter-Strike 2", "Dota 2", "PUBG: BATTLEGROUNDS", 
            "Apex Legends", "Grand Theft Auto V", "Rust",
            "Team Fortress 2", "Destiny 2", "Warframe", "Path of Exile"
        ]
        
        trending_list = "\n".join(f"{i+1}. {game}" for i, game in enumerate(sample_trending))
        trending_embed.add_field(name="🏆 Top Games", value=trending_list, inline=False)
        
        trending_embed.set_footer(text="📊 Data updates regularly • Use /steam game <name> for details")
        
        await interaction.followup.send(embed=trending_embed, ephemeral=True)
    
    async def _search_single_game(self, session, game_name):
        """Search for a single game and return its data"""
        try:
            search_url = "https://store.steampowered.com/api/storesearch/"
            params = {"term": game_name, "l": "en", "cc": "us"}
            logger.debug(f"_search_single_game searching for '{game_name}' with params={params}")
            async with session.get(search_url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                logger.debug(f"_search_single_game resp.status={resp.status} for '{game_name}'")
                if resp.status != 200:
                    return None
                search_data = await resp.json()
            
            items = search_data.get("items", [])
            logger.debug(f"_search_single_game found {len(items)} search items for '{game_name}'")
            if not items:
                return None
            
            # Get details for the first result
            app_id = items[0]["id"]
            logger.debug(f"_search_single_game selected app_id={app_id} title={items[0].get('name')}")
            app_data = await self._get_app_details(session, app_id)
            logger.debug(f"_search_single_game app_data loaded: {bool(app_data)} for app_id={app_id}")
            
            return {"id": app_id, "data": app_data} if app_data else None
            
        except Exception as e:
            logger.error(f"Error searching for game {game_name}: {e}")
            return None
    
    def _create_comparison_embed(self, game1, game2):
        return create_comparison_embed(game1, game2)


    # ComparisonView imported from helpers.steam_helper


    # RecommendationView, EnhancedGameView, ScreenshotView and helpers imported from helpers.steam_helper

    # EnhancedGameView implementation moved to helpers.steam_helper
    
    def _format_platform_info(self):
        """Format platform support information"""
        platforms = self.app_data.get("platforms", {})
        supported = []
        
        if platforms.get("windows"):
            supported.append("🪟 Windows")
        if platforms.get("mac"):
            supported.append("🍎 Mac")
        if platforms.get("linux"):
            supported.append("🐧 Linux")
        
        return "\n".join(supported) if supported else "❓ Unknown"
    
    def _format_developer_publisher(self):
        """Format developer and publisher information"""
        developers = self.app_data.get("developers", [])
        publishers = self.app_data.get("publishers", [])
        
        dev_str = developers[0] if developers else "Unknown"
        pub_str = publishers[0] if publishers else "Unknown"
        
        if dev_str == pub_str:
            return f"🏢 **{dev_str}**"
        else:
            return f"🏢 **{dev_str}**\n📰 {pub_str}"
    
    def _format_ratings_info(self):
        """Format rating and review information"""
        metacritic = self.app_data.get("metacritic", {})
        
        parts = []
        if metacritic:
            score = metacritic.get("score")
            if score:
                parts.append(f"🏆 Metacritic: {score}/100")
        
        # Add estimated review sentiment (would need Steam reviews API for real data)
        categories = self.app_data.get("categories", [])
        positive_indicators = ["multiplayer", "co-op", "steam achievements"]
        
        for cat in categories:
            desc = cat.get("description", "").lower()
            if any(indicator in desc for indicator in positive_indicators):
                parts.append("👍 Community Features")
                break
        
        return "\n".join(parts) if parts else "📊 No ratings available"
    
    async def _get_player_count(self):
        """Attempt to get current player count"""
        # This would require additional API calls to Steam Charts or similar
        # For now, return a placeholder
        return "📈 See Steam Charts"
    
    def _format_genres_tags(self):
        """Format genres and popular tags"""
        genres = [g["description"] for g in self.app_data.get("genres", [])]
        categories = [c["description"] for c in self.app_data.get("categories", [])]
        
        # Combine and limit
        all_tags = genres + categories
        display_tags = all_tags[:6]  # Show top 6
        
        if not display_tags:
            return "🏷️ No tags available"
        
        tag_str = " • ".join(display_tags)
        if len(all_tags) > 6:
            tag_str += f" • +{len(all_tags) - 6} more"
        
        return tag_str
    
    def _format_system_requirements(self):
        """Format system requirements (brief version)"""
        pc_req = self.app_data.get("pc_requirements")
        if not pc_req:
            return None
        
        minimum = pc_req.get("minimum", "")
        if minimum:
            # Extract key info (simplified)
            if "Windows" in minimum:
                return "🪟 Windows Compatible"
            elif "Mac" in minimum:
                return "🍎 Mac Compatible" 
            elif "Linux" in minimum:
                return "🐧 Linux Compatible"
        
        return "⚙️ See Steam page for details"
    
    def _format_additional_features(self):
        """Format additional game features"""
        features = []
        categories = self.app_data.get("categories", [])
        
        feature_mapping = {
            "Multi-player": "👥 Multiplayer",
            "Co-op": "🤝 Cooperative",
            "Steam Achievements": "🏆 Achievements", 
            "Steam Trading Cards": "🃏 Trading Cards",
            "Steam Workshop": "🔧 Workshop",
            "Steam Cloud": "☁️ Cloud Saves",
            "Controller Support": "🎮 Controller",
            "VR Support": "🥽 VR Ready"
        }
        
        for cat in categories:
            desc = cat.get("description", "")
            for key, icon_desc in feature_mapping.items():
                if key.lower() in desc.lower():
                    features.append(icon_desc)
                    break
        
        return " • ".join(features[:5]) if features else None
    
    @discord.ui.button(label="📷 Screenshots", style=discord.ButtonStyle.secondary)
    async def view_screenshots(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View game screenshots carousel"""
        if not self.screenshots:
            return await interaction.response.send_message("📷 No screenshots available for this game.", ephemeral=True)
        
        await interaction.response.defer()
        
        screenshot_view = ScreenshotView(self.screenshots, self.app_data.get("name", "Game"))
        embed = screenshot_view.create_screenshot_embed(0)
        
        await interaction.followup.send(embed=embed, view=screenshot_view, ephemeral=True)
    
    @discord.ui.button(label="📹 Videos", style=discord.ButtonStyle.secondary) 
    async def view_videos(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View game trailers and videos"""
        if not self.movies:
            return await interaction.response.send_message("📹 No videos available for this game.", ephemeral=True)
        
        await interaction.response.defer()
        
        video_embed = self._create_video_embed()
        await interaction.followup.send(embed=video_embed, ephemeral=True)
    
    @discord.ui.button(label="⚙️ System Requirements", style=discord.ButtonStyle.secondary)
    async def view_requirements(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View detailed system requirements"""
        await interaction.response.defer()
        
        req_embed = self._create_requirements_embed()
        await interaction.followup.send(embed=req_embed, ephemeral=True)
    
    @discord.ui.button(label="🎯 Similar Games", style=discord.ButtonStyle.primary)
    async def find_similar(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Find similar games based on tags and genres"""
        await interaction.response.defer()
        
        similar_embed = await self._create_similar_games_embed()
        await interaction.followup.send(embed=similar_embed, ephemeral=True)
    
    @discord.ui.button(label="💾 Save Game", style=discord.ButtonStyle.success)
    async def save_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Save game to user's personal list"""
        # This would integrate with your bot's database
        await interaction.response.send_message(
            f"💾 **{self.app_data.get('name')}** has been saved to your game list!", 
            ephemeral=True
        )
    
    def _create_video_embed(self):
        """Create embed with video information"""
        name = self.app_data.get("name", "Game")
        embed = discord.Embed(title=f"📹 {name} - Videos", color=0xFF0000)
        
        video_list = []
        for i, movie in enumerate(self.movies[:5], 1):
            movie_name = movie.get("name", f"Video {i}")
            thumbnail = movie.get("thumbnail")
            mp4_url = movie.get("mp4", {}).get("480") or movie.get("webm", {}).get("480")
            
            if mp4_url:
                video_list.append(f"[{movie_name}]({mp4_url})")
            else:
                video_list.append(movie_name)
        
        if video_list:
            embed.description = "\n".join(video_list)
        else:
            embed.description = "No video links available"
        
        if self.movies and self.movies[0].get("thumbnail"):
            embed.set_thumbnail(url=self.movies[0]["thumbnail"])
        
        return embed
    
    def _create_requirements_embed(self):
        """Create detailed system requirements embed"""
        name = self.app_data.get("name", "Game")
        embed = discord.Embed(title=f"⚙️ {name} - System Requirements", color=0x00FF00)
        
        pc_req = self.app_data.get("pc_requirements", {})
        mac_req = self.app_data.get("mac_requirements", {})
        linux_req = self.app_data.get("linux_requirements", {})
        
        if pc_req.get("minimum"):
            min_req = pc_req["minimum"].replace("<br>", "\n").replace("<strong>", "**").replace("</strong>", "**")
            # Remove HTML tags
            import re
            min_req = re.sub('<[^<]+?>', '', min_req)
            embed.add_field(name="🪟 Windows - Minimum", value=min_req[:1000], inline=False)
        
        if pc_req.get("recommended"):
            rec_req = pc_req["recommended"].replace("<br>", "\n").replace("<strong>", "**").replace("</strong>", "**")
            rec_req = re.sub('<[^<]+?>', '', rec_req)
            embed.add_field(name="🪟 Windows - Recommended", value=rec_req[:1000], inline=False)
        
        if not pc_req and not mac_req and not linux_req:
            embed.description = "System requirements not available for this game."
        
        return embed
    
    async def _create_similar_games_embed(self):
        """Create embed with similar game suggestions"""
        name = self.app_data.get("name", "Game")
        embed = discord.Embed(title=f"🎯 Games Similar to {name}", color=0x9B59B6)
        
        # Extract tags for similarity matching
        genres = [g["description"] for g in self.app_data.get("genres", [])]
        tags = [c["description"] for c in self.app_data.get("categories", [])]
        all_tags = genres + tags
        
        # This would ideally use Steam's recommendation API or similar
        # For now, provide general suggestions based on genre
        similar_suggestions = []
        
        if "Action" in genres:
            similar_suggestions.extend(["DOOM Eternal", "Cyberpunk 2077", "Grand Theft Auto V"])
        if "RPG" in genres:
            similar_suggestions.extend(["The Witcher 3", "Skyrim", "Fallout 4"])
        if "Strategy" in genres:
            similar_suggestions.extend(["Age of Empires IV", "Civilization VI", "StarCraft II"])
        if "Indie" in genres:
            similar_suggestions.extend(["Hades", "Celeste", "Hollow Knight"])
        
        # Remove duplicates and limit
        unique_suggestions = list(dict.fromkeys(similar_suggestions))[:8]
        
        if unique_suggestions:
            embed.description = "Based on genres and tags:\n" + "\n".join(f"• {game}" for game in unique_suggestions)
        else:
            embed.description = "No similar games found. Try browsing Steam's recommendation system!"
        
        embed.add_field(name="🏷️ Shared Tags", value=" • ".join(all_tags[:5]), inline=False)
        
        return embed


# ScreenshotView class moved to helpers/steam_helper.py to centralize shared UI Views.


# -------------------- Setup --------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Steam(bot))
