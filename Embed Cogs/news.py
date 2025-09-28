import asyncio
import os
import time
import itertools
from datetime import datetime

import discord
from discord.ext import commands, tasks
from discord import app_commands

import aiohttp

# Try to import aiosqlite for database operations
try:
    import aiosqlite
    _AIOSQLITE_AVAILABLE = True
except ImportError:
    _AIOSQLITE_AVAILABLE = False
    aiosqlite = None

# Import database functions
import database
from helpers.command_logger import log_command


# ---------------------- Scraping ----------------------

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
]

async def fetch_tweets(username: str, limit: int = 5):
    """Fetch tweets using Nitter JSON (rotates through instances)."""
    username = username.replace("@", "").lower()
    for base in NITTER_INSTANCES:
        url = f"{base}/{username}/rss"  # RSS feed gives structured data
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        continue
                    text = await resp.text()
                    # Parse RSS manually (simple)
                    import re
                    items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
                    tweets = []
                    for item in items[:limit]:
                        guid = re.search(r"<guid.*?>(.*?)</guid>", item).group(1)
                        link = re.search(r"<link.*?>(.*?)</link>", item).group(1)
                        desc = re.search(r"<description>(.*?)</description>", item).group(1)
                        pubdate = re.search(r"<pubDate>(.*?)</pubDate>", item).group(1)

                        tweets.append({
                            "id": guid.split("/")[-1],
                            "url": link,
                            "text": discord.utils.escape_markdown(desc),
                            "date": datetime.strptime(pubdate, "%a, %d %b %Y %H:%M:%S %Z")
                        })
                    return tweets
        except Exception:
            continue
    return []


# ---------------------- Cog ----------------------

class NewsCog(commands.Cog):
    """Twitter monitoring cog with Nitter scraping and keyword filters."""

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

    # ---------------------- Commands ----------------------

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
        await interaction.followup.send(embed=embed)

    @news_group.command(name="status", description="Check bot status and scraping health")
    @log_command
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        status_lines = []

        # Database is always connected now via main database
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

        # Get counts from database functions
        accounts = await database.get_news_accounts()
        filters = await database.get_news_filters()
        status_lines.append(f"📊 Tracked Accounts: {len(accounts)}")
        status_lines.append(f"🔍 Active Filters: {len(filters)}")

        embed = discord.Embed(title="📰 News Cog Status", description="\n".join(status_lines), color=0x1DA1F2)
        await interaction.followup.send(embed=embed)

    # ---------------------- Background Tasks ----------------------

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
                    # Apply filters
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
