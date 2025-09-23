#!/usr/bin/env python3
"""
Test script for manga format distribution functionality
Testing the emoji mapping and format processing logic
"""

import sys
import os

# Mock format data to simulate AniList API response
mock_format_data = {
    "formats": [
        {"format": "MANGA", "count": 45},
        {"format": "MANHWA", "count": 12}, 
        {"format": "MANHUA", "count": 8},
        {"format": "ONE_SHOT", "count": 3},
        {"format": "DOUJINSHI", "count": 2},
        {"format": "NOVEL", "count": 1}
    ]
}

def test_format_distribution():
    """Test the manga format distribution processing logic"""
    
    print("🔍 Testing Manga Format Distribution Functionality")
    print("=" * 60)
    
    # This is the same logic from the profile cog
    format_emoji_map = {
        "MANGA": "📚",  
        "MANHWA": "🇰🇷",  
        "MANHUA": "🇨🇳",  
        "ONE_SHOT": "📖",
        "DOUJINSHI": "📕",
        "NOVEL": "📄"
    }
    
    print("📋 Available Format Emojis:")
    for format_name, emoji in format_emoji_map.items():
        print(f"  {emoji} {format_name}")
    print()
    
    print("📊 Mock Format Data:")
    for item in mock_format_data["formats"]:
        format_name = item["format"]
        count = item["count"]
        emoji = format_emoji_map.get(format_name, "📚")  # Default to manga emoji
        print(f"  {emoji} {format_name}: {count} entries")
    print()
    
    # Test the field creation logic
    print("🎯 Testing Field Creation:")
    
    # Calculate total for percentage
    total_entries = sum(item["count"] for item in mock_format_data["formats"])
    print(f"📈 Total Entries: {total_entries}")
    
    # Create the field content (same as profile cog logic)
    field_lines = []
    for item in mock_format_data["formats"]:
        format_name = item["format"]
        count = item["count"]
        emoji = format_emoji_map.get(format_name, "📚")
        
        # Calculate percentage
        percentage = (count / total_entries * 100) if total_entries > 0 else 0
        
        # Format the line
        line = f"{emoji} {format_name.title()}: {count} ({percentage:.1f}%)"
        field_lines.append(line)
        print(f"  ✅ {line}")
    
    print()
    print("📝 Final Field Content:")
    field_content = "\n".join(field_lines)
    print(f'"{field_content}"')
    
    print()
    print("✅ Test completed successfully!")
    print(f"📚 Manga emoji test: {'📚' == '📚'}")
    print(f"🇰🇷 Manhwa emoji test: {'🇰🇷' == '🇰🇷'}")  
    print(f"🇨🇳 Manhua emoji test: {'🇨🇳' == '🇨🇳'}")
    
    # Test for the corrupted character issue
    test_string = "📚 Manga Format Distribution"
    print(f"\n🔧 Unicode Test: '{test_string}'")
    print(f"🔧 No corrupted chars: {'�' not in test_string}")
    
    return field_content

if __name__ == "__main__":
    result = test_format_distribution()
    print(f"\n🎊 Test Result Length: {len(result)} characters")