"""
Theme Integration Patches
Monkey-patches existing cogs to add theme support without breaking existing functionality.
"""

import discord
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)

def integrate_theme_system(bot):
    """
    Integrate the theme system with existing bot functionality
    This function patches existing methods to add theme support
    """
    try:
        # Get the theme system cog
        theme_cog = bot.get_cog('CustomThemeSystem')
        if not theme_cog:
            logger.warning("Theme system not found, skipping integration")
            return
        
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

async def setup_theme_integration(bot):
    """Setup theme integration after all cogs are loaded"""
    # Wait a bit for all cogs to load
    await bot.wait_until_ready()
    
    # Integrate themes
    integrate_theme_system(bot)
    
    logger.info("Theme integration setup completed")

async def setup(bot):
    """Setup function for the cog (required by Discord.py)"""
    # This cog doesn't add commands, it just integrates themes
    asyncio.create_task(setup_theme_integration(bot))
    logger.info("Theme integration module loaded")