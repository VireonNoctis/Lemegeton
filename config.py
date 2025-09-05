import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
BOT_ID = int(os.getenv("BOT_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")