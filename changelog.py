import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime

# IDs you provided
CHANGELOG_CHANNEL_ID = 1420448966423609407
ALLOWED_ROLE_ID = 1420451296304959641

class Changelog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Restrict command to users with the role (hidden for others)
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return any(r.id == ALLOWED_ROLE_ID for r in interaction.user.roles)

    @app_commands.command(name="changelog", description="Publish a new changelog message.")
    @app_commands.describe(
        markdown="Main content of the changelog (supports full markdown).",
        description="Optional description below the changelog (supports full markdown).",
        elaboration="Optional further elaboration (each line auto-prefixed with '-#').",
        elaboration_title="Optional: Custom title for the elaboration section.",
        role="Role to ping (required)."
    )
    async def changelog(
        self,
        interaction: discord.Interaction,
        markdown: str,
        role: discord.Role,
        description: str = None,
        elaboration: str = None,
        elaboration_title: str = "Further Elaboration"
    ):
        # --- Format changelog ---
        formatted_changelog = self.apply_markdown(markdown)

        # --- Build embed ---
        embed = discord.Embed(
            title="📢 New Changelog",
            description=formatted_changelog,
            color=discord.Color.blurple()
        )

        if description:
            embed.add_field(
                name="📝 Description",
                value=self.apply_markdown(description),
                inline=False
            )

        if elaboration:
            embed.add_field(
                name=f"📌 {elaboration_title}",
                value=self.apply_elaboration(elaboration),
                inline=False
            )

        # Author at top
        embed.set_author(
            name=f"Published by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )

        # Footer with date/time
        embed.set_footer(
            text=f"Published on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

        # --- Get channel ---
        channel = self.bot.get_channel(CHANGELOG_CHANNEL_ID)
        if not channel:
            return await interaction.response.send_message(
                "❌ I couldn't find the changelog channel.",
                ephemeral=True
            )

        # --- Send message ---
        await channel.send(content=role.mention, embed=embed)
        await interaction.response.send_message("✅ Changelog published!", ephemeral=True)

    def apply_markdown(self, text: str) -> str:
        """
        Wraps content inside triple backticks, preserving formatting.
        Supports:
        - Bold (**)
        - Italics (*)
        - Bullet points (- item)
        - Numbered lists (1. item)
        - Headings (#, ##, ###)
        - Horizontal divider (---)
        """
        lines = text.splitlines()
        formatted_lines = []

        for line in lines:
            stripped = line.strip()

            # Horizontal divider
            if stripped == "---":
                new_line = "────────────────────────"

            # Headings
            elif stripped.startswith("# "):
                new_line = f"**{stripped[2:].upper()}**"
            elif stripped.startswith("## "):
                new_line = f"**{stripped[3:].upper()}**"
            elif stripped.startswith("### "):
                new_line = f"**{stripped[4:].upper()}**"

            # Bullet point
            elif stripped.startswith("- "):
                new_line = f"- {stripped[2:]}"

            # Numbered list
            elif stripped[:2].isdigit() and stripped[2:3] == ".":
                number = stripped.split(".", 1)[0]
                rest = stripped[len(number) + 1:].strip()
                new_line = f"{number}. {rest}"

            else:
                new_line = stripped

            formatted_lines.append(new_line)

        text = "\n".join(formatted_lines)
        if not text.startswith("```") and not text.endswith("```"):
            text = f"```{text}```"

        return text

    def apply_elaboration(self, text: str) -> str:
        """
        Formats elaboration lines so they always come out like '-# text'
        and are wrapped inside a code block.
        """
        lines = text.splitlines()
        formatted_lines = [f"-# {line.strip()}" for line in lines if line.strip()]
        return f"```{chr(10).join(formatted_lines)}```"

async def setup(bot: commands.Bot):
    await bot.add_cog(Changelog(bot))
