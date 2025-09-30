import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import logging
from pathlib import Path
import config

# ------------------------------------------------------
# Logging Setup
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "notifications.log"

# Setup logger
logger = logging.getLogger("notifications")
logger.setLevel(logging.INFO)

# Only add handler if not already present
if not logger.handlers:
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Failed to setup file logging for notifications: {e}")


class NotificationView(View):
    """View with subscribe/unsubscribe buttons for bot update notifications."""
    
    def __init__(self):
        super().__init__(timeout=300)  # 5 minutes timeout
    
    @discord.ui.button(label="📢 Subscribe", style=discord.ButtonStyle.green, emoji="✅")
    async def subscribe_button(self, interaction: discord.Interaction, button: Button):
        """Handle subscribe button click."""
        await self._handle_subscribe(interaction)
    
    @discord.ui.button(label="🔕 Unsubscribe", style=discord.ButtonStyle.red, emoji="❌")
    async def unsubscribe_button(self, interaction: discord.Interaction, button: Button):
        """Handle unsubscribe button click."""
        await self._handle_unsubscribe(interaction)
    
    async def _handle_subscribe(self, interaction: discord.Interaction):
        """Handle subscription logic."""
        try:
            # Check if BOT_UPDATE_ROLE_ID is configured
            if not config.BOT_UPDATE_ROLE_ID:
                embed = discord.Embed(
                    title="❌ Configuration Error",
                    description="Bot update notifications are not configured on this server.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                logger.warning(f"Subscribe button used but BOT_UPDATE_ROLE_ID not configured - User: {interaction.user.id}")
                return

            # Get the role
            role = interaction.guild.get_role(config.BOT_UPDATE_ROLE_ID)
            if not role:
                embed = discord.Embed(
                    title="❌ Role Not Found",
                    description="The bot update role could not be found on this server.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                logger.error(f"Bot update role {config.BOT_UPDATE_ROLE_ID} not found in guild {interaction.guild.id}")
                return

            # Check if user already has the role
            if role in interaction.user.roles:
                embed = discord.Embed(
                    title="ℹ️ Already Subscribed",
                    description=f"You're already subscribed to bot update notifications with the **{role.name}** role!",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="💡 Want to unsubscribe?",
                    value="Click the **🔕 Unsubscribe** button to remove the role.",
                    inline=False
                )
                await interaction.response.edit_message(embed=embed, view=self)
                logger.info(f"User {interaction.user.id} tried to subscribe but already has bot update role")
                return

            # Add the role to the user
            await interaction.user.add_roles(role, reason="User subscribed to bot updates")
            
            embed = discord.Embed(
                title="✅ Successfully Subscribed!",
                description=f"You've been given the **{role.name}** role and will now receive bot update notifications!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📢 What you'll receive:",
                value="• New feature announcements\n• Important bot updates\n• Maintenance notifications\n• Bug fix updates",
                inline=False
            )
            embed.add_field(
                name="💡 Want to unsubscribe later?",
                value="Use the `/notifications` command again and click **🔕 Unsubscribe**.",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            logger.info(f"User {interaction.user.id} ({interaction.user.name}) subscribed to bot updates")

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to manage roles. Please contact a server administrator.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            logger.error(f"Insufficient permissions to add bot update role to user {interaction.user.id}")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ An Error Occurred",
                description="Something went wrong while subscribing you to updates. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            logger.error(f"Error in subscribe button for user {interaction.user.id}: {e}")
    
    async def _handle_unsubscribe(self, interaction: discord.Interaction):
        """Handle unsubscription logic."""
        try:
            # Check if BOT_UPDATE_ROLE_ID is configured
            if not config.BOT_UPDATE_ROLE_ID:
                embed = discord.Embed(
                    title="❌ Configuration Error",
                    description="Bot update notifications are not configured on this server.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                logger.warning(f"Unsubscribe button used but BOT_UPDATE_ROLE_ID not configured - User: {interaction.user.id}")
                return

            # Get the role
            role = interaction.guild.get_role(config.BOT_UPDATE_ROLE_ID)
            if not role:
                embed = discord.Embed(
                    title="❌ Role Not Found",
                    description="The bot update role could not be found on this server.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                logger.error(f"Bot update role {config.BOT_UPDATE_ROLE_ID} not found in guild {interaction.guild.id}")
                return

            # Check if user doesn't have the role
            if role not in interaction.user.roles:
                embed = discord.Embed(
                    title="ℹ️ Not Subscribed",
                    description="You're not currently subscribed to bot update notifications.",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="💡 Want to subscribe?",
                    value="Click the **📢 Subscribe** button to get the role and receive notifications.",
                    inline=False
                )
                await interaction.response.edit_message(embed=embed, view=self)
                logger.info(f"User {interaction.user.id} tried to unsubscribe but doesn't have bot update role")
                return

            # Remove the role from the user
            await interaction.user.remove_roles(role, reason="User unsubscribed from bot updates")
            
            embed = discord.Embed(
                title="✅ Successfully Unsubscribed!",
                description=f"The **{role.name}** role has been removed. You will no longer receive bot update notifications.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="💡 Changed your mind?",
                value="Use the `/notifications` command again and click **📢 Subscribe** to re-enable notifications.",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
            logger.info(f"User {interaction.user.id} ({interaction.user.name}) unsubscribed from bot updates")

        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Permission Error",
                description="I don't have permission to manage roles. Please contact a server administrator.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            logger.error(f"Insufficient permissions to remove bot update role from user {interaction.user.id}")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ An Error Occurred",
                description="Something went wrong while unsubscribing you from updates. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            logger.error(f"Error in unsubscribe button for user {interaction.user.id}: {e}")

    async def on_timeout(self):
        """Handle view timeout."""
        # Disable all buttons when the view times out
        for item in self.children:
            item.disabled = True


class NotificationsCog(commands.Cog):
    """Cog for managing bot update notifications and subscriptions."""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="notifications", description="Manage your bot update notification preferences")
    async def notifications(self, interaction: discord.Interaction):
        """Main command to manage bot update notifications with button interface."""
        try:
            # Check if BOT_UPDATE_ROLE_ID is configured
            if not config.BOT_UPDATE_ROLE_ID:
                embed = discord.Embed(
                    title="❌ Configuration Error",
                    description="Bot update notifications are not configured on this server.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.warning(f"Bot-updates command used but BOT_UPDATE_ROLE_ID not configured - User: {interaction.user.id}")
                return

            # Get the role
            role = interaction.guild.get_role(config.BOT_UPDATE_ROLE_ID)
            if not role:
                embed = discord.Embed(
                    title="❌ Role Not Found",
                    description="The bot update role could not be found on this server.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.error(f"Bot update role {config.BOT_UPDATE_ROLE_ID} not found in guild {interaction.guild.id}")
                return

            # Check current subscription status
            is_subscribed = role in interaction.user.roles
            
            # Create embed based on current status
            if is_subscribed:
                embed = discord.Embed(
                    title="📢 Bot Update Notifications",
                    description=f"You're currently **subscribed** to bot updates with the **{role.name}** role.",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="✅ Currently receiving:",
                    value="• New feature announcements\n• Important bot updates\n• Maintenance notifications\n• Bug fix updates",
                    inline=False
                )
                embed.add_field(
                    name="� What would you like to do?",
                    value="Use the buttons below to manage your subscription:",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="📢 Bot Update Notifications",
                    description="You're currently **not subscribed** to bot update notifications.",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="📢 What you'll receive if you subscribe:",
                    value="• New feature announcements\n• Important bot updates\n• Maintenance notifications\n• Bug fix updates",
                    inline=False
                )
                embed.add_field(
                    name="🔧 What would you like to do?",
                    value="Use the buttons below to manage your subscription:",
                    inline=False
                )
            
            # Create view with buttons
            view = NotificationView()
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            logger.info(f"User {interaction.user.id} ({interaction.user.name}) opened bot updates interface - Subscribed: {is_subscribed}")

        except Exception as e:
            embed = discord.Embed(
                title="❌ An Error Occurred",
                description="Something went wrong while loading the bot updates interface. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            logger.error(f"Error in notifications command for user {interaction.user.id}: {e}")


async def setup(bot):
    """Setup function for the notifications cog."""
    await bot.add_cog(NotificationsCog(bot))