import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import aiohttp
import io
from typing import Optional

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

    def _parse_color(self, color_input: str, changelog_type: str) -> discord.Color:
        """Parse color input and return appropriate discord.Color."""
        if color_input:
            color_input = color_input.strip()
            # Handle hex colors
            if color_input.startswith('#'):
                try:
                    return discord.Color(int(color_input[1:], 16))
                except ValueError:
                    pass
            # Handle named colors
            color_map = {
                'red': discord.Color.red(),
                'green': discord.Color.green(),
                'blue': discord.Color.blue(),
                'yellow': discord.Color.yellow(),
                'orange': discord.Color.orange(),
                'purple': discord.Color.purple(),
                'gold': discord.Color.gold(),
                'dark_red': discord.Color.dark_red(),
                'dark_green': discord.Color.dark_green(),
                'dark_blue': discord.Color.dark_blue(),
            }
            if color_input.lower() in color_map:
                return color_map[color_input.lower()]
        
        # Default colors based on type
        type_colors = {
            'bugfix': discord.Color.red(),
            'feature': discord.Color.green(),
            'update': discord.Color.blue(),
            'announcement': discord.Color.gold(),
            'maintenance': discord.Color.orange(),
            'general': discord.Color.blurple(),
        }
        return type_colors.get(changelog_type, discord.Color.blurple())

    def _get_type_config(self, changelog_type: str) -> dict:
        """Get configuration for different changelog types."""
        type_configs = {
            'bugfix': {
                'emoji': '🐛',
                'title': 'Bug Fix',
                'footer': '🔧 Bug Fix Update'
            },
            'feature': {
                'emoji': '✨',
                'title': 'New Feature',
                'footer': '🚀 Feature Update'
            },
            'update': {
                'emoji': '🔄',
                'title': 'Update',
                'footer': '⬆️ System Update'
            },
            'announcement': {
                'emoji': '📢',
                'title': 'Announcement',
                'footer': '📣 Important Announcement'
            },
            'maintenance': {
                'emoji': '🔧',
                'title': 'Maintenance',
                'footer': '🛠️ Maintenance Update'
            },
            'general': {
                'emoji': '📝',
                'title': 'Changelog',
                'footer': '📋 General Update'
            }
        }
        return type_configs.get(changelog_type, type_configs['general'])

    def _format_markdown(self, text: str) -> str:
        """Enhanced markdown formatting for changelog text."""
        if not text:
            return text
            
        # Support for bullet points
        text = text.replace('- ', '• ')
        text = text.replace('* ', '• ')
        
        # Support for numbered lists (basic)
        lines = text.split('\n')
        formatted_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith(tuple(f'{i}.' for i in range(1, 10))):
                # Add emoji numbers for visual appeal
                number = line[0]
                rest = line[2:].strip()
                emoji_numbers = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣']
                if int(number) <= 9:
                    formatted_lines.append(f"{emoji_numbers[int(number)-1]} {rest}")
                else:
                    formatted_lines.append(line)
            else:
                formatted_lines.append(line)
        
        # Ensure proper line spacing for readability
        result = '\n'.join(formatted_lines)
        
        # Handle double line breaks for paragraph separation
        result = result.replace('\n\n\n', '\n\n')  # Prevent too many empty lines
        
        return result

    async def _validate_image_url(self, url: str) -> bool:
        """Validate if the URL points to a valid image."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=5) as response:
                    if response.status == 200:
                        content_type = response.headers.get('content-type', '').lower()
                        return content_type.startswith('image/')
                    return False
        except Exception:
            return False

    async def _process_image(self, image_input: str) -> Optional[discord.File]:
        """Process image input - download and convert to Discord file."""
        if not image_input:
            return None
            
        try:
            # If it's a URL
            if image_input.startswith(('http://', 'https://')):
                if not await self._validate_image_url(image_input):
                    return None
                    
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_input) as response:
                        if response.status == 200:
                            image_data = await response.read()
                            # Get file extension from content-type or URL
                            content_type = response.headers.get('content-type', '')
                            if 'png' in content_type:
                                ext = 'png'
                            elif 'jpeg' in content_type or 'jpg' in content_type:
                                ext = 'jpg'
                            elif 'gif' in content_type:
                                ext = 'gif'
                            elif 'webp' in content_type:
                                ext = 'webp'
                            else:
                                ext = 'png'  # Default
                                
                            return discord.File(
                                io.BytesIO(image_data),
                                filename=f"changelog_image.{ext}"
                            )
            return None
        except Exception:
            return None





    @changelog_only()
    @app_commands.command(name="changelog", description="Create a changelog from an uploaded text file.")
    @app_commands.describe(
        file="Text file to convert into changelog",
        changelog_type="Type of changelog update",
        color="Embed color (hex code like #FF5733 or color name)",
        role="Optional role to ping",
        image_url="Optional image URL to embed",
        title_override="Override the auto-detected title"
    )
    @app_commands.choices(changelog_type=[
        app_commands.Choice(name="🐛 Bug Fix", value="bugfix"),
        app_commands.Choice(name="✨ New Feature", value="feature"),
        app_commands.Choice(name="🔄 Update", value="update"),
        app_commands.Choice(name="📢 Announcement", value="announcement"),
        app_commands.Choice(name="🔧 Maintenance", value="maintenance"),
        app_commands.Choice(name="📝 General", value="general")
    ])
    async def changelog(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        changelog_type: str = "general",
        color: str = None,
        role: discord.Role = None,
        image_url: str = None,
        title_override: str = None
    ):
        """Create a changelog from an uploaded text file with automatic formatting."""
        try:
            await interaction.response.defer(ephemeral=True)
            
            # Validate file
            if not file.filename.lower().endswith(('.txt', '.md')):
                await interaction.followup.send("❌ Please upload a .txt or .md file.", ephemeral=True)
                return
                
            if file.size > 1024 * 1024:  # 1MB limit
                await interaction.followup.send("❌ File is too large. Maximum size is 1MB.", ephemeal=True)
                return
            
            # Download and read file content
            try:
                file_content = await file.read()
                text_content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    text_content = file_content.decode('latin-1')
                except:
                    await interaction.followup.send("❌ Could not decode file. Please ensure it's a text file with UTF-8 or Latin-1 encoding.", ephemeral=True)
                    return
            except Exception as e:
                await interaction.followup.send(f"❌ Failed to read file: {str(e)}", ephemeral=True)
                return
            
            # Parse the text content
            parsed_data = self._parse_text_file(text_content, title_override)
            
            # Determine embed color
            embed_color = self._parse_color(color, changelog_type)
            type_config = self._get_type_config(changelog_type)
            
            embed = discord.Embed(
                title=f"{type_config['emoji']} {type_config['title']}",
                color=embed_color
            )
            
            # Add title
            if parsed_data['title']:
                embed.add_field(
                    name="📝 **Title**",
                    value=f"**{parsed_data['title']}**",
                    inline=False
                )
            
            # Add main content sections
            for section in parsed_data['sections']:
                # Limit field values to Discord's 1024 character limit
                content = section['content']
                if len(content) > 1020:
                    content = content[:1017] + "..."
                
                embed.add_field(
                    name=section['name'],
                    value=content,
                    inline=False
                )
            
            # Author info
            embed.set_author(
                name=f"Published by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )
            
            # Footer
            embed.set_footer(
                text=f"{type_config['footer']} • Published on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} • From: {file.filename}"
            )
            
            # Process image if provided
            image_file = None
            if image_url:
                image_file = await self._process_image(image_url)
                if image_file:
                    embed.set_image(url=f"attachment://{image_file.filename}")
            
            # Send to changelog channel
            channel = self.bot.get_channel(CHANGELOG_CHANNEL_ID)
            if not channel:
                await interaction.followup.send("❌ Could not find changelog channel.", ephemeral=True)
                return
            
            content_msg = role.mention if role else None
            
            if image_file:
                await channel.send(content=content_msg, embed=embed, file=image_file)
            else:
                await channel.send(content=content_msg, embed=embed)
            
            await interaction.followup.send(f"✅ {type_config['title']} created from file **{file.filename}** and published successfully!", ephemeral=True)
            
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Failed to process file and publish changelog: {str(e)}", ephemeral=True)
            except:
                pass
            raise e

    def _parse_text_file(self, content: str, title_override: str = None) -> dict:
        """Parse text file content into structured changelog data."""
        lines = content.strip().split('\n')
        sections = []
        current_section_name = "📖 **Details**"
        current_section_content = []
        title = title_override
        
        # Try to detect title from first line if not overridden
        if not title and lines:
            first_line = lines[0].strip()
            # Check if first line looks like a title (short, no markdown lists, etc.)
            if (len(first_line) < 100 and 
                not first_line.startswith(('- ', '* ', '1. ', '2. ')) and
                not first_line.startswith('#') and
                first_line):
                title = first_line
                lines = lines[1:]  # Remove title from content
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines at the start of sections
            if not line and not current_section_content:
                i += 1
                continue
            
            # Detect section headers (lines that end with : or are all caps/markdown headers)
            is_section_header = False
            if line:
                # Check for markdown headers
                if line.startswith('#'):
                    is_section_header = True
                    line = line.lstrip('#').strip()
                # Check for lines ending with colon
                elif line.endswith(':') and len(line.split()) <= 5:
                    is_section_header = True
                    line = line[:-1].strip()
                # Check for all caps short lines (likely headers)
                elif (line.isupper() and len(line.split()) <= 4 and 
                      len(line) > 2 and not line.startswith(('- ', '* ', '1. '))):
                    is_section_header = True
            
            if is_section_header:
                # Save previous section if it has content
                if current_section_content:
                    formatted_content = self._format_markdown('\n'.join(current_section_content).strip())
                    if formatted_content:
                        sections.append({
                            'name': current_section_name,
                            'content': formatted_content
                        })
                
                # Start new section
                current_section_name = f"📌 **{line.title()}**"
                current_section_content = []
            else:
                # Add line to current section
                if line or current_section_content:  # Keep empty lines if we have content
                    current_section_content.append(line)
            
            i += 1
        
        # Add final section
        if current_section_content:
            formatted_content = self._format_markdown('\n'.join(current_section_content).strip())
            if formatted_content:
                sections.append({
                    'name': current_section_name,
                    'content': formatted_content
                })
        
        # If no sections were created, put everything in one section
        if not sections and content.strip():
            sections.append({
                'name': "📖 **Details**",
                'content': self._format_markdown(content.strip())
            })
        
        return {
            'title': title or "Update",
            'sections': sections
        }






async def setup(bot: commands.Bot):
    await bot.add_cog(Changelog(bot))