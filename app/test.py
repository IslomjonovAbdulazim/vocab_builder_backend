# Quick Database Schema Fix
# Run this script to update your database schema

import sqlite3
import os
from pathlib import Path


def fix_database_schema():
    """Add missing columns to existing database"""

    # Database path from your .env
    db_path = "database/vocabbuilder_1.db"

    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False

    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🔍 Checking database schema...")

        # Check if shared_at column exists
        cursor.execute("PRAGMA table_info(folders)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'shared_at' not in columns:
            print("➕ Adding missing 'shared_at' column to folders table...")
            cursor.execute("""
                ALTER TABLE folders 
                ADD COLUMN shared_at DATETIME DEFAULT CURRENT_TIMESTAMP
            """)
            print("✅ Added shared_at column")
        else:
            print("✅ shared_at column already exists")

        # Commit changes
        conn.commit()
        conn.close()

        print("🎉 Database schema updated successfully!")
        return True

    except Exception as e:
        print(f"❌ Error updating database: {str(e)}")
        return False


if __name__ == "__main__":
    fix_database_schema()