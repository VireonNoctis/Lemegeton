import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button
import logging
from pathlib import Path
from config import CHANNEL_ID

# ------------------------------------------------------
# Logging Setup - Auto-clearing
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "feedback.log"

# Clear the log file on startup
if LOG_FILE.exists():
    LOG_FILE.unlink()

# Setup logger
logger = logging.getLogger("feedback")
logger.setLevel(logging.INFO)

# File handler
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)

# Add handler if not already added
if not logger.handlers:
    logger.addHandler(file_handler)

logger.info("Feedback cog logging initialized - log file cleared")


class Feedback(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.feedback_threads = {}  # thread_id -> user_id
        self.user_threads = {}      # user_id -> thread_id
        self.pending_users = set()  # users waiting for thread to be opened
        logger.info("Feedback cog initialized")

    async def _prepare_message_data(self, message: discord.Message):
        """Helper method to prepare files and embeds from a message."""
        files = None
        embeds = None
        
        if message.attachments:
            try:
                files = [await a.to_file() for a in message.attachments]
            except Exception as e:
                logger.warning(f"Failed to process attachments: {e}")
                
        if message.embeds:
            embeds = message.embeds
            
        return files, embeds

    @app_commands.command(name="feedback", description="Submit an idea or report a bug")
    @app_commands.choices(type=[
        app_commands.Choice(name="Ideas", value="ideas"),
        app_commands.Choice(name="Bugs", value="bugs")
    ])
    @app_commands.describe(description="Your idea or bug description", image="Optional image attachment")
    async def feedback(self, interaction: discord.Interaction, type: app_commands.Choice[str], description: str, image: discord.Attachment = None):
        """Handle feedback submission from users."""
        user_info = f"{interaction.user.display_name} (ID: {interaction.user.id})"
        logger.info(f"Feedback submission started by {user_info} - Type: {type.name}")
        
        try:
            channel = self.bot.get_channel(CHANNEL_ID)
            if not channel:
                logger.error(f"Target channel {CHANNEL_ID} not found")
                await interaction.response.send_message("❌ Target channel not found.", ephemeral=True)
                return

            # Create embed
            color = discord.Color.green() if type.value == "ideas" else discord.Color.red()
            embed = discord.Embed(
                title=f"New {type.name} Submitted",
                description=description,
                color=color
            )
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            embed.set_footer(text=f"Submitted by {interaction.user}")

            if image:
                embed.set_image(url=image.url)
                logger.info(f"Image attachment included in feedback from {user_info}")

            # Send embed + button in ONE message
            view = FeedbackView(self.bot, interaction.user)
            message = await channel.send(embed=embed, view=view)

            # Track user as pending
            self.pending_users.add(interaction.user.id)
            logger.info(f"Feedback submitted successfully by {user_info} in message {message.id}")

            await interaction.response.send_message(
                "✅ Thanks for the submission! We will review it soon.",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error in feedback submission by {user_info}: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while submitting your feedback. Please try again later.",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle DM communication between mods and users."""
        if message.author.bot:
            return

        # === If a mod replies inside a tracked feedback thread ===
        if message.channel.id in self.feedback_threads:
            user_id = self.feedback_threads[message.channel.id]
            user = self.bot.get_user(user_id)
            if not user:
                logger.warning(f"Could not find user {user_id} for thread {message.channel.id}")
                return

            logger.info(f"Mod reply in thread {message.channel.id} for user {user.display_name}")
            try:
                content = f"📩 Reply from the moderators:\n{message.content}" if message.content else "📩 Reply from the moderators:"
                
                # Handle attachments and embeds
                files, embeds = await self._prepare_message_data(message)

                await user.send(content, files=files, embeds=embeds)
                logger.info(f"Successfully forwarded mod reply to {user.display_name}")
                
            except discord.Forbidden:
                logger.warning(f"Could not DM user {user.display_name} - DMs disabled")
                await message.channel.send("⚠️ Could not DM the user (they might have DMs disabled).")

        # === If the user replies in DM to the bot ===
        elif isinstance(message.channel, discord.DMChannel):
            user_id = message.author.id
            user_display = message.author.display_name

            # If still pending (thread not opened yet)
            if user_id in self.pending_users:
                logger.info(f"User {user_display} tried to reply before thread opened")
                await message.channel.send("⚠️ Please wait until a moderator opens your feedback thread.")
                return

            # If no active thread
            if user_id not in self.user_threads:
                logger.info(f"User {user_display} sent DM without active thread")
                await message.channel.send("⚠️ You don't have an active feedback thread with the moderators.")
                return

            thread_id = self.user_threads[user_id]
            thread = self.bot.get_channel(thread_id)
            if not thread:
                logger.warning(f"Thread {thread_id} not found for user {user_display}")
                await message.channel.send("⚠️ Could not find the feedback thread. It might have been deleted.")
                return

            logger.info(f"Forwarding user DM from {user_display} to thread {thread_id}")
            try:
                # Handle attachments and embeds
                files, embeds = await self._prepare_message_data(message)

                await thread.send(f"💬 Message from {message.author.mention}:\n{message.content}", files=files, embeds=embeds)
                
                # Acknowledge receipt
                try:
                    await message.add_reaction("✉️")
                    logger.debug(f"Added reaction to message from {user_display}")
                except discord.Forbidden:
                    logger.debug(f"Could not add reaction to message from {user_display}")
                    
            except Exception as e:
                logger.error(f"Error forwarding message from {user_display}: {e}")


class FeedbackView(View):
    def __init__(self, bot, user: discord.User):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user

    @discord.ui.button(label="Open Thread", style=discord.ButtonStyle.primary)
    async def open_thread(self, interaction: discord.Interaction, button: Button):
        """Open a feedback thread for moderation discussion."""
        logger.info(f"Opening thread for feedback from {self.user.display_name}")
        
        try:
            feedback_cog = self.bot.get_cog("Feedback")
            if not feedback_cog:
                logger.error("Feedback cog not found")
                await interaction.response.send_message("❌ Feedback system not available.", ephemeral=True)
                return

            # Create thread name (safe for Discord)
            safe_name = "".join(c for c in self.user.display_name if c.isalnum() or c in '-_').lower()
            safe_name = safe_name[:20] if safe_name else "user"  # Limit length
            thread_name = f"feedback-{safe_name}-{self.user.id}"

            # Create the thread
            thread = await interaction.channel.create_thread(
                name=thread_name,
                message=interaction.message,
                type=discord.ChannelType.public_thread
            )

            # Track the thread
            feedback_cog.feedback_threads[thread.id] = self.user.id
            feedback_cog.user_threads[self.user.id] = thread.id
            feedback_cog.pending_users.discard(self.user.id)

            logger.info(f"Thread {thread.id} created for {self.user.display_name}")

            # Send initial message in thread
            await thread.send(
                f"Thread opened for {self.user.mention}'s feedback. Mods, discuss here 👇",
                view=CloseThreadView(self.bot, self.user, thread)
            )
            
            await interaction.response.send_message(f"✅ Thread created: {thread.mention}", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error opening thread for {self.user.display_name}: {e}")
            await interaction.response.send_message("❌ Failed to create thread.", ephemeral=True)


class CloseThreadView(View):
    def __init__(self, bot, user: discord.User, thread: discord.Thread):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.thread = thread

    @discord.ui.button(label="Close Thread", style=discord.ButtonStyle.danger)
    async def close_thread(self, interaction: discord.Interaction, button: Button):
        """Initiate thread closure confirmation."""
        logger.info(f"Close thread requested for {self.user.display_name} by {interaction.user.display_name}")
        
        await interaction.response.send_message(
            "⚠️ Are you sure you want to close this thread?",
            view=ConfirmCloseView(self.bot, self.user, self.thread, interaction.user),
            ephemeral=True
        )


class ConfirmCloseView(View):
    def __init__(self, bot, user: discord.User, thread: discord.Thread, mod: discord.User):
        super().__init__(timeout=30)
        self.bot = bot
        self.user = user
        self.thread = thread
        self.mod = mod

    @discord.ui.button(label="✅ Yes, close it", style=discord.ButtonStyle.danger)
    async def confirm_yes(self, interaction: discord.Interaction, button: Button):
        """Confirm and close the feedback thread."""
        logger.info(f"Thread {self.thread.id} being closed by {self.mod.display_name}")
        
        try:
            feedback_cog = self.bot.get_cog("Feedback")
            if feedback_cog:
                # Clean up tracking
                feedback_cog.feedback_threads.pop(self.thread.id, None)
                feedback_cog.user_threads.pop(self.user.id, None)
                feedback_cog.pending_users.discard(self.user.id)

            # Edit interaction response BEFORE archiving
            await interaction.response.edit_message(
                content="✅ Thread closed, user notified, and action logged.",
                view=None
            )

            # Log thread closure
            await self.thread.send(f"🛑 Thread closed by **{self.mod.display_name}**")

            # Notify user
            try:
                await self.user.send(
                    "📌 Your feedback thread has been closed by the moderators.\n\n"
                    "🙏 Thank you for your input — it really helps us improve! 💡"
                )
                logger.info(f"Successfully notified {self.user.display_name} of thread closure")
            except discord.Forbidden:
                logger.warning(f"Could not notify {self.user.display_name} of thread closure")
                await self.thread.send("⚠️ Could not notify the user (they might have DMs disabled).")

            # Archive and lock the thread
            await self.thread.edit(archived=True, locked=True)
            logger.info(f"Thread {self.thread.id} archived and locked")
            
        except Exception as e:
            logger.error(f"Error closing thread {self.thread.id}: {e}")

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def confirm_no(self, interaction: discord.Interaction, button: Button):
        """Cancel thread closure."""
        logger.info(f"Thread closure cancelled by {interaction.user.display_name}")
        await interaction.response.edit_message(content="❎ Close thread cancelled.", view=None)

    async def on_timeout(self):
        """Handle confirmation timeout."""
        logger.info("Thread close confirmation timed out")


# Add cog to bot
async def setup(bot):
    await bot.add_cog(Feedback(bot))