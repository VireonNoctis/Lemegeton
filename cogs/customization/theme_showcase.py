"""
Theme Showcase and Testing System
Interactive views for theme preview and advanced theme management.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import List, Optional, Dict, Any
import asyncio
import logging

logger = logging.getLogger(__name__)

class ThemePreviewView(discord.ui.View):
    """Interactive view for previewing themes"""
    
    def __init__(self, theme_manager, user_id: int, themes: List, current_index: int = 0):
        super().__init__(timeout=300.0)
        self.theme_manager = theme_manager
        self.user_id = user_id
        self.themes = themes
        self.current_index = current_index
        self.max_index = len(themes) - 1
        
        # Update button states
        self._update_buttons()
    
    def _update_buttons(self):
        """Update button states based on current position"""
        # Previous button
        prev_button = self.children[0]
        prev_button.disabled = self.current_index == 0
        
        # Next button  
        next_button = self.children[1]
        next_button.disabled = self.current_index >= self.max_index
        
        # Apply button
        apply_button = self.children[2]
        apply_button.disabled = False
    
    def _get_preview_embed(self) -> discord.Embed:
        """Create preview embed for current theme"""
        if not self.themes:
            return discord.Embed(title="❌ No Themes", color=0xFF0000)
        
        theme = self.themes[self.current_index]
        
        embed = discord.Embed(
            title=f"🎨 Theme Preview: {theme.name}",
            description=f"**Description:** {theme.description}\n"
                       f"**Category:** {theme.category.value.replace('_', ' ').title()}\n"
                       f"**Emoji:** {theme.emoji}",
            color=theme.colors.primary
        )
        
        if theme.character_source:
            embed.add_field(
                name="📺 Character Source",
                value=theme.character_source,
                inline=True
            )
        
        # Color showcase
        color_info = f"**Primary:** #{theme.colors.primary:06X}\n"
        color_info += f"**Secondary:** #{theme.colors.secondary:06X}\n"
        color_info += f"**Accent:** #{theme.colors.accent:06X}"
        
        embed.add_field(
            name="🎨 Colors",
            value=color_info,
            inline=True
        )
        
        embed.add_field(
            name="📍 Navigation",
            value=f"Theme {self.current_index + 1} of {len(self.themes)}",
            inline=False
        )
        
        # Sample content to show theme in action
        embed.add_field(
            name="📖 Sample Content",
            value="**Title:** Attack on Titan\n"
                  "**Status:** Completed\n"
                  "**Score:** 9/10\n"
                  "**Progress:** 139/139 chapters",
            inline=False
        )
        
        embed.set_footer(text=f"Theme: {theme.name} {theme.emoji}")
        
        return embed
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary)
    async def previous_theme(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous theme"""
        if self.current_index > 0:
            self.current_index -= 1
            self._update_buttons()
            
            embed = self._get_preview_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.secondary)
    async def next_theme(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next theme"""
        if self.current_index < self.max_index:
            self.current_index += 1
            self._update_buttons()
            
            embed = self._get_preview_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="✅ Apply Theme", style=discord.ButtonStyle.primary)
    async def apply_theme(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Apply the current theme"""
        if not self.themes:
            await interaction.response.defer()
            return
        
        theme = self.themes[self.current_index]
        success = self.theme_manager.set_user_theme(self.user_id, theme.id)
        
        if success:
            embed = discord.Embed(
                title=f"✅ Theme Applied: {theme.name}",
                description=f"🎉 Your theme has been set to **{theme.name}**!\n"
                           f"All your embeds will now use this beautiful theme.",
                color=theme.colors.primary
            )
            embed.set_footer(text=f"Theme: {theme.name} {theme.emoji}")
            
            # Disable all buttons
            for child in self.children:
                child.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ Failed to apply theme.", ephemeral=True)
    
    @discord.ui.button(label="🎲 Random", style=discord.ButtonStyle.secondary)
    async def random_theme(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Jump to a random theme"""
        import random
        new_index = random.randint(0, self.max_index)
        
        if new_index != self.current_index:
            self.current_index = new_index
            self._update_buttons()
            
            embed = self._get_preview_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label="❌ Close", style=discord.ButtonStyle.danger)
    async def close_preview(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the preview"""
        embed = discord.Embed(
            title="🎨 Theme Preview Closed",
            description="Theme preview session ended.",
            color=0x666666
        )
        
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)

class ThemeCategorySelect(discord.ui.Select):
    """Dropdown for selecting theme categories"""
    
    def __init__(self, theme_manager):
        self.theme_manager = theme_manager
        
        options = [
            discord.SelectOption(
                label="All Themes",
                description="Browse all available themes",
                emoji="🎨",
                value="all"
            ),
            discord.SelectOption(
                label="Classic",
                description="Traditional color themes",
                emoji="🔵",
                value="classic"
            ),
            discord.SelectOption(
                label="Anime Characters",
                description="Themes inspired by anime characters",
                emoji="👤",
                value="anime_character"
            ),
            discord.SelectOption(
                label="Seasonal",
                description="Themes that change with the seasons",
                emoji="🌸",
                value="seasonal"
            ),
            discord.SelectOption(
                label="Mood-based",
                description="Themes that match your mood",
                emoji="😊",
                value="mood"
            ),
            discord.SelectOption(
                label="Gradient",
                description="Beautiful gradient color schemes",
                emoji="🌈",
                value="gradient"
            ),
            discord.SelectOption(
                label="Neon",
                description="Bright neon themes",
                emoji="💫",
                value="neon"
            )
        ]
        
        super().__init__(
            placeholder="Choose a theme category to preview...",
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        """Handle category selection"""
        try:
            from .themes import ThemeCategory
            
            if self.values[0] == "all":
                themes = list(self.theme_manager.themes.values())
            else:
                category = ThemeCategory(self.values[0])
                themes = self.theme_manager.get_themes_by_category(category)
            
            if not themes:
                embed = discord.Embed(
                    title="❌ No Themes Found",
                    description=f"No themes available in category: {self.values[0]}",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Create preview view
            view = ThemePreviewView(self.theme_manager, interaction.user.id, themes)
            embed = view._get_preview_embed()
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Error in theme category callback: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while loading themes.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class ThemeCategoryView(discord.ui.View):
    """View for theme category selection"""
    
    def __init__(self, theme_manager):
        super().__init__(timeout=300.0)
        self.add_item(ThemeCategorySelect(theme_manager))

class AdvancedThemeCommands(commands.Cog):
    """Advanced theme management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="theme_preview", description="Interactive theme preview and testing")
    async def theme_preview(self, interaction: discord.Interaction):
        """Open interactive theme preview"""
        try:
            theme_cog = self.bot.get_cog('CustomThemeSystem')
            if not theme_cog:
                embed = discord.Embed(
                    title="❌ Theme System Not Available",
                    description="The theme system is not currently loaded.",
                    color=0xFF0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🎨 Theme Preview & Testing",
                description="Choose a category below to preview and test themes!\n\n"
                           "🖱️ **How to use:**\n"
                           "• Select a category from the dropdown\n"
                           "• Navigate through themes with the buttons\n"
                           "• Preview how embeds look with each theme\n"
                           "• Apply themes you like instantly",
                color=0x02A9FF
            )
            
            embed.add_field(
                name="🌟 Features",
                value="• Live theme preview\n• Interactive navigation\n• Instant theme application\n• Random theme discovery",
                inline=True
            )
            
            embed.add_field(
                name="📊 Available",
                value=f"• {len(theme_cog.theme_manager.themes)} total themes\n• 7 different categories\n• Character-based themes\n• Seasonal themes",
                inline=True
            )
            
            view = ThemeCategoryView(theme_cog.theme_manager)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        except Exception as e:
            logger.error(f"Error in theme_preview command: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while opening theme preview.",
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="theme_showcase", description="Showcase all available themes")
    @app_commands.describe(category="Filter themes by category")
    @app_commands.choices(category=[
        app_commands.Choice(name="All Categories", value="all"),
        app_commands.Choice(name="Classic", value="classic"),
        app_commands.Choice(name="Anime Characters", value="anime_character"),
        app_commands.Choice(name="Seasonal", value="seasonal"),
        app_commands.Choice(name="Mood-based", value="mood"),
        app_commands.Choice(name="Gradient", value="gradient"),
        app_commands.Choice(name="Neon", value="neon")
    ])
    async def theme_showcase(self, interaction: discord.Interaction, category: str = "all"):
        """Show a comprehensive showcase of available themes"""
        try:
            await interaction.response.defer()
            
            theme_cog = self.bot.get_cog('CustomThemeSystem')
            if not theme_cog:
                embed = discord.Embed(
                    title="❌ Theme System Not Available",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed)
                return
            
            from .themes import ThemeCategory
            
            if category == "all":
                themes = list(theme_cog.theme_manager.themes.values())
                title = "🎨 All Available Themes"
            else:
                cat_enum = ThemeCategory(category)
                themes = theme_cog.theme_manager.get_themes_by_category(cat_enum)
                title = f"🎨 {category.replace('_', ' ').title()} Themes"
            
            if not themes:
                embed = discord.Embed(
                    title="❌ No Themes Found",
                    description=f"No themes available in category: {category}",
                    color=0xFF0000
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Create showcase embed
            embed = discord.Embed(
                title=title,
                description=f"Discover {len(themes)} amazing themes! Use `/theme_preview` for interactive testing.\n",
                color=0x02A9FF
            )
            
            # Group themes by category for display
            by_category = {}
            for theme in themes[:20]:  # Limit for embed space
                cat = theme.category.value
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(theme)
            
            for cat_name, cat_themes in by_category.items():
                theme_list = []
                for theme in cat_themes[:6]:  # Limit per category
                    source_info = f" *({theme.character_source})*" if theme.character_source else ""
                    theme_list.append(f"{theme.emoji} **{theme.name}**{source_info}")
                
                if len(cat_themes) > 6:
                    theme_list.append(f"*...and {len(cat_themes) - 6} more themes*")
                
                embed.add_field(
                    name=f"📁 {cat_name.replace('_', ' ').title()}",
                    value="\n".join(theme_list),
                    inline=True
                )
            
            embed.add_field(
                name="🚀 Quick Commands",
                value="`/theme_preview` - Interactive preview\n"
                      "`/theme set <name>` - Apply theme\n" 
                      "`/theme random` - Random theme",
                inline=False
            )
            
            embed.set_footer(text=f"Total themes available: {len(theme_cog.theme_manager.themes)} 🎨")
            
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.error(f"Error in theme_showcase command: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while loading theme showcase.",
                color=0xFF0000
            )
            await interaction.followup.send(embed=embed)

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(AdvancedThemeCommands(bot))
    logger.info("Advanced Theme Commands loaded successfully")