import discord
from discord.ext import commands
from discord import app_commands
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
import asyncio
from typing import Optional, List, Tuple
import time

# Set up logging
log_file_path = Path(__file__).parent.parent / "logs" / "timestamp.log"
log_file_path.parent.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

try:
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(file_handler)
except Exception:
    # Fall back to console logging if the file cannot be created (Windows lock, etc.)
    if not logger.handlers:
        stream = logging.StreamHandler()
        stream.setLevel(logging.INFO)
        stream.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logger.addHandler(stream)

class TimestampConverter(commands.Cog):
    """Watches chat for time mentions and converts them to dynamic Discord timestamps."""
    
    def __init__(self, bot):
        self.bot = bot
        self.watching_enabled = True  # Global toggle for all channels - enabled by default
        self.recently_processed = set()  # Track recently processed message IDs to prevent loops
        
        # Time patterns to match (ordered by specificity to prevent overlaps)
        self.time_patterns = [
            # Date and time combinations first (most specific) - these should match first
            r'\b(tomorrow|today)\s+at\s+(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b',
            r'\b(tomorrow|today)\s+at\s+(\d{1,2})\s*(am|pm|AM|PM)\b',
            r'\b(\w{3,9}\s+\d{1,2})\s+at\s+(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b',
            r'\b(\w{3,9}\s+\d{1,2})\s+at\s+(\d{1,2})\s*(am|pm|AM|PM)\b',
            # Standalone time formats (will be filtered out by overlap detection)
            r'\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b',
            r'\b(\d{1,2})\s*(am|pm|AM|PM)\b',
            # 24-hour format (very restrictive - must have colon and be valid time)
            r'\b([01]?\d|2[0-3]):([0-5]\d)\b(?=\s|$|[^\d])',
        ]
        
        logger.info("TimestampConverter cog initialized")

    @app_commands.command(name="timestamp_watch", description="Toggle automatic timestamp conversion for all channels")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    async def toggle_timestamp_watch(self, interaction: discord.Interaction):
        """Toggle automatic timestamp conversion for all channels. Admin only."""
        try:
            # Double-check permissions
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("❌ You need administrator permissions to use this command.", ephemeral=True)
                return
            
            if self.watching_enabled:
                self.watching_enabled = False
                embed = discord.Embed(
                    title="⏰ Timestamp Watch Disabled",
                    description="Automatic timestamp conversion is now **OFF** for all channels in this server",
                    color=discord.Color.red()
                )
                logger.info(f"Timestamp watching disabled globally by {interaction.user}")
            else:
                self.watching_enabled = True
                embed = discord.Embed(
                    title="⏰ Timestamp Watch Enabled",
                    description="Automatic timestamp conversion is now **ON** for all channels in this server\n\n"
                               f"I'll watch for times like:\n"
                               f"• `3:30pm`, `11:45 AM`\n"
                               f"• `15:30`, `23:45`\n"
                               f"• `tomorrow at 3pm`\n"
                               f"• `Dec 25 at 2:30pm`",
                    color=discord.Color.green()
                )
                logger.info(f"Timestamp watching enabled globally by {interaction.user}")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in toggle_timestamp_watch: {e}")
            await interaction.response.send_message("❌ An error occurred while toggling timestamp watch.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for messages in all channels and auto-convert timestamps when enabled."""
        try:
            # Skip if bot message, webhook message, or watching is disabled
            if message.author.bot or not self.watching_enabled:
                return
            
            # Skip webhook messages (these are messages sent by webhooks, including our own)
            if message.webhook_id is not None:
                return
                
            # Double-check: Skip if this message was sent by our webhook
            if hasattr(message, 'author') and hasattr(message.author, 'name'):
                if message.author.name == "Lemegeton Timestamp":
                    return
            
            # Skip if message is a command
            if message.content.startswith(('/', '!', '?', '.')):
                return
            
            # Skip if this looks like a message that was already processed
            # (contains Discord timestamp format)
            if '<t:' in message.content and ':R>' in message.content:
                return
            
            # Skip if we've recently processed this message (prevent loops)
            if message.id in self.recently_processed:
                return
            
            # Add to recently processed (limit size to prevent memory issues)
            self.recently_processed.add(message.id)
            if len(self.recently_processed) > 100:  # Keep only last 100 message IDs
                # Remove oldest entries (this is a simple approach)
                self.recently_processed = set(list(self.recently_processed)[-50:])
            
            converted_message = self.convert_times_in_message(message.content)
            
            if converted_message and converted_message != message.content:
                # Wait a moment to avoid spam
                await asyncio.sleep(0.5)
                
                # Send the converted message with user's display name and avatar
                webhook = None
                try:
                    # Try to get or create a webhook for this channel
                    webhooks = await message.channel.webhooks()
                    webhook = next((w for w in webhooks if w.name == "Lemegeton Timestamp"), None)
                    
                    if not webhook:
                        webhook = await message.channel.create_webhook(name="Lemegeton Timestamp")
                    
                    # Send the message as the user with converted timestamps
                    await webhook.send(
                        content=converted_message,
                        username=message.author.display_name,
                        avatar_url=message.author.display_avatar.url
                    )
                    
                    # Delete the original message
                    try:
                        await message.delete()
                    except discord.Forbidden:
                        # If we can't delete, just send a note
                        await message.channel.send(
                            f"*{message.author.mention} said:*\n{converted_message}",
                            reference=message,
                            mention_author=False
                        )
                    
                    logger.info(f"Auto-converted timestamps for {message.author} in {message.channel}")
                    
                except discord.Forbidden:
                    # Fallback if we can't use webhooks
                    await message.channel.send(
                        f"*{message.author.mention} said:*\n{converted_message}",
                        reference=message,
                        mention_author=False
                    )
                    logger.info(f"Auto-converted timestamps (fallback) for {message.author} in {message.channel}")
                
        except Exception as e:
            logger.error(f"Error in on_message timestamp detection: {e}")

    def convert_times_in_message(self, content: str) -> str:
        """Convert all time mentions in a message to Discord timestamps."""
        converted_content = content
        
        # Pre-filter: Skip entire message if it contains specific duration phrases
        # Be more specific to avoid false positives
        if re.search(r'\bin\s+\d+\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b', content, re.IGNORECASE):
            return content  # Return unchanged if it contains "in X hours" patterns
        
        if re.search(r'\b\d+\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\s+(ago|from\s+now|later)\b', content, re.IGNORECASE):
            return content  # Return unchanged if it contains "X hours ago" or "X hours from now" patterns
        
        # Find all times and their positions, avoiding overlaps
        replacements = []
        processed_ranges = []  # Track which parts of the string have been processed
        
        for pattern in self.time_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                original_text = match.group(0)
                start_pos = match.start()
                end_pos = match.end()
                
                # Check if this match overlaps with any already processed range
                overlaps = any(
                    not (end_pos <= proc_start or start_pos >= proc_end)
                    for proc_start, proc_end in processed_ranges
                )
                
                if overlaps:
                    continue  # Skip this match to avoid overlaps
                
                # Additional check: make sure this match isn't part of a duration phrase
                context_start = max(0, start_pos - 15)
                context_end = min(len(content), end_pos + 15)
                context = content[context_start:context_end].lower()
                
                # Skip if this appears to be part of a duration statement
                # But be more specific - don't just look for "in" anywhere
                if re.search(r'\bin\s+\d+\s*(hours?|hrs?|minutes?|mins?)\b', context):
                    continue
                if re.search(r'\b(ago\b|from\s+now|later)\b', context):
                    continue
                
                timestamp = self.parse_time_string(original_text)
                if timestamp:
                    unix_timestamp = int(timestamp.timestamp())
                    # Use short time format for clean display that maintains grammar
                    # :t shows "3:30 PM", :f shows "December 28, 2023 3:30 PM"
                    # For better readability, use :f for dates with time, :t for just times
                    if any(word in original_text.lower() for word in ['tomorrow', 'today', 'dec', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov']):
                        discord_timestamp = f"<t:{unix_timestamp}:f>"  # Full date and time
                    else:
                        discord_timestamp = f"<t:{unix_timestamp}:t>"  # Just time
                    replacements.append((match.start(), match.end(), original_text, discord_timestamp))
                    processed_ranges.append((start_pos, end_pos))
        
        # Sort replacements by position (reverse order to avoid index shifting)
        replacements.sort(key=lambda x: x[0], reverse=True)
        
        # Apply replacements
        for start, end, original, replacement in replacements:
            converted_content = converted_content[:start] + replacement + converted_content[end:]
        
        return converted_content

    def find_times_in_message(self, content: str) -> List[Tuple[str, datetime]]:
        """Find all time mentions in a message and return parsed timestamps."""
        found_times = []
        
        for pattern in self.time_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                original_text = match.group(0)
                timestamp = self.parse_time_string(original_text)
                if timestamp:
                    found_times.append((original_text, timestamp))
        
        return found_times

    def parse_time_string(self, time_str: str, date_str: Optional[str] = None) -> Optional[datetime]:
        """Parse various time formats and return a datetime object."""
        try:
            # Skip if this looks like a duration/future statement
            # Be more specific - only skip if it's clearly a duration
            if re.search(r'\bin\s+\d+\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b', time_str, re.IGNORECASE):
                return None
            if re.search(r'\b\d+\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\s+(ago|from\s+now|later)\b', time_str, re.IGNORECASE):
                return None
            
            # Use local time for calculations - this will be the user's system timezone
            now = datetime.now()
            
            # Combine time and date strings if provided
            full_str = f"{date_str} {time_str}" if date_str else time_str
            
            # Clean up the string
            full_str = full_str.strip().lower()
            
            # Handle "tomorrow at X" or "today at X"
            if "tomorrow" in full_str:
                base_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                base_date = base_date.replace(day=base_date.day + 1)
                time_part = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', full_str)
            elif "today" in full_str:
                base_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                time_part = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', full_str)
            elif re.search(r'\w{3,9}\s+\d{1,2}\s+at', full_str):
                # Handle "Dec 25 at" type patterns
                base_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                # For now, assume it's this year (could be enhanced later)
                time_part = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', full_str)
            else:
                base_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                time_part = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)?', full_str)
            
            if not time_part:
                return None
                
            hour = int(time_part.group(1))
            minute = int(time_part.group(2)) if time_part.group(2) else 0
            am_pm = time_part.group(3)
            
            # Handle AM/PM conversion
            if am_pm:
                if am_pm in ['pm'] and hour != 12:
                    hour += 12
                elif am_pm in ['am'] and hour == 12:
                    hour = 0
            
            # If no AM/PM specified and hour is 1-12, assume next occurrence
            elif hour <= 12:
                # If the time has already passed today, assume tomorrow
                test_time = base_date.replace(hour=hour, minute=minute)
                if test_time < now:
                    # Try PM version
                    if hour != 12:
                        test_time = base_date.replace(hour=hour + 12, minute=minute)
                        if test_time < now:
                            # Still in the past, use tomorrow
                            base_date = base_date.replace(day=base_date.day + 1)
                            hour = hour  # Keep original hour for tomorrow
                    else:
                        # For 12:xx, try tomorrow
                        base_date = base_date.replace(day=base_date.day + 1)
            
            # Validate hour and minute
            if hour > 23 or minute > 59:
                return None
            
            # Create the final datetime in local time
            result = base_date.replace(hour=hour, minute=minute)
            
            # Convert local time to UTC for Discord timestamps
            # Use time.mktime to get local timestamp, then convert to UTC
            local_timestamp = time.mktime(result.timetuple())
            utc_result = datetime.fromtimestamp(local_timestamp, tz=timezone.utc)
                
            return utc_result
            
        except Exception as e:
            logger.error(f"Error parsing time string '{time_str}': {e}")
            return None

async def setup(bot):
    await bot.add_cog(TimestampConverter(bot))
    print("TimestampConverter cog loaded")