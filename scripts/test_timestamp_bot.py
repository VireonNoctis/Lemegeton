import os
import sys
sys.path.append('.')

# Create a minimal bot just for testing timestamp
import discord
from discord.ext import commands
import asyncio
from cogs.timestamp import TimestampConverter
from config import TOKEN

class TestBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
    
    async def on_ready(self):
        print(f'{self.user} is ready!')
        
    async def setup_hook(self):
        await self.add_cog(TimestampConverter(self))

if __name__ == "__main__":
    bot = TestBot()
    try:
        bot.run(TOKEN)
    except KeyboardInterrupt:
        print("Bot stopped.")