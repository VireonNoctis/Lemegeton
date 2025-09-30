import asyncio
import os
import time
import re
import html
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp

try:
    import aiosqlite
    _AIOSQLITE_AVAILABLE = True
except ImportError:
    _AIOSQLITE_AVAILABLE = False
    aiosqlite = None

import database
from helpers.command_logger import log_command


# ---------------------- Scraper Config ----------------------

STATIC_NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
]

JINA_READER_PREFIX = "https://r.jina.ai/http://"
NITTER_STATUS_URL = "https://status.d420.de/"
MXTTR_PREFIX = "https://nitter.mxttr.it/"

_dead_instances: Dict[str, datetime] = {}


# ---------------------- Scraper Utils ----------------------

def _clean_text(s: str) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<.*?>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return discord.utils.escape_markdown(s)

def _parse_rfc2822_date(datestr: str) -> Optional[datetime]:
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(datestr)
    except Exception:
        try:
            return datetime.strptime(datestr, "%a, %d %b %Y %H:%M:%S %Z")
        except Exception:
            return None

async def fetch_live_nitter_instances(session: aiohttp.ClientSession, limit: int = 30) -> List[str]:
    candidates = list(STATIC_NITTER_INSTANCES)
    try:
        async with session.get(NITTER_STATUS_URL, timeout=8) as resp:
            if resp.status == 200:
                text = await resp.text()
                found = re.findall(r"https?://[a-z0-9.-]*nitter[^\s'\"<>]+", text, re.I)
                for f in found:
                    f_norm = f.rstrip("/")
                    if f_norm not in candidates:
                        candidates.append(f_norm)
    except Exception:
        pass

    try:
        gist_url = "https://gist.githubusercontent.com/cmj/7dace466c983e07d4e3b13be4b786c29/raw"
        async with session.get(gist_url, timeout=8) as resp2:
            if resp2.status == 200:
                txt = await resp2.text()
                found = re.findall(r"https?://[^\s'\"<>]+", txt)
                for f in found:
                    if "nitter" in f and f.rstrip("/") not in candidates:
                        candidates.append(f.rstrip("/"))
    except Exception:
        pass

    unique = []
    for c in candidates:
        if c not in unique:
            unique.append(c)
        if len(unique) >= limit:
            break
    return unique


# ---------------------- Scraper Methods ----------------------

async def _fetch_nitter_rss_instance(session: aiohttp.ClientSession, base: str, username: str, limit: int = 5) -> List[Dict]:
    if base in _dead_instances and _dead_instances[base] > datetime.utcnow():
        return []
    url = f"{base.rstrip('/')}/{username}/rss"
    tweets = []
    try:
        async with session.get(url, timeout=10) as resp:
            if resp.status != 200:
                _dead_instances[base] = datetime.utcnow() + timedelta(minutes=10)
                return []
            text = await resp.text()
            import xml.etree.ElementTree as ET
            try:
                root = ET.fromstring(text)
            except ET.ParseError:
                _dead_instances[base] = datetime.utcnow() + timedelta(minutes=10)
                return []
            items = root.findall(".//item")
            for item in items[:limit]:
                guid_el = item.find("guid")
                link_el = item.find("link")
                desc_el = item.find("description")
                pub_el = item.find("pubDate")

                guid = guid_el.text if guid_el is not None else ""
                link = link_el.text if link_el is not None else ""
                desc = desc_el.text if desc_el is not None else ""
                pub = pub_el.text if pub_el is not None else ""

                tid_match = re.search(r"/status/(\d+)$", guid) or re.search(r"/([^/]+)$", guid)
                tid = tid_match.group(1) if tid_match else (guid.split("/")[-1] if guid else "")

                date_obj = _parse_rfc2822_date(pub) or datetime.utcnow()

                tweets.append({
                    "id": tid,
                    "url": link,
                    "text": _clean_text(desc),
                    "date": date_obj
                })
    except Exception:
        _dead_instances[base] = datetime.utcnow() + timedelta(minutes=10)
        return []
    return tweets

async def _fetch_with_nitter(username: str, limit: int = 5) -> List[Dict]:
    async with aiohttp.ClientSession() as session:
        instances = await fetch_live_nitter_instances(session)
        for inst in STATIC_NITTER_INSTANCES:
            if inst not in instances:
                instances.append(inst)
        for base in instances:
            try:
                tweets = await _fetch_nitter_rss_instance(session, base, username, limit)
                if tweets:
                    return tweets
            except Exception:
                continue
    return []

