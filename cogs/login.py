import discord
from discord import app_commands
from discord.ext import commands
import logging
import re
import aiohttp
from pathlib import Path
from typing import Optional

from database import (
    add_user, get_user, update_username, remove_user,
    # New guild-aware functions
    add_user_guild_aware, get_user_guild_aware, register_user_guild_aware, 
    is_user_registered_in_guild
)

# Configuration constants
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "login.log"
MAX_USERNAME_LENGTH = 50
USERNAME_REGEX = r"^[\w-]+$"
ANILIST_ENDPOINT = "https://graphql.anilist.co"
VIEW_TIMEOUT = 60

# Ensure logs directory exists
LOG_DIR.mkdir(exist_ok=True)

# Set up file-based logging with auto-clearing
logger = logging.getLogger("Login")
logger.setLevel(logging.DEBUG)

# Clear handlers to avoid duplicates
logger.handlers.clear()

# Create file handler that clears on startup
file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter(
    fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(file_handler)

logger.info("Login cog logging system initialized")

class LoginView(discord.ui.View):
    """Interactive view for login/registration/unregistration actions."""
    
    def __init__(self, user_id: int, username: str, is_registered: bool, anilist_username: str = None):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.user_id = user_id
        self.username = username
        self.is_registered = is_registered
        self.anilist_username = anilist_username
        
        logger.debug(f"Created LoginView for {username} (ID: {user_id}), registered: {is_registered}")

    @discord.ui.button(label="📝 Register/Update", style=discord.ButtonStyle.primary, emoji="📝")
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show modal for registration or updating AniList username."""
        logger.info(f"Register/Update button clicked by {interaction.user.display_name} (ID: {self.user_id})")
        
        modal = RegistrationModal(self.is_registered)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🗑️ Unregister", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def unregister_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show confirmation for unregistration."""
        if not self.is_registered:
            await interaction.response.send_message(
                "⚠️ You are not registered, so there's nothing to unregister.", 
                ephemeral=True
            )
            logger.debug(f"Unregister attempted by non-registered user: {interaction.user.display_name}")
            return
            
        logger.info(f"Unregister button clicked by {interaction.user.display_name} (ID: {self.user_id})")
        
        # Show confirmation
        view = UnregisterConfirmView(self.user_id)
        await interaction.response.send_message(
            "❗ **Are you sure you want to unregister?**\n\n"
            "This action cannot be undone and will remove:\n"
            "• Your AniList connection\n"
            "• All your manga/anime progress\n"
            "• All your challenge progress\n"
            "• All your statistics and data\n\n"
            "⚠️ **This is permanent and cannot be recovered!**",
            view=view,
            ephemeral=True
        )

    @discord.ui.button(label="ℹ️ Status", style=discord.ButtonStyle.secondary, emoji="ℹ️")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show user's current registration status."""
        logger.debug(f"Status button clicked by {interaction.user.display_name} (ID: {self.user_id})")
        
        if self.is_registered:
            embed = discord.Embed(
                title="📊 Your Account Status",
                description=f"✅ **Registered**\n🔗 **AniList**: {self.anilist_username or 'Unknown'}",
                color=discord.Color.green()
            )
            embed.set_footer(text="Use the buttons above to update or unregister")
        else:
            embed = discord.Embed(
                title="📊 Your Account Status", 
                description="❌ **Not Registered**\n\nYou need to register with your AniList username to use the bot's features.",
                color=discord.Color.red()
            )
            embed.set_footer(text="Use the Register button above to get started")
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def on_timeout(self):
        """Handle view timeout by disabling buttons."""
        try:
            self.clear_items()
            logger.debug(f"LoginView timed out for user ID: {self.user_id}")
        except Exception as e:
            logger.error(f"Error handling LoginView timeout: {e}", exc_info=True)


class RegistrationModal(discord.ui.Modal):
    """Modal for collecting AniList username during registration."""
    
    def __init__(self, is_update: bool = False):
        self.is_update = is_update
        title = "Update AniList Username" if is_update else "Register with AniList"
        super().__init__(title=title)
        
        self.username_input = discord.ui.TextInput(
            label="AniList Username",
            placeholder="Enter your exact AniList username (case-sensitive)",
            required=True,
            max_length=MAX_USERNAME_LENGTH
        )
        self.add_item(self.username_input)
        
        logger.debug(f"Created RegistrationModal (update: {is_update})")

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission and process registration."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command can only be used in a server!", 
                ephemeral=True
            )
            return
            
        guild_id = interaction.guild.id
        logger.info(f"Registration modal submitted by {interaction.user.display_name} "
                   f"(ID: {interaction.user.id}) in guild {guild_id} with username: {self.username_input.value}")
        
        await interaction.response.defer(ephemeral=True)
        
        login_cog = interaction.client.get_cog("Login")
        if login_cog:
            result = await login_cog.handle_register(
                interaction.user.id,
                guild_id,
                str(interaction.user),
                self.username_input.value.strip()
            )
            await interaction.followup.send(result, ephemeral=True)
        else:
            logger.error("Login cog not found when processing registration modal")
            await interaction.followup.send(
                "❌ System error: Login cog not available. Please try again later.",
                ephemeral=True
            )


