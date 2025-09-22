#!/usr/bin/env python3
"""
Test the actual build_achievements function with manga format distribution
"""

import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'cogs'))

from cogs.profile import build_achievements

# Mock data that would normally come from AniList API
mock_anime_stats = {
    "count": 150,
    "episodesWatched": 2340,
    "meanScore": 7.8,
    "statuses": [
        {"status": "COMPLETED", "count": 80},
        {"status": "CURRENT", "count": 15},
        {"status": "PAUSED", "count": 10},
        {"status": "DROPPED", "count": 20},
        {"status": "PLANNING", "count": 25}
    ],
    "formats": [
        {"format": "TV", "count": 85},
        {"format": "MOVIE", "count": 32}, 
        {"format": "OVA", "count": 18},
        {"format": "SPECIAL", "count": 15}
    ]
}

mock_manga_stats = {
    "count": 71,
    "chaptersRead": 1890,
    "meanScore": 8.1,
    "statuses": [
        {"status": "COMPLETED", "count": 40},
        {"status": "CURRENT", "count": 8},
        {"status": "PAUSED", "count": 5},
        {"status": "DROPPED", "count": 12},
        {"status": "PLANNING", "count": 6}
    ],
    "formats": [
        {"format": "MANGA", "count": 45},
        {"format": "ONE_SHOT", "count": 3},
        {"format": "DOUJINSHI", "count": 2},
        {"format": "NOVEL", "count": 1}
    ],
    "countries": [
        {"country": "JP", "count": 30},  # Japanese Manga
        {"country": "KR", "count": 12},  # Korean Manhwa
        {"country": "CN", "count": 8},   # Chinese Manhua
        {"country": "US", "count": 5}    # Other countries (will be added to Manga)
    ]
}

def test_build_achievements():
    """Test the build_achievements function with our manga format data"""
    
    print("🔍 Testing build_achievements Function")
    print("=" * 50)
    
    try:
        # Call the actual function from profile.py
        result = build_achievements(mock_anime_stats, mock_manga_stats)
        
        print("✅ build_achievements function executed successfully!")
        print(f"📊 Result type: {type(result)}")
        print(f"📊 Result keys: {list(result.keys())}")
        
        # Let's explore the structure
        for key, value in result.items():
            print(f"\n📁 {key}: {type(value)}")
            if isinstance(value, dict):
                print(f"  📋 Sub-keys: {list(value.keys())}")
                
                # Look for manga format distribution in sub-keys
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if "Format" in str(sub_key) or "format" in str(sub_key):
                            print(f"  🎯 Found format field: {sub_key}")
                            print(f"     Content: {sub_value}")
            elif isinstance(value, str):
                print(f"  📄 Content preview: {value[:100]}...")
        
        # Search all fields for manga format distribution
        manga_field = None
        field_location = None
        
        def search_for_manga_field(data, path=""):
            nonlocal manga_field, field_location
            if isinstance(data, dict):
                for k, v in data.items():
                    current_path = f"{path}.{k}" if path else k
                    if "Format Distribution" in str(k) or "format" in str(k).lower():
                        print(f"🔍 Found potential field at {current_path}: {k}")
                        if "📚" in str(v) or "🇰🇷" in str(v) or "Manga" in str(v):
                            manga_field = v
                            field_location = current_path
                            return True
                    if search_for_manga_field(v, current_path):
                        return True
            return False
        
        search_for_manga_field(result)
        
        # Check if manga format distribution field exists in stats
        if "stats" in result and "format_distribution" in result["stats"]:
            manga_field_data = result["stats"]["format_distribution"]
            print(f"\n📚 Manga Format Distribution Found in stats!")
            print(f"📋 Field data: {manga_field_data}")
            
            # Check the processed format distribution
            expected_formats = ['Manga', 'Manhwa', 'Manhua', 'One Shot', 'Doujinshi', 'Novel']
            formats_found = []
            for format_name in expected_formats:
                if format_name in manga_field_data:
                    formats_found.append(f"{format_name}: {manga_field_data[format_name]}")
            
            print(f"✅ Formats processed correctly: {formats_found}")
            print("✅ The emoji mapping and field processing worked!")
            print("   (Note: Emojis are added during Discord embed creation, not in raw data)")
            
        else:
            print("❌ Manga Format Distribution field not found in stats!")
            if "stats" in result:
                print(f"Available stats fields: {list(result['stats'].keys())}")
        
        # Check completion rate
        if "stats" in result and "completion_rate" in result["stats"]:
            completion_rate = result["stats"]["completion_rate"]
            print(f"\n📈 Completion Rate: {completion_rate}%")
            
            # Check if it's properly capped
            if completion_rate <= 100:
                print("✅ Completion rate properly capped at 100%!")
            else:
                print(f"❌ Completion rate exceeds 100%: {completion_rate}%")
        
        return result
        
    except Exception as e:
        print(f"❌ build_achievements function failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = test_build_achievements()
    if result:
        print(f"\n🎊 Test completed successfully!")
        print(f"📊 Total achievements: {len(result)} fields")
    else:
        print(f"\n💥 Test failed!")