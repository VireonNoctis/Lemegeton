import discord
from discord.ext import commands, tasks
import sqlite3
import asyncio
import os
try:
    import importlib
    sntwitter = importlib.import_module("snscrape.modules.twitter")
    _SNSCRAPE_AVAILABLE = True
except Exception:
    sntwitter = None
    _SNSCRAPE_AVAILABLE = False
import logging
from datetime import datetime, timezone
from helpers.command_logger import log_command
from helpers.logging_helper import get_logger

logger = get_logger("NewsCog")

# Store the news cog DB in the central `data/` folder at the repo root
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'news_cog.db')

# Ensure the data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

class NewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.conn = sqlite3.connect(DB_PATH)
        self.cursor = self.conn.cursor()
        self._setup_db()
        # Start background task only if snscrape is available
        if _SNSCRAPE_AVAILABLE:
            self.check_tweets.start()
        else:
            logger.warning("snscrape not available; NewsCog background task disabled. Install 'snscrape' to enable Twitter scraping.")

    def cog_unload(self):
        self.check_tweets.cancel()
        self.conn.close()

    def _setup_db(self):
        """Initialize database tables."""
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            handle TEXT UNIQUE,
            channel_id INTEGER,
            last_tweet_id TEXT
        )
        """)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT UNIQUE
        )
        """)
        self.conn.commit()

    # ---------------------- Commands ----------------------

    @commands.group(name="news", invoke_without_command=True)
    async def news_group(self, ctx):
        """Main news command group."""
        await ctx.send("Subcommands: add, remove, list, setchannel, addfilter, listfilters")

    @log_command
    @news_group.command(name="add")
    async def add_account(self, ctx, handle: str):
        """Follow a new Twitter account by handle."""
        try:
            self.cursor.execute("INSERT INTO accounts (handle, channel_id, last_tweet_id) VALUES (?, ?, ?)",
                                (handle, ctx.channel.id, None))
            self.conn.commit()
            await ctx.send(f"✅ Now following **{handle}** in {ctx.channel.mention}")
        except sqlite3.IntegrityError:
            await ctx.send("⚠️ This account is already being tracked.")

    @log_command
    @news_group.command(name="remove")
    async def remove_account(self, ctx, handle: str):
        """Unfollow a Twitter account."""
        self.cursor.execute("DELETE FROM accounts WHERE handle = ?", (handle,))
        self.conn.commit()
        await ctx.send(f"🗑️ Removed tracking for {handle}")

    @log_command
    @news_group.command(name="list")
    async def list_accounts(self, ctx):
        """List tracked Twitter accounts."""
        self.cursor.execute("SELECT handle, channel_id FROM accounts")
        rows = self.cursor.fetchall()
        if not rows:
            await ctx.send("No accounts are being tracked yet.")
            return

        msg = "\n".join([f"- **{handle}** → <#{channel_id}>" for handle, channel_id in rows])
        await ctx.send(f"Tracked accounts:\n{msg}")

    @log_command
    @news_group.command(name="setchannel")
    async def set_channel(self, ctx, handle: str, channel: discord.TextChannel):
        """Set output channel for a Twitter account."""
        self.cursor.execute("UPDATE accounts SET channel_id = ? WHERE handle = ?", (channel.id, handle))
        self.conn.commit()
        await ctx.send(f"📡 Output channel for {handle} set to {channel.mention}")

    @log_command
    @news_group.command(name="addfilter")
    async def add_filter(self, ctx, *, word: str):
        """Add a keyword filter (case-insensitive)."""
        try:
            self.cursor.execute("INSERT INTO filters (word) VALUES (?)", (word.lower(),))
            self.conn.commit()
            await ctx.send(f"🔎 Added filter word: **{word}**")
        except sqlite3.IntegrityError:
            await ctx.send("⚠️ This filter already exists.")

    @log_command
    @news_group.command(name="listfilters")
    async def list_filters(self, ctx):
        """List all filter words."""
        self.cursor.execute("SELECT word FROM filters")
        rows = [r[0] for r in self.cursor.fetchall()]
        if not rows:
            await ctx.send("No filters set.")
        else:
            await ctx.send("Active filters:\n" + ", ".join([f"`{w}`" for w in rows]))

    # ---------------------- Tweet Scraper ----------------------

    async def fetch_new_tweets(self, handle, last_id):
        """Fetch new tweets since last_id."""
        tweets = []
        try:
            scraper = sntwitter.TwitterUserScraper(handle)
            for tweet in scraper.get_items():
                if last_id and str(tweet.id) <= str(last_id):
                    break
                tweets.append(tweet)
            return tweets
        except Exception as e:
            logger.error(f"Error fetching tweets from {handle}: {e}")
            return []

    def passes_filters(self, text):
        """Check if tweet matches any keyword filter."""
        self.cursor.execute("SELECT word FROM filters")
        filters = [row[0] for row in self.cursor.fetchall()]
        return any(word.lower() in text.lower() for word in filters) if filters else True

    # ---------------------- Background Task ----------------------

    @tasks.loop(minutes=5)
    async def check_tweets(self):
        await self.bot.wait_until_ready()

        self.cursor.execute("SELECT id, handle, channel_id, last_tweet_id FROM accounts")
        accounts = self.cursor.fetchall()

        for acc_id, handle, channel_id, last_tweet_id in accounts:
            tweets = await self.fetch_new_tweets(handle, last_tweet_id)
            if not tweets:
                continue

            tweets.sort(key=lambda t: t.date)  # oldest → newest
            for tweet in tweets:
                if not self.passes_filters(tweet.content):
                    continue

                channel = self.bot.get_channel(channel_id)
                if channel:
                    ts = int(tweet.date.replace(tzinfo=timezone.utc).timestamp())
                    msg = f"**@{handle}** made a new post <t:{ts}:R>: https://x.com/{handle}/status/{tweet.id}"
                    await channel.send(msg)

                # Update last tweet id
                self.cursor.execute("UPDATE accounts SET last_tweet_id = ? WHERE id = ?", (str(tweet.id), acc_id))
                self.conn.commit()

    @check_tweets.before_loop
    async def before_check_tweets(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(NewsCog(bot))
