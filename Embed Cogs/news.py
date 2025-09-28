import asyncio
import importlib
import logging
import os
import time
from datetime import timezone
import itertools

import discord
from discord.ext import commands, tasks
from discord import app_commands

# Try to import snscrape for Twitter scraping
try:
    import snscrape.modules.twitter as sntwitter
    _SNSCRAPE_AVAILABLE = True
except ImportError:
    _SNSCRAPE_AVAILABLE = False
    sntwitter = None

# Try to import aiosqlite for database operations
try:
    import aiosqlite
    _AIOSQLITE_AVAILABLE = True
except ImportError:
    _AIOSQLITE_AVAILABLE = False
    aiosqlite = None


class NewsCog(commands.Cog):
    """Twitter monitoring cog with guild-only commands for better server control."""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = None
        self.db_path = os.path.join("data", "news_cog.db")
        
        # Create data directory if it doesn't exist
        os.makedirs("data", exist_ok=True)

    async def initialize(self):
        """Initialize the database and start background tasks."""
        if not _AIOSQLITE_AVAILABLE:
            print("❌ aiosqlite not available - news cog disabled")
            return

        try:
            self.db = await aiosqlite.connect(self.db_path)
            await self.db.execute('''
                CREATE TABLE IF NOT EXISTS accounts (
                    handle TEXT PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    last_tweet_id TEXT
                )
            ''')
            await self.db.execute('''
                CREATE TABLE IF NOT EXISTS filters (
                    word TEXT PRIMARY KEY
                )
            ''')
            await self.db.commit()
            print(f"✅ News cog database initialized at {self.db_path}")
            
            # Count accounts for status
            cur = await self.db.execute("SELECT COUNT(*) FROM accounts")
            count = (await cur.fetchone())[0]
            print(f"📊 News cog loaded with {count} tracked accounts")
            
            # Start background task
            if _SNSCRAPE_AVAILABLE:
                if not self.check_tweets.is_running():
                    self.check_tweets.start()
                    print("✅ News cog background tweet checking started")
            else:
                print("⚠️ snscrape not available - background checking disabled")
                
        except Exception as e:
            print(f"❌ Failed to initialize news cog: {e}")

    async def cog_load(self):
        """Called when the cog is loaded."""
        await self.initialize()

    async def cog_unload(self):
        """Called when the cog is unloaded."""
        if hasattr(self, 'check_tweets') and self.check_tweets.is_running():
            self.check_tweets.cancel()
        
        if self.db:
            try:
                asyncio.create_task(self.db.close())
            except Exception:
                pass

    # ---------------------- Commands ----------------------
    
    # Create guild-only command group
    news_group = app_commands.Group(name="news", description="Twitter monitoring commands (guild-only)")

    @news_group.command(name="add", description="Add Twitter account to monitor")
    @app_commands.guild_only()
    async def add_account(self, interaction: discord.Interaction, handle: str):
        """Add a Twitter account to monitor in this channel."""
        if not self.db:
            await interaction.response.send_message("❌ Database not available", ephemeral=True)
            return
        
        # Defer to prevent timeout
        await interaction.response.defer()
            
        handle = handle.replace('@', '').lower()
        try:
            await self.db.execute(
                "INSERT OR REPLACE INTO accounts (handle, channel_id) VALUES (?, ?)",
                (handle, interaction.channel.id)
            )
            await self.db.commit()
            embed = discord.Embed(
                title="✅ Account Added", 
                description=f"Now monitoring @{handle} in {interaction.channel.mention}", 
                color=0x00ff00
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error adding account: {e}")

    @news_group.command(name="remove", description="Remove Twitter account from monitoring")
    @app_commands.guild_only()
    async def remove_account(self, interaction: discord.Interaction, handle: str):
        """Remove a Twitter account from monitoring."""
        if not self.db:
            await interaction.response.send_message("❌ Database not available", ephemeral=True)
            return
        
        # Defer to prevent timeout
        await interaction.response.defer()
            
        handle = handle.replace('@', '').lower()
        try:
            result = await self.db.execute("DELETE FROM accounts WHERE handle = ?", (handle,))
            await self.db.commit()
            if result.rowcount > 0:
                await interaction.followup.send(f"🗑️ Stopped monitoring @{handle}")
            else:
                await interaction.followup.send(f"⚠️ @{handle} was not being monitored.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error removing account: {e}")

    @news_group.command(name="list", description="List all monitored Twitter accounts")
    @app_commands.guild_only()
    async def list_accounts(self, interaction: discord.Interaction):
        """List all monitored Twitter accounts."""
        if not self.db:
            await interaction.response.send_message("❌ Database not available", ephemeral=True)
            return
        
        # Defer to prevent timeout
        await interaction.response.defer()
            
        try:
            cur = await self.db.execute("SELECT handle, channel_id FROM accounts")
            accounts = await cur.fetchall()
            if accounts:
                account_list = "\\n".join([f"@{handle} → <#{channel_id}>" for handle, channel_id in accounts])
                embed = discord.Embed(title="📋 Monitored Accounts", description=account_list, color=0x1DA1F2)
            else:
                embed = discord.Embed(title="📋 Monitored Accounts", description="No accounts being monitored.", color=0xffaa00)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error listing accounts: {e}")

    @news_group.command(name="setchannel", description="Set output channel for ALL Twitter notifications in this server")
    @app_commands.guild_only()
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set the channel for notifications from ALL Twitter accounts in this server."""
        if not self.db:
            await interaction.response.send_message("❌ Database not available", ephemeral=True)
            return
        
        # Respond immediately to prevent timeout
        await interaction.response.defer()
            
        try:
            # Update all accounts to use the new channel
            result = await self.db.execute("UPDATE accounts SET channel_id = ?", (channel.id,))
            await self.db.commit()
            
            if result.rowcount > 0:
                await interaction.followup.send(f"✅ All {result.rowcount} monitored accounts will now send notifications to {channel.mention}")
            else:
                await interaction.followup.send("⚠️ No accounts are currently being monitored. Add some first with `/news add`")
        except Exception as e:
            await interaction.followup.send(f"❌ Error setting channel: {e}")

    @news_group.command(name="addfilter", description="Add keyword filter to suppress notifications")
    @app_commands.guild_only()
    async def add_filter(self, interaction: discord.Interaction, word: str):
        """Add a keyword filter to suppress notifications containing specific words."""
        if not self.db:
            await interaction.response.send_message("❌ Database not available", ephemeral=True)
            return
        
        # Defer to prevent timeout
        await interaction.response.defer()
            
        try:
            await self.db.execute("INSERT OR REPLACE INTO filters (word) VALUES (?)", (word.lower(),))
            await self.db.commit()
            await interaction.followup.send(f"🔍 Added filter: **{word}** (tweets containing this will be suppressed)")
        except Exception as e:
            await interaction.followup.send(f"❌ Error adding filter: {e}")

    @news_group.command(name="listfilters", description="List all active keyword filters")
    @app_commands.guild_only()
    async def list_filters(self, interaction: discord.Interaction):
        """List all active keyword filters."""
        if not self.db:
            await interaction.response.send_message("❌ Database not available", ephemeral=True)
            return
        
        # Defer to prevent timeout
        await interaction.response.defer()
            
        try:
            cur = await self.db.execute("SELECT word FROM filters ORDER BY word")
            filters = await cur.fetchall()
            if filters:
                filter_list = "\\n".join([f"• {word[0]}" for word in filters])
                embed = discord.Embed(title="🔍 Active Filters", description=filter_list, color=0x1DA1F2)
            else:
                embed = discord.Embed(title="🔍 Active Filters", description="No filters configured.", color=0xffaa00)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Error listing filters: {e}")

    @news_group.command(name="removefilter", description="Remove a keyword filter")
    @app_commands.guild_only()
    async def remove_filter(self, interaction: discord.Interaction, word: str):
        """Remove a keyword filter."""
        if not self.db:
            await interaction.response.send_message("❌ Database not available", ephemeral=True)
            return
        
        # Defer to prevent timeout
        await interaction.response.defer()
            
        try:
            result = await self.db.execute("DELETE FROM filters WHERE word = ?", (word.lower(),))
            await self.db.commit()
            if result.rowcount > 0:
                await interaction.followup.send(f"🗑️ Removed filter: **{word}**")
            else:
                await interaction.followup.send(f"⚠️ Filter **{word}** not found.")
        except Exception as e:
            await interaction.followup.send(f"❌ Error removing filter: {e}")

    @news_group.command(name="status", description="Check news cog health and Twitter API status")
    @app_commands.guild_only()
    async def status(self, interaction: discord.Interaction):
        """Check the status of the news cog and Twitter scraping."""
        await interaction.response.defer()  # This might take a moment
        
        status_lines = []
        
        # Database status
        if self.db:
            status_lines.append("✅ Database: Connected")
        else:
            status_lines.append("❌ Database: Disconnected")
        
        # Twitter scraping status
        if _SNSCRAPE_AVAILABLE:
            try:
                # Quick test with a well-known account
                scraper = sntwitter.TwitterUserScraper('nasa')
                test_tweets = list(itertools.islice(scraper.get_items(), 1))
                if test_tweets:
                    status_lines.append("✅ Twitter API: Working")
                else:
                    status_lines.append("⚠️ Twitter API: No tweets found (may be rate limited)")
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
            try:
                cur = await self.db.execute("SELECT COUNT(*) FROM accounts")
                count = (await cur.fetchone())[0]
                status_lines.append(f"📊 Tracked Accounts: {count}")
                
                # Filter count
                cur = await self.db.execute("SELECT COUNT(*) FROM filters")
                filter_count = (await cur.fetchone())[0]
                status_lines.append(f"🔍 Active Filters: {filter_count}")
            except Exception as e:
                status_lines.append(f"❌ Database query error: {e}")
        
        embed = discord.Embed(
            title="📰 News Cog Status",
            description="\\n".join(status_lines),
            color=0x1DA1F2
        )
        await interaction.followup.send(embed=embed)

    @news_group.command(name="test", description="Test Twitter scraping functionality")
    @app_commands.guild_only()
    async def test_scraping(self, interaction: discord.Interaction, handle: str = "nasa"):
        """Test Twitter scraping functionality with a specific handle."""
        if not _SNSCRAPE_AVAILABLE:
            await interaction.response.send_message("❌ snscrape is not available. Install it to enable Twitter scraping.", ephemeral=True)
            return
        
        await interaction.response.defer()  # This might take a moment
        
        try:
            handle = handle.replace('@', '').lower()
            scraper = sntwitter.TwitterUserScraper(handle)
            tweets = list(itertools.islice(scraper.get_items(), 3))
            
            if tweets:
                embed = discord.Embed(
                    title=f"🐦 Test Results: @{handle}",
                    description=f"Successfully found {len(tweets)} recent tweets",
                    color=0x1DA1F2
                )
                for i, tweet in enumerate(tweets[:2], 1):
                    content = tweet.content[:100] + "..." if len(tweet.content) > 100 else tweet.content
                    embed.add_field(
                        name=f"Tweet {i}",
                        value=f"{content}\\n[View Tweet](https://twitter.com/{handle}/status/{tweet.id})",
                        inline=False
                    )
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(f"⚠️ No tweets found for @{handle}. Account may not exist or be private.")
        
        except Exception as e:
            error_msg = str(e)[:200] + "..." if len(str(e)) > 200 else str(e)
            await interaction.followup.send(f"❌ Error testing @{handle}: {error_msg}")

    # ---------------------- Background Tasks ----------------------

    @tasks.loop(minutes=5)
    async def check_tweets(self):
        """Background task to check for new tweets from monitored accounts."""
        if not self.db or not _SNSCRAPE_AVAILABLE:
            return

        try:
            cur = await self.db.execute("SELECT handle, channel_id, last_tweet_id FROM accounts")
            accounts = await cur.fetchall()

            for handle, channel_id, last_tweet_id in accounts:
                try:
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        continue

                    scraper = sntwitter.TwitterUserScraper(handle)
                    tweets = list(itertools.islice(scraper.get_items(), 10))

                    if not tweets:
                        continue

                    # Find new tweets
                    new_tweets = []
                    for tweet in tweets:
                        if last_tweet_id and str(tweet.id) == last_tweet_id:
                            break
                        new_tweets.append(tweet)

                    # Process new tweets (newest first, but send oldest first)
                    new_tweets.reverse()
                    for tweet in new_tweets[-3:]:  # Limit to last 3 to avoid spam
                        # Check filters
                        should_filter = False
                        if self.db:
                            filter_cur = await self.db.execute("SELECT word FROM filters")
                            filters = await filter_cur.fetchall()
                            for filter_word, in filters:
                                if filter_word.lower() in tweet.content.lower():
                                    should_filter = True
                                    break

                        if not should_filter:
                            embed = discord.Embed(
                                title=f"🐦 New Tweet from @{handle}",
                                description=tweet.content,
                                color=0x1DA1F2,
                                url=f"https://twitter.com/{handle}/status/{tweet.id}",
                                timestamp=tweet.date
                            )
                            embed.set_footer(text="Twitter", icon_url="https://abs.twimg.com/icons/apple-touch-icon-192x192.png")
                            await channel.send(embed=embed)

                    # Update last tweet ID
                    if new_tweets:
                        await self.db.execute(
                            "UPDATE accounts SET last_tweet_id = ? WHERE handle = ?",
                            (str(tweets[0].id), handle)
                        )

                except Exception as e:
                    print(f"Error checking tweets for {handle}: {e}")

            await self.db.commit()

        except Exception as e:
            print(f"Error in check_tweets task: {e}")

    @check_tweets.before_loop
    async def before_check_tweets(self):
        """Wait for the bot to be ready before starting the loop."""
        await self.bot.wait_until_ready()


async def setup(bot):
    """Setup function to add the cog."""
    cog = NewsCog(bot)
    await bot.add_cog(cog)
    # The cog_load method will be called automatically, which calls initialize()
