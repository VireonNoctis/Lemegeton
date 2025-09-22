#!/usr/bin/env python3
"""Debug script for the specific failing case"""

import re

def debug_specific_case():
    # The specific failing message
    test_message = "hey lets meet in 20 hours tomorrow at 3pm"
    
    print(f"Testing message: '{test_message}'")
    
    # Pre-filter check
    if re.search(r'\bin\s+\d+\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b', test_message, re.IGNORECASE):
        print("WOULD BE FILTERED: Contains 'in X hours' pattern")
        return test_message
    
    # Find all pattern matches
    patterns = [
        r'\b(tomorrow|today)\s+at\s+(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b',
        r'\b(tomorrow|today)\s+at\s+(\d{1,2})\s*(am|pm|AM|PM)\b',
    ]
    
    all_matches = []
    for i, pattern in enumerate(patterns):
        matches = list(re.finditer(pattern, test_message, re.IGNORECASE))
        for match in matches:
            print(f"Pattern {i} found: '{match.group(0)}' at {match.start()}-{match.end()}")
            all_matches.append((match.start(), match.end(), match.group(0)))
    
    return test_message

# Also test what happens if user types exactly what they reported
def test_user_reported_case():
    # What if the user's message was already corrupted somehow?
    weird_message = "hey lets meet in 20 hours1758466800:R>"
    print(f"\nTesting weird message: '{weird_message}'")
    
    # Check if this has patterns that would match
    patterns = [
        r'\b(tomorrow|today)\s+at\s+(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)\b',
        r'\b(tomorrow|today)\s+at\s+(\d{1,2})\s*(am|pm|AM|PM)\b',
    ]
    
    for i, pattern in enumerate(patterns):
        matches = list(re.finditer(pattern, weird_message, re.IGNORECASE))
        for match in matches:
            print(f"Pattern {i} found in weird message: '{match.group(0)}'")

if __name__ == "__main__":
    debug_specific_case()
    test_user_reported_case()