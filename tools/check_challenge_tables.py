import sqlite3
import os
import config

# Connect to database using configured path (fallback to data/database.db)
database_path = os.getenv('DATABASE_PATH', getattr(config, 'DB_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'database.db')))
conn = sqlite3.connect(database_path)
cursor = conn.cursor()

cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [row[0] for row in cursor.fetchall()]

print('Challenge-related tables with guild_id status:')
challenge_tables = [t for t in tables if 'challenge' in t.lower() or 'manga' in t.lower() or 'user' in t.lower()]

for table in sorted(challenge_tables):
    cursor.execute(f'PRAGMA table_info({table})')
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    has_guild_id = 'guild_id' in column_names
    status = 'YES' if has_guild_id else 'NO'
    print(f'  {table}: guild_id = {status}')

conn.close()