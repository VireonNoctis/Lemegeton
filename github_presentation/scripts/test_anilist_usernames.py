#!/usr/bin/env python3
"""
Test script to verify AniList username checking functionality.
"""

import sys
import os
import asyncio
import aiohttp
import json

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_anilist_username(username: str):
    """Test if an AniList username exists."""
    ANILIST_API_URL = "https://graphql.anilist.co"
    
    query = """
    query ($username: String) {
      User(name: $username) {
        id
        name
      }
    }
    """
    variables = {"username": username}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(ANILIST_API_URL, json={"query": query, "variables": variables}) as resp:
                text = await resp.text()
                print(f"Status: {resp.status}")
                
                if resp.status == 200:
                    data = json.loads(text)
                    user_data = data.get("data", {}).get("User")
                    if user_data:
                        print(f"✅ User exists: {user_data.get('name')} (ID: {user_data.get('id')})")
                        return True
                    else:
                        print(f"❌ User not found in response: {data}")
                        return False
                else:
                    try:
                        data = json.loads(text)
                        print(f"❌ API Error: {data}")
                    except:
                        print(f"❌ API Error: {text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Network Error: {e}")
        return False

async def main():
    """Test various AniList usernames."""
    test_usernames = [
        "slopking._",        # The problematic username
        "slopking",          # Without special characters
        "Slopking._",        # Different capitalization
        "nonexistentuser123", # Definitely doesn't exist
        "demo"               # Known to exist
    ]
    
    print("🧪 Testing AniList username checking functionality...")
    print("=" * 50)
    
    for username in test_usernames:
        print(f"\n🔍 Testing username: '{username}'")
        exists = await test_anilist_username(username)
        print(f"Result: {'✅ EXISTS' if exists else '❌ NOT FOUND'}")
        
        # Small delay between tests
        await asyncio.sleep(1.0)
    
    print("\n" + "=" * 50)
    print("🎉 Username testing completed!")

if __name__ == "__main__":
    asyncio.run(main())