"""
Test script for VocabBuilder email service with Timeweb SMTP
Tests all Timeweb ports: 2525, 25, 465
"""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.email_service import email_service


async def test_timeweb_email():
    """Test sending emails with Timeweb SMTP ports"""

    print("=" * 60)
    print("VocabBuilder Timeweb Email Test")
    print("=" * 60)
    print("Testing ports: 2525 (TLS), 25 (TLS), 465 (SSL)")
    print("=" * 60)

    # Get test email
    test_email = input("Enter email address to test: ").strip()
    if not test_email:
        print("❌ No email address provided")
        return

    # Test 1: Verification email
    print(f"\n📧 Sending verification email to {test_email}...")
    print("Trying Timeweb ports in order: 2525 → 25 → 465")

    success = await email_service.send_otp_email(
        email=test_email,
        otp_code="123456",
        purpose="verification"
    )

    if success:
        print("✅ Verification email sent successfully!")
        print("Check your email inbox and spam folder.")
    else:
        print("❌ Failed to send verification email")
        print("All Timeweb ports failed. Check logs above for details.")
        return

    # Test 2: Password reset email
    print(f"\n🔐 Sending password reset email to {test_email}...")

    success = await email_service.send_otp_email(
        email=test_email,
        otp_code="654321",
        purpose="reset"
    )

    if success:
        print("✅ Password reset email sent successfully!")
    else:
        print("❌ Failed to send password reset email")

    print("\n🎯 Test completed!")
    print("If emails were sent successfully, Timeweb SMTP is working!")


if __name__ == "__main__":
    try:
        asyncio.run(test_timeweb_email())
    except KeyboardInterrupt:
        print("\n\n👋 Test cancelled by user")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")