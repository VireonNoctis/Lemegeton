import discord
from discord.ext import commands
from discord import app_commands
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import sqlite3
import asyncio
from datetime import datetime
import random

from database import DB_PATH, execute_db_operation

# ------------------------------------------------------
# Logging Setup - Clears on each bot run
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "invite_tracker.log"

# Clear the log file on startup (safe method)
try:
    if LOG_FILE.exists():
        LOG_FILE.unlink()
except PermissionError:
    # File is in use, just continue with existing file
    pass

# Create logger
logger = logging.getLogger("InviteTracker")
logger.setLevel(logging.INFO)

# Remove existing handlers to avoid duplicates
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Create file handler
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(file_handler)

logger.info("Invite Tracker cog logging initialized")

# ------------------------------------------------------
# Xianxia Themed Messages
# ------------------------------------------------------
XIANXIA_JOIN_MESSAGES = [
    "{joiner} has been recommended to the sect by {inviter} and is now a disciple of the sect.",
    "{joiner} has followed the dao of {inviter} and entered the sect as a new disciple.",
    "{joiner} was guided by Senior {inviter} and has joined the sect to cultivate.",
    "{joiner} has been brought into the sect by {inviter} to begin their cultivation journey.",
    "{joiner} answered the call of {inviter} and is now a disciple of our sect."
]

XIANXIA_LEAVE_MESSAGES = [
    "**{user}** left the sect. It seems their dao heart was shaken.",
    "**{user}** has departed from the sect. Their cultivation was insufficient.",
    "**{user}** abandoned the sect. Perhaps the path of cultivation was too arduous.",
    "**{user}** left the sect in search of their own dao. May they find enlightenment elsewhere.",
    "**{user}** has severed ties with the sect. Their heart demon proved too strong.",
    "**{user}** departed the sect. The heavenly tribulation of our community was too much.",
    "**{user}** left the sect to pursue a different cultivation method.",
    "**{user}** has gone into secluded cultivation... in another sect.",
]

RECRUITMENT_TITLES = [
    "has recruited",
    "has guided",
    "has brought",
    "has mentored",
    "has sponsored"
]


