# schema_fix.py - Database migration for new folder access system
import sqlite3
import os
from datetime import datetime


def fix_database_schema():
    """Migrate database from folder_copies system to folder_access system"""

    # Database path from your .env
    db_path = "database/vocabbuilder_1.db"

    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False

    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🔍 Starting database migration for new folder access system...")

        # Step 1: Check current schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        print(f"📋 Existing tables: {existing_tables}")

        # Step 2: Create new folder_access table
        print("➕ Creating folder_access table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folder_access (
                id INTEGER PRIMARY KEY,
                folder_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (folder_id) REFERENCES folders (id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(folder_id, user_id)
            )
        """)
        print("✅ folder_access table created")

        # Step 3: Check if folders table has total_copies column
        cursor.execute("PRAGMA table_info(folders)")
        folder_columns = [row[1] for row in cursor.fetchall()]

        # Step 4: Rename total_copies to total_followers in folders table
        if 'total_copies' in folder_columns and 'total_followers' not in folder_columns:
            print("🔄 Migrating total_copies to total_followers...")

            # SQLite doesn't support RENAME COLUMN directly, so we'll do it manually
            cursor.execute("ALTER TABLE folders ADD COLUMN total_followers INTEGER DEFAULT 0")
            cursor.execute("UPDATE folders SET total_followers = total_copies")
            print("✅ Added total_followers column and copied data")

            # We'll keep total_copies for now to avoid breaking things

        elif 'total_followers' not in folder_columns:
            print("➕ Adding total_followers column...")
            cursor.execute("ALTER TABLE folders ADD COLUMN total_followers INTEGER DEFAULT 0")
            print("✅ Added total_followers column")
        else:
            print("✅ total_followers column already exists")

        # Step 5: Clear old folder_copies data and start fresh
        if 'folder_copies' in existing_tables:
            print("🧹 Clearing old folder_copies data...")
            cursor.execute("DELETE FROM folder_copies")
            print("✅ Cleared old folder_copies data")

            print("⚠️  NOTE: All previous folder copies have been cleared.")
            print("   Users will need to re-follow folders using share codes.")

        # Step 6: Reset total_followers count for all folders
        print("🔄 Resetting folder followers count...")
        cursor.execute("UPDATE folders SET total_followers = 0")
        print("✅ Reset all folder followers count to 0")

        # Step 7: Add shared_at column if it doesn't exist
        if 'shared_at' not in folder_columns:
            print("➕ Adding shared_at column to folders...")
            cursor.execute("ALTER TABLE folders ADD COLUMN shared_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            print("✅ Added shared_at column")

        # Step 8: Update all folders shared_at to current timestamp
        print("🔄 Updating shared_at timestamps...")
        current_time = datetime.now().isoformat()
        cursor.execute("UPDATE folders SET shared_at = ? WHERE shared_at IS NULL", (current_time,))
        print("✅ Updated shared_at timestamps")

        # Commit all changes
        conn.commit()

        # Step 9: Verify new schema
        print("\n📊 Verifying new schema...")

        cursor.execute("PRAGMA table_info(folders)")
        folder_columns = [row[1] for row in cursor.fetchall()]
        print(f"📁 Folders table columns: {folder_columns}")

        cursor.execute("PRAGMA table_info(folder_access)")
        access_columns = [row[1] for row in cursor.fetchall()]
        print(f"🔗 Folder access table columns: {access_columns}")

        # Step 10: Show statistics
        cursor.execute("SELECT COUNT(*) FROM folders")
        folder_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM folder_access")
        access_count = cursor.fetchone()[0]

        print(f"\n📈 Migration Statistics:")
        print(f"   📁 Total folders: {folder_count}")
        print(f"   🔗 Total folder access records: {access_count}")

        conn.close()

        print("\n🎉 Database migration completed successfully!")
        print("\n📋 Summary of Changes:")
        print("   ✅ Created new folder_access table")
        print("   ✅ Added total_followers column to folders")
        print("   ✅ Added/updated shared_at column")
        print("   ✅ Cleared old folder_copies data")
        print("   ⚠️  Users need to re-follow folders with share codes")
        print("\n🚀 Your API is now ready with the new folder access system!")

        return True

    except Exception as e:
        print(f"❌ Error during migration: {str(e)}")
        return False


def verify_migration():
    """Verify that migration was successful"""
    db_path = "database/vocabbuilder_1.db"

    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🔍 Verifying migration...")

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ['users', 'folders', 'folder_access', 'vocab_items', 'quiz_sessions', 'quiz_answers', 'otps']
        missing_tables = [table for table in required_tables if table not in tables]

        if missing_tables:
            print(f"❌ Missing tables: {missing_tables}")
            return False

        # Check folder_access table structure
        cursor.execute("PRAGMA table_info(folder_access)")
        access_columns = [row[1] for row in cursor.fetchall()]
        required_access_columns = ['id', 'folder_id', 'user_id', 'accessed_at']

        missing_access_columns = [col for col in required_access_columns if col not in access_columns]
        if missing_access_columns:
            print(f"❌ Missing folder_access columns: {missing_access_columns}")
            return False

        # Check folders table has required columns
        cursor.execute("PRAGMA table_info(folders)")
        folder_columns = [row[1] for row in cursor.fetchall()]
        required_folder_columns = ['id', 'title', 'owner_id', 'share_code', 'total_followers', 'shared_at']

        missing_folder_columns = [col for col in required_folder_columns if col not in folder_columns]
        if missing_folder_columns:
            print(f"❌ Missing folders columns: {missing_folder_columns}")
            return False

        conn.close()

        print("✅ Migration verification successful!")
        print("🚀 Database is ready for the new folder access system!")

        return True

    except Exception as e:
        print(f"❌ Verification error: {str(e)}")
        return False


def cleanup_old_system():
    """Optional: Remove old folder_copies table and total_copies column"""
    db_path = "database/vocabbuilder_1.db"

    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("🧹 Cleaning up old system...")

        # Check if folder_copies table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='folder_copies'")
        if cursor.fetchone():
            print("🗑️  Dropping folder_copies table...")
            cursor.execute("DROP TABLE folder_copies")
            print("✅ Dropped folder_copies table")

        # Note: We can't easily drop the total_copies column in SQLite
        # So we'll just leave it there but unused

        conn.commit()
        conn.close()

        print("✅ Cleanup completed!")
        return True

    except Exception as e:
        print(f"❌ Cleanup error: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🔧 VocabBuilder Database Migration Tool")
    print("=" * 60)
    print()

    # Run migration
    success = fix_database_schema()

    if success:
        print()
        # Verify migration
        verify_migration()

        print()
        cleanup_choice = input("🗑️  Do you want to cleanup old tables? (y/n): ").lower()
        if cleanup_choice == 'y':
            cleanup_old_system()

    print("\n" + "=" * 60)
    print("🏁 Migration Complete!")
    print("=" * 60)