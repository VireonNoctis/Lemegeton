#!/usr/bin/env python3
"""
Quick script to check database schema
"""
import asyncio
import sqlite3
from pathlib import Path

async def check_schema():
    db_path = Path("database.db")
    
    if not db_path.exists():
        print("Database file does not exist")
        return
    
    # Use sync sqlite3 for schema inspection
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print("Database Tables:")
    print("=" * 50)
    
    for (table_name,) in tables:
        print(f"\nTable: {table_name}")
        print("-" * 30)
        
        # Get table schema
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        
        for column in columns:
            cid, name, dtype, notnull, default, pk = column
            pk_str = " (PRIMARY KEY)" if pk else ""
            null_str = " NOT NULL" if notnull else ""
            default_str = f" DEFAULT {default}" if default else ""
            print(f"  {name}: {dtype}{null_str}{default_str}{pk_str}")
    
    conn.close()

if __name__ == "__main__":
    asyncio.run(check_schema())