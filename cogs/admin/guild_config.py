import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from pathlib import Path

from database import (
    set_guild_challenge_role, get_guild_challenge_roles, remove_guild_challenge_role,
    set_guild_mod_role, get_guild_mod_role, remove_guild_mod_role,
    add_bot_moderator, remove_bot_moderator, get_all_bot_moderators, is_user_bot_moderator,
    is_user_moderator
)

# ------------------------------------------------------
# Logging Setup - Clears on each bot run
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "guild_config.log"

# Create logger
logger = logging.getLogger("GuildConfig")
logger.setLevel(logging.INFO)

# Remove existing handlers to avoid duplicates
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

try:
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
except Exception:
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(stream_handler)

logger.info("Guild Config cog logging initialized - file or stream fallback in use")


class GuildConfig(commands.Cog):
    """Guild configuration management for multi-guild support."""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("GuildConfig cog initialized")
    
    @app_commands.command(name="setup_challenge_role", description="Set up a challenge role for this guild (Server Moderator only)")
    @app_commands.describe(
        challenge_id="The challenge ID (1-13)",
        role="The role to assign when threshold is met", 
        threshold="The points threshold to earn the role (default: 1.0)"
    )
    async def setup_challenge_role(self, interaction: discord.Interaction, challenge_id: int, role: discord.Role, threshold: float = 1.0):
        """Set up a challenge role for the guild."""
        
        # Check server moderator permissions
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
            
        member = interaction.user if isinstance(interaction.user, discord.Member) else await interaction.guild.fetch_member(interaction.user.id)
        if not await is_user_moderator(member, interaction.guild.id):
            await interaction.response.send_message("❌ You need to be a server moderator to use this command.", ephemeral=True)
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
    
    @app_commands.command(name="list_challenge_roles", description="List all configured challenge roles for this guild (Server Moderator only)")
    async def list_challenge_roles(self, interaction: discord.Interaction):
        """List all challenge roles configured for the guild."""
        
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
            
        # Check server moderator permissions
        member = interaction.user if isinstance(interaction.user, discord.Member) else await interaction.guild.fetch_member(interaction.user.id)
        if not await is_user_moderator(member, interaction.guild.id):
            await interaction.response.send_message("❌ You need to be a server moderator to use this command.", ephemeral=True)
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
    
    @app_commands.command(name="remove_challenge_role", description="Remove a challenge role configuration (Server Moderator only)")
    @app_commands.describe(
        challenge_id="The challenge ID to remove role for",
        threshold="The specific threshold to remove (leave empty to remove all thresholds)"
    )
    async def remove_challenge_role(self, interaction: discord.Interaction, challenge_id: int, threshold: float = None):
        """Remove a challenge role configuration."""
        
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
            
        # Check server moderator permissions
        member = interaction.user if isinstance(interaction.user, discord.Member) else await interaction.guild.fetch_member(interaction.user.id)
        if not await is_user_moderator(member, interaction.guild.id):
            await interaction.response.send_message("❌ You need to be a server moderator to use this command.", ephemeral=True)
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

    @app_commands.command(name="set_mod_role", description="Set the moderator role for this server")
    @app_commands.describe(role="The role to designate as moderator role")
    @app_commands.default_permissions(manage_guild=True)
    async def set_mod_role(self, interaction: discord.Interaction, role: discord.Role):
        """Set the moderator role for the guild."""
        
        # Check permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need 'Manage Server' permission to use this command.", ephemeral=True)
            return
            
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        
        try:
            # Check if bot can see and manage the role if needed
            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    f"⚠️ **Role Set with Warning**\n"
                    f"🛡️ **Moderator Role:** {role.mention}\n"
                    f"⚠️ This role is higher than my highest role, so I may not be able to check it properly in some cases.",
                    ephemeral=True
                )
            
            # Set the mod role in the database
            success = await set_guild_mod_role(interaction.guild.id, role.id)
            
            if success:
                await interaction.response.send_message(
                    f"✅ **Moderator Role Set!**\n"
                    f"🛡️ **Moderator Role:** {role.mention}\n"
                    f"👥 Users with this role will have access to moderator commands.",
                    ephemeral=True
                )
                logger.info(f"Set mod role for guild {interaction.guild.id}: {role.name} ({role.id})")
            else:
                await interaction.response.send_message("❌ Failed to set moderator role. Please try again.", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error setting mod role: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="show_mod_role", description="Show the current moderator role for this server")
    @app_commands.default_permissions(manage_guild=True)
    async def show_mod_role(self, interaction: discord.Interaction):
        """Show the current moderator role for the guild."""
        
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        
        try:
            role_id = await get_guild_mod_role(interaction.guild.id)
            
            if not role_id:
                await interaction.response.send_message(
                    "📝 **No Moderator Role Set**\n"
                    "Use `/set_mod_role` to configure the moderator role for this server.\n"
                    "Without a mod role set, moderator commands will fall back to checking Discord permissions.",
                    ephemeral=True
                )
                return
            
            role = interaction.guild.get_role(role_id)
            
            if role:
                await interaction.response.send_message(
                    f"🛡️ **Current Moderator Role**\n"
                    f"**Role:** {role.mention}\n"
                    f"**Members:** {len(role.members)} users\n"
                    f"**Created:** <t:{int(role.created_at.timestamp())}:R>",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"⚠️ **Moderator Role Configuration Issue**\n"
                    f"The configured moderator role (ID: {role_id}) no longer exists.\n"
                    f"Use `/remove_mod_role` to clear the configuration or `/set_mod_role` to set a new one.",
                    ephemeral=True
                )
            
            logger.info(f"Showed mod role for guild {interaction.guild.id}: {role_id}")
            
        except Exception as e:
            logger.error(f"Error showing mod role: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="remove_mod_role", description="Remove the moderator role configuration for this server")
    @app_commands.default_permissions(manage_guild=True)
    async def remove_mod_role(self, interaction: discord.Interaction):
        """Remove the moderator role configuration for the guild."""
        
        # Check permissions
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need 'Manage Server' permission to use this command.", ephemeral=True)
            return
            
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return
        
        try:
            # Check if there's a mod role configured
            current_role_id = await get_guild_mod_role(interaction.guild.id)
            
            if not current_role_id:
                await interaction.response.send_message(
                    "📝 **No Moderator Role Configuration**\n"
                    "There is no moderator role currently set for this server.",
                    ephemeral=True
                )
                return
            
            # Remove the mod role configuration
            success = await remove_guild_mod_role(interaction.guild.id)
            
            if success:
                current_role = interaction.guild.get_role(current_role_id)
                role_mention = current_role.mention if current_role else f"<@&{current_role_id}>"
                
                await interaction.response.send_message(
                    f"✅ **Moderator Role Configuration Removed!**\n"
                    f"🗑️ Removed: {role_mention}\n"
                    f"🔄 Moderator commands will now fall back to checking Discord permissions.",
                    ephemeral=True
                )
                logger.info(f"Removed mod role configuration for guild {interaction.guild.id}")
            else:
                await interaction.response.send_message("❌ Failed to remove moderator role configuration. Please try again.", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error removing mod role: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="add_bot_moderator", description="Add a bot moderator (bot-wide actions)")
    @app_commands.describe(user="The user to add as a bot moderator")
    async def add_bot_moderator_cmd(self, interaction: discord.Interaction, user: discord.User):
        """Add a bot moderator who can perform bot-wide actions."""
        
        # Check if user is admin or existing bot moderator
        if not await is_user_bot_moderator(interaction.user):
            await interaction.response.send_message("❌ Only bot administrators and moderators can manage bot moderators.", ephemeral=True)
            return
        
        try:
            # Add the bot moderator
            success = await add_bot_moderator(user.id, user.display_name, interaction.user.id)
            
            if success:
                await interaction.response.send_message(
                    f"✅ **Bot Moderator Added!**\n"
                    f"👑 **User:** {user.mention}\n"
                    f"🌐 This user can now perform bot-wide actions like publishing changelogs to all servers.",
                    ephemeral=True
                )
                logger.info(f"Added bot moderator: {user.display_name} ({user.id}) by {interaction.user.display_name} ({interaction.user.id})")
            else:
                await interaction.response.send_message("❌ Failed to add bot moderator. Please try again.", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error adding bot moderator: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="remove_bot_moderator", description="Remove a bot moderator")
    @app_commands.describe(user="The user to remove as a bot moderator")
    async def remove_bot_moderator_cmd(self, interaction: discord.Interaction, user: discord.User):
        """Remove a bot moderator."""
        
        # Check if user is admin or existing bot moderator
        if not await is_user_bot_moderator(interaction.user):
            await interaction.response.send_message("❌ Only bot administrators and moderators can manage bot moderators.", ephemeral=True)
            return
        
        try:
            # Remove the bot moderator
            success = await remove_bot_moderator(user.id)
            
            if success:
                await interaction.response.send_message(
                    f"✅ **Bot Moderator Removed!**\n"
                    f"👤 **User:** {user.mention}\n"
                    f"🚫 This user can no longer perform bot-wide actions.",
                    ephemeral=True
                )
                logger.info(f"Removed bot moderator: {user.display_name} ({user.id}) by {interaction.user.display_name} ({interaction.user.id})")
            else:
                await interaction.response.send_message("❌ Failed to remove bot moderator. Please try again.", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error removing bot moderator: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="list_bot_moderators", description="List all bot moderators")
    async def list_bot_moderators_cmd(self, interaction: discord.Interaction):
        """List all bot moderators."""
        
        # Check if user is admin or existing bot moderator
        if not await is_user_bot_moderator(interaction.user):
            await interaction.response.send_message("❌ Only bot administrators and moderators can view bot moderators.", ephemeral=True)
            return
        
        try:
            moderators = await get_all_bot_moderators()
            
            if not moderators:
                await interaction.response.send_message(
                    "📝 **No Bot Moderators**\n"
                    "There are currently no bot moderators configured.\n"
                    "Use `/add_bot_moderator` to add bot moderators.",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title="👑 Bot Moderators",
                description="Users who can perform bot-wide actions",
                color=0x9932cc
            )
            
            moderator_list = []
            for discord_id, username, added_by, created_at in moderators:
                user = self.bot.get_user(discord_id)
                user_mention = user.mention if user else f"<@{discord_id}>"
                
                # Get who added them
                added_by_user = self.bot.get_user(added_by)
                added_by_mention = added_by_user.display_name if added_by_user else f"ID: {added_by}"
                
                moderator_list.append(
                    f"👑 {user_mention} (`{username}`)\n"
                    f"   Added by: {added_by_mention}\n"
                    f"   Date: <t:{int(created_at.timestamp()) if hasattr(created_at, 'timestamp') else int(created_at)}:R>"
                )
            
            embed.add_field(
                name=f"Bot Moderators ({len(moderators)})",
                value="\n\n".join(moderator_list),
                inline=False
            )
            
            embed.set_footer(text="Bot moderators can publish changelogs and manage bot-wide settings")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.info(f"Listed bot moderators for {interaction.user.display_name} ({interaction.user.id})")
            
        except Exception as e:
            logger.error(f"Error listing bot moderators: {e}", exc_info=True)
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(GuildConfig(bot))
    logger.info("GuildConfig cog loaded successfully")