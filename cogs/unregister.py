import discord
from discord import app_commands
from discord.ext import commands
import logging
from pathlib import Path

from config import GUILD_ID
from database import get_user, remove_user

# ------------------------------------------------------
# Logging Setup - Clears on each bot run
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "unregister.log"

# Clear the log file on startup
if LOG_FILE.exists():
    LOG_FILE.unlink()

# Create logger
logger = logging.getLogger("Unregister")
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

logger.info("Unregister cog logging initialized - log file cleared")

# ------------------------------------------------------
# Unregister Cog
# ------------------------------------------------------
class Unregister(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("Unregister cog initialized")
        
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="unregister",
        description="Unregister yourself from the system"
    )
    async def unregister(self, interaction: discord.Interaction):
        logger.info(f"Unregister command invoked by {interaction.user} (ID: {interaction.user.id})")
        
        try:
            user = await get_user(interaction.user.id)
            if not user:
                logger.info(f"Unregister attempt by non-registered user: {interaction.user} (ID: {interaction.user.id})")
                await interaction.response.send_message(
                    "⚠️ You are not registered in the system.", ephemeral=True
                )
                return

            logger.info(f"Confirmed user registration exists for {interaction.user} (ID: {interaction.user.id})")
            # Ask for confirmation via buttons
            view = UnregisterConfirmView(user_id=interaction.user.id)
            await interaction.response.send_message(
                "❗ Are you sure you want to unregister? This action cannot be undone and will remove all your data.",
                view=view,
                ephemeral=True
            )
            logger.info(f"Sent confirmation prompt to {interaction.user} (ID: {interaction.user.id})")
            
        except Exception as e:
            logger.error(f"Exception in unregister command for {interaction.user} (ID: {interaction.user.id}): {e}")
            error_msg = "❌ An error occurred while trying to unregister. Please try again later."
            
            if not interaction.response.is_done():
                await interaction.response.send_message(error_msg, ephemeral=True)
            else:
                await interaction.followup.send(error_msg, ephemeral=True)

    async def cog_load(self):
        """Called when the cog is loaded"""
        logger.info("Unregister cog loaded successfully")

    async def cog_unload(self):
        """Called when the cog is unloaded"""
        logger.info("Unregister cog unloaded")

# ------------------------------------------------------
# Confirmation View
# ------------------------------------------------------
class UnregisterConfirmView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id
        logger.info(f"Created UnregisterConfirmView for user ID: {user_id}")

    @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"User {interaction.user} (ID: {self.user_id}) confirmed unregister action")
        
        try:
            await remove_user(self.user_id)
            logger.info(f"Successfully removed user {interaction.user} (ID: {self.user_id}) from database")
            
            await interaction.response.edit_message(
                content="✅ You have been unregistered successfully. All your data has been removed from the system.",
                view=None
            )
            
        except Exception as e:
            logger.error(f"Failed to remove user {interaction.user} (ID: {self.user_id}) from database: {e}")
            await interaction.response.edit_message(
                content="❌ Failed to unregister. Please try again later or contact support.",
                view=None
            )

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"User {interaction.user} (ID: {self.user_id}) canceled unregister action")
        await interaction.response.edit_message(
            content="❎ Unregister canceled. Your account remains active.", 
            view=None
        )

    async def on_timeout(self):
        """Handle view timeout"""
        logger.info(f"UnregisterConfirmView timed out for user ID: {self.user_id}")
        # Disable all buttons
        for item in self.children:
            item.disabled = True

# ------------------------------------------------------
# Cog Setup
# ------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Unregister(bot))
