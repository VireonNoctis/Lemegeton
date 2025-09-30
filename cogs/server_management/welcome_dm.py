import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
import aiohttp
from typing import Optional
from database import execute_db_operation

logger = logging.getLogger("WelcomeDM")

class WelcomeDM(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    async def cog_load(self):
        """Initialize the welcome_dm table when the cog loads."""
        await self.init_database()
        
    async def init_database(self):
        """Create the welcome_dm table if it doesn't exist."""
        create_table_query = """
            CREATE TABLE IF NOT EXISTS welcome_dm (
                guild_id INTEGER PRIMARY KEY,
                message_content TEXT NOT NULL,
                enabled BOOLEAN DEFAULT TRUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        
        try:
            await execute_db_operation(
                "create welcome_dm table",
                create_table_query
            )
            logger.info("Welcome DM table initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize welcome DM table: {e}")
    
    async def get_welcome_message(self, guild_id: int) -> Optional[str]:
        """Get the welcome message for a specific guild."""
        try:
            query = "SELECT message_content FROM welcome_dm WHERE guild_id = ? AND enabled = TRUE"
            result = await execute_db_operation(
                "get welcome message",
                query,
                (guild_id,),
                fetch_one=True
            )
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Failed to get welcome message for guild {guild_id}: {e}")
            return None
    
    async def set_welcome_message(self, guild_id: int, message_content: str) -> bool:
        """Set or update the welcome message for a specific guild."""
        try:
            query = """
                INSERT INTO welcome_dm (guild_id, message_content, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(guild_id) DO UPDATE SET 
                    message_content = excluded.message_content,
                    updated_at = CURRENT_TIMESTAMP
            """
            
            await execute_db_operation(
                "set welcome message",
                query,
                (guild_id, message_content)
            )
            logger.info(f"Welcome message updated for guild {guild_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to set welcome message for guild {guild_id}: {e}")
            return False
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send welcome DM to new members."""
        if member.bot:
            return  # Don't send welcome messages to bots
            
        guild_id = member.guild.id
        welcome_message = await self.get_welcome_message(guild_id)
        
        if not welcome_message:
            logger.debug(f"No welcome message configured for guild {guild_id}")
            return
            
        try:
            # Replace placeholders in the message
            formatted_message = welcome_message.replace("{user}", member.display_name)
            formatted_message = formatted_message.replace("{server}", member.guild.name)
            formatted_message = formatted_message.replace("{mention}", member.mention)
            
            # Send the welcome DM
            await member.send(formatted_message)
            logger.info(f"Welcome DM sent to {member.display_name} ({member.id}) in guild {member.guild.name}")
            
        except discord.Forbidden:
            logger.warning(f"Could not send welcome DM to {member.display_name} - DMs disabled")
        except Exception as e:
            logger.error(f"Failed to send welcome DM to {member.display_name}: {e}")
    
    @app_commands.command(
        name="set-welcome-dm",
        description="Set the welcome DM message by uploading a text file (Admin only)"
    )
    @app_commands.describe(
        text_file="Upload a .txt file containing the welcome message"
    )
    async def set_welcome_dm(self, interaction: discord.Interaction, text_file: discord.Attachment):
        """Admin command to set welcome DM message from uploaded text file."""
        
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ **Access Denied**\n\nYou need Administrator permissions to use this command.",
                ephemeral=True
            )
            return
        
        # Validate file type
        if not text_file.filename.lower().endswith('.txt'):
            await interaction.response.send_message(
                "❌ **Invalid File Type**\n\nPlease upload a `.txt` file containing your welcome message.",
                ephemeral=True
            )
            return
        
        # Check file size (limit to 1MB)
        if text_file.size > 1024 * 1024:  # 1MB
            await interaction.response.send_message(
                "❌ **File Too Large**\n\nThe text file must be smaller than 1MB.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Download and read the file content
            async with aiohttp.ClientSession() as session:
                async with session.get(text_file.url) as response:
                    if response.status == 200:
                        file_content = await response.text(encoding='utf-8')
                    else:
                        await interaction.followup.send(
                            "❌ **Download Failed**\n\nCould not download the uploaded file.",
                            ephemeral=True
                        )
                        return
            
            # Validate content length
            if len(file_content.strip()) == 0:
                await interaction.followup.send(
                    "❌ **Empty File**\n\nThe uploaded text file is empty.",
                    ephemeral=True
                )
                return
            
            if len(file_content) > 2000:
                await interaction.followup.send(
                    "❌ **Message Too Long**\n\nThe welcome message must be 2000 characters or less for Discord DM limits.",
                    ephemeral=True
                )
                return
            
            # Save the welcome message
            success = await self.set_welcome_message(interaction.guild_id, file_content.strip())
            
            if success:
                # Create preview embed
                preview_embed = discord.Embed(
                    title="✅ Welcome DM Updated",
                    description="The welcome DM message has been successfully updated!",
                    color=discord.Color.green()
                )
                
                # Show preview with placeholder replacements
                preview_content = file_content.strip()
                preview_content = preview_content.replace("{user}", "NewUser")
                preview_content = preview_content.replace("{server}", interaction.guild.name)
                preview_content = preview_content.replace("{mention}", "@NewUser")
                
                if len(preview_content) > 1024:
                    preview_content = preview_content[:1021] + "..."
                
                preview_embed.add_field(
                    name="📋 Message Preview",
                    value=f"```\n{preview_content}\n```",
                    inline=False
                )
                
                preview_embed.add_field(
                    name="🏷️ Available Placeholders",
                    value="• `{user}` - Member's display name\n• `{server}` - Server name\n• `{mention}` - Mention the user",
                    inline=False
                )
                
                preview_embed.set_footer(text="New members will receive this message when they join the server.")
                
                await interaction.followup.send(embed=preview_embed, ephemeral=True)
            else:
                await interaction.followup.send(
                    "❌ **Database Error**\n\nFailed to save the welcome message. Please try again.",
                    ephemeral=True
                )
                
        except UnicodeDecodeError:
            await interaction.followup.send(
                "❌ **Encoding Error**\n\nThe file must be a valid UTF-8 encoded text file.",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error processing welcome DM file upload: {e}")
            await interaction.followup.send(
                "❌ **Unexpected Error**\n\nAn error occurred while processing your file. Please try again.",
                ephemeral=True
            )
    
    @app_commands.command(
        name="welcome-dm-status",
        description="Check the current welcome DM configuration (Admin only)"
    )
    async def welcome_dm_status(self, interaction: discord.Interaction):
        """Admin command to check current welcome DM status."""
        
        # Check if user has administrator permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ **Access Denied**\n\nYou need Administrator permissions to use this command.",
                ephemeral=True
            )
            return
        
        welcome_message = await self.get_welcome_message(interaction.guild_id)
        
        if welcome_message:
            # Create status embed
            status_embed = discord.Embed(
                title="📨 Welcome DM Configuration",
                description="Welcome DM is currently **enabled** for this server.",
                color=discord.Color.blue()
            )
            
            # Show preview with placeholder replacements
            preview_content = welcome_message
            preview_content = preview_content.replace("{user}", "NewUser")
            preview_content = preview_content.replace("{server}", interaction.guild.name)
            preview_content = preview_content.replace("{mention}", "@NewUser")
            
            if len(preview_content) > 1024:
                preview_content = preview_content[:1021] + "..."
            
            status_embed.add_field(
                name="📋 Current Message",
                value=f"```\n{preview_content}\n```",
                inline=False
            )
            
            status_embed.add_field(
                name="🏷️ Available Placeholders",
                value="• `{user}` - Member's display name\n• `{server}` - Server name\n• `{mention}` - Mention the user",
                inline=False
            )
            
            status_embed.set_footer(text="Use /set-welcome-dm to update the message.")
            
        else:
            status_embed = discord.Embed(
                title="📨 Welcome DM Configuration",
                description="Welcome DM is currently **disabled** for this server.\n\nUse `/set-welcome-dm` to configure a welcome message.",
                color=discord.Color.orange()
            )
        
        await interaction.response.send_message(embed=status_embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeDM(bot))