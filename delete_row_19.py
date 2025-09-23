#!/usr/bin/env python3
"""
Simple script to delete row 19 from users table.
"""

import sqlite3
import sys
from pathlib import Path

# Database path
DB_PATH = Path("data/database.db")

def main():
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    print(f"🗄️ Using database: {DB_PATH}")
    
    try:
        # Open connection
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        cursor = conn.cursor()
        
        # First show what we're about to delete
        cursor.execute("SELECT rowid, discord_id, guild_id, anilist_username FROM users WHERE rowid = 19")
        user = cursor.fetchone()
        
        if not user:
            print("❌ Row 19 not found")
            conn.close()
            return
        
        print(f"📋 Found row 19:")
        print(f"   Discord ID: {user[1]}")
        print(f"   Guild ID: {user[2]}")
        print(f"   AniList: {user[3]}")
        print()
        
        # Delete the row
        cursor.execute("DELETE FROM users WHERE rowid = 19")
        
        if cursor.rowcount > 0:
            print(f"✅ Successfully deleted row 19")
            conn.commit()
        else:
            print("❌ No rows were deleted")
        
        conn.close()
        print("✅ Database connection closed")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()