class UnregisterConfirmView(discord.ui.View):
    """Confirmation view for unregistration."""
    
    def __init__(self, user_id: int):
        super().__init__(timeout=VIEW_TIMEOUT)
        self.user_id = user_id
        logger.debug(f"Created UnregisterConfirmView for user ID: {user_id}")

    @discord.ui.button(label="✅ Confirm Unregister", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm and execute unregistration."""
        logger.info(f"Unregister confirmed by {interaction.user.display_name} (ID: {self.user_id})")
        
        try:
            await remove_user(self.user_id)
            logger.info(f"Successfully removed user {interaction.user.display_name} (ID: {self.user_id}) from database")
            
            embed = discord.Embed(
                title="✅ Unregistration Complete",
                description="You have been successfully unregistered from the system.\n\n"
                           "All your data has been permanently removed:\n"
                           "• AniList connection\n"
                           "• Manga/anime progress\n" 
                           "• Challenge progress\n"
                           "• Statistics and data\n\n"
                           "You can register again anytime using `/login`.",
                color=discord.Color.green()
            )
            
            await interaction.response.edit_message(content=None, embed=embed, view=None)
            
        except Exception as e:
            logger.error(f"Failed to remove user {interaction.user.display_name} (ID: {self.user_id}) from database: {e}")
            await interaction.response.edit_message(
                content="❌ Failed to unregister. Please try again later or contact support.",
                view=None
            )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel unregistration."""
        logger.info(f"Unregister canceled by {interaction.user.display_name} (ID: {self.user_id})")
        
        embed = discord.Embed(
            title="❎ Unregister Canceled",
            description="Your account remains active and all your data is safe.",
            color=discord.Color.blue()
        )
        
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    async def on_timeout(self):
        """Handle view timeout."""
        logger.debug(f"UnregisterConfirmView timed out for user ID: {self.user_id}")
        self.clear_items()


class Login(commands.Cog):
    """Discord cog for user login/registration management."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Login cog initialized")

    def _is_valid_username(self, username: str) -> bool:
        """Validate username format and length."""
        if not username or not isinstance(username, str):
            return False
        return bool(re.match(USERNAME_REGEX, username)) and 0 < len(username) <= MAX_USERNAME_LENGTH

    async def _fetch_anilist_id(self, anilist_username: str) -> Optional[int]:
        """Fetch AniList user ID from username via GraphQL API."""
        query = """
        query ($name: String) {
          User(name: $name) { 
            id 
            name
          }
        }
        """
        
        logger.debug(f"Fetching AniList ID for username: {anilist_username}")
        
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(
                    ANILIST_ENDPOINT,
                    json={"query": query, "variables": {"name": anilist_username}}
                ) as resp:
                    if resp.status != 200:
                        logger.warning(f"AniList API returned status {resp.status} for username: {anilist_username}")
                        return None
                    
                    data = await resp.json()
                    logger.debug(f"AniList API response received for username: {anilist_username}")
                    
                    user_data = data.get("data", {}).get("User")
                    if user_data and "id" in user_data:
                        user_id = user_data["id"]
                        actual_name = user_data.get("name", anilist_username)
                        logger.info(f"Successfully found AniList user: {actual_name} (ID: {user_id})")
                        return user_id
                    
                    logger.warning(f"AniList user not found: {anilist_username}")
                    return None
                    
        except aiohttp.ClientError as e:
            logger.error(f"Network error while fetching AniList ID for {anilist_username}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while fetching AniList ID for {anilist_username}: {e}", exc_info=True)
            return None

    async def handle_register(self, user_id: int, guild_id: int, discord_user: str, anilist_username: str) -> str:
        """Handle user registration with comprehensive validation and logging."""
        logger.info(f"Registration attempt by {discord_user} (ID: {user_id}) in guild {guild_id} with AniList username: {anilist_username}")
        
        # Input validation
        anilist_username = anilist_username.strip()
        if not anilist_username:
            logger.warning(f"Empty username provided by {discord_user} (ID: {user_id}) in guild {guild_id}")
            return "❌ AniList username cannot be empty."
            
        if len(anilist_username) > MAX_USERNAME_LENGTH:
            logger.warning(f"Username too long ({len(anilist_username)} chars) by {discord_user} (ID: {user_id}) in guild {guild_id}")
            return f"❌ Username too long. Maximum {MAX_USERNAME_LENGTH} characters allowed."
            
        if not self._is_valid_username(anilist_username):
            logger.warning(f"Invalid username format '{anilist_username}' by {discord_user} (ID: {user_id}) in guild {guild_id}")
            return "❌ Invalid username. Only letters, numbers, underscores, and hyphens are allowed."

        # Fetch and validate AniList ID
        anilist_id = await self._fetch_anilist_id(anilist_username)
        if not anilist_id:
            logger.warning(f"AniList user '{anilist_username}' not found for {discord_user} (ID: {user_id}) in guild {guild_id}")
            return f"❌ Could not find AniList user **{anilist_username}**. Please check the spelling and try again."

        # Database operations
        try:
            existing_user = await get_user_guild_aware(user_id, guild_id)
            
            if existing_user:
                # Update existing user
                await self._update_existing_user_guild_aware(user_id, guild_id, discord_user, anilist_username, anilist_id)
                logger.info(f"Updated registration for {discord_user} (ID: {user_id}) in guild {guild_id} -> AniList: {anilist_username} (ID: {anilist_id})")
                return f"✅ Your AniList username has been updated to **{anilist_username}** in this server!"
            else:
                # Register new user
                await self._register_new_user_guild_aware(user_id, guild_id, discord_user, anilist_username, anilist_id)
                logger.info(f"Successfully registered new user {discord_user} (ID: {user_id}) in guild {guild_id} -> AniList: {anilist_username} (ID: {anilist_id})")
                return f"🎉 Successfully registered with AniList username **{anilist_username}** in this server!"
                
        except Exception as e:
            logger.error(f"Database error during registration for {discord_user} (ID: {user_id}) in guild {guild_id}: {e}", exc_info=True)
            return "❌ An error occurred while registering you. Please try again later."

    async def _update_existing_user(self, user_id: int, discord_user: str, anilist_username: str, anilist_id: int):
        """Update existing user's AniList information. (DEPRECATED: Use _update_existing_user_guild_aware)"""
        logger.warning("Using deprecated _update_existing_user method. Consider using guild-aware version.")
        try:
            from database import update_anilist_info
            await update_anilist_info(user_id, anilist_username, anilist_id)
            logger.info(f"Updated AniList info for existing user {discord_user} (ID: {user_id})")
        except Exception as e:
            logger.error(f"Failed to update existing user {discord_user} (ID: {user_id}): {e}")
            # Fallback to username-only update
            await update_username(user_id, anilist_username)
            logger.info(f"Fallback: Updated username only for {discord_user} (ID: {user_id})")

    async def _update_existing_user_guild_aware(self, user_id: int, guild_id: int, discord_user: str, anilist_username: str, anilist_id: int):
        """Update existing user's AniList information for a specific guild."""
        try:
            # Use the guild-aware registration function which handles updates via INSERT OR REPLACE
            await register_user_guild_aware(user_id, guild_id, discord_user, anilist_username, anilist_id)
            logger.info(f"Updated AniList info for existing user {discord_user} (ID: {user_id}) in guild {guild_id}")
        except Exception as e:
            logger.error(f"Failed to update existing user {discord_user} (ID: {user_id}) in guild {guild_id}: {e}")
            raise

    async def _register_new_user(self, user_id: int, discord_user: str, anilist_username: str, anilist_id: int):
        """Register a completely new user. (DEPRECATED: Use _register_new_user_guild_aware)"""
        logger.warning("Using deprecated _register_new_user method. Consider using guild-aware version.")
        await add_user(user_id, discord_user, anilist_username, anilist_id)
        logger.info(f"Added new user to database: {discord_user} (ID: {user_id})")

    async def _register_new_user_guild_aware(self, user_id: int, guild_id: int, discord_user: str, anilist_username: str, anilist_id: int):
        """Register a completely new user in a specific guild."""
        await register_user_guild_aware(user_id, guild_id, discord_user, anilist_username, anilist_id)
        logger.info(f"Added new user to database: {discord_user} (ID: {user_id}) in guild {guild_id}")

    @app_commands.command(
        name="login",
        description="🔐 Manage your account - register, update, or unregister"
    )
    async def login(self, interaction: discord.Interaction):
        """Smart login command that adapts based on user's registration status."""
        try:
            # Ensure command is used in a guild
            if not interaction.guild:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server!", 
                    ephemeral=True
                )
                return
            
            guild_id = interaction.guild.id
            logger.info(f"Login command invoked by {interaction.user.display_name} "
                       f"({interaction.user.id}) in {interaction.guild.name} (Guild ID: {guild_id})")
            
            # Check if user is already registered in this guild
            user = await get_user_guild_aware(interaction.user.id, guild_id)
            is_registered = user is not None
            anilist_username = user[4] if user else None  # anilist_username is now at index 4 in new schema
            
            logger.debug(f"User {interaction.user.display_name} registration status in guild {guild_id}: {is_registered}")
            
            # Create appropriate embed based on registration status
            if is_registered:
                embed = discord.Embed(
                    title="🔐 Account Management",
                    description=f"Welcome back, **{interaction.user.display_name}**!\n\n"
                               f"✅ **Status**: Registered in **{interaction.guild.name}**\n"
                               f"🔗 **AniList**: {anilist_username or 'Unknown'}\n\n"
                               f"Use the buttons below to manage your account:",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Available Actions",
                    value="📝 **Register/Update** - Change your AniList username\n"
                          "🗑️ **Unregister** - Remove your account and data from this server\n"
                          "ℹ️ **Status** - View detailed account information",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="🔐 Welcome to the Bot!",
                    description=f"Hello **{interaction.user.display_name}**!\n\n"
                               f"❌ **Status**: Not Registered in **{interaction.guild.name}**\n\n"
                               f"To use this bot's features in this server, you need to register with your AniList username.\n\n"
                               f"Use the buttons below to get started:",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="Available Actions",
                    value="📝 **Register** - Connect your AniList account\n"
                          "ℹ️ **Status** - View account information",
                    inline=False
                )
            
            embed.set_footer(text="Your data is secure and can be removed anytime")
            
            # Create interactive view
            view = LoginView(
                user_id=interaction.user.id,
                username=str(interaction.user),
                is_registered=is_registered,
                anilist_username=anilist_username
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            logger.info(f"Login interface sent to {interaction.user.display_name} "
                       f"(registered: {is_registered})")
            
        except Exception as e:
            logger.error(f"Unexpected error in login command for {interaction.user.display_name} "
                        f"(ID: {interaction.user.id}): {e}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ An unexpected error occurred. Please try again later.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ An unexpected error occurred. Please try again later.",
                        ephemeral=True
                    )
            except Exception as follow_e:
                logger.error(f"Failed to send error message: {follow_e}", exc_info=True)

    async def cog_load(self):
        """Called when the cog is loaded."""
        logger.info("Login cog loaded successfully")

    async def cog_unload(self):
        """Called when the cog is unloaded."""
        logger.info("Login cog unloaded")


async def setup(bot: commands.Bot):
    """Set up the Login cog."""
    try:
        await bot.add_cog(Login(bot))
        logger.info("Login cog successfully loaded")
    except Exception as e:
        logger.error(f"Failed to load Login cog: {e}", exc_info=True)
        raise