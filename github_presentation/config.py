import os
from dotenv import load_dotenv

load_dotenv()

# Discord Configuration
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))  # Your Discord server ID
BOT_ID = int(os.getenv("BOT_ID", "0"))  # Your bot's user ID
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))  # Main channel ID

# Database path - Railway compatible
DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "data", "database.db"))

# Challenge Role Configuration
# Configure these role IDs for your Discord server's challenge system
CHALLENGE_ROLE_IDS = {
    # challenge_id: {threshold: role_id}
    # Example configuration - replace with your server's role IDs
    1: {  # Challenge ID 1
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    2: {  # Challenge ID 2
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    3: {  # Challenge ID 3
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    4: {  # Challenge ID 4
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    5: {  # Challenge ID 5
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    6: {  # Challenge ID 6
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    7: {  # Challenge ID 7
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    8: {  # Challenge ID 8
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    9: {  # Challenge ID 9
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    10: {  # Challenge ID 10
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    11: {  # Challenge ID 11
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    12: {  # Challenge ID 12
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    13: {  # Challenge ID 13
        1.0: 000000000000000000,  # Replace with actual role ID
    },
    # Add more challenges as needed
}
