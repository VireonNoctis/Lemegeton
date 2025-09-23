#!/usr/bin/env python3
"""Debug script for timestamp conversion issues"""

import re
from datetime import datetime, timezone

def convert_times_in_message(content: str) -> str:
    """Test version of the convert times function"""
    converted_content = content
    
    # Time patterns (simplified version for testing)
    time_patterns = [
        r'\b(tomorrow|today)\s+at\s+(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b',
        r'\b(tomorrow|today)\s+at\s+(\d{1,2})\s*(am|pm|AM|PM)\b',
    ]
    
    # Pre-filter: Skip entire message if it contains specific duration phrases
    if re.search(r'\bin\s+\d+\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b', content, re.IGNORECASE):
        print(f"SKIPPED due to 'in X hours' pattern: {content}")
        return content
    
    if re.search(r'\b\d+\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\s+(ago|from\s+now|later)\b', content, re.IGNORECASE):
        print(f"SKIPPED due to 'X hours ago' pattern: {content}")
        return content
    
    # Find all times and their positions
    replacements = []
    
    for pattern in time_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            original_text = match.group(0)
            print(f"Found match: '{original_text}' at position {match.start()}-{match.end()}")
            
            # Additional context check
            start_pos = match.start()
            end_pos = match.end()
            context_start = max(0, start_pos - 15)
            context_end = min(len(content), end_pos + 15)
            context = content[context_start:context_end].lower()
            
            if re.search(r'\bin\s+\d+\s*(hours?|hrs?|minutes?|mins?)\b', context):
                print(f"SKIPPED due to context 'in X hours': {context}")
                continue
            if re.search(r'\b(ago\b|from\s+now|later)\b', context):
                print(f"SKIPPED due to context 'ago/later': {context}")
                continue
            
            # Simulate timestamp creation
            unix_timestamp = 1758466800  # Fixed timestamp for testing
            discord_timestamp = f"<t:{unix_timestamp}:R>"
            
            print(f"Creating replacement: '{original_text}' -> '{discord_timestamp}'")
            replacements.append((match.start(), match.end(), original_text, discord_timestamp))
    
    # Sort replacements by position (reverse order to avoid index shifting)
    replacements.sort(key=lambda x: x[0], reverse=True)
    print(f"Final replacements: {replacements}")
    
    # Apply replacements
    for start, end, original, replacement in replacements:
        print(f"Applying: pos {start}-{end}, '{original}' -> '{replacement}'")
        before = converted_content
        converted_content = converted_content[:start] + replacement + converted_content[end:]
        print(f"Before: '{before}'")
        print(f"After:  '{converted_content}'")
    
    return converted_content

if __name__ == "__main__":
    # Test cases
    test_messages = [
        "hey lets meet tomorrow at 3pm",
        "hey lets meet in 20 hours",
        "tomorrow at 3pm would work",
        "see you tomorrow at 3:30pm",
        "I'll be there in 20 hours",
        "tomorrow at 3pm sounds good",
    ]
    
    for msg in test_messages:
        print(f"\n=== Testing: '{msg}' ===")
        result = convert_times_in_message(msg)
        print(f"Result: '{result}'")
        print("-" * 50)