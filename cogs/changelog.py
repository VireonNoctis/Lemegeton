import discord
from discord import app_commands
from discord.ext import commands
from pathlib import Path
import re

class Changelog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.changelog_path = Path("changelog.txt")  # Ensure this file exists in the root directory

    @app_commands.command(name="changelog", description="View the latest bot updates and changes")
    async def changelog(self, interaction: discord.Interaction):
        if not self.changelog_path.exists():
            await interaction.response.send_message(
                "⚠️ No changelog found. Please ensure `changelog.txt` exists in the root directory.",
                ephemeral=True
            )
            return

        # Read the changelog file
        with open(self.changelog_path, "r", encoding="utf-8") as file:
            content = file.read()

        # --- Extract the latest version only ---
        latest_version_match = re.search(
            r"(Version:\s*\d+\.\d+\.\d+.*?)(?=^Version:|\Z)", 
            content, re.DOTALL | re.MULTILINE
        )
        if not latest_version_match:
            await interaction.response.send_message("⚠️ Could not find any version in the changelog.", ephemeral=True)
            return

        latest_version_text = latest_version_match.group(1).strip()

        # --- Extract version number for title ---
        version_number_match = re.search(r"Version:\s*(\d+\.\d+\.\d+)", latest_version_text)
        version_number = version_number_match.group(1) if version_number_match else "Unknown"

        # --- Parse sections ---
        sections = {
            "added": "",
            "changed": "",
            "removed": "",
            "planned": "",
            "requested": "",
            "bugs": ""
        }
        current_section = None

        for line in latest_version_text.splitlines():
            line_strip = line.strip().lower()
            if line_strip.startswith("added:"):
                current_section = "added"
                continue
            elif line_strip.startswith("changed:"):
                current_section = "changed"
                continue
            elif line_strip.startswith("removed:"):
                current_section = "removed"
                continue
            elif line_strip.startswith("planned:"):
                current_section = "planned"
                continue
            elif line_strip.startswith("requested:"):
                current_section = "requested"
                continue
            elif line_strip.startswith("bugs:") or line_strip.startswith("bug:"):
                current_section = "bugs"
                continue

            # Keep bullet points and preserve formatting
            if current_section and line.strip():
                sections[current_section] += line + "\n"

        # --- Build embed ---
        embed = discord.Embed(
            title=f"📜 Manga Updater Bot — Changelog v{version_number}",
            color=discord.Color.blurple()
        )

        max_len = 1024
        for section, name_emoji in [
            ("added","✅ Added"),
            ("changed","🔄 Changed"),
            ("removed","❌ Removed"),
            ("planned","🛠 Planned"),
            ("requested","📬 Requested"),
            ("bugs","🐞 Bugs")
        ]:
            if sections[section]:
                value = sections[section].strip()
                # Replace simple "-" bullets with actual bullets for better readability
                value = re.sub(r"^-", "•", value, flags=re.MULTILINE)
                if len(value) > max_len:
                    value = value[:max_len-3] + "..."
                embed.add_field(name=name_emoji, value=f"```{value}```", inline=False)

        embed.set_footer(text="Manga Updater Bot • Only latest version shown")
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Changelog(bot))
