"""
Bot Integration for Monitoring System
Integrates the monitoring system with the Discord bot for live metrics.
"""

import logging
import time
from datetime import datetime
from functools import wraps

# Import monitoring system
try:
    from monitoring_system import setup_monitoring, get_monitoring
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    logging.warning("Monitoring system not available - install psutil to enable monitoring")

def setup_bot_monitoring(bot):
    """Setup monitoring integration with the Discord bot"""
    if not MONITORING_AVAILABLE:
        logging.warning("⚠️ Monitoring system not available")
        return None
    
    try:
        monitoring = setup_monitoring(bot)
        logging.info("✅ Bot monitoring system initialized")
        
        # Add monitoring to bot events
        add_monitoring_events(bot, monitoring)
        
        return monitoring
    except Exception as e:
        logging.error(f"❌ Failed to setup bot monitoring: {e}")
        return None

def add_monitoring_events(bot, monitoring):
    """Add monitoring event handlers to the bot"""
    
    @bot.event
    async def on_ready():
        """Bot ready event with monitoring"""
        logging.info(f"🤖 Bot is ready! Logged in as {bot.user}")
        logging.info(f"📊 Monitoring {len(bot.guilds)} guilds with {sum(g.member_count for g in bot.guilds)} total users")
        
        # Log guild information for monitoring
        for guild in bot.guilds:
            monitoring.guild_activity[guild.id] = {
                'commands_24h': 0,
                'errors_24h': 0,
                'last_activity': datetime.utcnow()
            }
            logging.info(f"  📍 {guild.name} ({guild.id}): {guild.member_count} members")
    
    @bot.event
    async def on_guild_join(guild):
        """Track new guild joins"""
        logging.info(f"🎉 Bot joined new guild: {guild.name} ({guild.id}) with {guild.member_count} members")
        
        # Initialize guild in monitoring
        monitoring.guild_activity[guild.id] = {
            'commands_24h': 0,
            'errors_24h': 0,
            'last_activity': datetime.utcnow()
        }
    
    @bot.event
    async def on_guild_remove(guild):
        """Track guild removals"""
        logging.info(f"👋 Bot removed from guild: {guild.name} ({guild.id})")
        
        # Remove guild from monitoring
        if guild.id in monitoring.guild_activity:
            del monitoring.guild_activity[guild.id]
    
    @bot.event
    async def on_command_error(ctx, error):
        """Track command errors for monitoring"""
        guild_id = ctx.guild.id if ctx.guild else None
        command_name = ctx.command.name if ctx.command else "unknown"
        
        # Record error in monitoring
        monitoring.record_error(error, guild_id, command_name)
        
        # Log the error
        logging.error(f"🚨 Command error in {ctx.guild.name if ctx.guild else 'DM'}: {error}")

def monitor_command(func):
    """Decorator to monitor command usage and response times"""
    if not MONITORING_AVAILABLE:
        return func
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract interaction from arguments
        interaction = None
        for arg in args:
            if hasattr(arg, 'response') and hasattr(arg, 'guild'):
                interaction = arg
                break
        
        if not interaction:
            return await func(*args, **kwargs)
        
        start_time = time.time()
        guild_id = interaction.guild.id if interaction.guild else None
        command_name = getattr(interaction, 'command', {}).get('name', 'unknown')
        
        try:
            result = await func(*args, **kwargs)
            
            # Record successful command usage
            response_time = time.time() - start_time
            monitoring = get_monitoring()
            if monitoring:
                monitoring.record_command_usage(command_name, guild_id, response_time)
            
            return result
            
        except Exception as e:
            # Record command error
            monitoring = get_monitoring()
            if monitoring:
                monitoring.record_error(e, guild_id, command_name)
            raise
    
    return wrapper

