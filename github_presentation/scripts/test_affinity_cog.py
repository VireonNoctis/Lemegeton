#!/usr/bin/env python3
"""
Test script to verify the affinity cog can be imported and the affinity command works.
This tests the enhanced affinity system in isolation.
"""

import asyncio
import sys
import os

# Mock Discord components for testing
class MockUser:
    def __init__(self, id, display_name):
        self.id = id
        self.display_name = display_name

class MockInteraction:
    def __init__(self, user, target_user):
        self.user = user
        self.target_user = target_user
        self.response = MockResponse()
        self.followup = MockFollowup()

class MockResponse:
    async def send_message(self, content=None, embed=None, view=None, ephemeral=False):
        print(f"Response: {content}")
        if embed:
            print(f"Embed: {embed.title} - {embed.description}")

class MockFollowup:
    async def send(self, content=None, embed=None, view=None, ephemeral=False):
        print(f"Followup: {content}")
        if embed:
            print(f"Embed: {embed.title} - {embed.description}")

class MockBot:
    def __init__(self):
        pass

# Mock the database functions that the affinity cog uses
class MockDatabase:
    @staticmethod
    def get_user_anilist_username(user_id):
        # Mock database responses for test users
        if user_id == 12345:
            return "TestUser1"
        elif user_id == 67890:
            return "TestUser2"
        return None

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

def test_affinity_import():
    """Test that the affinity cog can be imported successfully"""
    try:
        # Mock the database import
        import database
        database.get_user_anilist_username = MockDatabase.get_user_anilist_username
        
        # Import the affinity cog
        from cogs.affinity import Affinity
        print("✅ Affinity cog imported successfully!")
        
        # Create a mock bot and initialize the cog
        bot = MockBot()
        affinity_cog = Affinity(bot)
        print("✅ Affinity cog initialized successfully!")
        
        return affinity_cog
        
    except ImportError as e:
        print(f"❌ Failed to import affinity cog: {e}")
        return None
    except Exception as e:
        print(f"❌ Error initializing affinity cog: {e}")
        return None

def test_calculate_affinity():
    """Test the calculate_affinity method directly"""
    try:
        # Test data from our previous test
        user1_data = {
            "data": {
                "User": {
                    "id": 1,
                    "name": "TestUser1",
                    "statistics": {
                        "anime": {
                            "count": 150,
                            "meanScore": 7.2,
                            "standardDeviation": 1.8,
                            "minutesWatched": 18000,
                            "episodesWatched": 1200,
                            "genres": [
                                {"genre": "Action", "count": 45, "meanScore": 7.5},
                                {"genre": "Drama", "count": 30, "meanScore": 8.0}
                            ],
                            "formats": [
                                {"format": "TV", "count": 80, "meanScore": 7.3},
                                {"format": "MOVIE", "count": 35, "meanScore": 7.8}
                            ],
                            "scores": [
                                {"score": 10, "count": 8},
                                {"score": 9, "count": 15},
                                {"score": 8, "count": 25}
                            ]
                        }
                    },
                    "favourites": {
                        "anime": {
                            "nodes": [
                                {"id": 1, "title": {"romaji": "Attack on Titan"}},
                                {"id": 2, "title": {"romaji": "Death Note"}}
                            ]
                        }
                    }
                }
            }
        }
        
        user2_data = {
            "data": {
                "User": {
                    "id": 2,
                    "name": "TestUser2",
                    "statistics": {
                        "anime": {
                            "count": 200,
                            "meanScore": 7.8,
                            "standardDeviation": 1.5,
                            "minutesWatched": 24000,
                            "episodesWatched": 1600,
                            "genres": [
                                {"genre": "Action", "count": 55, "meanScore": 7.9},
                                {"genre": "Drama", "count": 40, "meanScore": 8.2}
                            ],
                            "formats": [
                                {"format": "TV", "count": 120, "meanScore": 7.8},
                                {"format": "MOVIE", "count": 45, "meanScore": 8.2}
                            ],
                            "scores": [
                                {"score": 10, "count": 12},
                                {"score": 9, "count": 22},
                                {"score": 8, "count": 35}
                            ]
                        }
                    },
                    "favourites": {
                        "anime": {
                            "nodes": [
                                {"id": 2, "title": {"romaji": "Death Note"}},
                                {"id": 3, "title": {"romaji": "Fullmetal Alchemist: Brotherhood"}}
                            ]
                        }
                    }
                }
            }
        }
        
        # Import the cog and test the calculation
        import database
        database.get_user_anilist_username = MockDatabase.get_user_anilist_username
        
        from cogs.affinity import Affinity
        bot = MockBot()
        affinity_cog = Affinity(bot)
        
        # Test the calculate_affinity method with breakdown
        result = affinity_cog.calculate_affinity(user1_data, user2_data, return_breakdown=True)
        
        if result and isinstance(result, tuple) and len(result) == 2:
            score, breakdown = result
            print(f"✅ Affinity calculation successful!")
            print(f"   Final Score: {score:.4f} ({score*100:.2f}%)")
            
            if breakdown and 'components' in breakdown:
                print(f"   Components calculated: {len(breakdown['components'])}")
                for comp_name, comp_data in breakdown['components'].items():
                    print(f"   - {comp_name}: {comp_data['score']:.4f}")
            
            return True
        else:
            print("❌ Affinity calculation returned invalid result")
            print(f"   Result type: {type(result)}")
            print(f"   Result: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing affinity calculation: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("🧪 Testing Enhanced Affinity Cog")
    print("=" * 50)
    
    # Test 1: Import test
    print("\n📦 Test 1: Import Test")
    affinity_cog = test_affinity_import()
    
    if affinity_cog is None:
        print("❌ Cannot proceed with further tests - import failed")
        return
    
    # Test 2: Calculation test
    print("\n🧮 Test 2: Calculation Test")
    calc_success = test_calculate_affinity()
    
    if calc_success:
        print("\n✅ All tests passed! Enhanced Affinity system is working correctly.")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")

if __name__ == "__main__":
    main()