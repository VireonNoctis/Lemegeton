#!/usr/bin/env python3
"""Test the updated regex patterns for overlap issues"""

import re

# Updated patterns with overlap prevention (fixed regex)
time_patterns = [
    # Date and time combinations first (most specific) - these should match first
    r'\b(tomorrow|today)\s+at\s+(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b',
    r'\b(tomorrow|today)\s+at\s+(\d{1,2})\s*(am|pm|AM|PM)\b',
    r'\b(\w{3,9}\s+\d{1,2})\s+at\s+(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b',
    r'\b(\w{3,9}\s+\d{1,2})\s+at\s+(\d{1,2})\s*(am|pm|AM|PM)\b',
    # Standalone time formats (will be filtered out by overlap detection)
    r'\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b',
    r'\b(\d{1,2})\s*(am|pm|AM|PM)\b',
    # 24-hour format (very restrictive - must have colon and be valid time)
    r'\b([01]?\d|2[0-3]):([0-5]\d)\b(?=\s|$|[^\d])',
]

def test_patterns():
    test_messages = [
        "hey lets meet tomorrow at 3pm",
        "let's meet at 3pm tomorrow",  # This should NOT double-match
        "see you at 3pm",
        "tomorrow at 3:30pm works",
        "I'll be there at 15:30",
        "meeting is at 3pm today",
    ]
    
    for content in test_messages:
        print(f"\n=== Testing: '{content}' ===")
        
        # Track all matches and check for overlaps
        all_matches = []
        processed_ranges = []
        
        for i, pattern in enumerate(time_patterns):
            matches = list(re.finditer(pattern, content, re.IGNORECASE))
            for match in matches:
                start_pos = match.start()
                end_pos = match.end()
                
                # Check for overlaps
                overlaps = any(
                    not (end_pos <= proc_start or start_pos >= proc_end)
                    for proc_start, proc_end in processed_ranges
                )
                
                if overlaps:
                    print(f"  Pattern {i} SKIPPED (overlap): '{match.group(0)}' at {start_pos}-{end_pos}")
                    continue
                
                print(f"  Pattern {i} matched: '{match.group(0)}' at {start_pos}-{end_pos}")
                all_matches.append((start_pos, end_pos, match.group(0), f"<t:1758466800:R>"))
                processed_ranges.append((start_pos, end_pos))
        
        print(f"  Final matches: {len(all_matches)}")
        
        # Simulate replacement
        if all_matches:
            # Sort by position (reverse order)
            all_matches.sort(key=lambda x: x[0], reverse=True)
            
            result = content
            for start, end, original, replacement in all_matches:
                result = result[:start] + replacement + result[end:]
            
            print(f"  Result: '{result}'")

if __name__ == "__main__":
    test_patterns()