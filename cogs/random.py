import discord
from discord.ext import commands
from discord import app_commands
import random

<<<<<<< HEAD
from config import GUILD_ID
=======
>>>>>>> 8131418acf03dcad9a033a81f4e956fefafa2a4b
from helpers.media_helper import fetch_random_media


class Random(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

<<<<<<< HEAD
    @app_commands.guilds(discord.Object(id=GUILD_ID))
=======
>>>>>>> 8131418acf03dcad9a033a81f4e956fefafa2a4b
    @app_commands.command(
        name="random",
        description="🎲 Get a completely random Anime, Manga, Light Novel, or All suggestion from AniList"
    )
    @app_commands.describe(media_type="Choose the type of media to get a random suggestion for")
    @app_commands.choices(media_type=[
        app_commands.Choice(name="Anime", value="ANIME"),
        app_commands.Choice(name="Manga", value="MANGA"),
        app_commands.Choice(name="Light Novel", value="LN"),
        app_commands.Choice(name="All", value="ALL"),
    ])
    async def random_media(self, interaction: discord.Interaction, media_type: app_commands.Choice[str]):
        await interaction.response.defer()

        chosen_type = media_type.value
        if chosen_type == "ALL":
            chosen_type = random.choice(["ANIME", "MANGA", "LN"])

        embed = await fetch_random_media(chosen_type)
        if not embed:
            await interaction.followup.send("⚠️ Could not fetch a random title. Try again!", ephemeral=True)
            return

        # 🎨 Random color each time
        embed.color = discord.Color(random.randint(0, 0xFFFFFF))

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Random(bot))
