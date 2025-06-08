import random
import string
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.otp import OTP
from app.core.security import hash_password, verify_password, create_access_token
from app.services.email_service import send_otp_email
from app.config import settings


def generate_otp() -> str:
    """Generate 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))


def create_otp(db: Session, email: str, purpose: str = "verification") -> str:
    """Create and store OTP"""
    # Delete old OTPs for this email
    db.query(OTP).filter(OTP.email == email).delete()
    db.commit()

    # Generate new OTP
    otp_code = generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.otp_expire_minutes)

    # Save OTP
    otp = OTP(email=email, code=otp_code, expires_at=expires_at)
    db.add(otp)
    db.commit()

    # Send email
    send_otp_email(email, otp_code, purpose)

    return otp_code


def verify_otp(db: Session, email: str, code: str) -> bool:
    """Verify OTP code"""
    otp = db.query(OTP).filter(
        OTP.email == email,
        OTP.code == code,
        OTP.expires_at > datetime.utcnow()
    ).first()

    if otp:
        # Delete used OTP
        db.delete(otp)
        db.commit()
        return True
    return False


def cleanup_expired_otps(db: Session):
    """Clean up expired OTPs"""
    expired = db.query(OTP).filter(OTP.expires_at <= datetime.utcnow()).all()
    for otp in expired:
        db.delete(otp)
    db.commit()


def cleanup_unverified_users(db: Session):
    """Delete unverified users older than 5 minutes"""
    cutoff = datetime.utcnow() - timedelta(minutes=settings.otp_expire_minutes)
    unverified = db.query(User).filter(
        User.is_verified == False,
        User.created_at <= cutoff
    ).all()

    for user in unverified:
        # Also delete their OTPs
        db.query(OTP).filter(OTP.email == user.email).delete()
        db.delete(user)

    db.commit()
    return len(unverified)


def register_user(db: Session, email: str, password: str, name: str) -> dict:
    """Register new user"""
    # Clean up first
    cleanup_expired_otps(db)
    cleanup_unverified_users(db)

    # Check if verified user exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user and existing_user.is_verified:
        return {"success": False, "message": "Email already registered"}

    # Delete unverified user if exists
    if existing_user and not existing_user.is_verified:
        db.delete(existing_user)
        db.commit()

    # Validate password
    if len(password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters"}

    # Create user
    hashed_password = hash_password(password)
    user = User(email=email, password=hashed_password, name=name)
    db.add(user)
    db.commit()

    # Send OTP
    create_otp(db, email, "verification")

    return {"success": True, "message": "Registration successful. Please verify your email."}


def login_user(db: Session, email: str, password: str) -> dict:
    """Login user"""
    # Clean up first
    cleanup_expired_otps(db)
    cleanup_unverified_users(db)

    # Find user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"success": False, "message": "Invalid email or password"}

    # Check password
    if not verify_password(password, user.password):
        return {"success": False, "message": "Invalid email or password"}

    # Check if verified
    if not user.is_verified:
        # Send new OTP
        create_otp(db, email, "verification")
        return {"success": False, "message": "Please verify your email first. New code sent."}

    # Create token
    token = create_access_token(email)
    return {"success": True, "message": "Login successful", "token": token}


def verify_user_email(db: Session, email: str, otp_code: str) -> dict:
    """Verify user email with OTP"""
    # Clean up first
    cleanup_expired_otps(db)

    # Verify OTP
    if not verify_otp(db, email, otp_code):
        return {"success": False, "message": "Invalid or expired verification code"}

    # Find and verify user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"success": False, "message": "User not found"}

    user.is_verified = True
    db.commit()

    # Create token
    token = create_access_token(email)
    return {"success": True, "message": "Email verified successfully", "token": token}


def forgot_password(db: Session, email: str) -> dict:
    """Send password reset OTP"""
    # Clean up first
    cleanup_expired_otps(db)
    cleanup_unverified_users(db)

    # Check if user exists and is verified
    user = db.query(User).filter(User.email == email, User.is_verified == True).first()
    if not user:
        return {"success": False, "message": "Email not found or not verified"}

    # Send reset OTP
    create_otp(db, email, "reset")
    return {"success": True, "message": "Password reset code sent to your email"}


def reset_password(db: Session, email: str, new_password: str) -> dict:
    """Reset password (should be called after OTP verification)"""
    # Validate password
    if len(new_password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters"}

    # Find user
    user = db.query(User).filter(User.email == email, User.is_verified == True).first()
    if not user:
        return {"success": False, "message": "User not found"}

    # Update password
    user.password = hash_password(new_password)
    db.commit()

    # Create new token
    token = create_access_token(email)
    return {"success": True, "message": "Password reset successful", "token": token}


def get_user_by_email(db: Session, email: str) -> User | None:
    """Get user by email"""
    return db.query(User).filter(User.email == email, User.is_verified == True).first()