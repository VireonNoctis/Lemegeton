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
            # Get or create the notification role
            notifications_cog = interaction.client.get_cog("NotificationsCog")
            if not notifications_cog:
                embed = discord.Embed(
                    title="❌ System Error",
                    description="Notifications system is not available.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                logger.error(f"NotificationsCog not found when user {interaction.user.id} tried to subscribe")
                return
            
            try:
                role = await notifications_cog.get_or_create_notification_role(interaction.guild)
            except discord.Forbidden:
                embed = discord.Embed(
                    title="❌ Permission Error",
                    description="I don't have permission to create or manage the notification role. Please contact a server administrator.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                return
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Role Error",
                    description="Failed to get or create the notification role. Please try again later.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                logger.error(f"Error getting/creating role for user {interaction.user.id}: {e}")
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
            # Get or create the notification role
            notifications_cog = interaction.client.get_cog("NotificationsCog")
            if not notifications_cog:
                embed = discord.Embed(
                    title="❌ System Error",
                    description="Notifications system is not available.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                logger.error(f"NotificationsCog not found when user {interaction.user.id} tried to unsubscribe")
                return
            
            try:
                role = await notifications_cog.get_or_create_notification_role(interaction.guild)
            except discord.Forbidden:
                embed = discord.Embed(
                    title="❌ Permission Error",
                    description="I don't have permission to manage the notification role. Please contact a server administrator.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                return
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Role Error",
                    description="Failed to get the notification role. Please try again later.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                logger.error(f"Error getting role for user {interaction.user.id}: {e}")
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
    
    async def get_or_create_notification_role(self, guild: discord.Guild) -> discord.Role:
        """Get the bot update notification role, creating it if it doesn't exist."""
        role_name = "bot-updates"
        
        # If BOT_UPDATE_ROLE_ID is configured, try to get that specific role
        if config.BOT_UPDATE_ROLE_ID:
            role = guild.get_role(config.BOT_UPDATE_ROLE_ID)
            if role:
                logger.info(f"Using configured bot update role '{role.name}' (ID: {role.id}) in guild {guild.id}")
                return role
            else:
                logger.warning(f"Configured BOT_UPDATE_ROLE_ID {config.BOT_UPDATE_ROLE_ID} not found in guild {guild.id}, will create new role")
        
        # Try to find role by name
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            logger.info(f"Found existing bot update role '{role.name}' (ID: {role.id}) in guild {guild.id}")
            return role
        
        # Create the role if it doesn't exist
        try:
            role = await guild.create_role(
                name=role_name,
                mentionable=True,
                reason="Auto-created for bot update notifications",
                color=discord.Color.blue()
            )
            logger.info(f"Created new bot update role '{role.name}' (ID: {role.id}) in guild {guild.id}")
            return role
        except discord.Forbidden:
            logger.error(f"Insufficient permissions to create bot update role in guild {guild.id}")
            raise
        except Exception as e:
            logger.error(f"Error creating bot update role in guild {guild.id}: {e}")
            raise

    @app_commands.command(name="notifications", description="Manage your bot update notification preferences")
    async def notifications(self, interaction: discord.Interaction):
        """Main command to manage bot update notifications with button interface."""
        try:
            # Get or create the notification role
            try:
                role = await self.get_or_create_notification_role(interaction.guild)
            except discord.Forbidden:
                embed = discord.Embed(
                    title="❌ Permission Error",
                    description="I don't have permission to create or manage the notification role. Please contact a server administrator and ensure I have the 'Manage Roles' permission.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.error(f"Insufficient permissions to create/manage notification role in guild {interaction.guild.id}")
                return
            except Exception as e:
                embed = discord.Embed(
                    title="❌ Role Error",
                    description="Failed to get or create the notification role. Please try again later.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                logger.error(f"Error getting/creating notification role in guild {interaction.guild.id}: {e}")
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