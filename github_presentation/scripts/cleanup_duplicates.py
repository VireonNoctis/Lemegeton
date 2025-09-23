import sqlite3
from pathlib import Path

# Connect to database
DB_PATH = Path("database.db").resolve()
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Cleaning up duplicate user_stats entries...")

# Clean up duplicates by removing entries with low IDs that have high ID counterparts
cursor.execute('''
DELETE FROM user_stats 
WHERE discord_id IN (
    SELECT us1.discord_id 
    FROM user_stats us1
    JOIN user_stats us2 ON us1.username = us2.username 
    WHERE us1.discord_id != us2.discord_id AND us1.discord_id < 1000
)
''')

deleted = cursor.rowcount
conn.commit()
print(f'Deleted {deleted} duplicate entries')

# Check for remaining duplicates
cursor.execute('''
SELECT username, COUNT(*) as count 
FROM user_stats 
GROUP BY username 
HAVING COUNT(*) > 1
''')
duplicates = cursor.fetchall()
print(f'Remaining duplicates: {len(duplicates)}')
if duplicates:
    print("Duplicated users:")
    for username, count in duplicates:
        print(f"  {username}: {count} entries")

conn.close()