# Monitoring Commands Cog Integration
class BotMonitoringCommands:
    """Monitoring commands integrated with the bot"""
    
    @staticmethod
    def add_monitoring_commands(bot):
        """Add monitoring slash commands to the bot"""
        if not MONITORING_AVAILABLE:
            return
        
        @bot.tree.command(name="health", description="Check bot health status (Admin only)")
        async def health_command(interaction):
            """Check bot health status"""
            # Check if user has administrator permissions
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True
                )
                return
            
            monitoring = get_monitoring()
            if not monitoring:
                await interaction.response.send_message(
                    "❌ Monitoring system not available",
                    ephemeral=True
                )
                return
            
            health = await monitoring.health_check()
            
            # Create health status embed
            import discord
            
            color = discord.Color.green() if health['status'] == 'healthy' else \
                   discord.Color.yellow() if health['status'] == 'degraded' else \
                   discord.Color.red()
            
            embed = discord.Embed(
                title=f"🏥 Bot Health: {health['status'].upper()}",
                color=color,
                timestamp=datetime.utcnow()
            )
            
            checks = health.get('checks', {})
            for check, status in checks.items():
                embed.add_field(
                    name=check.replace('_', ' ').title(),
                    value="✅ Pass" if status else "❌ Fail",
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        @bot.tree.command(name="bot-stats", description="Show bot statistics (Admin only)")
        async def stats_command(interaction):
            """Show bot metrics"""
            # Check if user has administrator permissions
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "❌ You need administrator permissions to use this command.",
                    ephemeral=True
                )
                return
            
            monitoring = get_monitoring()
            if not monitoring:
                await interaction.response.send_message(
                    "❌ Monitoring system not available",
                    ephemeral=True
                )
                return
            
            await interaction.response.defer(ephemeral=True)
            
            try:
                system_metrics = await monitoring.get_system_metrics()
                bot_metrics = await monitoring.get_bot_metrics()
                
                import discord
                embed = discord.Embed(
                    title="📊 Bot Statistics",
                    color=discord.Color.blue(),
                    timestamp=datetime.utcnow()
                )
                
                # System metrics
                embed.add_field(
                    name="🖥️ System",
                    value=f"CPU: {system_metrics.cpu_percent}%\n"
                          f"RAM: {system_metrics.memory_percent}%\n"
                          f"Latency: {system_metrics.latency_ms}ms",
                    inline=True
                )
                
                # Bot metrics
                embed.add_field(
                    name="🤖 Bot Stats",
                    value=f"Guilds: {bot_metrics.guild_count}\n"
                          f"Users: {bot_metrics.total_users:,}\n"
                          f"Registered: {bot_metrics.total_registered_users}",
                    inline=True
                )
                
                # Activity metrics
                embed.add_field(
                    name="⚡ Activity",
                    value=f"Commands/hr: {bot_metrics.commands_per_hour}\n"
                          f"Errors/hr: {bot_metrics.errors_per_hour}\n"
                          f"Uptime: {system_metrics.uptime_hours:.1f}h",
                    inline=True
                )
                
                # Top commands
                if bot_metrics.top_commands:
                    top_cmds = list(bot_metrics.top_commands.items())[:5]
                    top_cmd_text = "\n".join([f"{cmd}: {count}" for cmd, count in top_cmds])
                    embed.add_field(
                        name="🔥 Top Commands",
                        value=top_cmd_text,
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Error generating stats: {e}",
                    ephemeral=True
                )

# Easy integration function
def integrate_monitoring_with_bot(bot):
    """
    Easy one-function integration of monitoring with Discord bot.
    Call this in your main bot file after creating the bot instance.
    """
    logging.info("🔧 Integrating monitoring with Discord bot...")
    
    # Setup monitoring
    monitoring = setup_bot_monitoring(bot)
    
    if monitoring:
        # Add monitoring commands
        BotMonitoringCommands.add_monitoring_commands(bot)
        logging.info("✅ Monitoring integration complete")
        return True
    else:
        logging.warning("⚠️ Monitoring integration failed - continuing without monitoring")
        return False

# For manual integration in existing bots
def add_monitoring_to_existing_bot(bot):
    """Add monitoring to an existing bot without modifying main bot file"""
    return integrate_monitoring_with_bot(bot)