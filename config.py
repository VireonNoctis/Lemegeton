import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
BOT_ID = int(os.getenv("BOT_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")
CHALLENGE_ROLE_IDS = {
    # challenge_id: {threshold: role_id}
    1: {  # Challenge ID 1
        1.0: 1093985707091046593,
    },
    2: {  # Challenge ID 2
        1.0: 1010651450239627417,
    },
    3: {  # Challenge ID 3
        1.0: 1020028721010319360,
    },
    4: {  # Challenge ID 4
        1.0: 1033338002820313121,
    },
    5: {  # Challenge ID 5
        1.0: 1075042063596392469,
    },
    6: {  # Challenge ID 6
        1.0: 1163794823657037874,
    },
    7: {  # Challenge ID 7
        1.0: 1075042050455650385,
    },
    8: {  # Challenge ID 8
        1.0: 1180150004279693392,
    },
    9: {  # Challenge ID 9
        1.0: 1004793487432106064,
    },
    10: {  # Challenge ID 10
        1.0: 1413986509631131708,
    },
    11: {  # Challenge ID 11
        1.0: 1414696905317023754,
    },
    12: {  # Challenge ID 12
        1.0: 1414697102474219611,
    },
    13: {  # Challenge ID 13
        1.0: 1414286327507321074,
    },
}
