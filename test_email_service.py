"""
Test script for VocabBuilder email service
Run this to verify your Timeweb SMTP configuration is working correctly
"""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.services.email_service import email_service
from app.config import settings


async def test_email_service():
    """Test the email service with various scenarios"""

    print("=" * 60)
    print("VocabBuilder Email Service Test")
    print("=" * 60)
    print(f"SMTP Host: {settings.smtp_host}")
    print(f"SMTP Port: {settings.smtp_port}")
    print(f"From Email: {settings.from_email}")
    print(f"From Name: {settings.from_name}")
    print("=" * 60)

    # Test 1: Health Check
    print("\n1. Testing email service health check...")
    is_healthy = await email_service.health_check()
    if is_healthy:
        print("✅ Email service is healthy")
    else:
        print("❌ Email service health check failed")
        print("   Please check your SMTP credentials and network connection")
        return

    # Test 2: Send verification email
    test_email = input("\nEnter email address to test: ").strip()
    if not test_email:
        print("❌ No email address provided")
        return

    print(f"\n2. Sending verification OTP to {test_email}...")
    result = await email_service.send_otp_email(
        email=test_email,
        otp_code="123456",
        purpose="verification"
    )

    if result.success:
        print(f"✅ Verification email sent successfully!")
        print(f"   Message: {result.message}")
    else:
        print(f"❌ Failed to send verification email")
        print(f"   Error: {result.error_details}")

    # Test 3: Send password reset email
    print(f"\n3. Sending password reset OTP to {test_email}...")
    result = await email_service.send_otp_email(
        email=test_email,
        otp_code="654321",
        purpose="reset"
    )

    if result.success:
        print(f"✅ Password reset email sent successfully!")
        print(f"   Message: {result.message}")
    else:
        print(f"❌ Failed to send password reset email")
        print(f"   Error: {result.error_details}")

    # Test 4: Get statistics
    print("\n4. Email Service Statistics:")
    stats = await email_service.get_stats()
    print(f"   Emails sent: {stats['sent']}")
    print(f"   Emails failed: {stats['failed']}")
    print(f"   Success rate: {stats['success_rate']:.1f}%")
    if stats['last_success']:
        print(f"   Last success: {stats['last_success']}")
    if stats['last_error']:
        print(f"   Last error: {stats['last_error']}")

    # Clean up
    await email_service.close()
    print("\n✅ Test completed!")


async def test_connection_only():
    """Test only the SMTP connection"""
    print("\nTesting SMTP connection...")

    try:
        conn = await email_service.connection_pool._create_connection()
        print("✅ SMTP connection successful!")
        conn.quit()
        return True
    except Exception as e:
        print(f"❌ SMTP connection failed: {str(e)}")
        return False


if __name__ == "__main__":
    print("VocabBuilder Email Service Tester\n")
    print("1. Full email test (sends actual emails)")
    print("2. Connection test only (no emails sent)")

    choice = input("\nSelect test type (1 or 2): ").strip()

    if choice == "1":
        asyncio.run(test_email_service())
    elif choice == "2":
        asyncio.run(test_connection_only())
    else:
        print("Invalid choice. Please run again and select 1 or 2.")