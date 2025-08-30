import discord
from discord import app_commands
from discord.ext import commands
from config import GUILD_ID
from database import get_user, remove_user  # Ensure remove_user is async
import logging
from typing import Optional

# ------------------------------------------------------
# Logging Setup
# ------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("UnregisterCog")

# ------------------------------------------------------
# Unregister Cog
# ------------------------------------------------------
class Unregister(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.command(
        name="unregister",
        description="Unregister yourself from the system"
    )
    async def unregister(self, interaction: discord.Interaction):
        logger.info(f"User {interaction.user.id} initiated /unregister")
        try:
            user: Optional[dict] = await get_user(interaction.user.id)
            if not user:
                logger.info(f"Unregister attempt for non-registered user {interaction.user.id}")
                await interaction.response.send_message(
                    "⚠️ You are not registered.", ephemeral=True
                )
                return

            # Ask for confirmation via buttons
            view = UnregisterConfirmView(user_id=interaction.user.id)
            await interaction.response.send_message(
                "❗ Are you sure you want to unregister? This action cannot be undone.",
                view=view,
                ephemeral=True
            )
        except Exception as e:
            logger.exception(f"Error in /unregister for user {interaction.user.id}")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ An error occurred while trying to unregister. Please try again later.",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ An error occurred while trying to unregister. Please try again later.",
                    ephemeral=True
                )

# ------------------------------------------------------
# Confirmation View
# ------------------------------------------------------
class UnregisterConfirmView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=60)
        self.user_id = user_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await remove_user(self.user_id)
            logger.info(f"User {self.user_id} successfully unregistered")
            await interaction.response.edit_message(
                content="✅ You have been unregistered successfully.",
                view=None
            )
        except Exception as e:
            logger.exception(f"Error removing user {self.user_id}")
            await interaction.response.edit_message(
                content="❌ Failed to unregister. Please try again later.",
                view=None
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        logger.info(f"User {self.user_id} canceled unregister")
        await interaction.response.edit_message(
            content="❎ Unregister canceled.", view=None
        )

# ------------------------------------------------------
# Cog Setup
# ------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(Unregister(bot))
