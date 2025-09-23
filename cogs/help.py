import discord
from discord import app_commands
from discord.ext import commands
import logging
from pathlib import Path
from config import BOT_ID

# ------------------------------------------------------
# Logging Setup - Safe handling
# ------------------------------------------------------
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "help.log"

# Setup logger
logger = logging.getLogger("help")
logger.setLevel(logging.INFO)

# Only add handler if not already present
if not logger.handlers:
    # File handler with safe file access
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

logger.info("Help cog logging initialized")

class HelpCog(commands.Cog):
    """A comprehensive help system for the Lemegeton bot."""

    def __init__(self, bot):
        self.bot = bot
        logger.info("Help cog initialized")
        
        # Command categories and details
        self.command_categories = {
            "🔐 Account Management": {
                "login": {
                    "desc": "Manage your account - register, update, or unregister",
                    "usage": "/login",
                    "note": "Start here to connect your AniList account!"
                },
                "check_anilist": {
                    "desc": "Check if an AniList username exists and is accessible",
                    "usage": "/check_anilist <username>",
                    "note": "Verify AniList usernames before registration"
                }
            },
            "📊 Profile & Stats": {
                "profile": {
                    "desc": "View your AniList profile with stats & achievements",
                    "usage": "/profile [user]",
                    "note": "Shows detailed profile information and achievements"
                },
                "stats": {
                    "desc": "Show your AniList statistics",
                    "usage": "/stats",
                    "note": "View your anime/manga consumption statistics"
                }
            },
            "📺 Anime & Manga": {
                "watchlist": {
                    "desc": "Show what someone is currently watching or reading on AniList", 
                    "usage": "/watchlist [member] [username]",
                    "note": "View current watching/reading progress with detailed status"
                },
                "browse": {
                    "desc": "Search and browse anime, manga, light novels, and general novels",
                    "usage": "/browse",
                    "note": "Interactive browsing with advanced filtering and sorting options"
                },
                "trending": {
                    "desc": "View trending anime and manga",
                    "usage": "/trending",
                    "note": "See what's popular right now"
                },
                "recommendations": {
                    "desc": "Get personalized recommendations based on your highly-rated manga (≥8.0/10)",
                    "usage": "/recommendations [member]",
                    "note": "AI-powered recommendations with interactive browsing by category"
                },
                "search_similar": {
                    "desc": "Find anime/manga similar to a specific title",
                    "usage": "/search_similar",
                    "note": "Discover titles similar to ones you enjoy"
                },
                "random": {
                    "desc": "Get random anime/manga suggestions",
                    "usage": "/random",
                    "note": "For when you can't decide what to watch/read"
                }
            },
            "🏆 Challenges & Competition": {
                "challenge_progress": {
                    "desc": "View your reading challenge progress",
                    "usage": "/challenge_progress",
                    "note": "Track your annual reading goals"
                },
                "challenge_update": {
                    "desc": "Update your challenge progress",
                    "usage": "/challenge_update",
                    "note": "Manually update your reading challenge"
                },
                "challenge_manage": {
                    "desc": "Manage reading challenges",
                    "usage": "/challenge_manage",
                    "note": "Create and manage reading challenges"
                },
                "challenge_leaderboard": {
                    "desc": "View challenge leaderboards",
                    "usage": "/challenge_leaderboard",
                    "note": "See who's leading in various challenges"
                },
                "leaderboard": {
                    "desc": "View server leaderboards for various metrics",
                    "usage": "/leaderboard",
                    "note": "Server rankings and competitions"
                }
            },
            "🔍 Comparison & Analysis": {
                "compare": {
                    "desc": "Compare anime/manga lists between users",
                    "usage": "/compare",
                    "note": "Find shared interests and differences"
                },
                "affinity": {
                    "desc": "Check compatibility with other users",
                    "usage": "/affinity",
                    "note": "See how similar your tastes are"
                }
            },
            "🎮 Gaming": {
                "steam": {
                    "desc": "Steam game information and recommendations",
                    "usage": "/steam",
                    "note": "Gaming recommendations based on your preferences"
                }
            },
            "🛠️ Utilities": {
                "timestamp_watch": {
                    "desc": "Toggle automatic timestamp conversion",
                    "usage": "/timestamp_watch",
                    "note": "Automatically convert timestamps in messages"
                },
                "embed": {
                    "desc": "Create custom embeds",
                    "usage": "/embed",
                    "note": "Create formatted message embeds"
                },
                "invite_tracker": {
                    "desc": "Track server invites",
                    "usage": "/invite_tracker",
                    "note": "Monitor who joins via which invite"
                }
            },
            "ℹ️ Bot Information": {
                "invite": {
                    "desc": "Get an invite link to add this bot to your server",
                    "usage": "/invite",
                    "note": "Share the bot with other servers"
                },
                "changelog": {
                    "desc": "View the latest bot updates and changes",
                    "usage": "/changelog",
                    "note": "Stay updated with new features"
                },
                "feedback": {
                    "desc": "Submit ideas or report bugs",
                    "usage": "/feedback",
                    "note": "Help improve the bot with your suggestions"
                },
                "help": {
                    "desc": "Display this help information",
                    "usage": "/help [category]",
                    "note": "Get detailed command information"
                }
            }
        }

    async def cog_load(self):
        """Called when the cog is loaded."""
        logger.info("Help cog loaded successfully")

    @app_commands.command(name="help", description="Get comprehensive help for bot commands and features")
    @app_commands.describe(
        category="Choose a specific category to view detailed information"
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="🔐 Account Management", value="account"),
        app_commands.Choice(name="📊 Profile & Stats", value="profile"),
        app_commands.Choice(name="📺 Anime & Manga", value="anime"),
        app_commands.Choice(name="🏆 Challenges", value="challenges"),
        app_commands.Choice(name="🔍 Comparison", value="comparison"),
        app_commands.Choice(name="🎮 Gaming", value="gaming"),
        app_commands.Choice(name="🛠️ Utilities", value="utilities"),
        app_commands.Choice(name="ℹ️ Bot Info", value="info"),
    ])
    async def help(self, interaction: discord.Interaction, category: app_commands.Choice[str] = None):
        """Display comprehensive help information for bot commands."""
        
        try:
            logger.info(f"Help command requested by {interaction.user.display_name} (ID: {interaction.user.id}) - Category: {category.value if category else 'overview'}")
            
            if category is None:
                # Show overview of all categories
                embed = await self._create_overview_embed(interaction)
            else:
                # Show detailed category information
                embed = await self._create_category_embed(category.value, interaction)
            
            # Create navigation view
            view = HelpNavigationView(self, interaction.user)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
            logger.info(f"Help information sent successfully to {interaction.user.display_name}")
            
        except Exception as e:
            logger.error(f"Error displaying help information: {e}", exc_info=True)
            
            error_embed = discord.Embed(
                title="❌ Error",
                description="Failed to load help information. Please try again later.",
                color=discord.Color.red()
            )
            
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

    async def _create_overview_embed(self, interaction: discord.Interaction) -> discord.Embed:
        """Create the main overview embed showing all categories."""
        
        embed = discord.Embed(
            title="🤖 Lemegeton Bot - Command Help",
            description=(
                "**Welcome to Lemegeton!** Your ultimate anime/manga tracking companion with AI-powered features.\n\n"
                "**🚀 Quick Start:**\n"
                "1. Use `/login` to connect your AniList account\n"
                "2. Explore commands by category below\n"
                "3. Join our [Support Server](https://discord.gg/xUGD7krzws) for help\n"
                "4. Use `/feedback` to suggest improvements\n\n"
                "**📋 Command Categories:**"
            ),
            color=discord.Color.blue()
        )
        
        # Add category overview
        category_overview = []
        for category_name, commands in self.command_categories.items():
            command_count = len(commands)
            category_overview.append(f"{category_name} • **{command_count} commands**")
        
        embed.add_field(
            name="Available Categories",
            value="\n".join(category_overview),
            inline=False
        )
        
        embed.add_field(
            name="💡 Pro Tips",
            value=(
                "• Most commands work better after using `/login`\n"
                "• Use the dropdown menu below to explore categories\n"
                "• Commands marked with 🔒 require registration\n"
                "• Some commands have optional parameters for flexibility"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔗 Useful Links",
            value=(
                "• [AniList Website](https://anilist.co) - Create your account\n"
                "• [Bot Invite Link](https://discord.com/api/oauth2/authorize?client_id={}&permissions=0&scope=bot%20applications.commands) - Share with friends\n"
                "• [Support Server](https://discord.gg/xUGD7krzws) - Get help and report issues\n"
                "• Use `/feedback` to report issues or suggest features"
            ).format(BOT_ID),
            inline=False
        )
        
        embed.set_footer(
            text=f"Total Commands: {sum(len(cmds) for cmds in self.command_categories.values())} | Use the dropdown to explore categories",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        
        return embed

    async def _create_category_embed(self, category_key: str, interaction: discord.Interaction) -> discord.Embed:
        """Create a detailed embed for a specific category."""
        
        category_mapping = {
            "account": "🔐 Account Management",
            "profile": "📊 Profile & Stats", 
            "anime": "📺 Anime & Manga",
            "challenges": "🏆 Challenges & Competition",
            "comparison": "🔍 Comparison & Analysis",
            "gaming": "🎮 Gaming",
            "utilities": "🛠️ Utilities",
            "info": "ℹ️ Bot Information"
        }
        
        category_name = category_mapping.get(category_key, "Unknown Category")
        commands = self.command_categories.get(category_name, {})
        
        embed = discord.Embed(
            title=f"{category_name}",
            description=f"Detailed information for **{len(commands)} commands** in this category:",
            color=discord.Color.green()
        )
        
        # Add each command in the category
        for cmd_name, cmd_info in commands.items():
            embed.add_field(
                name=f"/{cmd_name}",
                value=(
                    f"**Description:** {cmd_info['desc']}\n"
                    f"**Usage:** `{cmd_info['usage']}`\n"
                    f"💡 *{cmd_info['note']}*"
                ),
                inline=False
            )
        
        # Add category-specific tips
        tips = self._get_category_tips(category_key)
        if tips:
            embed.add_field(
                name="💡 Category Tips",
                value=tips,
                inline=False
            )
        
        embed.set_footer(
            text="Use the dropdown menu to explore other categories",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        
        return embed

    def _get_category_tips(self, category_key: str) -> str:
        """Get category-specific tips and information."""
        
        tips = {
            "account": (
                "• Start with `/login` - it's required for most features\n"
                "• Your AniList username must be exact (case-sensitive)\n"
                "• Use `/check_anilist` to verify usernames before registration\n"
                "• You can update or change your linked account anytime"
            ),
            "profile": (
                "• Profiles show achievements, stats, and activity\n"
                "• Stats include detailed breakdowns of your watching history\n"
                "• You can view other users' profiles if they're registered"
            ),
            "anime": (
                "• Most commands work with both anime and manga\n"
                "• Recommendations use advanced AI filtering for quality results\n"
                "• Rate titles 8.0+ for best recommendation accuracy\n"
                "• Browse supports advanced filtering by genre, year, format"
            ),
            "challenges": (
                "• Join reading challenges to stay motivated\n"
                "• Progress updates automatically from your AniList\n"
                "• Compete with friends on the leaderboards"
            ),
            "comparison": (
                "• Compare lists to find shared interests\n"
                "• Affinity scores help find users with similar tastes\n"
                "• Great for finding new friends and recommendations"
            ),
            "gaming": (
                "• Steam integration provides game recommendations\n"
                "• Based on your gaming preferences and activity\n"
                "• Discover new games similar to ones you enjoy"
            ),
            "utilities": (
                "• These commands enhance your server experience\n"
                "• Timestamp conversion helps with scheduling\n"
                "• Embed creation allows custom formatted messages"
            ),
            "info": (
                "• Keep up with bot updates via `/changelog`\n"
                "• Use `/feedback` to suggest improvements\n"
                "• Share the bot with `/invite` command\n"
                "• Join our [Support Server](https://discord.gg/xUGD7krzws) for help"
            )
        }
        
        return tips.get(category_key, "")


class HelpNavigationView(discord.ui.View):
    """Navigation view for help command with dropdown menu."""
    
    def __init__(self, help_cog: HelpCog, user: discord.User):
        super().__init__(timeout=300)  # 5 minute timeout
        self.help_cog = help_cog
        self.user = user
        
        # Add the dropdown select menu
        self.add_item(CategorySelect(help_cog))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to interact with the view."""
        if interaction.user != self.user:
            await interaction.response.send_message(
                "❌ You can't use this menu. Use `/help` to get your own help interface!",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        """Disable all items when the view times out."""
        for item in self.children:
            item.disabled = True


class CategorySelect(discord.ui.Select):
    """Dropdown select menu for choosing help categories."""
    
    def __init__(self, help_cog: HelpCog):
        self.help_cog = help_cog
        
        options = [
            discord.SelectOption(
                label="📋 Overview",
                value="overview",
                description="Show all categories and getting started info",
                emoji="📋"
            ),
            discord.SelectOption(
                label="Account Management",
                value="account",
                description="Registration and account settings",
                emoji="🔐"
            ),
            discord.SelectOption(
                label="Profile & Stats", 
                value="profile",
                description="View profiles and statistics",
                emoji="📊"
            ),
            discord.SelectOption(
                label="Anime & Manga",
                value="anime", 
                description="Browse, track, and discover titles",
                emoji="📺"
            ),
            discord.SelectOption(
                label="Challenges",
                value="challenges",
                description="Reading challenges and leaderboards", 
                emoji="🏆"
            ),
            discord.SelectOption(
                label="Comparison",
                value="comparison",
                description="Compare lists and find compatibility",
                emoji="🔍"
            ),
            discord.SelectOption(
                label="Gaming",
                value="gaming",
                description="Steam integration and game recommendations",
                emoji="🎮"
            ),
            discord.SelectOption(
                label="Utilities",
                value="utilities",
                description="Helper commands and tools",
                emoji="🛠️"
            ),
            discord.SelectOption(
                label="Bot Information",
                value="info",
                description="Changelog, feedback, and bot info",
                emoji="ℹ️"
            )
        ]
        
        super().__init__(
            placeholder="📖 Choose a category to explore...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle selection from the dropdown menu."""
        
        selected_value = self.values[0]
        
        try:
            if selected_value == "overview":
                embed = await self.help_cog._create_overview_embed(interaction)
            else:
                embed = await self.help_cog._create_category_embed(selected_value, interaction)
            
            await interaction.response.edit_message(embed=embed, view=self.view)
            
            logger.info(f"Help category '{selected_value}' displayed for {interaction.user.display_name}")
            
        except Exception as e:
            logger.error(f"Error in category selection: {e}", exc_info=True)
            
            await interaction.response.send_message(
                "❌ An error occurred while loading that category. Please try again.",
                ephemeral=True
            )


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(HelpCog(bot))
    logger.info("Help cog successfully loaded")