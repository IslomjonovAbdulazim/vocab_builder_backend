# app/auth.py - All authentication and user management
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
import asyncio

from app.database import get_db
from app.models import User, OTP
from app.utils import (
    StandardResponse, hash_password, verify_password, create_access_token,
    get_current_user_id, generate_otp, validate_password, generate_username,
    cleanup_expired_otps, cleanup_unverified_users, save_avatar
)
from app.email import send_otp_email
from app.config import settings

router = APIRouter()


# ================================
# REQUEST MODELS
# ================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp_code: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    new_password: str


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None


# ================================
# FLUTTER-COMPATIBLE RESPONSE MODEL
# ================================

class AuthResponse(BaseModel):
    status_code: int
    details: str
    is_success: bool
    token: Optional[str] = None


# ================================
# OTP MANAGEMENT
# ================================

def create_otp(db: Session, email: str, purpose: str = "verification") -> str:
    """Create and store OTP, send email"""
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

    # Send email asynchronously
    asyncio.create_task(send_otp_email(email, otp_code, purpose))
    return otp_code


def verify_otp(db: Session, email: str, code: str) -> bool:
    """Verify OTP code"""
    otp = db.query(OTP).filter(
        OTP.email == email,
        OTP.code == code,
        OTP.expires_at > datetime.utcnow()
    ).first()

    if otp:
        db.delete(otp)
        db.commit()
        return True
    return False


# ================================
# AUTHENTICATION ENDPOINTS
# ================================

@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register new user"""
    # Clean up first
    cleanup_expired_otps(db)
    cleanup_unverified_users(db)

    # Check if verified user exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user and existing_user.is_verified:
        raise HTTPException(400, "Email already registered")

    # Delete unverified user if exists
    if existing_user and not existing_user.is_verified:
        db.delete(existing_user)
        db.commit()

    # Validate password
    if not validate_password(request.password):
        raise HTTPException(400, "Password must be at least 6 characters")

    # Generate username
    username = generate_username(request.name, request.email)
    while db.query(User).filter(User.username == username).first():
        username = generate_username(request.name, request.email)

    # Create user
    user = User(
        email=request.email,
        password=hash_password(request.password),
        name=request.name,
        username=username
    )
    db.add(user)
    db.commit()

    # Send OTP
    create_otp(db, request.email, "verification")

    return AuthResponse(
        status_code=201,
        is_success=True,
        details="Registration successful. Please verify your email."
    )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """User login"""
    cleanup_expired_otps(db)
    cleanup_unverified_users(db)

    # Find user
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not verify_password(request.password, user.password):
        raise HTTPException(400, "Invalid email or password")

    # Check if verified
    if not user.is_verified:
        create_otp(db, request.email, "verification")
        raise HTTPException(400, "Please verify your email first. New code sent.")

    # Create token
    token = create_access_token(request.email)
    return AuthResponse(
        status_code=200,
        is_success=True,
        details="Login successful",
        token=token
    )


@router.post("/verify-email", response_model=AuthResponse)
async def verify_email(request: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email with OTP"""
    cleanup_expired_otps(db)

    # Verify OTP
    if not verify_otp(db, request.email, request.otp_code):
        raise HTTPException(400, "Invalid or expired verification code")

    # Find and verify user
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(400, "User not found")

    user.is_verified = True
    db.commit()

    # Create token
    token = create_access_token(request.email)
    return AuthResponse(
        status_code=200,
        is_success=True,
        details="Email verified successfully",
        token=token
    )


@router.post("/forgot-password", response_model=AuthResponse)
async def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send password reset OTP"""
    cleanup_expired_otps(db)
    cleanup_unverified_users(db)

    # Check if user exists and is verified
    user = db.query(User).filter(User.email == request.email, User.is_verified == True).first()
    if not user:
        raise HTTPException(400, "Email not found or not verified")

    # Send reset OTP
    create_otp(db, request.email, "reset")
    return AuthResponse(
        status_code=200,
        is_success=True,
        details="Password reset code sent to your email"
    )


@router.post("/reset-password", response_model=AuthResponse)
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password (should be called after OTP verification)"""
    # Validate password
    if not validate_password(request.new_password):
        raise HTTPException(400, "Password must be at least 6 characters")

    # Find user
    user = db.query(User).filter(User.email == request.email, User.is_verified == True).first()
    if not user:
        raise HTTPException(400, "User not found")

    # Update password
    user.password = hash_password(request.new_password)
    db.commit()

    # Create new token
    token = create_access_token(request.email)
    return AuthResponse(
        status_code=200,
        is_success=True,
        details="Password reset successful",
        token=token
    )