async def _fetch_with_jina(username: str, limit: int = 5) -> List[Dict]:
    url = f"{JINA_READER_PREFIX}twitter.com/{username}"
    tweets = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=12) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
                entries = []
                for m in re.finditer(r"https?://(?:www\.)?twitter\.com/[^/]+/status/(\d+)", text):
                    full = m.group(0)
                    tid = m.group(1)
                    entries.append((m.start(), full, tid))

                seen = set()
                ordered = []
                for pos, full, tid in entries:
                    if tid in seen:
                        continue
                    seen.add(tid)
                    ordered.append((pos, full, tid))

                for pos, full, tid in ordered[:limit]:
                    start = max(0, pos - 300)
                    snippet = text[start:pos + 400]
                    snippet = re.sub(r"https?://\S+", "", snippet)
                    snippet = _clean_text(snippet)
                    tweets.append({
                        "id": tid,
                        "url": full,
                        "text": snippet or f"Tweet {tid}",
                        "date": datetime.utcnow()
                    })
    except Exception:
        return []
    return tweets

async def _fetch_with_mxttr(username: str, limit: int = 5) -> List[Dict]:
    url = f"{MXTTR_PREFIX}{username}/rss"
    tweets = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=12) as resp:
                if resp.status != 200:
                    return []
                text = await resp.text()
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(text)
                except ET.ParseError:
                    return []
                items = root.findall(".//item")
                for item in items[:limit]:
                    link_el = item.find("link")
                    desc_el = item.find("description")
                    pub_el = item.find("pubDate")

                    link = link_el.text if link_el is not None else ""
                    desc = desc_el.text if desc_el is not None else ""
                    pub = pub_el.text if pub_el is not None else ""

                    tid_match = re.search(r"/status/(\d+)$", link)
                    tid = tid_match.group(1) if tid_match else link.split("/")[-1]

                    date_obj = _parse_rfc2822_date(pub) or datetime.utcnow()

                    tweets.append({
                        "id": tid,
                        "url": link,
                        "text": _clean_text(desc),
                        "date": date_obj
                    })
    except Exception:
        return []
    return tweets

async def fetch_tweets(username: str, limit: int = 5) -> List[Dict]:
    username = username.replace("@", "").lower()
    for fetcher in (_fetch_with_nitter, _fetch_with_jina, _fetch_with_mxttr):
        try:
            tweets = await fetcher(username, limit)
            if tweets:
                return tweets
        except Exception:
            continue
    return []


# ---------------------- Cog ----------------------

class NewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def initialize(self):
        if not _AIOSQLITE_AVAILABLE:
            print("❌ aiosqlite not available - news cog disabled")
            return
        try:
            print("✅ News cog initialized using main database")
            if not self.check_tweets.is_running():
                self.check_tweets.start()
                print("✅ Background tweet checking started")
        except Exception as e:
            print(f"❌ Failed to initialize news cog: {e}")

    async def cog_load(self):
        await self.initialize()

    async def cog_unload(self):
        if self.check_tweets.is_running():
            self.check_tweets.cancel()

    news_group = app_commands.Group(name="news", description="Twitter monitoring commands")

    @news_group.command(name="add", description="Add a Twitter account to monitor")
    @app_commands.describe(username="The Twitter @username you want to track (without @)")
    @log_command
    async def add_account(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        username = username.replace("@", "").lower()
        try:
            success = await database.add_news_account(username, interaction.channel.id)
            if success:
                embed = discord.Embed(
                    title="✅ Account Added",
                    description=f"Now monitoring [@{username}](https://twitter.com/{username}) in {interaction.channel.mention}",
                    color=0x00ff00
                )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(embed=discord.Embed(
                    title="❌ Error",
                    description="Failed to add account to database",
                    color=0xff0000
                ))
        except Exception as e:
            await interaction.followup.send(embed=discord.Embed(
                title="❌ Error",
                description=str(e),
                color=0xff0000
            ))

    @news_group.command(name="remove", description="Remove a monitored Twitter account")
    @app_commands.describe(username="The Twitter @username you want to stop tracking")
    @log_command
    async def remove_account(self, interaction: discord.Interaction, username: str):
        await interaction.response.defer()
        username = username.replace("@", "").lower()
        success = await database.remove_news_account(username)
        if success:
            embed = discord.Embed(
                title="🗑️ Account Removed",
                description=f"Stopped monitoring [@{username}](https://twitter.com/{username})",
                color=0xff5555
            )
        else:
            embed = discord.Embed(
                title="⚠️ Not Found",
                description=f"[@{username}](https://twitter.com/{username}) was not being monitored.",
                color=0xffaa00
            )
        await interaction.followup.send(embed=embed)

    @news_group.command(name="list", description="List all monitored accounts")
    @log_command
    async def list_accounts(self, interaction: discord.Interaction):
        await interaction.response.defer()
        accounts = await database.get_news_accounts()
        if accounts:
            desc = "\n".join(
                f"[ @{acc['handle']} ](https://twitter.com/{acc['handle']}) → <#{acc['channel_id']}>"
                for acc in accounts
            )
            embed = discord.Embed(title="📋 Monitored Accounts", description=desc, color=0x1DA1F2)
        else:
            embed = discord.Embed(title="📋 Monitored Accounts", description="No accounts are being monitored.", color=0xffaa00)
        await interaction.followup.send(embed=embed)

    @news_group.command(name="addfilter", description="Add a keyword filter")
    @app_commands.describe(keyword="Tweets containing this word will be suppressed")
    @log_command
    async def add_filter(self, interaction: discord.Interaction, keyword: str):
        await interaction.response.defer()
        success = await database.add_news_filter(keyword)
        if success:
            embed = discord.Embed(
                title="🔍 Filter Added",
                description=f"Tweets containing **{keyword}** will be suppressed.",
                color=0x00ff00
            )
        else:
            embed = discord.Embed(
                title="⚠️ Filter Already Exists",
                description=f"Filter for **{keyword}** already exists.",
                color=0xffaa00
            )
        await interaction.followup.send(embed=embed)

    @news_group.command(name="listfilters", description="List all keyword filters")
    @log_command
    async def list_filters(self, interaction: discord.Interaction):
        await interaction.response.defer()
        filters = await database.get_news_filters()
        if filters:
            desc = "\n".join([f"• {word}" for word in filters])
            embed = discord.Embed(title="🔍 Active Filters", description=desc, color=0x1DA1F2)
        else:
            embed = discord.Embed(title="🔍 Active Filters", description="No filters configured.", color=0xffaa00)
        await interaction.followup.send(embed=embed)

    @news_group.command(name="removefilter", description="Remove a keyword filter")
    @app_commands.describe(keyword="The word you want to remove from filters")
    @log_command
    async def remove_filter(self, interaction: discord.Interaction, keyword: str):
        await interaction.response.defer()
        success = await database.remove_news_filter(keyword)
        if success:
            embed = discord.Embed(title="🗑️ Filter Removed", description=f"Removed filter: **{keyword}**", color=0xff5555)
        else:
            embed = discord.Embed(title="⚠️ Not Found", description=f"Filter **{keyword}** not found.", color=0xffaa00)
        await interaction.followup.send(embed=embed)

    @news_group.command(name="status", description="Check bot status and scraping health")
    @log_command
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        status_lines = []
        status_lines.append("✅ Database: Connected (Main Database)")
        try:
            tweets = await fetch_tweets("nasa", 1)
            if tweets:
                status_lines.append("✅ Scraping: Working")
            else:
                status_lines.append("⚠️ Scraping: No tweets found")
        except Exception:
            status_lines.append("❌ Scraping: Error")

        if hasattr(self, 'check_tweets') and self.check_tweets.is_running():
            status_lines.append("✅ Background Task: Running")
            status_lines.append(f"📅 Next check: <t:{int(time.time()) + 300}:R>")
        else:
            status_lines.append("⚠️ Background Task: Not running")

        accounts = await database.get_news_accounts()
        filters = await database.get_news_filters()
        status_lines.append(f"📊 Tracked Accounts: {len(accounts)}")
        status_lines.append(f"🔍 Active Filters: {len(filters)}")

        embed = discord.Embed(title="📰 News Cog Status", description="\n".join(status_lines), color=0x1DA1F2)
        await interaction.followup.send(embed=embed)

    @tasks.loop(minutes=5)
    async def check_tweets(self):
        accounts = await database.get_news_accounts()
        if not accounts:
            return
        for account in accounts:
            handle = account['handle']
            channel_id = account['channel_id']
            last_tweet_id = account['last_tweet_id']
            try:
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue
                tweets = await fetch_tweets(handle, 5)
                if not tweets:
                    continue
                new_tweets = []
                for t in tweets:
                    tid = str(t["id"])
                    if last_tweet_id and tid == last_tweet_id:
                        break
                    new_tweets.append(t)
                new_tweets.reverse()
                for t in new_tweets[-3:]:
                    should_filter = False
                    filters = await database.get_news_filters()
                    for filter_word in filters:
                        if filter_word.lower() in t["text"].lower():
                            should_filter = True
                            break
                    if should_filter:
                        continue
                    await channel.send(f"🐦 [@{handle}](https://twitter.com/{handle}) has posted a new update:\n{t['url']}")
                if new_tweets:
                    await database.update_last_tweet_id(handle, str(tweets[0]["id"]))
            except Exception as e:
                print(f"Error checking tweets for {handle}: {e}")

    @check_tweets.before_loop
    async def before_check_tweets(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    cog = NewsCog(bot)
    await bot.add_cog(cog)
