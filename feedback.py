import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button

CHANNEL_ID = 123456789012345678  # replace with your mod channel ID


class Feedback(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.feedback_threads = {}  # thread_id -> user_id
        self.user_threads = {}      # user_id -> thread_id
        self.pending_users = set()  # users waiting for thread to be opened

    @app_commands.command(name="feedback", description="Submit an idea or report a bug")
    @app_commands.choices(type=[
        app_commands.Choice(name="Ideas", value="ideas"),
        app_commands.Choice(name="Bugs", value="bugs")
    ])
    @app_commands.describe(description="Your idea or bug description", image="Optional image attachment")
    async def feedback(self, interaction: discord.Interaction, type: app_commands.Choice[str], description: str, image: discord.Attachment = None):
        channel = self.bot.get_channel(CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("Target channel not found.", ephemeral=True)
            return

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

        # Send embed + button in ONE message
        view = FeedbackView(self.bot, interaction.user)
        await channel.send(embed=embed, view=view)

        # Track user as pending (they can’t DM until thread is opened)
        self.pending_users.add(interaction.user.id)

        await interaction.response.send_message(
            "✅ Thanks for the submission! We will review it Soon.",
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # === If a mod replies inside a tracked feedback thread ===
        if message.channel.id in self.feedback_threads:
            user_id = self.feedback_threads[message.channel.id]
            user = self.bot.get_user(user_id)
            if not user:
                return

            try:
                content = f"📩 Reply from the moderators:\n{message.content}" if message.content else "📩 Reply from the moderators:"

                files = [await a.to_file() for a in message.attachments] if message.attachments else None
                embeds = message.embeds if message.embeds else None

                await user.send(content, files=files, embeds=embeds)
            except discord.Forbidden:
                await message.channel.send("⚠️ Could not DM the user (they might have DMs disabled).")

        # === If the user replies in DM to the bot ===
        elif isinstance(message.channel, discord.DMChannel):
            user_id = message.author.id

            # If still pending (thread not opened yet)
            if user_id in self.pending_users:
                await message.channel.send("⚠️ Please wait until a moderator opens your feedback thread.")
                return

            # If no active thread
            if user_id not in self.user_threads:
                await message.channel.send("⚠️ You don’t have an active feedback thread with the moderators.")
                return

            thread_id = self.user_threads[user_id]
            thread = self.bot.get_channel(thread_id)
            if not thread:
                await message.channel.send("⚠️ Could not find the feedback thread. It might have been deleted.")
                return

            files = [await a.to_file() for a in message.attachments] if message.attachments else None
            embeds = message.embeds if message.embeds else None

            await thread.send(f"💬 Message from {message.author.mention}:\n{message.content}", files=files, embeds=embeds)

            try:
                await message.add_reaction("✉️")
            except discord.Forbidden:
                pass


class FeedbackView(View):
    def __init__(self, bot, user: discord.User):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user

    @discord.ui.button(label="Open Thread", style=discord.ButtonStyle.primary)
    async def open_thread(self, interaction: discord.Interaction, button: Button):
        feedback_cog = self.bot.get_cog("Feedback")

        # Thread name based on user
        safe_name = self.user.name.lower().replace(" ", "-")
        thread_name = f"feedback-{safe_name}-{self.user.discriminator}"

        thread = await interaction.channel.create_thread(
            name=thread_name,
            message=interaction.message,
            type=discord.ChannelType.public_thread
        )

        feedback_cog.feedback_threads[thread.id] = self.user.id
        feedback_cog.user_threads[self.user.id] = thread.id
        feedback_cog.pending_users.discard(self.user.id)

        await thread.send(
            f"Thread opened for {self.user.mention}'s feedback. Mods, discuss here 👇",
            view=CloseThreadView(self.bot, self.user, thread)
        )
        await interaction.response.send_message(f"✅ Thread created: {thread.mention}", ephemeral=True)


class CloseThreadView(View):
    def __init__(self, bot, user: discord.User, thread: discord.Thread):
        super().__init__(timeout=None)
        self.bot = bot
        self.user = user
        self.thread = thread

    @discord.ui.button(label="Close Thread", style=discord.ButtonStyle.danger)
    async def close_thread(self, interaction: discord.Interaction, button: Button):
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
        feedback_cog = self.bot.get_cog("Feedback")

        feedback_cog.feedback_threads.pop(self.thread.id, None)
        feedback_cog.user_threads.pop(self.user.id, None)
        feedback_cog.pending_users.discard(self.user.id)

        # ✅ Edit interaction BEFORE archiving thread
        await interaction.response.edit_message(
            content="✅ Thread closed, user notified, and action logged.",
            view=None
        )

        await self.thread.send(f"🛑 Thread closed by **{self.mod.display_name}**")

        try:
            await self.user.send(
                "📌 Your feedback thread has been closed by the moderators.\n\n"
                "🙏 Thank you for your input — it really helps us improve! 💡"
            )
        except discord.Forbidden:
            await interaction.channel.send("⚠️ Could not notify the user (they might have DMs disabled).")

        # ✅ Archive + lock after response edit
        await self.thread.edit(archived=True, locked=True)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
    async def confirm_no(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="❎ Close thread cancelled.", view=None)


# Add cog to bot
async def setup(bot):
    await bot.add_cog(Feedback(bot))