# ================================
# USER PROFILE ENDPOINTS
# ================================

@router.get("/profile", response_model=StandardResponse)
async def get_profile(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Get user profile"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found")

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Profile retrieved successfully",
        data={
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "username": user.username,
            "bio": user.bio,
            "avatar_url": user.avatar_url,
            "is_verified": user.is_verified,
            "total_folders_created": user.total_folders_created,
            "total_quizzes_taken": user.total_quizzes_taken,
            "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    )


@router.put("/profile", response_model=StandardResponse)
async def update_profile(
        profile_data: UserProfileUpdate,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Update user profile"""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found")

    # Update fields if provided
    if profile_data.name:
        if len(profile_data.name.strip()) < 1:
            raise HTTPException(400, "Name cannot be empty")
        user.name = profile_data.name.strip()

    if profile_data.username:
        username = profile_data.username.strip().lower()

        if len(username) < 3 or len(username) > 20:
            raise HTTPException(400, "Username must be 3-20 characters")

        # Check if username is taken
        existing = db.query(User).filter(User.username == username, User.id != user_id).first()
        if existing:
            raise HTTPException(400, "Username is already taken")

        user.username = username

    if profile_data.bio is not None:
        if len(profile_data.bio) > 500:
            raise HTTPException(400, "Bio must be less than 500 characters")
        user.bio = profile_data.bio.strip() if profile_data.bio.strip() else None

    db.commit()

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Profile updated successfully",
        data={
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "bio": user.bio
        }
    )


@router.post("/avatar", response_model=StandardResponse)
async def upload_avatar(
        file: UploadFile = File(...),
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Upload user avatar - deletes old avatar automatically"""
    # Validate file
    if not file.content_type.startswith('image/'):
        raise HTTPException(400, "File must be an image")

    # Check file size (5MB limit)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(400, "File size must be less than 5MB")

    # Get user and old avatar URL
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    old_avatar_url = user.avatar_url  # Get old avatar before saving new one

    # Save new avatar (this will delete the old one)
    avatar_url = save_avatar(file, user_id, old_avatar_url)

    # Update user record
    user.avatar_url = avatar_url
    db.commit()

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Avatar uploaded successfully. Old avatar deleted.",
        data={"avatar_url": avatar_url}
    )


@router.get("/stats", response_model=StandardResponse)
async def get_user_stats(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Get user statistics"""
    from app.models import Folder, QuizSession

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    # Get additional stats
    owned_folders = db.query(Folder).filter(Folder.owner_id == user_id).all()
    total_words_created = sum(folder.total_words for folder in owned_folders)
    total_folder_copies = sum(folder.total_copies for folder in owned_folders)

    # Recent quiz performance
    recent_quizzes = db.query(QuizSession).filter(
        QuizSession.user_id == user_id,
        QuizSession.status == "completed"
    ).order_by(QuizSession.completed_at.desc()).limit(10).all()

    average_score = 0
    if recent_quizzes:
        average_score = sum(quiz.score for quiz in recent_quizzes) / len(recent_quizzes)

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="User statistics retrieved successfully",
        data={
            "user_id": user.id,
            "username": user.username,
            "name": user.name,
            "folders_created": user.total_folders_created,
            "quizzes_taken": user.total_quizzes_taken,
            "total_words_created": total_words_created,
            "total_folder_copies": total_folder_copies,
            "average_recent_score": round(average_score, 1),
            "recent_quizzes_count": len(recent_quizzes),
            "member_since": user.created_at.strftime("%Y-%m-%d")
        }
    )