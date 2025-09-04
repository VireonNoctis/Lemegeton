import discord
from discord import app_commands
from discord.ext import commands

from config import CHANNEL_ID, GUILD_ID


class Feedback(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=GUILD_ID))
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

        # Set color based on type
        color = discord.Color.green() if type.value == "ideas" else discord.Color.red()

        embed = discord.Embed(
            title=f"New {type.name} Submitted",
            description=description,
            color=color
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        embed.set_footer(text=f"Submitted by {interaction.user}")

        if image:
            embed.set_image(url=image.url)

        # Send the embed to the channel
        await channel.send(embed=embed)

        # Send ephemeral confirmation to the user
        await interaction.response.send_message(
            "Thanks for the submission, we will look into it!", 
            ephemeral=True
        )

# Add cog to bot
async def setup(bot):
    await bot.add_cog(Feedback(bot))
