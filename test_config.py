#!/usr/bin/env python3
"""
Simple test script to verify configuration is working
"""


def test_config():
    print("🔍 Testing configuration...")

    try:
        from app.config import settings
        print("✅ Config imported successfully")
        print(f"📊 Database URL: {settings.database_url}")
        print(f"📧 Email configured: {settings.is_email_configured()}")
        print(f"🔐 Secret key length: {len(settings.secret_key)} chars")
        return True
    except Exception as e:
        print(f"❌ Config error: {str(e)}")
        return False


def test_database():
    print("\n🔍 Testing database...")

    try:
        from app.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            row = result.fetchone()

        if row and row[0] == 1:
            print("✅ Database connection successful")
            return True
        else:
            print("❌ Database connection failed")
            return False

    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return False


def test_imports():
    print("\n🔍 Testing imports...")

    try:
        from app import auth, folders, quiz
        print("✅ All modules imported successfully")
        return True
    except Exception as e:
        print(f"❌ Import error: {str(e)}")
        return False


if __name__ == "__main__":
    print("🚀 VocabBuilder API Configuration Test\n")

    tests = [
        ("Configuration", test_config),
        ("Database", test_database),
        ("Imports", test_imports)
    ]

    all_passed = True
    for name, test_func in tests:
        if not test_func():
            all_passed = False

    print(f"\n{'=' * 50}")
    if all_passed:
        print("🎉 All tests passed! API should start successfully.")
        print("💡 Run: uvicorn app.main:app --reload")
    else:
        print("💥 Some tests failed. Please fix the issues above.")
    print("=" * 50)