class InviteTracker(commands.Cog):
    """Track invites with Xianxia-themed join/leave messages"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invite_cache: Dict[int, List[discord.Invite]] = {}
        self.announcement_channels: Dict[int, int] = {}  # guild_id -> channel_id
        logger.info("Invite Tracker cog initialized")
    
    async def cog_load(self):
        """Load invite cache when cog loads"""
        # Load channel settings from database
        await self._load_channel_settings()
        
        if self.bot.is_ready():
            await self._cache_invites()
            logger.info("Invite Tracker cog loaded and invite cache initialized")
        else:
            # Will cache invites in on_ready event
            logger.info("Invite Tracker cog loaded, will cache invites when bot is ready")
    
    async def _cache_invites(self):
        """Cache all current invites for tracking"""
        self.invite_cache.clear()
        
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self.invite_cache[guild.id] = invites
                
                # Update database with current invites
                await self._update_invites_in_db(guild.id, invites)
                
                logger.info(f"Cached {len(invites)} invites for guild {guild.name}")
            except discord.Forbidden:
                logger.warning(f"Missing permissions to view invites in {guild.name}")
            except Exception as e:
                logger.error(f"Error caching invites for {guild.name}: {e}")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Cache invites when bot is ready if not already done"""
        if not self.invite_cache:
            await self._cache_invites()
    
    async def _load_channel_settings(self):
        """Load announcement channel settings from database"""
        try:
            settings = await execute_db_operation(
                "load channel settings",
                "SELECT guild_id, announcement_channel_id FROM invite_tracker_settings",
                fetch_type='all'
            )
            
            if settings:
                for guild_id, channel_id in settings:
                    self.announcement_channels[guild_id] = channel_id
                logger.info(f"Loaded announcement channel settings for {len(settings)} guilds")
            
        except Exception as e:
            logger.error(f"Error loading channel settings: {e}")
    
    async def _update_invites_in_db(self, guild_id: int, invites: List[discord.Invite]):
        """Update invite database with current invite data"""
        for invite in invites:
            try:
                await execute_db_operation(
                    "upsert invite",
                    """
                    INSERT OR REPLACE INTO invites 
                    (invite_code, guild_id, inviter_id, inviter_name, channel_id, max_uses, uses)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invite.code,
                        guild_id,
                        invite.inviter.id if invite.inviter else 0,
                        invite.inviter.display_name if invite.inviter else "Unknown",
                        invite.channel.id if invite.channel else None,
                        invite.max_uses or -1,
                        invite.uses or 0
                    )
                )
            except Exception as e:
                logger.error(f"Error updating invite {invite.code} in database: {e}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member join and track which invite was used"""
        if member.bot:
            return
        
        guild = member.guild
        logger.info(f"{member} joined {guild.name}")
        
        try:
            # Get current invites
            current_invites = await guild.invites()
            cached_invites = self.invite_cache.get(guild.id, [])
            
            # Find which invite was used
            used_invite = None
            inviter = None
            
            for current_invite in current_invites:
                # Find matching cached invite
                cached_invite = next(
                    (inv for inv in cached_invites if inv.code == current_invite.code),
                    None
                )
                
                if cached_invite and current_invite.uses > cached_invite.uses:
                    used_invite = current_invite
                    inviter = current_invite.inviter
                    break
            
            # Update cache
            self.invite_cache[guild.id] = current_invites
            
            if used_invite and inviter and inviter != member:
                await self._handle_invited_join(member, inviter, used_invite)
            else:
                await self._handle_unknown_join(member)
            
            await self._update_invites_in_db(guild.id, current_invites)
            
        except discord.Forbidden:
            logger.warning(f"Missing permissions to check invites in {guild.name}")
            await self._handle_unknown_join(member)
        except Exception as e:
            logger.error(f"Error handling member join for {member}: {e}")
            await self._handle_unknown_join(member)
    
    async def _handle_invited_join(self, member: discord.Member, inviter: discord.Member, invite: discord.Invite):
        """Handle when someone joins via a tracked invite"""
        guild = member.guild
        
        try:
            # Record the invite use in database
            await execute_db_operation(
                "record invite use",
                """
                INSERT INTO invite_uses 
                (guild_id, invite_code, inviter_id, inviter_name, joiner_id, joiner_name)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    guild.id,
                    invite.code,
                    inviter.id,
                    inviter.display_name,
                    member.id,
                    member.display_name
                )
            )
            
            # Update recruitment stats
            await execute_db_operation(
                "update recruitment stats",
                """
                INSERT OR REPLACE INTO recruitment_stats
                (user_id, guild_id, username, total_recruits)
                VALUES (?, ?, ?, COALESCE((
                    SELECT total_recruits + 1 FROM recruitment_stats 
                    WHERE user_id = ? AND guild_id = ?
                ), 1))
                """,
                (inviter.id, guild.id, inviter.display_name, inviter.id, guild.id)
            )
            
            # Get updated recruit count
            result = await execute_db_operation(
                "get recruit count",
                """
                SELECT total_recruits FROM recruitment_stats 
                WHERE user_id = ? AND guild_id = ?
                """,
                (inviter.id, guild.id),
                fetch_type='one'
            )
            
            recruit_count = result[0] if result else 1
            
        except Exception as e:
            logger.error(f"Error recording invite join for {member}: {e}")
            recruit_count = 1
        
        # Send themed join message
        message_template = random.choice(XIANXIA_JOIN_MESSAGES)
        recruitment_action = random.choice(RECRUITMENT_TITLES)
        
        join_message = f"{message_template.format(joiner=member.mention, inviter=inviter.display_name)}\n"
        join_message += f"{inviter.display_name} {recruitment_action} **{recruit_count}** disciples."
        
        # Find the configured announcement channel
        channel = await self._get_announcement_channel(guild)
        if channel:
            try:
                await channel.send(join_message)
                logger.info(f"Sent join message for {member} invited by {inviter} to #{channel.name}")
            except discord.Forbidden:
                logger.warning(f"Cannot send join message in {channel} - missing permissions")
            except Exception as e:
                logger.error(f"Error sending join message: {e}")
        else:
            logger.info(f"No announcement channel configured for {guild.name} - join message not sent. Use /set_invite_channel to configure.")  
        
        # Log the successful recruitment tracking
        logger.info(f"Tracked recruitment: {inviter.display_name} invited {member.display_name} (total recruits: {recruit_count})")
        
    async def _handle_unknown_join(self, member: discord.Member):
        """Handle when someone joins but we can't determine the inviter"""
        guild = member.guild
        
        # Still send a generic join message
        generic_messages = [
            f"{member.mention} has joined the sect through mysterious means.",
            f"{member.mention} has found their way to the sect. Welcome, new disciple!",
            f"{member.mention} has entered the sect. Their dao led them here.",
            f"{member.mention} has arrived at the sect to begin cultivation."
        ]
        
        join_message = random.choice(generic_messages)
        
        channel = await self._get_announcement_channel(guild)
        if channel:
            try:
                await channel.send(join_message)
                logger.info(f"Sent generic join message for {member} to #{channel.name}")
            except discord.Forbidden:
                logger.warning(f"Cannot send join message in {channel} - missing permissions")
            except Exception as e:
                logger.error(f"Error sending generic join message: {e}")
        else:
            logger.info(f"No announcement channel configured for {guild.name} - generic join message not sent. Use /set_invite_channel to configure.")
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member leave with themed message"""
        if member.bot:
            return
        
        guild = member.guild
        
        # Calculate days in server
        join_date = member.joined_at
        days_in_server = (datetime.utcnow() - join_date).days if join_date else 0
        
        try:
            # Check if they were invited by someone
            result = await execute_db_operation(
                "get inviter for leaving member",
                """
                SELECT inviter_id FROM invite_uses 
                WHERE guild_id = ? AND joiner_id = ? 
                ORDER BY joined_at DESC LIMIT 1
                """,
                (guild.id, member.id),
                fetch_type='one'
            )
            
            inviter_id = result[0] if result else None
            
            # Record the leave
            await execute_db_operation(
                "record member leave",
                """
                INSERT INTO user_leaves 
                (guild_id, user_id, username, was_invited_by, days_in_server)
                VALUES (?, ?, ?, ?, ?)
                """,
                (guild.id, member.id, member.display_name, inviter_id, days_in_server)
            )
            
        except Exception as e:
            logger.error(f"Error recording member leave for {member}: {e}")
        
        # Send themed leave message
        leave_message = random.choice(XIANXIA_LEAVE_MESSAGES).format(user=member.display_name)
        
        channel = await self._get_announcement_channel(guild)
        if channel:
            try:
                await channel.send(leave_message)
                logger.info(f"Sent leave message for {member} to #{channel.name}")
            except discord.Forbidden:
                logger.warning(f"Cannot send leave message in {channel} - missing permissions")
            except Exception as e:
                logger.error(f"Error sending leave message: {e}")
        else:
            logger.info(f"No announcement channel configured for {guild.name} - leave message not sent. Use /set_invite_channel to configure.")
    
    async def _get_announcement_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Get the configured announcement channel for invite messages"""
        # First priority: Check if a specific channel is configured for this guild
        if guild.id in self.announcement_channels:
            channel_id = self.announcement_channels[guild.id]
            configured_channel = guild.get_channel(channel_id)
            
            if configured_channel and isinstance(configured_channel, discord.TextChannel):
                permissions = configured_channel.permissions_for(guild.me)
                if permissions.send_messages:
                    logger.debug(f"Using configured announcement channel: {configured_channel.name}")
                    return configured_channel
                else:
                    logger.warning(f"No send permissions in configured channel {configured_channel.name} (ID: {channel_id})")
                    return None
            else:
                logger.warning(f"Configured channel {channel_id} not found or is not a text channel")
                return None
        
        # No configured channel - don't send messages to avoid spam
        logger.debug(f"No announcement channel configured for guild {guild.name}. Use /set_invite_channel to configure one.")
        return None
    
    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Update cache when new invite is created"""
        guild_invites = self.invite_cache.get(invite.guild.id, [])
        guild_invites.append(invite)
        self.invite_cache[invite.guild.id] = guild_invites
        
        # Update database
        await self._update_invites_in_db(invite.guild.id, [invite])
        logger.info(f"Cached new invite {invite.code} for {invite.guild.name}")
    
    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Update cache when invite is deleted"""
        guild_invites = self.invite_cache.get(invite.guild.id, [])
        self.invite_cache[invite.guild.id] = [inv for inv in guild_invites if inv.code != invite.code]
        logger.info(f"Removed deleted invite {invite.code} from cache")
    
    @app_commands.command(
        name="set_invite_channel",
        description="🔧 Set the channel for invite tracking messages (Admin only)"
    )
    @app_commands.describe(
        channel="The channel where invite join/leave messages will be sent"
    )
    @app_commands.default_permissions(administrator=True)
    async def set_invite_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """Set the announcement channel for invite tracking"""
        # Defer immediately to prevent timeout
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            logger.error(f"Interaction token expired for set_invite_channel command")
            return
        except Exception as e:
            logger.error(f"Failed to defer interaction for set_invite_channel: {e}")
            return
        
        guild_id = interaction.guild.id
        
        # Check if bot has permission to send messages in the channel
        permissions = channel.permissions_for(interaction.guild.me)
        if not permissions.send_messages:
            await interaction.followup.send(
                f"❌ I don't have permission to send messages in {channel.mention}.",
                ephemeral=True
            )
            return
        
        try:
            # Update database
            await execute_db_operation(
                "set invite channel",
                """
                INSERT OR REPLACE INTO invite_tracker_settings 
                (guild_id, announcement_channel_id, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                (guild_id, channel.id)
            )
            
            # Update cache
            self.announcement_channels[guild_id] = channel.id
            
            embed = discord.Embed(
                title="🔧 Invite Channel Configuration",
                description=f"✅ **Successfully configured invite tracking!**\n\nInvite tracking messages will now be sent to {channel.mention}",
                color=0x00FF00
            )
            
            embed.add_field(
                name="Channel Settings",
                value=f"```\nChannel: #{channel.name}\nChannel ID: {channel.id}\nPermissions: ✅ Send Messages\nStatus: ✅ Saved to Database```",
                inline=False
            )
            
            embed.add_field(
                name="What happens next?",
                value="• New members joining will trigger themed messages\n• Members leaving will trigger departure messages\n• All messages will only be sent to this channel",
                inline=False
            )
            
            embed.set_footer(text="Use /invite_channel_info to view current settings • Messages will only appear in the configured channel")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Set invite channel to #{channel.name} for guild {interaction.guild.name}")
            
        except Exception as e:
            logger.error(f"Error setting invite channel: {e}")
            try:
                await interaction.followup.send(
                    "❌ An error occurred while setting the invite channel.",
                    ephemeral=True
                )
            except:
                logger.error("Failed to send error message - interaction may have expired")
    
    @app_commands.command(
        name="invite_channel_info",
        description="ℹ️ View current invite tracking channel settings"
    )
    @app_commands.default_permissions(administrator=True)
    async def invite_channel_info(self, interaction: discord.Interaction):
        """View current invite channel configuration"""
        guild_id = interaction.guild.id
        
        embed = discord.Embed(
            title="ℹ️ Invite Tracking Channel Status",
            color=0x3498DB
        )
        
        if guild_id in self.announcement_channels:
            channel_id = self.announcement_channels[guild_id]
            channel = interaction.guild.get_channel(channel_id)
            
            if channel:
                permissions = channel.permissions_for(interaction.guild.me)
                permission_status = "✅ Working" if permissions.send_messages else "❌ No Permission"
                
                embed.description = f"✅ **Invite tracking is active!**\nMessages will be sent to {channel.mention}"
                embed.color = 0x00FF00
                
                embed.add_field(
                    name="Current Configuration",
                    value=f"```\nChannel: #{channel.name}\nChannel ID: {channel.id}\nBot Permissions: {permission_status}```",
                    inline=False
                )
                
                embed.add_field(
                    name="What gets tracked?",
                    value="• Member joins (with inviter credit)\n• Member departures\n• Recruitment statistics",
                    inline=True
                )
            else:
                embed.description = "⚠️ **Configured channel is missing!**\nThe configured channel was deleted or is no longer accessible."
                embed.color = 0xFF6B35
                
                embed.add_field(
                    name="⚠️ Configuration Issue",
                    value=f"```\nConfigured Channel ID: {channel_id}\nStatus: Channel not found or deleted```",
                    inline=False
                )
                
                embed.add_field(
                    name="Action Required",
                    value="Use `/set_invite_channel` to configure a new channel",
                    inline=False
                )
        else:
            embed.description = "❌ **No invite tracking channel configured**\nInvite messages are currently disabled."
            embed.color = 0xE74C3C
            
            embed.add_field(
                name="Current Status",
                value="```\nChannel: Not configured\nMessages: Disabled\nTracking: Data only (no notifications)```",
                inline=False
            )
            
            embed.add_field(
                name="To Enable Messages",
                value="Use `/set_invite_channel` to configure a channel for invite notifications",
                inline=False
            )
        
        embed.set_footer(text="Invite data is always tracked regardless of channel configuration")
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(
        name="recruitment_stats",
        description="🏮 Check recruitment statistics for the sect"
    )
    @app_commands.describe(
        user="Check specific user's recruitment stats (leave empty for top recruiters)"
    )
    @app_commands.default_permissions(administrator=True)
    async def recruitment_stats(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None
    ):
        """Check recruitment statistics"""
        # Defer immediately to prevent timeout
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            logger.error(f"Interaction token expired for recruitment_stats command")
            return
        except Exception as e:
            logger.error(f"Failed to defer interaction for recruitment_stats: {e}")
            return
            
        guild_id = interaction.guild.id
        
        try:
            if user:
                # Get specific user stats
                result = await execute_db_operation(
                    "get user recruitment stats",
                    """
                    SELECT total_recruits FROM recruitment_stats 
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (user.id, guild_id),
                    fetch_type='one'
                )
                
                recruit_count = result[0] if result else 0
                
                embed = discord.Embed(
                    title="🏮 Individual Recruitment Stats",
                    description=f"**{user.display_name}** has recruited **{recruit_count}** disciples to the sect.",
                    color=0xFFD700
                )
                
                # Get recent recruits
                recent_recruits = await execute_db_operation(
                    "get recent recruits",
                    """
                    SELECT joiner_name, joined_at FROM invite_uses 
                    WHERE inviter_id = ? AND guild_id = ? 
                    ORDER BY joined_at DESC LIMIT 5
                    """,
                    (user.id, guild_id),
                    fetch_type='all'
                )
                
                if recent_recruits:
                    recent_list = []
                    for name, joined_at in recent_recruits:
                        # Convert timestamp to relative time
                        joined_date = datetime.fromisoformat(joined_at)
                        days_ago = (datetime.now() - joined_date).days
                        time_str = f"{days_ago} days ago" if days_ago > 0 else "Today"
                        recent_list.append(f"• {name} ({time_str})")
                    
                    embed.add_field(
                        name="Recent Recruits",
                        value="\n".join(recent_list),
                        inline=False
                    )
            
            else:
                # Get top recruiters
                top_recruiters = await execute_db_operation(
                    "get top recruiters",
                    """
                    SELECT username, total_recruits FROM recruitment_stats 
                    WHERE guild_id = ? 
                    ORDER BY total_recruits DESC LIMIT 10
                    """,
                    (guild_id,),
                    fetch_type='all'
                )
                
                embed = discord.Embed(
                    title="🏮 Sect Recruitment Leaderboard",
                    description="*Top disciples who have brought others to the sect*",
                    color=0xFFD700
                )
                
                if top_recruiters:
                    leaderboard = []
                    for i, (username, count) in enumerate(top_recruiters, 1):
                        if i == 1:
                            emoji = "🥇"
                        elif i == 2:
                            emoji = "🥈"
                        elif i == 3:
                            emoji = "🥉"
                        else:
                            emoji = f"{i}."
                        
                        leaderboard.append(f"{emoji} **{username}** - {count} disciples")
                    
                    embed.add_field(
                        name="Top Recruiters",
                        value="\n".join(leaderboard),
                        inline=False
                    )
                else:
                    embed.description = "No recruitment data available yet."
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in recruitment_stats command: {e}")
            try:
                await interaction.followup.send("An error occurred while retrieving recruitment statistics.", ephemeral=True)
            except:
                logger.error("Failed to send error message - interaction may have expired")
    
    @app_commands.command(
        name="sect_analytics",
        description="📊 View detailed sect analytics and statistics"
    )
    @app_commands.default_permissions(administrator=True)
    async def sect_analytics(self, interaction: discord.Interaction):
        """View detailed analytics about the sect"""
        # Defer immediately to prevent timeout
        try:
            await interaction.response.defer()
        except discord.errors.NotFound:
            logger.error(f"Interaction token expired for sect_analytics command")
            return
        except Exception as e:
            logger.error(f"Failed to defer interaction for sect_analytics: {e}")
            return
            
        guild_id = interaction.guild.id
        
        try:
            # Total recruits
            result = await execute_db_operation(
                "get total recruited count",
                "SELECT COUNT(*) FROM invite_uses WHERE guild_id = ?",
                (guild_id,),
                fetch_type='one'
            )
            total_recruited = result[0] if result else 0
            
            # Total leaves
            result = await execute_db_operation(
                "get total leaves count",
                "SELECT COUNT(*) FROM user_leaves WHERE guild_id = ?",
                (guild_id,),
                fetch_type='one'
            )
            total_leaves = result[0] if result else 0
            
            # Average days in server for those who left
            result = await execute_db_operation(
                "get avg days before leaving",
                """
                SELECT AVG(days_in_server) FROM user_leaves 
                WHERE guild_id = ? AND days_in_server > 0
                """,
                (guild_id,),
                fetch_type='one'
            )
            avg_days = result[0] if result and result[0] else 0
            
            # Most active recruiter
            result = await execute_db_operation(
                "get top recruiter",
                """
                SELECT username, total_recruits FROM recruitment_stats 
                WHERE guild_id = ? ORDER BY total_recruits DESC LIMIT 1
                """,
                (guild_id,),
                fetch_type='one'
            )
            top_recruiter = result
            
            # Recent activity (last 7 days)
            result = await execute_db_operation(
                "get recent joins",
                """
                SELECT COUNT(*) FROM invite_uses 
                WHERE guild_id = ? AND joined_at >= datetime('now', '-7 days')
                """,
                (guild_id,),
                fetch_type='one'
            )
            recent_joins = result[0] if result else 0
            
            result = await execute_db_operation(
                "get recent leaves",
                """
                SELECT COUNT(*) FROM user_leaves 
                WHERE guild_id = ? AND left_at >= datetime('now', '-7 days')
                """,
                (guild_id,),
                fetch_type='one'
            )
            recent_leaves = result[0] if result else 0
            
        except Exception as e:
            logger.error(f"Error getting analytics data: {e}")
            await interaction.followup.send("An error occurred while retrieving analytics data.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="📊 Sect Analytics Dashboard",
            description="*Comprehensive statistics about our cultivation community*",
            color=0x9146FF
        )
        
        embed.add_field(
            name="🎯 Overall Statistics",
            value=f"```yaml\n"
                  f"Total Recruited: {total_recruited}\n"
                  f"Total Departures: {total_leaves}\n"
                  f"Retention Rate: {((total_recruited - total_leaves) / max(total_recruited, 1) * 100):.1f}%\n"
                  f"Avg Days Before Leaving: {avg_days:.1f}"
                  f"```",
            inline=False
        )
        
        embed.add_field(
            name="📈 Recent Activity (7 Days)",
            value=f"```css\n"
                  f"New Disciples: {recent_joins}\n"
                  f"Departures: {recent_leaves}\n"
                  f"Net Growth: {recent_joins - recent_leaves}"
                  f"```",
            inline=True
        )
        
        if top_recruiter:
            embed.add_field(
                name="🏆 Top Recruiter",
                value=f"```\n{top_recruiter[0]}\n{top_recruiter[1]} disciples```",
                inline=True
            )
        
        embed.set_footer(text="Use /recruitment_stats for detailed recruitment information")
        
        await interaction.followup.send(embed=embed)
    
    async def cog_unload(self):
        """Clean up when cog is unloaded"""
        logger.info("Invite Tracker cog unloaded")


async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTracker(bot))