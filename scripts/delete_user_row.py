#!/usr/bin/env python3
"""
Script to delete a specific row from the users table by row number.
This script provides a safe way to remove user records from the database.

Usage: python delete_user_row.py --row-id <row_number>
Example: python delete_user_row.py --row-id 19

CAUTION: This operation is irreversible. Make sure you have a backup!
"""

import os
import sys
import sqlite3
import argparse
from pathlib import Path

# Add the parent directory to the path to import config
sys.path.append(str(Path(__file__).parent.parent))

try:
    import config
    DB_PATH = config.DB_PATH
except ImportError:
    # Fallback to default path
    DB_PATH = Path(__file__).parent.parent / "data" / "database.db"

def get_user_by_rowid(db_path: Path, rowid: int):
    """Get user information by ROWID"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT rowid, discord_id, guild_id, anilist_username, created_at FROM users WHERE rowid = ?", (rowid,))
        user_row = cursor.fetchone()
        conn.close()
        
        if user_row:
            return {
                'rowid': user_row[0],
                'discord_id': user_row[1],
                'guild_id': user_row[2], 
                'anilist_username': user_row[3],
                'created_at': user_row[4]
            }
        return None
    except Exception as e:
        print(f"❌ Error retrieving user: {e}")
        return None

def delete_user_by_rowid(db_path: Path, rowid: int, confirm: bool = False):
    """Delete user by ROWID with safety checks"""
    
    # First, check if the user exists and show details
    user = get_user_by_rowid(db_path, rowid)
    if not user:
        print(f"❌ No user found with row ID {rowid}")
        return False
    
    print(f"📋 Found user to delete:")
    print(f"   Row ID: {user['rowid']}")
    print(f"   Discord ID: {user.get('discord_id', 'N/A')}")
    print(f"   Guild ID: {user.get('guild_id', 'N/A')}")
    print(f"   AniList Username: {user.get('anilist_username', 'N/A')}")
    print(f"   Created: {user.get('created_at', 'N/A')}")
    print()
    
    if not confirm:
        response = input("⚠️  Are you sure you want to delete this user? This cannot be undone! (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Operation cancelled")
            return False
    
    # Perform the deletion
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Delete the user
        cursor.execute("DELETE FROM users WHERE rowid = ?", (rowid,))
        
        if cursor.rowcount == 0:
            print(f"❌ No user found with row ID {rowid}")
            conn.close()
            return False
        
        conn.commit()
        conn.close()
        
        print(f"✅ Successfully deleted user with row ID {rowid}")
        print(f"   Discord ID: {user.get('discord_id')}")
        print(f"   AniList Username: {user.get('anilist_username', 'N/A')}")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting user: {e}")
        return False

def list_recent_users(db_path: Path, limit: int = 10):
    """List recent users to help identify the correct row"""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT rowid, discord_id, guild_id, anilist_username, created_at 
            FROM users 
            ORDER BY rowid DESC 
            LIMIT ?
        """, (limit,))
        
        users = cursor.fetchall()
        conn.close()
        
        if not users:
            print("❌ No users found in database")
            return
        
        print(f"📋 Recent {len(users)} users:")
        print("Row ID | Discord ID          | Guild ID            | AniList Username | Created")
        print("-" * 85)
        
        for user in users:
            # Access by index since column names might not match
            rowid = user[0] if len(user) > 0 else 'N/A'
            discord_id = str(user[1]) if len(user) > 1 and user[1] else 'N/A'
            guild_id = str(user[2]) if len(user) > 2 and user[2] else 'N/A' 
            anilist_username = user[3] if len(user) > 3 and user[3] else 'N/A'
            created = user[4] if len(user) > 4 and user[4] else 'N/A'
            
            print(f"{rowid:<6} | {discord_id:<19} | {guild_id:<19} | {anilist_username:<16} | {created}")
        
    except Exception as e:
        print(f"❌ Error listing users: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Delete a user row from the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python delete_user_row.py --list                    # Show recent users
  python delete_user_row.py --row-id 19              # Delete row 19 (with confirmation)
  python delete_user_row.py --row-id 19 --confirm    # Delete row 19 (no confirmation)
  
CAUTION: This operation is irreversible. Make sure you have a backup!
        """
    )
    
    parser.add_argument('--row-id', type=int, help='Row ID to delete from users table')
    parser.add_argument('--list', action='store_true', help='List recent users to help identify row IDs')
    parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--db-path', type=str, default=str(DB_PATH), 
                       help=f'Path to database file (default: {DB_PATH})')
    
    args = parser.parse_args()
    
    db_path = Path(args.db_path)
    
    # Check if database exists
    if not db_path.exists():
        print(f"❌ Database file not found: {db_path}")
        print("Make sure the bot has been run at least once to create the database.")
        sys.exit(1)
    
    print(f"🗄️  Using database: {db_path}")
    print(f"📊 Database size: {db_path.stat().st_size:,} bytes")
    print()
    
    if args.list:
        list_recent_users(db_path)
        return
    
    if not args.row_id:
        print("❌ Please specify --row-id or use --list to see available rows")
        parser.print_help()
        sys.exit(1)
    
    # Perform the deletion
    success = delete_user_by_rowid(db_path, args.row_id, args.confirm)
    
    if success:
        print("\n🎉 User deletion completed successfully!")
    else:
        print("\n❌ User deletion failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()