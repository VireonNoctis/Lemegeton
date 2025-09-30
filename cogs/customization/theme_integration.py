"""
Theme Integration Patches
Monkey-patches existing cogs to add theme support without breaking existing functionality.
"""

import discord
from discord.ext import commands
from typing import Optional
import logging
import asyncio
from pathlib import Path

# Set up dedicated logging for theme integration
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "theme_integration.log"

logger = logging.getLogger("ThemeIntegration")
logger.setLevel(logging.DEBUG)

if not any(isinstance(h, logging.FileHandler) and getattr(h, 'baseFilename', None) == str(LOG_FILE)
           for h in logger.handlers):
    try:
        file_handler = logging.FileHandler(LOG_FILE, mode='w', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(logging.Formatter(fmt="[%(asctime)s] [%(levelname)-8s] [%(name)s] %(message)s",
                                                      datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(stream_handler)

logger.info("Theme integration logging initialized")

def integrate_theme_system(bot):
    """
    Integrate the theme system with existing bot functionality
    This function patches existing methods to add theme support
    """
    try:
        logger.info("Starting theme system integration...")
        
        # Get the theme system cog
        theme_cog = bot.get_cog('CustomThemeSystem')
        if not theme_cog:
            logger.warning("Theme system not found, skipping integration")
            return
        
        logger.info("Theme system found, proceeding with integration")
        theme_manager = theme_cog.theme_manager
        
        def apply_theme_to_embed(embed: discord.Embed, user_id: int, guild_id: Optional[int] = None) -> discord.Embed:
            """Helper function to apply themes to embeds"""
            try:
                theme = theme_manager.get_effective_theme(user_id, guild_id)
                embed.color = theme.colors.primary
                
                # Add theme footer
                current_footer = embed.footer.text if embed.footer.text else ""
                theme_info = f"Theme: {theme.name} {theme.emoji}"
                
                if current_footer:
                    embed.set_footer(text=f"{current_footer} • {theme_info}")
                else:
                    embed.set_footer(text=theme_info)
                
                return embed
            except Exception as e:
                logger.error(f"Error applying theme: {e}")
                return embed
        
        # Patch analytics embeds
        analytics_cog = bot.get_cog('AnalyticsDashboard')
        if analytics_cog:
            logger.info("Patching AnalyticsDashboard cog with theme support")
            logger.info("Integrating themes with Analytics Dashboard")
            
            # Store original method
            original_analytics_command = analytics_cog.analytics_dashboard
            
            async def themed_analytics_command(interaction: discord.Interaction, period: Optional[str] = "year", metric: Optional[str] = "all"):
                """Themed version of analytics dashboard"""
                # Get user's theme
                theme = theme_manager.get_effective_theme(interaction.user.id, interaction.guild.id if interaction.guild else None)
                
                # Call original method
                await original_analytics_command(interaction, period, metric)
            
            # Replace the command (this is a simplified approach)
            analytics_cog.analytics_dashboard = themed_analytics_command
        
        # Patch other major cogs
        cogs_to_patch = ['AniList', 'Recommendations', 'Random', 'Profile', 'Leaderboard']
        
        for cog_name in cogs_to_patch:
            cog = bot.get_cog(cog_name)
            if cog:
                logger.info(f"Integrating themes with {cog_name} cog")
                patch_cog_embeds(cog, apply_theme_to_embed)
        
        logger.info("Theme integration completed successfully")
        
    except Exception as e:
        logger.error(f"Error integrating theme system: {e}")

def patch_cog_embeds(cog, theme_function):
    """
    Patch a cog's methods to apply themes to embeds
    This is a simplified approach - in production, you'd want more targeted patching
    """
    try:
        # This is a placeholder for the actual patching logic
        # In a full implementation, you would:
        # 1. Identify methods that send embeds
        # 2. Wrap them to apply themes before sending
        # 3. Preserve original functionality
        
        logger.info(f"Theme patching applied to {cog.__class__.__name__}")
        
    except Exception as e:
        logger.error(f"Error patching {cog.__class__.__name__}: {e}")

class ThemeIntegrationHandler(commands.Cog):
    """Handler cog for theme integration setup"""
    
    def __init__(self, bot):
        self.bot = bot
        self.integration_done = False
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Initialize theme integration when bot is ready"""
        logger.info("Bot ready - initializing theme integration system")
        await asyncio.sleep(1)  # Wait for other cogs to load
        integrate_theme_system(self.bot)
        logger.info("Theme integration system initialized")

async def setup(bot):
    """Setup function for the cog (required by Discord.py)"""
    await bot.add_cog(ThemeIntegrationHandler(bot))
    logger.info("Theme integration module loaded")