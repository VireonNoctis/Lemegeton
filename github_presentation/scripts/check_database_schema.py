#!/usr/bin/env python3
"""
Check database schema to see column order.
"""

import sys
import os
import asyncio

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import execute_db_operation

async def check_schema():
    """Check the users table schema."""
    try:
        schema = await execute_db_operation('check schema', 'PRAGMA table_info(users)', fetch_type='all')
        print("Users table schema:")
        for i, column in enumerate(schema):
            print(f"  Index {i}: {column[1]} ({column[2]})")
        
        # Also check a sample user
        sample = await execute_db_operation('get sample user', 'SELECT * FROM users LIMIT 1', fetch_type='one')
        if sample:
            print(f"\nSample user data (length: {len(sample)}):")
            for i, value in enumerate(sample):
                column_name = schema[i][1] if i < len(schema) else f"unknown_{i}"
                print(f"  Index {i} ({column_name}): {value}")
        else:
            print("\nNo users found in database")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_schema())