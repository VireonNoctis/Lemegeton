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
import re
import textwrap

logger = logging.getLogger("steam")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
    logger.addHandler(h)


# ---------- Helpers ----------
async def safe_json(session, url, params=None, timeout=20):
    try:
        async with session.get(url, params=params, timeout=timeout) as resp:
            if resp.status != 200:
                logger.debug(f"safe_json: {url} -> {resp.status}")
                return None
            return await resp.json()
    except Exception:
        logger.exception("safe_json failed")
        return None


async def fetch_text(session, url, timeout=20):
    try:
        async with session.get(url, timeout=timeout) as resp:
            if resp.status != 200:
                logger.debug(f"fetch_text: {url} -> {resp.status}")
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
        discord.Color.dark_blue()
    ]
    return random.choice(palette)


# ---------- Cog ----------
class Steam(commands.Cog):
    """Steam commands with improved UX (single-message details, pagination, scraping)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    steam_group = app_commands.Group(name="steam", description="Steam commands")
    steam_group = app_commands.guilds(discord.Object(id=GUILD_ID))(steam_group)

    # ---------------- REGISTER ----------------
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

    # ---------------- PROFILE ----------------
    @steam_group.command(name="profile", description="View a Steam profile (registered or by id/vanity)")
    @app_commands.describe(user="SteamID64 or vanity (optional if registered)")
    async def profile(self, interaction: discord.Interaction, user: str = None):
        logger.info(f"/steam profile by {interaction.user} user={user}")
        await interaction.response.defer(ephemeral=True)

        # resolve steamid
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

            # friends list
            friends_json = await safe_json(session, "https://api.steampowered.com/ISteamUser/GetFriendList/v1/",
                                           params={"key": STEAM_API_KEY, "steamid": steamid, "relationship": "all"})
            friends_list = friends_json.get("friendslist", {}).get("friends", []) if friends_json else []
            friend_ids = [f["steamid"] for f in friends_list]

            # attempt badge count via scraping badges page
            badge_count = None
            try:
                badges_html = await fetch_text(session, f"https://steamcommunity.com/profiles/{steamid}/badges") or await fetch_text(session, f"https://steamcommunity.com/id/{user}/badges")
                if badges_html:
                    bsoup = BeautifulSoup(badges_html, "html.parser")
                    # badges tiles often have 'badge_row' or 'badge' classes — count visible tiles
                    tiles = bsoup.find_all("div", class_=lambda c: c and ("badge_row" in c or "badge" in c))
                    if tiles:
                        # heuristics: many unrelated divs may match; to be safer, count elements that include img or badge_title
                        clean_tiles = [t for t in tiles if t.find("img") or t.find(class_=re.compile(r"badge_title|badge_name"))]
                        badge_count = len(clean_tiles) if clean_tiles else len(tiles)
                    else:
                        # fallback: search text "Badges" with number
                        m = re.search(r"(\d+)\s+Badges", bsoup.get_text())
                        if m:
                            badge_count = int(m.group(1))
            except Exception:
                logger.debug("badge count scraping failed", exc_info=True)

        # status color
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

        # Build main profile embed
        embed = discord.Embed(title=f"{player.get('personaname','Unknown')} — {status_text}",
                              url=player.get("profileurl"),
                              color=color)
        avatar = player.get("avatarfull")
        if avatar:
            embed.set_thumbnail(url=avatar)

        embed.add_field(name="🆔 SteamID", value=str(steamid), inline=False)
        embed.add_field(name="⭐ Level", value=str(level), inline=True)
        embed.add_field(name="🎮 Games", value=str(total_games), inline=True)
        embed.add_field(name="👥 Friends", value=str(len(friend_ids)), inline=True)
        embed.add_field(name="🏅 Badges", value=str(badge_count) if badge_count is not None else "Unknown", inline=True)

        # real name / location / bio
        embed.add_field(name="🧑 Real Name", value=player.get("realname") or "N/A", inline=True)
        embed.add_field(name="🌍 Location", value=player.get("loccountrycode") or "N/A", inline=True)

        # attempt to scrape short bio (profile summary)
        summary_text = None
        try:
            async with aiohttp.ClientSession() as s:
                prof_html = await fetch_text(s, f"https://steamcommunity.com/profiles/{steamid}") or await fetch_text(s, f"https://steamcommunity.com/id/{user}")
                if prof_html:
                    sp = BeautifulSoup(prof_html, "html.parser")
                    summary = sp.select_one(".profile_summary") or sp.select_one("#summary") or sp.find("div", class_=lambda c: c and "profile_summary" in c)
                    if summary:
                        summary_text = summary.get_text(" ", strip=True)
        except Exception:
            logger.debug("bio scrape failed", exc_info=True)

        embed.add_field(name="📝 Bio", value=(summary_text[:900] + "…" if summary_text and len(summary_text) > 900 else summary_text) if summary_text else "N/A", inline=False)
        # top games preview
        if top_games := sorted(owned_games, key=lambda g: g.get("playtime_forever", 0), reverse=True)[:3]:
            preview = [f"**{g.get('name','Unknown')}** — {g.get('playtime_forever', 0)//60}h" for g in top_games]
            embed.add_field(name="🏆 Top Games (preview)", value="\n".join(preview), inline=False)

        embed.set_footer(text="ℹ️ Details • 👁 Toggle Visibility")

        # initial view (30 minutes)
        view = discord.ui.View(timeout=1800)
        view.is_ephemeral = True  # default ephemeral
        details_btn = discord.ui.Button(label="ℹ️ Details", style=discord.ButtonStyle.secondary)
        toggle_btn = discord.ui.Button(label="👁 Toggle Visibility", style=discord.ButtonStyle.danger)

        # DETAILS: edit the same message into a Details panel (single-message flow)
        async def details_cb(btn_inter: discord.Interaction):
            # Build the details panel embed and view (dropdown + buttons)
            details_embed = discord.Embed(title=f"{player.get('personaname','Unknown')} — Details", color=random_color())
            details_embed.description = "Choose a section from the dropdown below. Results will appear in this message."
            details_view = discord.ui.View(timeout=1800)

            select = discord.ui.Select(
                placeholder="Select a section...",
                options=[
                    discord.SelectOption(label="🏆 Top / Most Played Games", value="top_games"),
                    discord.SelectOption(label="🎮 All Games (A → Z)", value="all_games"),
                    discord.SelectOption(label="👥 Friends", value="friends"),
                    discord.SelectOption(label="📷 Screenshots", value="screenshots"),
                    discord.SelectOption(label="📹 Videos", value="videos"),
                    discord.SelectOption(label="💬 Profile Comments", value="comments"),
                    discord.SelectOption(label="👪 Groups", value="groups"),
                ],
                min_values=1, max_values=1
            )

            # state holders for pagination
            state = {
                "games_pages": None,
                "friends_pages": None,
                "groups_pages": None,
                "current_page_idx": 0,
                "last_choice": None
            }

            # helper to sort games A->Z and chunk
            def prepare_game_pages(all_games):
                # sort by name A-Z (case-insensitive)
                sorted_games = sorted(all_games, key=lambda x: (x.get("name") or "").lower())
                # create pages of 5, where each entry is (name, appid)
                pages = []
                chunked = chunk_list(sorted_games, 5)
                for ch in chunked:
                    page_rows = []
                    for g in ch:
                        name = g.get("name", "Unknown")
                        appid = g.get("appid") or g.get("appid") or g.get("id")
                        # make store link
                        url = f"https://store.steampowered.com/app/{appid}" if appid else None
                        page_rows.append({"name": name, "appid": appid, "url": url})
                    pages.append(page_rows)
                return pages

            # helper to build games embed page
            def games_embed_for(page_rows, page_idx, title_text):
                e = discord.Embed(title=f"{title_text} — page {page_idx+1}/{len(state['games_pages'])}", color=discord.Color.blurple())
                for i, entry in enumerate(page_rows, start=1):
                    name = entry["name"]
                    url = entry["url"]
                    # use field name as clickable link
                    if url:
                        e.add_field(name=f"{i}. [{name}]({url})", value="\u200b", inline=False)
                    else:
                        e.add_field(name=f"{i}. {name}", value="\u200b", inline=False)
                return e

            # friends embed builder: each friend gets its own small embed with author (avatar left)
            async def build_friends_pages(friend_ids_list):
                # fetch friend summaries in batches (100)
                friends_summary = []
                async with aiohttp.ClientSession() as s:
                    for chunk in chunk_list(friend_ids_list, 100):
                        json_ = await safe_json(s, "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
                                                params={"key": STEAM_API_KEY, "steamids": ",".join(chunk)})
                        if json_:
                            pls = json_.get("response", {}).get("players", []) or []
                            friends_summary.extend(pls)
                        await asyncio.sleep(0.08)
                # chunk into pages of 5
                pages = chunk_list(friends_summary, 5)
                return pages

            # groups pages builder
            async def build_groups_pages(steamid):
                groups = []
                async with aiohttp.ClientSession() as s:
                    html = await fetch_text(s, f"https://steamcommunity.com/profiles/{steamid}/groups/") or await fetch_text(s, f"https://steamcommunity.com/profiles/{steamid}") or await fetch_text(s, f"https://steamcommunity.com/id/{user}/groups/")
                if not html:
                    return []
                sp = BeautifulSoup(html, "html.parser")
                # first try groupBlock anchors
                for g in sp.select(".groupBlock a")[:200]:
                    if g.has_attr("href"):
                        groups.append({"name": g.get_text(" ", strip=True), "url": g["href"]})
                # fallback to any /groups/ anchors
                if not groups:
                    for a in sp.find_all("a", href=True):
                        if "/groups/" in a["href"]:
                            groups.append({"name": a.get_text(" ", strip=True), "url": a["href"]})
                return chunk_list(groups, 5)

            # screenshots builder
            async def fetch_screenshots(steamid):
                imgs = []
                async with aiohttp.ClientSession() as s:
                    html = await fetch_text(s, f"https://steamcommunity.com/profiles/{steamid}/screenshots/") or await fetch_text(s, f"https://steamcommunity.com/profiles/{steamid}") or await fetch_text(s, f"https://steamcommunity.com/id/{user}/screenshots/")
                if not html:
                    return imgs
                sp = BeautifulSoup(html, "html.parser")
                # common selectors for screenshots: profile_media_item img, screenshotItem, etc.
                for img in sp.select("img"):
                    src = img.get("src") or img.get("data-src")
                    if src and "cdn" in src:
                        imgs.append(src)
                # dedupe preserving order
                imgs = list(dict.fromkeys(imgs))
                return imgs

            # comments builder
            async def fetch_comments(steamid):
                parsed = []
                async with aiohttp.ClientSession() as s:
                    html = await fetch_text(s, f"https://steamcommunity.com/profiles/{steamid}") or await fetch_text(s, f"https://steamcommunity.com/id/{steamid}")
                if not html:
                    return parsed
                sp = BeautifulSoup(html, "html.parser")
                nodes = sp.select(".commentthread_comment") or sp.select(".profile_comment") or []
                for cn in nodes[:12]:
                    try:
                        a = cn.select_one(".commentthread_author_link") or cn.select_one("a")
                        author_name = a.get_text(" ", strip=True) if a else "Unknown"
                        author_link = a["href"] if a and a.has_attr("href") else None
                        av = cn.find("img")
                        avatar_url = av["src"] if av and av.has_attr("src") else None
                        text_el = cn.select_one(".commentthread_comment_text") or cn.find("div", class_=lambda c: c and "comment" in c)
                        comment_text = text_el.get_text(" ", strip=True) if text_el else ""
                        parsed.append({"author": author_name, "link": author_link, "avatar": avatar_url, "text": comment_text})
                    except Exception:
                        continue
                # fallback to comments page
                if not parsed:
                    html2 = await fetch_text(aiohttp.ClientSession(), f"https://steamcommunity.com/profiles/{steamid}/comments/") or None
                    # skipping fallback complexity; if none parsed, return []
                return parsed

            # dropdown callback (this will be called when someone selects)
            async def select_callback(sel_inter: discord.Interaction):
                val = sel_inter.data["values"][0]
                state["last_choice"] = val
                state["current_page_idx"] = 0

                # We'll edit the same message (sel_inter.message) to show results and keep the same view (with return-to-details)
                target_msg = sel_inter.message

                # TOP GAMES (just use top_games list prepared earlier)
                if val == "top_games":
                    # top games already sorted by playtime desc previously in profile; use that paginated
                    pages = chunk_list(sorted(owned_games, key=lambda g: g.get("playtime_forever", 0), reverse=True), 5)
                    if not pages:
                        await sel_inter.response.edit_message(content="No top games available.", embed=None, view=details_view)
                        return
                    state["games_pages"] = pages
                    # create embed for page 0
                    page_embed = discord.Embed(title=f"🏆 Top / Most Played Games — page 1/{len(pages)}", color=discord.Color.gold())
                    for i, g in enumerate(pages[0], start=1):
                        name = g.get("name", "Unknown")
                        appid = g.get("appid")
                        url = f"https://store.steampowered.com/app/{appid}" if appid else None
                        page_embed.add_field(name=f"{i}. [{name}]({url})" if url else f"{i}. {name}", value=f"🕒 {g.get('playtime_forever', 0)//60}h", inline=False)

                    # add pagination controls
                    pager_view = discord.ui.View(timeout=1800)
                    prev_b = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
                    page_btn = discord.ui.Button(label=f"Page 1/{len(pages)}", style=discord.ButtonStyle.secondary, disabled=True)
                    next_b = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)

                    async def prev_page(i):
                        state["current_page_idx"] = (state["current_page_idx"] - 1) % len(pages)
                        idx = state["current_page_idx"]
                        new_embed = discord.Embed(title=f"🏆 Top / Most Played Games — page {idx+1}/{len(pages)}", color=discord.Color.gold())
                        for ii, gg in enumerate(pages[idx], start=1):
                            name = gg.get("name", "Unknown")
                            appid = gg.get("appid")
                            url = f"https://store.steampowered.com/app/{appid}" if appid else None
                            new_embed.add_field(name=f"{ii}. [{name}]({url})" if url else f"{ii}. {name}", value=f"🕒 {gg.get('playtime_forever', 0)//60}h", inline=False)
                        page_btn.label = f"Page {idx+1}/{len(pages)}"
                        try:
                            await i.response.edit_message(embed=new_embed, view=pager_view)
                        except Exception:
                            await i.response.send_message(embed=new_embed, ephemeral=True)

                    async def next_page(i):
                        state["current_page_idx"] = (state["current_page_idx"] + 1) % len(pages)
                        idx = state["current_page_idx"]
                        new_embed = discord.Embed(title=f"🏆 Top / Most Played Games — page {idx+1}/{len(pages)}", color=discord.Color.gold())
                        for ii, gg in enumerate(pages[idx], start=1):
                            name = gg.get("name", "Unknown")
                            appid = gg.get("appid")
                            url = f"https://store.steampowered.com/app/{appid}" if appid else None
                            new_embed.add_field(name=f"{ii}. [{name}]({url})" if url else f"{ii}. {name}", value=f"🕒 {gg.get('playtime_forever', 0)//60}h", inline=False)
                        page_btn.label = f"Page {idx+1}/{len(pages)}"
                        try:
                            await i.response.edit_message(embed=new_embed, view=pager_view)
                        except Exception:
                            await i.response.send_message(embed=new_embed, ephemeral=True)

                    prev_b.callback = prev_page
                    next_b.callback = next_page
                    pager_view.add_item(prev_b)
                    pager_view.add_item(page_btn)
                    pager_view.add_item(next_b)

                    try:
                        await sel_inter.response.edit_message(embed=page_embed, view=pager_view, content=None)
                    except Exception:
                        await sel_inter.followup.send(embed=page_embed, view=pager_view, ephemeral=True)
                    return

                # ALL GAMES A-Z
                if val == "all_games":
                    pages = prepare_game_pages(owned_games)
                    if not pages:
                        await sel_inter.response.edit_message(content="No games available.", embed=None, view=details_view)
                        return
                    state["games_pages"] = pages
                    idx = 0
                    e = discord.Embed(title=f"🎮 All Games (A → Z) — page 1/{len(pages)}", color=discord.Color.blurple())
                    for i, g in enumerate(pages[0], start=1):
                        if g["url"]:
                            e.add_field(name=f"{i}. [{g['name']}]({g['url']})", value="\u200b", inline=False)
                        else:
                            e.add_field(name=f"{i}. {g['name']}", value="\u200b", inline=False)

                    pager_view = discord.ui.View(timeout=1800)
                    prev_b = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
                    page_btn = discord.ui.Button(label=f"Page 1/{len(pages)}", style=discord.ButtonStyle.secondary, disabled=True)
                    next_b = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)

                    async def prev_all(i):
                        state["current_page_idx"] = (state["current_page_idx"] - 1) % len(pages)
                        idx = state["current_page_idx"]
                        new_e = discord.Embed(title=f"🎮 All Games (A → Z) — page {idx+1}/{len(pages)}", color=discord.Color.blurple())
                        for ii, gg in enumerate(pages[idx], start=1):
                            if gg["url"]:
                                new_e.add_field(name=f"{ii}. [{gg['name']}]({gg['url']})", value="\u200b", inline=False)
                            else:
                                new_e.add_field(name=f"{ii}. {gg['name']}", value="\u200b", inline=False)
                        page_btn.label = f"Page {idx+1}/{len(pages)}"
                        try:
                            await i.response.edit_message(embed=new_e, view=pager_view)
                        except Exception:
                            await i.response.send_message(embed=new_e, ephemeral=True)

                    async def next_all(i):
                        state["current_page_idx"] = (state["current_page_idx"] + 1) % len(pages)
                        idx = state["current_page_idx"]
                        new_e = discord.Embed(title=f"🎮 All Games (A → Z) — page {idx+1}/{len(pages)}", color=discord.Color.blurple())
                        for ii, gg in enumerate(pages[idx], start=1):
                            if gg["url"]:
                                new_e.add_field(name=f"{ii}. [{gg['name']}]({gg['url']})", value="\u200b", inline=False)
                            else:
                                new_e.add_field(name=f"{ii}. {gg['name']}", value="\u200b", inline=False)
                        page_btn.label = f"Page {idx+1}/{len(pages)}"
                        try:
                            await i.response.edit_message(embed=new_e, view=pager_view)
                        except Exception:
                            await i.response.send_message(embed=new_e, ephemeral=True)

                    prev_b.callback = prev_all
                    next_b.callback = next_all
                    pager_view.add_item(prev_b)
                    pager_view.add_item(page_btn)
                    pager_view.add_item(next_b)

                    try:
                        await sel_inter.response.edit_message(embed=e, view=pager_view, content=None)
                    except Exception:
                        await sel_inter.followup.send(embed=e, view=pager_view, ephemeral=True)
                    return

                # FRIENDS (5 per page, each friend is a separate embed with set_author)
                if val == "friends":
                    # prepare pages (async)
                    pages = await build_friends_pages(friend_ids)
                    if not pages:
                        await sel_inter.response.edit_message(content="No friends visible or profile is private.", embed=None, view=details_view)
                        return
                    state["friends_pages"] = pages
                    idx = 0

                    # build embeds list (one embed per friend on the page)
                    embeds = []
                    for fr in pages[idx]:
                        e = discord.Embed(color=discord.Color.green())
                        name = fr.get("personaname", "Unknown")
                        purl = fr.get("profileurl")
                        avatar = fr.get("avatar") or fr.get("avatarfull")
                        # show as embed author so avatar appears left
                        try:
                            e.set_author(name=name, url=purl, icon_url=avatar)
                        except Exception:
                            e.set_author(name=name, url=purl)
                        # additional details if desired:
                        e.description = f"SteamID: `{fr.get('steamid')}`\nStatus: { 'Online' if fr.get('personastate')==1 else 'Offline' }"
                        embeds.append(e)

                    # pagination view
                    pager_view = discord.ui.View(timeout=1800)
                    prev_b = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
                    page_btn = discord.ui.Button(label=f"Page 1/{len(pages)}", style=discord.ButtonStyle.secondary, disabled=True)
                    next_b = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)

                    async def prev_f(i):
                        state["current_page_idx"] = (state["current_page_idx"] - 1) % len(pages)
                        idx = state["current_page_idx"]
                        # rebuild embeds for this page
                        embeds = []
                        for fr in pages[idx]:
                            e = discord.Embed(color=discord.Color.green())
                            name = fr.get("personaname", "Unknown")
                            purl = fr.get("profileurl")
                            avatar = fr.get("avatar") or fr.get("avatarfull")
                            try:
                                e.set_author(name=name, url=purl, icon_url=avatar)
                            except Exception:
                                e.set_author(name=name, url=purl)
                            e.description = f"SteamID: `{fr.get('steamid')}`\nStatus: { 'Online' if fr.get('personastate')==1 else 'Offline' }"
                            embeds.append(e)
                        page_btn.label = f"Page {idx+1}/{len(pages)}"
                        # send as multiple embeds in same message (Discord allows up to 10 embeds)
                        try:
                            await i.response.edit_message(embeds=embeds, view=pager_view, content=None)
                        except Exception:
                            await i.response.send_message(embeds=embeds, ephemeral=True)

                    async def next_f(i):
                        state["current_page_idx"] = (state["current_page_idx"] + 1) % len(pages)
                        idx = state["current_page_idx"]
                        embeds = []
                        for fr in pages[idx]:
                            e = discord.Embed(color=discord.Color.green())
                            name = fr.get("personaname", "Unknown")
                            purl = fr.get("profileurl")
                            avatar = fr.get("avatar") or fr.get("avatarfull")
                            try:
                                e.set_author(name=name, url=purl, icon_url=avatar)
                            except Exception:
                                e.set_author(name=name, url=purl)
                            e.description = f"SteamID: `{fr.get('steamid')}`\nStatus: { 'Online' if fr.get('personastate')==1 else 'Offline' }"
                            embeds.append(e)
                        page_btn.label = f"Page {idx+1}/{len(pages)}"
                        try:
                            await i.response.edit_message(embeds=embeds, view=pager_view, content=None)
                        except Exception:
                            await i.response.send_message(embeds=embeds, ephemeral=True)

                    prev_b.callback = prev_f
                    next_b.callback = next_f
                    pager_view.add_item(prev_b)
                    pager_view.add_item(page_btn)
                    pager_view.add_item(next_b)

                    # send first page (multiple embeds)
                    try:
                        await sel_inter.response.edit_message(embeds=embeds, view=pager_view, content=None)
                    except Exception:
                        try:
                            await sel_inter.followup.send(embeds=embeds, view=pager_view, ephemeral=True)
                        except Exception:
                            pass
                    return

                # SCREENSHOTS
                if val == "screenshots":
                    imgs = await fetch_screenshots(steamid)
                    if not imgs:
                        await sel_inter.response.edit_message(content="No screenshots found or profile private.", embed=None, view=details_view)
                        return
                    pages = chunk_list(imgs, 1)  # 1 per page for clarity
                    idx = 0

                    def screenshot_embed(i):
                        e = discord.Embed(title=f"📷 Screenshot {i+1}/{len(pages)}", color=discord.Color.dark_gray())
                        e.set_image(url=pages[i][0])
                        return e

                    pager_view = discord.ui.View(timeout=1800)
                    prev_b = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
                    page_btn = discord.ui.Button(label=f"Page 1/{len(pages)}", style=discord.ButtonStyle.secondary, disabled=True)
                    next_b = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)

                    async def prev_s(i):
                        state["current_page_idx"] = (state["current_page_idx"] - 1) % len(pages)
                        idx = state["current_page_idx"]
                        page_btn.label = f"Page {idx+1}/{len(pages)}"
                        try:
                            await i.response.edit_message(embed=screenshot_embed(idx), view=pager_view)
                        except Exception:
                            await i.response.send_message(embed=screenshot_embed(idx), ephemeral=True)

                    async def next_s(i):
                        state["current_page_idx"] = (state["current_page_idx"] + 1) % len(pages)
                        idx = state["current_page_idx"]
                        page_btn.label = f"Page {idx+1}/{len(pages)}"
                        try:
                            await i.response.edit_message(embed=screenshot_embed(idx), view=pager_view)
                        except Exception:
                            await i.response.send_message(embed=screenshot_embed(idx), ephemeral=True)

                    prev_b.callback = prev_s
                    next_b.callback = next_s
                    pager_view.add_item(prev_b)
                    pager_view.add_item(page_btn)
                    pager_view.add_item(next_b)

                    try:
                        await sel_inter.response.edit_message(embed=screenshot_embed(0), view=pager_view, content=None)
                    except Exception:
                        await sel_inter.followup.send(embed=screenshot_embed(0), view=pager_view, ephemeral=True)
                    return

                # VIDEOS
                if val == "videos":
                    async with aiohttp.ClientSession() as s:
                        html = await fetch_text(s, f"https://steamcommunity.com/profiles/{steamid}/videos/") or await fetch_text(s, f"https://steamcommunity.com/profiles/{steamid}") or await fetch_text(s, f"https://steamcommunity.com/id/{steamid}/videos/")
                    vids = []
                    if html:
                        sp = BeautifulSoup(html, "html.parser")
                        for a in sp.find_all("a", href=True):
                            href = a["href"]
                            if href and ("youtube.com" in href or "vimeo.com" in href or "/sharedfiles/" in href):
                                vids.append(href)
                    vids = list(dict.fromkeys(vids))
                    if not vids:
                        await sel_inter.response.edit_message(content="No videos found.", embed=None, view=details_view)
                        return
                    e = discord.Embed(title="📹 Videos", description="\n".join(f"[Video]({v})" for v in vids[:25]), color=discord.Color.dark_red())
                    try:
                        await sel_inter.response.edit_message(embed=e, view=None, content=None)
                    except Exception:
                        await sel_inter.followup.send(embed=e, ephemeral=True)
                    return

                # COMMENTS
                if val == "comments":
                    comments = await fetch_comments(steamid)
                    if not comments:
                        await sel_inter.response.edit_message(content="No comments found or profile private.", embed=None, view=details_view)
                        return
                    # build individual embeds for first 8 comments
                    c_embeds = []
                    for cm in comments[:8]:
                        e = discord.Embed(color=discord.Color.blurple())
                        try:
                            if cm["link"]:
                                e.set_author(name=cm["author"], url=cm["link"], icon_url=cm["avatar"])
                            else:
                                e.set_author(name=cm["author"], icon_url=cm["avatar"])
                        except Exception:
                            e.set_author(name=cm["author"])
                        txt = cm["text"] or "*No message*"
                        e.description = textwrap.fill(txt, width=900)
                        c_embeds.append(e)

                    # pagination controls for comments (prev/next)
                    idx = 0
                    c_view = discord.ui.View(timeout=1800)
                    prev_b = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
                    page_btn = discord.ui.Button(label=f"1/{len(c_embeds)}", style=discord.ButtonStyle.secondary, disabled=True)
                    next_b = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)

                    async def prev_c(i):
                        nonlocal idx
                        idx = (idx - 1) % len(c_embeds)
                        page_btn.label = f"{idx+1}/{len(c_embeds)}"
                        try:
                            await i.response.edit_message(embed=c_embeds[idx], view=c_view)
                        except Exception:
                            await i.response.send_message(embed=c_embeds[idx], ephemeral=True)

                    async def next_c(i):
                        nonlocal idx
                        idx = (idx + 1) % len(c_embeds)
                        page_btn.label = f"{idx+1}/{len(c_embeds)}"
                        try:
                            await i.response.edit_message(embed=c_embeds[idx], view=c_view)
                        except Exception:
                            await i.response.send_message(embed=c_embeds[idx], ephemeral=True)

                    prev_b.callback = prev_c
                    next_b.callback = next_c
                    c_view.add_item(prev_b); c_view.add_item(page_btn); c_view.add_item(next_b)

                    try:
                        await sel_inter.response.edit_message(embed=c_embeds[0], view=c_view, content=None)
                    except Exception:
                        await sel_inter.followup.send(embed=c_embeds[0], view=c_view, ephemeral=True)
                    return

                # GROUPS
                if val == "groups":
                    groups_pages = await build_groups_pages(steamid)
                    if not groups_pages:
                        await sel_inter.response.edit_message(content="No groups found or profile private.", embed=None, view=details_view)
                        return
                    state["groups_pages"] = groups_pages
                    idx = 0
                    def groups_embed(idx):
                        gpage = groups_pages[idx]
                        lines = []
                        for i, g in enumerate(gpage, start=1 + idx*5):
                            lines.append(f"**{i}. [{g['name']}]({g['url']})**")
                        e = discord.Embed(title=f"👪 Groups — page {idx+1}/{len(groups_pages)}", description="\n\n".join(lines), color=discord.Color.teal())
                        return e

                    pg_view = discord.ui.View(timeout=1800)
                    prev_b = discord.ui.Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
                    page_btn = discord.ui.Button(label=f"Page 1/{len(groups_pages)}", style=discord.ButtonStyle.secondary, disabled=True)
                    next_b = discord.ui.Button(label="Next ➡️", style=discord.ButtonStyle.secondary)

                    async def prev_g(i):
                        state["current_page_idx"] = (state["current_page_idx"] - 1) % len(groups_pages)
                        idx = state["current_page_idx"]
                        page_btn.label = f"Page {idx+1}/{len(groups_pages)}"
                        try:
                            await i.response.edit_message(embed=groups_embed(idx), view=pg_view)
                        except Exception:
                            await i.response.send_message(embed=groups_embed(idx), ephemeral=True)

                    async def next_g(i):
                        state["current_page_idx"] = (state["current_page_idx"] + 1) % len(groups_pages)
                        idx = state["current_page_idx"]
                        page_btn.label = f"Page {idx+1}/{len(groups_pages)}"
                        try:
                            await i.response.edit_message(embed=groups_embed(idx), view=pg_view)
                        except Exception:
                            await i.response.send_message(embed=groups_embed(idx), ephemeral=True)

                    prev_b.callback = prev_g
                    next_b.callback = next_g
                    pg_view.add_item(prev_b); pg_view.add_item(page_btn); pg_view.add_item(next_b)

                    try:
                        await sel_inter.response.edit_message(embed=groups_embed(0), view=pg_view, content=None)
                    except Exception:
                        await sel_inter.followup.send(embed=groups_embed(0), view=pg_view, ephemeral=True)
                    return

                # unknown fallback
                await sel_inter.response.edit_message(content="Unknown option.", embed=None, view=details_view)

            # attach select callback
            select.callback = select_callback

            # Return to profile button (edits message back to main profile embed)
            return_btn = discord.ui.Button(label="↩️ Return to Profile", style=discord.ButtonStyle.secondary)
            async def return_cb(bi: discord.Interaction):
                try:
                    await bi.response.edit_message(embed=embed, view=view, content=None)  # revert to profile embed & original view
                except Exception:
                    try:
                        await bi.response.send_message("Could not return to profile.", ephemeral=True)
                    except Exception:
                        pass
            return_btn.callback = return_cb

            details_view.add_item(select)
            details_view.add_item(return_btn)

            # edit the original message into the details panel (same message)
            try:
                await btn_inter.response.edit_message(embed=details_embed, view=details_view, content=None)
            except Exception:
                try:
                    await btn_inter.followup.send("Could not open details panel.", ephemeral=True)
                except Exception:
                    pass

        # Toggle visibility: only include if ephemeral mode (we set default ephemeral True)
        async def toggle_cb(btn_inter: discord.Interaction):
            try:
                # delete original message and re-send with flipped ephemeral
                try:
                    await btn_inter.message.delete()
                except Exception:
                    pass
                new_ephemeral = not getattr(view, "is_ephemeral", True)
                new_view = discord.ui.View(timeout=1800)
                new_view.is_ephemeral = new_ephemeral
                # re-add details button and toggle if ephemeral
                db = discord.ui.Button(label="ℹ️ Details", style=discord.ButtonStyle.secondary)
                db.callback = details_cb
                new_view.add_item(db)
                if new_ephemeral:
                    tb = discord.ui.Button(label="👁 Toggle Visibility", style=discord.ButtonStyle.danger)
                    tb.callback = toggle_cb
                    new_view.add_item(tb)
                # resend
                try:
                    await btn_inter.response.send_message(embed=embed, view=new_view, ephemeral=new_ephemeral)
                    view.is_ephemeral = new_ephemeral
                except Exception:
                    await btn_inter.followup.send("Could not toggle visibility.", ephemeral=True)
            except Exception:
                logger.exception("toggle failed")

        details_btn.callback = details_cb
        toggle_btn.callback = toggle_cb

        # add both buttons, toggle only shown if ephemeral is True
        view.add_item(details_btn)
        if view.is_ephemeral:
            view.add_item(toggle_btn)

        # finally send profile embed (ephemeral by default)
        try:
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception:
            try:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            except Exception:
                logger.exception("Failed to send profile embed")

    # ---------------- Games search (kept) ----------------
    @steam_group.command(name="game", description="Search Steam for a game")
    @app_commands.describe(game_name="Name of the game")
    async def game(self, interaction: discord.Interaction, game_name: str):
        await interaction.response.defer(ephemeral=True)
        search_url = f"https://store.steampowered.com/api/storesearch/?term={game_name}&l=en&cc=us"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(search_url) as resp:
                    if resp.status != 200:
                        return await interaction.followup.send(f"❌ Failed to search for '{game_name}'", ephemeral=True)
                    search_data = await resp.json()
            except Exception:
                return await interaction.followup.send("❌ Failed to search Steam.", ephemeral=True)

        items = search_data.get("items", [])
        if not items:
            return await interaction.followup.send(f"❌ No results found for '{game_name}'", ephemeral=True)

        top_items = items[:3]
        view = discord.ui.View(timeout=1800)

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

                result_view = discord.ui.View(timeout=1800)
                result_view.add_item(discord.ui.Button(label="View on Steam", url=f"https://store.steampowered.com/app/{appid}", style=discord.ButtonStyle.link))
                await button_inter.followup.send(embed=embed, view=result_view, ephemeral=True)

            button.callback = button_callback
            view.add_item(button)

        for it in top_items:
            await make_button(it)

        try:
            await interaction.followup.send(content=f"Select a game from the top {len(top_items)} results:", view=view, ephemeral=True)
        except Exception:
            await interaction.response.send_message(content=f"Select a game from the top {len(top_items)} results:", view=view, ephemeral=True)


# ---------------- Setup ----------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Steam(bot))
