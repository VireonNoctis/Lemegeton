"""
Bot Integration for Monitoring System
Integrates the monitoring system with the Discord bot for live metrics.
"""

import logging
import time
from datetime import datetime
from functools import wraps
from types import SimpleNamespace

# Import monitoring system - try package-style import first, then fallback to top-level module
MONITORING_AVAILABLE = False
setup_monitoring = None
get_monitoring = None
try:
    # Prefer explicit package import when utils is a package or we're running from project root
    from utils.monitoring_system import setup_monitoring as _setup_monitoring, get_monitoring as _get_monitoring
    setup_monitoring = _setup_monitoring
    get_monitoring = _get_monitoring
    MONITORING_AVAILABLE = True
except Exception:
    try:
        # Fallback to direct module import if monitoring_system.py is on sys.path
        from monitoring_system import setup_monitoring as _setup_monitoring, get_monitoring as _get_monitoring
        setup_monitoring = _setup_monitoring
        get_monitoring = _get_monitoring
        MONITORING_AVAILABLE = True
    except Exception:
        MONITORING_AVAILABLE = False
        logging.warning("Monitoring system not available (utils/monitoring_system.py missing or failed to import). To enable, ensure utils/monitoring_system.py exists and required deps (e.g. psutil) are installed.")

def setup_bot_monitoring(bot):
    """Setup monitoring integration with the Discord bot"""
    if not MONITORING_AVAILABLE:
        logging.warning("⚠️ Monitoring system not available")
        return None
    
    try:
        monitoring = setup_monitoring(bot)
        logging.info("✅ Bot monitoring system initialized (task start deferred)")

        # We defer starting the monitoring background loop until the bot is
        # ready. The loop will be started inside the on_ready handler added
        # by add_monitoring_events(), which executes within the bot's event
        # loop and avoids accessing bot.loop from synchronous code.
        add_monitoring_events(bot, monitoring)

        return monitoring
    except Exception as e:
        logging.error(f"❌ Failed to setup bot monitoring: {e}")
        return None

def add_monitoring_events(bot, monitoring):
    """Add monitoring event handlers to the bot using listeners (not decorators).

    Using bot.add_listener ensures our handlers run alongside other
    on_ready handlers defined elsewhere (and are not overridden).
    """

    async def _monitor_on_ready():
        """Bot ready event with monitoring"""
        try:
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

            # Start the monitoring background loop now that the bot is ready
            if monitoring and hasattr(monitoring, 'monitoring_task'):
                try:
                    if not monitoring.monitoring_task.is_running():
                        monitoring.monitoring_task.start()
                        logging.info("✅ Monitoring background task started from on_ready")
                    else:
                        logging.info("Monitoring background task already running")
                except Exception:
                    logging.exception("Failed to start monitoring background task from on_ready")
        except Exception:
            logging.exception("Unexpected error in monitoring on_ready handler")

    async def _monitor_on_guild_join(guild):
        """Track new guild joins"""
        logging.info(f"🎉 Bot joined new guild: {guild.name} ({guild.id}) with {guild.member_count} members")

        # Initialize guild in monitoring
        monitoring.guild_activity[guild.id] = {
            'commands_24h': 0,
            'errors_24h': 0,
            'last_activity': datetime.utcnow()
        }

    async def _monitor_on_guild_remove(guild):
        """Track guild removals"""
        logging.info(f"👋 Bot removed from guild: {guild.name} ({guild.id})")

        # Remove guild from monitoring
        if guild.id in monitoring.guild_activity:
            del monitoring.guild_activity[guild.id]

    async def _monitor_on_command_error(ctx, error):
        """Track command errors for monitoring"""
        guild_id = ctx.guild.id if ctx.guild else None
        command_name = ctx.command.name if ctx.command else "unknown"

        # Record error in monitoring
        monitoring.record_error(error, guild_id, command_name)

        # Log the error
        logging.error(f"🚨 Command error in {ctx.guild.name if ctx.guild else 'DM'}: {error}")

    # Register listeners so we don't interfere with other on_ready handlers
    try:
        bot.add_listener(_monitor_on_ready, 'on_ready')
        bot.add_listener(_monitor_on_guild_join, 'on_guild_join')
        bot.add_listener(_monitor_on_guild_remove, 'on_guild_remove')
        bot.add_listener(_monitor_on_command_error, 'on_command_error')
    except Exception:
        logging.exception("Failed to register monitoring event listeners")

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
                # Defensive: call system and bot metrics separately so a failure
                # in one (e.g., missing DB tables) doesn't abort the whole flow.
                try:
                    system_metrics = await monitoring.get_system_metrics()
                except Exception as e:
                    logging.warning(f"Monitoring system metrics failed: {e}")
                    system_metrics = SimpleNamespace(cpu_percent=0, memory_percent=0, latency_ms=0, uptime_hours=0)

                try:
                    bot_metrics = await monitoring.get_bot_metrics()
                except Exception as e:
                    logging.warning(f"Monitoring bot metrics failed: {e}")
                    bot_metrics = SimpleNamespace(
                        guild_count=0,
                        total_users=0,
                        total_registered_users=0,
                        commands_per_hour=0,
                        errors_per_hour=0,
                        top_commands={},
                        response_times=[]
                    )
                
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