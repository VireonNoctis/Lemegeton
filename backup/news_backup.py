import asyncio
import importlib
import logging
import os
import time
from datetime import timezone

import discord
from discord.ext import commands, tasks
from discord import app_commands

import aiosqlite
import sqlite3  # for catching sqlite errors

try:
    sntwitter = importlib.import_module("snscrape.modules.twitter")
    _SNSCRAPE_AVAILABLE = True
except Exception:
    sntwitter = None
    _SNSCRAPE_AVAILABLE = False

logging.basicConfig(level=logging.INFO)

# Store the news cog DB in the central `data/` folder at the repo root
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "news_cog.db")

# Ensure the data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


class NewsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db: aiosqlite.Connection | None = None
        self.db_path = DB_PATH

    async def initialize(self):
        """Open DB and create tables. Called from setup() before adding cog."""
        try:
            self.db = await aiosqlite.connect(self.db_path)
            await self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    handle TEXT UNIQUE,
                    channel_id INTEGER,
                    last_tweet_id TEXT
                )
                """
            )
            await self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS filters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT UNIQUE
                )
                """
            )
            await self.db.commit()
            logging.info(f"News cog database initialized at {self.db_path}")
            
            # Test database connection
            cur = await self.db.execute("SELECT COUNT(*) FROM accounts")
            account_count = (await cur.fetchone())[0]
            logging.info(f"News cog loaded with {account_count} tracked accounts")
            
        except Exception as e:
            logging.exception(f"Failed to initialize news cog database: {e}")
            raise

        # Start background task only if snscrape is available
        if _SNSCRAPE_AVAILABLE:
            self.check_tweets.start()
            logging.info("News cog background tweet checking started")
        else:
            logging.warning(
                "snscrape not available; NewsCog background task disabled. Install 'snscrape' to enable Twitter scraping."
            )

    def cog_unload(self):
        # tasks.loop.cancel() is safe to call from sync cog_unload; close DB asynchronously
        try:
            if self.check_tweets.is_running():
                self.check_tweets.cancel()
        except Exception:
            pass

        if self.db:
            # schedule the close in the event loop to avoid blocking
            try:
                asyncio.create_task(self.db.close())
            except Exception:
                pass

    # ---------------------- Commands ----------------------
    
    # Create guild-only command group
    news_group = app_commands.Group(name="news", description="Twitter monitoring commands (guild-only)")

    @news_group.command(name="help", description="Show news command help")
    @app_commands.guild_only()
    async def news_help(self, interaction: discord.Interaction):
        """Show news command help."""
        embed = discord.Embed(
            title="🗞️ News Command Help",
            description="Track Twitter accounts and get notifications in Discord channels.",
            color=0x1DA1F2
        )
        embed.add_field(
            name="Account Management",
            value="`/news add <handle>` - Follow Twitter account\n`/news remove <handle>` - Unfollow account\n`/news list` - Show tracked accounts\n`/news setchannel <handle> <channel>` - Set output channel",
            inline=False
        )
        embed.add_field(
            name="Filters",
            value="`/news addfilter <word>` - Add keyword filter\n`/news removefilter <word>` - Remove keyword filter\n`/news listfilters` - Show active filters",
            inline=False
        )
        embed.add_field(
            name="System",
            value="`/news status` - Check cog health and status\n`/news test [handle]` - Test Twitter scraping (default: nasa)",
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    @news_group.command(name="add")
    async def add_account(self, ctx, handle: str):
        """Follow a new Twitter account by handle."""
        try:
            await self.db.execute(
                "INSERT INTO accounts (handle, channel_id, last_tweet_id) VALUES (?, ?, ?)", (handle, ctx.channel.id, None)
            )
            await self.db.commit()
            await ctx.send(f"✅ Now following **{handle}** in {ctx.channel.mention}")
        except sqlite3.IntegrityError:
            await ctx.send("⚠️ This account is already being tracked.")

    @news_group.command(name="remove")
    async def remove_account(self, ctx, handle: str):
        """Unfollow a Twitter account."""
        await self.db.execute("DELETE FROM accounts WHERE handle = ?", (handle,))
        await self.db.commit()
        await ctx.send(f"🗑️ Removed tracking for {handle}")

    @news_group.command(name="list")
    async def list_accounts(self, ctx):
        """List tracked Twitter accounts."""
        cur = await self.db.execute("SELECT handle, channel_id FROM accounts")
        rows = await cur.fetchall()
        if not rows:
            await ctx.send("No accounts are being tracked yet.")
            return

        msg = "\n".join([f"- **{handle}** → <#{channel_id}>" for handle, channel_id in rows])
        await ctx.send(f"Tracked accounts:\n{msg}")

    @news_group.command(name="setchannel")
    async def set_channel(self, ctx, handle: str, channel: discord.TextChannel):
        """Set output channel for a Twitter account."""
        await self.db.execute("UPDATE accounts SET channel_id = ? WHERE handle = ?", (channel.id, handle))
        await self.db.commit()
        await ctx.send(f"📡 Output channel for {handle} set to {channel.mention}")

    @news_group.command(name="addfilter")
    async def add_filter(self, ctx, *, word: str):
        """Add a keyword filter (case-insensitive)."""
        try:
            await self.db.execute("INSERT INTO filters (word) VALUES (?)", (word.lower(),))
            await self.db.commit()
            await ctx.send(f"🔎 Added filter word: **{word}**")
        except sqlite3.IntegrityError:
            await ctx.send("⚠️ This filter already exists.")

    @news_group.command(name="listfilters")
    async def list_filters(self, ctx):
        """List all filter words."""
        cur = await self.db.execute("SELECT word FROM filters")
        rows = [r[0] for r in await cur.fetchall()]
        if not rows:
            await ctx.send("No filters set.")
        else:
            await ctx.send("Active filters:\n" + ", ".join([f"`{w}`" for w in rows]))

    @news_group.command(name="status")
    async def status(self, ctx):
        """Check news cog status and health."""
        status_lines = []
        
        # Database status
        if self.db:
            status_lines.append("✅ Database: Connected")
        else:
            status_lines.append("❌ Database: Disconnected")
        
        # Scraping availability
        if _SNSCRAPE_AVAILABLE:
            status_lines.append("✅ Twitter Scraping: Available")
            # Test if Twitter is actually working
            try:
                test_tweets = await self.fetch_new_tweets("nasa", None)
                if test_tweets:
                    status_lines.append("✅ Twitter API: Working")
                else:
                    status_lines.append("⚠️ Twitter API: No tweets returned (may be blocked)")
            except Exception as e:
                if '404' in str(e).lower() or 'blocked' in str(e).lower():
                    status_lines.append("❌ Twitter API: Blocked (404 errors)")
                else:
                    status_lines.append(f"❌ Twitter API: Error ({str(e)[:50]}...)")
        else:
            status_lines.append("❌ Twitter Scraping: Unavailable (install snscrape)")
        
        # Background task status
        if hasattr(self, 'check_tweets'):
            if self.check_tweets.is_running():
                status_lines.append("✅ Background Task: Running")
                status_lines.append(f"📅 Next check: <t:{int(time.time()) + 300}:R>")
            else:
                status_lines.append("⚠️ Background Task: Stopped")
        else:
            status_lines.append("❌ Background Task: Not initialized")
        
        # Account count
        if self.db:
            cur = await self.db.execute("SELECT COUNT(*) FROM accounts")
            count = (await cur.fetchone())[0]
            status_lines.append(f"📊 Tracked Accounts: {count}")
            
            # Filter count
            cur = await self.db.execute("SELECT COUNT(*) FROM filters")
            filter_count = (await cur.fetchone())[0]
            status_lines.append(f"🔍 Active Filters: {filter_count}")
        
        embed = discord.Embed(
            title="📰 News Cog Status",
            description="\n".join(status_lines),
            color=0x1DA1F2
        )
        await ctx.send(embed=embed)

    @news_group.command(name="removefilter", description="Remove a keyword filter")
    @app_commands.guild_only()
    async def remove_filter(self, interaction: discord.Interaction, word: str):
        """Remove a keyword filter."""
        result = await self.db.execute("DELETE FROM filters WHERE word = ?", (word.lower(),))
        await self.db.commit()
        if result.rowcount > 0:
            await interaction.response.send_message(f"🗑️ Removed filter: **{word}**")
        else:
            await interaction.response.send_message(f"⚠️ Filter **{word}** not found.")

    @news_group.command(name="test")
    async def test_scraping(self, ctx, handle: str = "nasa"):
        """Test Twitter scraping functionality with a specific handle."""
        if not _SNSCRAPE_AVAILABLE:
            await ctx.send("❌ snscrape is not available. Install it to enable Twitter scraping.")
            return
        
        await ctx.send(f"🔍 Testing Twitter scraping for @{handle}...")
        
        try:
            tweets = await self.fetch_new_tweets(handle, None)
            if tweets:
                latest_tweet = tweets[0]
                embed = discord.Embed(
                    title=f"✅ Twitter Scraping Test Successful",
                    description=f"Found {len(tweets)} recent tweets from @{handle}",
                    color=0x1DA1F2
                )
                embed.add_field(
                    name="Latest Tweet Preview",
                    value=latest_tweet.content[:200] + ("..." if len(latest_tweet.content) > 200 else ""),
                    inline=False
                )
                embed.add_field(name="Tweet ID", value=str(latest_tweet.id), inline=True)
                embed.add_field(name="Date", value=latest_tweet.date.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"⚠️ No tweets found for @{handle}. This could mean:\n" +
                             "• Account doesn't exist or is private\n" +
                             "• Twitter is blocking scraping requests\n" +
                             "• Rate limiting is in effect")
        except Exception as e:
            await ctx.send(f"❌ Error testing Twitter scraping: {str(e)[:200]}")

    # ---------------------- Tweet Scraper ----------------------

    async def fetch_new_tweets(self, handle, last_id):
        """Fetch new tweets since last_id in a thread so we don't block the event loop."""
        if not _SNSCRAPE_AVAILABLE:
            return []

        def _fetch_sync(h, lid):
            out = []
            try:
                scraper = sntwitter.TwitterUserScraper(h)
                tweet_count = 0
                for tweet in scraper.get_items():
                    if lid and str(tweet.id) <= str(lid):
                        break
                    out.append(tweet)
                    tweet_count += 1
                    # Limit to 10 tweets per fetch to avoid overwhelming
                    if tweet_count >= 10:
                        break
                logging.info(f"Successfully fetched {len(out)} new tweets from @{h}")
            except Exception as e:
                error_msg = str(e).lower()
                if '404' in error_msg or 'blocked' in error_msg:
                    logging.warning(f"Twitter blocked scraping for @{h}: {e}")
                elif 'rate limit' in error_msg:
                    logging.warning(f"Rate limited while scraping @{h}, will retry later")
                else:
                    logging.error(f"Error fetching tweets from @{h}: {e}")
            return out

        tweets = await asyncio.to_thread(_fetch_sync, handle, last_id)
        return tweets

    async def passes_filters(self, text):
        """Check if tweet matches any keyword filter."""
        cur = await self.db.execute("SELECT word FROM filters")
        filters = [row[0] for row in await cur.fetchall()]
        return any(word.lower() in text.lower() for word in filters) if filters else True

    # ---------------------- Background Task ----------------------

    @tasks.loop(minutes=5)
    async def check_tweets(self):
        # the before_loop will wait for readiness; here we assume bot is ready
        cur = await self.db.execute("SELECT id, handle, channel_id, last_tweet_id FROM accounts")
        accounts = await cur.fetchall()
        
        if not accounts:
            return  # No accounts to check
        
        logging.info(f"Checking tweets for {len(accounts)} tracked accounts")
        
        for acc_id, handle, channel_id, last_tweet_id in accounts:
            try:
                tweets = await self.fetch_new_tweets(handle, last_tweet_id)
                if not tweets:
                    continue

                tweets.sort(key=lambda t: t.date)  # oldest → newest
                new_tweets_count = 0
                
                for tweet in tweets:
                    try:
                        if not await self.passes_filters(tweet.content):
                            continue

                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            ts = int(tweet.date.replace(tzinfo=timezone.utc).timestamp())
                            msg = f"**@{handle}** made a new post <t:{ts}:R>: https://x.com/{handle}/status/{tweet.id}"
                            try:
                                await channel.send(msg)
                                new_tweets_count += 1
                            except discord.Forbidden:
                                logging.error(f"No permission to send messages in channel {channel_id} for account {handle}")
                            except discord.NotFound:
                                logging.error(f"Channel {channel_id} not found for account {handle}")
                            except Exception as e:
                                logging.exception(f"Failed to send tweet message for {handle}: {e}")
                        else:
                            logging.warning(f"Channel {channel_id} not found for account {handle}")

                        # Update last tweet id after successful processing
                        await self.db.execute("UPDATE accounts SET last_tweet_id = ? WHERE id = ?", (str(tweet.id), acc_id))
                        await self.db.commit()
                    except Exception as e:
                        logging.error(f"Error processing tweet {tweet.id} from {handle}: {e}")
                        continue
                        
                if new_tweets_count > 0:
                    logging.info(f"Posted {new_tweets_count} new tweets from @{handle}")
                    
            except Exception as e:
                logging.error(f"Error checking tweets for account {handle} (ID: {acc_id}): {e}")
                continue

    @check_tweets.before_loop
    async def before_check_tweets(self):
        # Bound the wait for readiness to avoid RuntimeError in some startup sequences
        try:
            await asyncio.wait_for(self.bot.wait_until_ready(), timeout=60)
        except (asyncio.TimeoutError, RuntimeError):
            # Fallback to polling for a short period
            logging.warning("NewsCog.before_check_tweets: bot.wait_until_ready() timed out; falling back to polling for readiness")
            for _ in range(12):
                if self.bot.is_ready():
                    return
                await asyncio.sleep(5)


async def setup(bot):
    cog = NewsCog(bot)
    await cog.initialize()
    await bot.add_cog(cog)