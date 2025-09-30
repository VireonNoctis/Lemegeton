import logging
import functools
from datetime import datetime
from typing import Callable, Any
import discord
from discord.ext import commands

logger = logging.getLogger("CommandLogger")
logger.setLevel(logging.INFO)

# Ensure logs directory exists
import os
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "command_usage.log")

# Set up file handler for command logging
if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == os.path.abspath(LOG_FILE)
           for h in logger.handlers):
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
        logger.addHandler(file_handler)
    except Exception:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s"))
        logger.addHandler(stream_handler)

def log_command(func: Callable) -> Callable:
    """
    Decorator to log command usage with user, guild, and command information.
    Works with both regular commands and app commands.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Extract interaction or context based on the first argument
        if args and hasattr(args[0], 'guild_id'):  # App command interaction
            interaction = args[0]
            user_id = interaction.user.id
            user_name = interaction.user.display_name
            guild_id = interaction.guild_id
            guild_name = interaction.guild.name if interaction.guild else "DM"
            command_name = func.__name__
            
            logger.info(f"Command '{command_name}' used by {user_name} ({user_id}) in guild '{guild_name}' ({guild_id})")
            
        elif args and hasattr(args[0], 'author'):  # Traditional command context
            ctx = args[0]
            user_id = ctx.author.id
            user_name = ctx.author.display_name
            guild_id = ctx.guild.id if ctx.guild else None
            guild_name = ctx.guild.name if ctx.guild else "DM"
            command_name = func.__name__
            
            logger.info(f"Command '{command_name}' used by {user_name} ({user_id}) in guild '{guild_name}' ({guild_id})")
            
        else:
            # Fallback logging
            logger.info(f"Command '{func.__name__}' executed")
        
        # Execute the original function
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            # Log any errors that occur during command execution
            logger.error(f"Error in command '{func.__name__}': {e}")
            raise
    
    return wrapper
