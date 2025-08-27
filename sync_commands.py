import discord
from discord.ext import commands
import asyncio
from config import TOKEN, GUILD_ID, BOT_ID

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents, application_id=BOT_ID)

# -------------------------------
# Example COG list (loaded cogs)
# -------------------------------
# Make sure these match your actual loaded cog class names
LOADED_COGS = [
    "Registration",
    "Manga",
    "Unregister",
    "ChallengeRules",
    "Changelog",
    "Anime",
    "Profile",
    "Recommendations",
    "AutoEmbed"
]

async def clear_unused_commands():
    await bot.wait_until_ready()
    guild = discord.Object(id=GUILD_ID)

    try:
        commands_in_guild = await bot.tree.fetch_commands(guild=guild)
        for cmd in commands_in_guild:
            # If command name not in any loaded cog, delete it
            if cmd.name not in [c.lower() for c in LOADED_COGS]:
                await bot.tree.delete_command(cmd.name, guild=guild)
                print(f"🗑 Deleted unused command: {cmd.name}")
            else:
                print(f"✅ Kept command: {cmd.name}")
        print("✅ Done clearing unused commands!")
    except Exception as e:
        print(f"❌ Error clearing commands: {e}")

async def main():
    async with bot:
        bot.loop.create_task(clear_unused_commands())
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
