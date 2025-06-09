"""
Simple test script for VocabBuilder email service
"""

import asyncio
import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.email_service import email_service


async def test_email():
    """Test sending emails"""

    print("=" * 50)
    print("VocabBuilder Email Test")
    print("=" * 50)

    # Get test email
    test_email = input("Enter email address to test: ").strip()
    if not test_email:
        print("❌ No email address provided")
        return

    # Test 1: Verification email
    print(f"\n📧 Sending verification email to {test_email}...")
    success = await email_service.send_otp_email(
        email=test_email,
        otp_code="123456",
        purpose="verification"
    )

    if success:
        print("✅ Verification email sent successfully!")
    else:
        print("❌ Failed to send verification email")
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

    print("\n✅ Test completed!")


if __name__ == "__main__":
    try:
        asyncio.run(test_email())
    except KeyboardInterrupt:
        print("\n\n👋 Test cancelled by user")
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")