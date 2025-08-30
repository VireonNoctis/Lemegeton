import sys
import os
import asyncio
from discord.ext import commands
import discord

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import TOKEN, GUILD_ID

intents = discord.Intents.default()

async def main():
    async with commands.Bot(command_prefix="!", intents=intents) as bot:
        @bot.event
        async def on_ready():
            print(f"Bot connected! Guilds: {[g.id for g in bot.guilds]}")
            guild = discord.Object(id=GUILD_ID)

            # Clear guild commands
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"✅ Guild commands cleared for {GUILD_ID}")

            # Clear global commands
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync(guild=None)
            print("✅ Global commands cleared")

            await bot.close()
            print("✅ Done!")

        await bot.start(TOKEN)

asyncio.run(main())
