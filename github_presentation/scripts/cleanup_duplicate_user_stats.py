"""
Script to clean up duplicate entries in the user_stats table.
Run this if you're experiencing duplicate users in leaderboards.
"""
import asyncio
import aiosqlite
from pathlib import Path

DB_PATH = Path("../database.db").resolve()

async def cleanup_duplicate_user_stats():
    """Clean up duplicate entries in user_stats table."""
    print("Starting cleanup of duplicate user_stats entries...")
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Find all duplicated usernames
        cursor = await db.execute("""
            SELECT username, COUNT(*) as count 
            FROM user_stats 
            GROUP BY username 
            HAVING count > 1
        """)
        duplicates = await cursor.fetchall()
        await cursor.close()
        
        if not duplicates:
            print("No duplicate user_stats entries found!")
            return
        
        print(f"Found {len(duplicates)} users with duplicate entries:")
        for username, count in duplicates:
            print(f"  - {username}: {count} entries")
        
        # For each duplicated username, keep only the entry with the correct discord_id from users table
        cleaned_count = 0
        for username, count in duplicates:
            print(f"\nCleaning up {count} duplicate entries for {username}...")
            
            # Get the correct discord_id from the users table
            cursor = await db.execute("""
                SELECT discord_id FROM users WHERE anilist_username = ? OR username = ?
            """, (username, username))
            correct_user = await cursor.fetchone()
            await cursor.close()
            
            if not correct_user:
                print(f"  ⚠️  No user found in users table for {username}, skipping...")
                continue
            
            correct_discord_id = correct_user[0]
            print(f"  Correct discord_id for {username}: {correct_discord_id}")
            
            # Get all entries for this username, prioritizing the one with correct discord_id
            cursor = await db.execute("""
                SELECT discord_id, username, total_manga, total_anime, 
                       avg_manga_score, avg_anime_score, total_chapters, total_episodes
                FROM user_stats 
                WHERE username = ?
                ORDER BY 
                    CASE WHEN discord_id = ? THEN 0 ELSE 1 END,  -- Prioritize correct discord_id
                    (total_manga + total_anime + COALESCE(total_chapters, 0) + COALESCE(total_episodes, 0)) DESC,
                    discord_id DESC
            """, (username, correct_discord_id))
            entries = await cursor.fetchall()
            await cursor.close()
            
            if entries:
                # Keep the first (most preferred) entry, but ensure discord_id is correct
                keep_entry = list(entries[0])
                keep_entry[0] = correct_discord_id  # Ensure discord_id is correct
                
                print(f"  Keeping entry with corrected discord_id={correct_discord_id}")
                print(f"  Removing {len(entries) - 1} duplicate entries...")
                
                # Delete all entries for this username
                await db.execute("DELETE FROM user_stats WHERE username = ?", (username,))
                
                # Re-insert the corrected entry
                await db.execute("""
                    INSERT INTO user_stats (
                        discord_id, username, total_manga, total_anime,
                        avg_manga_score, avg_anime_score, total_chapters, total_episodes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, keep_entry)
                
                cleaned_count += len(entries) - 1
        
        await db.commit()
        print(f"\n✅ Successfully cleaned up {cleaned_count} duplicate entries!")

async def main():
    try:
        await cleanup_duplicate_user_stats()
        print("\n🎉 Cleanup completed successfully!")
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")

if __name__ == "__main__":
    asyncio.run(main())