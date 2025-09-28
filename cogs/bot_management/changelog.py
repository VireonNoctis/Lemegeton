import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

# IDs from your setup
CHANGELOG_CHANNEL_ID = 1420500068678762537
ALLOWED_ROLE_ID = 1420451296304959641


def changelog_only():
    """App command check that allows only users with ALLOWED_ROLE_ID
    or users with administrative/manage permissions as a fallback.
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False

        try:
            member = interaction.user if isinstance(interaction.user, discord.Member) else await interaction.guild.fetch_member(interaction.user.id)

            # Role check
            for r in getattr(member, "roles", []):
                if getattr(r, "id", None) == ALLOWED_ROLE_ID:
                    return True

            # Fallback to permission checks
            perms = getattr(member, "guild_permissions", None)
            if perms:
                return perms.manage_roles or perms.manage_guild or perms.administrator
        except Exception:
            return False
        return False

    return app_commands.check(predicate)


class Changelog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @changelog_only()
    @app_commands.command(name="changelog", description="Publish a new changelog message.")
    @app_commands.describe(
        title="Main title of the changelog.",
        description="Main description text.",
        extra_description="Optional extra description for more details.",
        role="Optional role to ping."
    )
    async def changelog(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        extra_description: str = None,
        role: discord.Role = None
    ):
        """Slash command to post a changelog embed in the configured channel."""
        try:
            embed = discord.Embed(
                title="📢 New Changelog",
                color=discord.Color.blurple()
            )

            # Main Title
            embed.add_field(
                name="📝 Title",
                value=title,
                inline=False
            )

            # Description
            embed.add_field(
                name="📖 Description",
                value=description,
                inline=False
            )

            # Extra Description (optional)
            if extra_description:
                embed.add_field(
                    name="📌 Extra Description",
                    value=extra_description,
                    inline=False
                )

            # Author info
            embed.set_author(
                name=f"Published by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )

            # Footer
            embed.set_footer(
                text=f"📅 Published on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            )

            # Send to channel
            channel = self.bot.get_channel(CHANGELOG_CHANNEL_ID)
            if not channel:
                await interaction.response.send_message("❌ Could not find changelog channel.", ephemeral=True)
                return

            content = role.mention if role else None
            await channel.send(content=content, embed=embed)

            await interaction.response.send_message("✅ Changelog published!", ephemeral=True)

        except Exception as e:
            await interaction.response.send_message("❌ Failed to publish changelog.", ephemeral=True)
            raise e

    @changelog.error
    async def changelog_error(self, interaction: discord.Interaction, error):
        """Error handler for /changelog command."""
        from discord import app_commands as _app
        if isinstance(error, (_app.MissingRole, _app.MissingPermissions, _app.CheckFailure)):
            try:
                await interaction.response.send_message("❌ You don’t have permission to use this command.", ephemeral=True)
            except Exception:
                pass
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Changelog(bot))
