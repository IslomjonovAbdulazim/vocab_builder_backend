# migrate_database.py
"""
Simple database migration script for VocabBuilder MVP
Run this once to update your existing database with new fields and tables
"""

import sqlite3
import os
from app.core.utils import generate_username

def migrate_database():
    """Migrate existing database to new schema"""
    db_path = "database/vocabbuilder_1.db"

    if not os.path.exists(db_path):
        print("Database file not found. Please run the app first to create initial tables.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Starting database migration...")

    try:
        # 1. Add new columns to users table
        print("1. Adding new columns to users table...")

        # Check if username column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'username' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN username TEXT")
            print("   - Added username column")

        if 'bio' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN bio TEXT")
            print("   - Added bio column")

        if 'avatar_url' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
            print("   - Added avatar_url column")

        if 'total_folders_created' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN total_folders_created INTEGER DEFAULT 0")
            print("   - Added total_folders_created column")

        if 'total_quizzes_taken' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN total_quizzes_taken INTEGER DEFAULT 0")
            print("   - Added total_quizzes_taken column")

        # 2. Generate usernames for existing users
        print("2. Generating usernames for existing users...")
        cursor.execute("SELECT id, name, email FROM users WHERE username IS NULL")
        users_without_username = cursor.fetchall()

        for user_id, name, email in users_without_username:
            username = generate_username(name, email)
            # Ensure username is unique
            counter = 1
            original_username = username
            while True:
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                if not cursor.fetchone():
                    break
                username = f"{original_username}_{counter}"
                counter += 1

            cursor.execute("UPDATE users SET username = ? WHERE id = ?", (username, user_id))
            print(f"   - Generated username '{username}' for user {user_id}")

        # 3. Create folders table
        print("3. Creating folders table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                owner_id INTEGER NOT NULL,
                share_code TEXT UNIQUE NOT NULL,
                is_shareable BOOLEAN DEFAULT 1,
                total_words INTEGER DEFAULT 0,
                total_copies INTEGER DEFAULT 0,
                total_quizzes INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users (id)
            )
        """)
        print("   - Folders table created/verified")

        # 4. Create vocab_items table
        print("4. Creating vocab_items table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vocab_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                translation TEXT NOT NULL,
                definition TEXT,
                example_sentence TEXT,
                order_index INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (folder_id) REFERENCES folders (id)
            )
        """)
        print("   - Vocab items table created/verified")

        # 5. Create folder_copies table
        print("5. Creating folder_copies table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folder_copies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_folder_id INTEGER NOT NULL,
                copied_folder_id INTEGER NOT NULL,
                copied_by_user_id INTEGER NOT NULL,
                copied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (original_folder_id) REFERENCES folders (id),
                FOREIGN KEY (copied_folder_id) REFERENCES folders (id),
                FOREIGN KEY (copied_by_user_id) REFERENCES users (id),
                UNIQUE (original_folder_id, copied_by_user_id)
            )
        """)
        print("   - Folder copies table created/verified")

        # 6. Create quiz_sessions table
        print("6. Creating quiz_sessions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quiz_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                folder_id INTEGER NOT NULL,
                quiz_type TEXT DEFAULT 'mixed',
                question_count INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                current_question INTEGER DEFAULT 1,
                score REAL DEFAULT 0.0,
                correct_answers INTEGER DEFAULT 0,
                total_answers INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (folder_id) REFERENCES folders (id)
            )
        """)
        print("   - Quiz sessions table created/verified")

        # 7. Create quiz_answers table
        print("7. Creating quiz_answers table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quiz_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_session_id INTEGER NOT NULL,
                vocab_item_id INTEGER NOT NULL,
                question_type TEXT NOT NULL,
                question_text TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                user_answer TEXT,
                is_correct BOOLEAN NOT NULL,
                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (quiz_session_id) REFERENCES quiz_sessions (id),
                FOREIGN KEY (vocab_item_id) REFERENCES vocab_items (id)
            )
        """)
        print("   - Quiz answers table created/verified")

        # 8. Create indexes for better performance
        print("8. Creating indexes...")

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
            "CREATE INDEX IF NOT EXISTS idx_folders_owner ON folders(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_folders_share_code ON folders(share_code)",
            "CREATE INDEX IF NOT EXISTS idx_vocab_folder ON vocab_items(folder_id)",
            "CREATE INDEX IF NOT EXISTS idx_vocab_word ON vocab_items(word)",
            "CREATE INDEX IF NOT EXISTS idx_copy_original ON folder_copies(original_folder_id)",
            "CREATE INDEX IF NOT EXISTS idx_copy_user ON folder_copies(copied_by_user_id)",
            "CREATE INDEX IF NOT EXISTS idx_quiz_user_folder ON quiz_sessions(user_id, folder_id)",
            "CREATE INDEX IF NOT EXISTS idx_quiz_answers_session ON quiz_answers(quiz_session_id)"
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)

        print("   - Indexes created/verified")

        # 9. Make username column NOT NULL (if it was added)
        print("9. Finalizing schema...")
        cursor.execute("UPDATE users SET username = 'user_' || id WHERE username IS NULL OR username = ''")

        # Commit all changes
        conn.commit()
        print("\n✅ Database migration completed successfully!")
        print("\nNew features available:")
        print("- User profiles with username, bio, and avatar")
        print("- Folder creation and sharing with codes")
        print("- Vocabulary management")
        print("- Quiz system")
        print("- Copy tracking")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    migrate_database()