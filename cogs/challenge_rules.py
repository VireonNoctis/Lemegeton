import discord
from discord import app_commands
from discord.ext import commands
from database import set_challenge_rules, get_challenge_rules  # These are placeholders in database.py
import logging

# ------------------------------------------------------
# Simple Logging Setup
# ------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ChallengeRulesCog")

# ------------------------------------------------------
# Challenge Rules Cog
# ------------------------------------------------------
class ChallengeRules(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("ChallengeRules cog loaded")

    @app_commands.command(
        name="challenge-rules-create",
        description="Administrator: Create or update the challenge rules"
    )
    @app_commands.describe(rules="The rules text to display for the challenge")
    async def create_rules(self, interaction: discord.Interaction, rules: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You do not have permission to create challenge rules.",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} attempted to create challenge rules without permission")
            return

        try:
            await set_challenge_rules(rules)  # Placeholder will not fail
            await interaction.response.send_message(
                "✅ Challenge rules updated successfully!",
                ephemeral=True
            )
            logger.info(f"User {interaction.user.id} updated challenge rules successfully")
        except Exception as e:
            logger.exception(f"Failed to set challenge rules by user {interaction.user.id}: {e}")
            await interaction.response.send_message(
                "❌ Failed to update challenge rules. Please try again later.",
                ephemeral=True
            )

    @app_commands.command(
        name="challenge-rules",
        description="View the general challenge rules"
    )
    async def view_rules(self, interaction: discord.Interaction):
        try:
            rules_text = await get_challenge_rules()
            logger.info(f"User {interaction.user.id} viewed challenge rules")
        except Exception as e:
            logger.exception(f"Failed to fetch challenge rules for user {interaction.user.id}: {e}")
            rules_text = None

        if not rules_text:
            rules_text = "No rules have been set yet. Administrators can set them using `/challenge-rules-create`"

        embed = discord.Embed(
            title="📜 Manga Challenge Rules",
            description="**Follow these rules when participating in any manga challenge!**",
            colour=discord.Colour.purple()
        )

        embed.add_field(
            name="📝 Progress Updates",
            value=(
                "- Name which trial it is (e.g. *Trial*, *Stage 1*) and resend your updated progress message when finished.\n"
                "- Notify **@kyerstorm** when done.\n"
                "- Use one of the following statuses:\n"
                "`Reread` • `Completed` • `Caught Up` • `In-Progress` • `Skipped` • `Paused` • `Dropped` • `Not Started`\n\n"
                "**Status Definitions:**\n"
                "• **Completed** → Fully read a finished work.\n"
                "• **Caught-Up** → Reached the latest chapter of an ongoing work.\n"
                "• **In-Progress** → Currently reading.\n"
                "• **Skipped** → Previously read, not rereading.\n"
                "• **Reread** → Reread a previously completed work.\n"
                "• **Dropped** → Read **≥25 chapters** and chose not to continue."
            ),
            inline=False
        )

        embed.add_field(
            name="📌 General Rules",
            value=(
                "- Cannot complain or request changes if absent during challenge discussions.\n"
                "- **70%** of titles must be **Completed / Caught Up / Skipped**.\n"
                "- **30%** of titles can be **Dropped**.\n"
                "- Must read **≥25 chapters** before marking as Dropped.\n"
                "- No time limits unless stated.\n"
                "- Challenge entries are decided via **community voting**."
            ),
            inline=False
        )

        embed.add_field(
            name="👥 Community Challenge Rules",
            value=(
                "- No points awarded while a challenge is marked **Awaiting Approval**, but you may start it.\n"
                "- Cannot suggest or use titles already in other challenges.\n"
                "[**📄 Full Title List Here**](https://docs.google.com/spreadsheets/d/11WFnWLsLB5aSCcSuPTTfxBbPc105VgTXPpI5ePnxy54/edit?usp=sharing)\n"
                "- Check challenge pins — rules may vary per challenge."
            ),
            inline=False
        )

        embed.add_field(
            name="🏆 Leaderboard",
            value=(
                "- Use `/show \"Manga Challenge Leaderboard\"` to view rankings.\n"
                "- Updated on the **1st of each month**.\n"
                "- **Important:** Progress edits won't count unless you notify @kyerstorm."
            ),
            inline=False
        )

        embed.add_field(
            name="📚 Manga Point System",
            value=(
                "- **20** Grimoires → 100% completed\n"
                "- **10** Grimoires → 70% completed\n"
                "- **7** Grimoires → Reread (only if ≥1/3 already read)\n"
                "- **5** Grimoires → Per manga completed\n"
                "- **2** Grimoires → Per skip\n"
                "- **1** Grimoire → Per drop"
            ),
            inline=False
        )

        embed.add_field(
            name="📖 CN/KN Novel Point System",
            value=(
                "- **20** Grimoires → 100% completed\n"
                "- **15** Grimoires → 70% completed\n"
                "- **20** Grimoires → Per novel completed (**>2000 chapters**)\n"
                "- **15** Grimoires → Per novel completed (**1501–2000 chapters**)\n"
                "- **10** Grimoires → Per novel completed (**501–1500 chapters**)\n"
                "- **5** Grimoires → Per novel completed (**<500 chapters**)\n"
                "- **3** Grimoires → Per skip\n"
                "- **1** Grimoire → Per drop"
            ),
            inline=False
        )

        embed.set_footer(text="📌 Always double-check challenge pins for specific rules!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ------------------------------------------------------
# Cog Setup
# ------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(ChallengeRules(bot))
