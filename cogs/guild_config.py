import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from pathlib import Path

from database import set_guild_challenge_role, get_guild_challenge_roles, remove_guild_challenge_role

# ------------------------------------------------------
# Logging Setup - Clears on each bot run
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "guild_config.log"

# Clear the log file on startup
if LOG_FILE.exists():
    LOG_FILE.unlink()

# Create logger
logger = logging.getLogger("GuildConfig")
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

logger.info("Guild Config cog logging initialized - log file cleared")


class GuildConfig(commands.Cog):
    """Guild configuration management for multi-guild support."""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("GuildConfig cog initialized")
    
    @app_commands.command(name="setup_challenge_role", description="Set up a challenge role for this guild")
    @app_commands.describe(
        challenge_id="The challenge ID (1-13)",
        role="The role to assign when threshold is met", 
        threshold="The points threshold to earn the role (default: 1.0)"
    )
    async def setup_challenge_role(self, interaction: discord.Interaction, challenge_id: int, role: discord.Role, threshold: float = 1.0):
        """Set up a challenge role for the guild."""
        
        # Check permissions
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You need 'Manage Roles' permission to use this command.", ephemeral=True)
            return
            
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        
        try:
            # Validate inputs
            if challenge_id < 1 or challenge_id > 13:
                await interaction.response.send_message("❌ Challenge ID must be between 1 and 13.", ephemeral=True)
                return
                
            if threshold <= 0:
                await interaction.response.send_message("❌ Threshold must be greater than 0.", ephemeral=True)
                return
            
            # Check bot permissions
            if not interaction.guild.me.guild_permissions.manage_roles:
                await interaction.response.send_message("❌ I don't have permission to manage roles in this server.", ephemeral=True)
                return
                
            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message("❌ I cannot manage that role because it's higher than or equal to my highest role.", ephemeral=True)
                return
            
            # Set the challenge role in the database
            await set_guild_challenge_role(interaction.guild.id, challenge_id, threshold, role.id)
            
            await interaction.response.send_message(
                f"✅ **Challenge Role Configured!**\n"
                f"🎯 **Challenge {challenge_id}** will award {role.mention} at **{threshold} points**\n"
                f"📊 Users who reach this threshold will automatically receive the role!",
                ephemeral=True
            )
            
            logger.info(f"Challenge role configured for guild {interaction.guild.id}: Challenge {challenge_id} -> {role.name} ({role.id}) at {threshold} points")
            
        except Exception as e:
            logger.error(f"Error setting up challenge role: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="list_challenge_roles", description="List all configured challenge roles for this guild")
    async def list_challenge_roles(self, interaction: discord.Interaction):
        """List all challenge roles configured for the guild."""
        
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        
        try:
            roles_config = await get_guild_challenge_roles(interaction.guild.id)
            
            if not roles_config:
                await interaction.response.send_message(
                    "📝 **No Challenge Roles Configured**\n"
                    "Use `/setup_challenge_role` to configure challenge roles for this server.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="🎯 Challenge Roles Configuration",
                description=f"Challenge roles configured for **{interaction.guild.name}**",
                color=0x00ff00
            )
            
            for challenge_id in sorted(roles_config.keys()):
                thresholds = roles_config[challenge_id]
                role_info = []
                
                for threshold in sorted(thresholds.keys()):
                    role_id = thresholds[threshold]
                    role = interaction.guild.get_role(role_id)
                    role_mention = role.mention if role else f"<@&{role_id}> (deleted)"
                    role_info.append(f"**{threshold} points** → {role_mention}")
                
                embed.add_field(
                    name=f"Challenge {challenge_id}",
                    value="\n".join(role_info),
                    inline=True
                )
            
            embed.set_footer(text="Use /setup_challenge_role to add more roles or /remove_challenge_role to remove them")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Listed challenge roles for guild {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"Error listing challenge roles: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)
    
    @app_commands.command(name="remove_challenge_role", description="Remove a challenge role configuration")
    @app_commands.describe(
        challenge_id="The challenge ID to remove role for",
        threshold="The specific threshold to remove (leave empty to remove all thresholds)"
    )
    async def remove_challenge_role(self, interaction: discord.Interaction, challenge_id: int, threshold: float = None):
        """Remove a challenge role configuration."""
        
        # Check permissions
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You need 'Manage Roles' permission to use this command.", ephemeral=True)
            return
            
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        
        try:
            # Validate challenge ID
            if challenge_id < 1 or challenge_id > 13:
                await interaction.response.send_message("❌ Challenge ID must be between 1 and 13.", ephemeral=True)
                return
            
            # Remove the challenge role
            await remove_guild_challenge_role(interaction.guild.id, challenge_id, threshold)
            
            if threshold is not None:
                await interaction.response.send_message(
                    f"✅ **Challenge Role Removed!**\n"
                    f"🗑️ Removed role configuration for **Challenge {challenge_id}** at **{threshold} points**",
                    ephemeral=True
                )
                logger.info(f"Removed challenge role for guild {interaction.guild.id}: Challenge {challenge_id} at {threshold} points")
            else:
                await interaction.response.send_message(
                    f"✅ **Challenge Roles Removed!**\n"
                    f"🗑️ Removed all role configurations for **Challenge {challenge_id}**",
                    ephemeral=True
                )
                logger.info(f"Removed all challenge roles for guild {interaction.guild.id}: Challenge {challenge_id}")
            
        except Exception as e:
            logger.error(f"Error removing challenge role: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(GuildConfig(bot))
    logger.info("GuildConfig cog loaded successfully")