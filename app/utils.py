# app/utils.py - Shared utilities and common functions
import random
import string
import os
import uuid
import logging
import glob
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import HTTPException, Depends, Header, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from app.config import settings
from app.database import get_db

# Setup logging
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
security = HTTPBearer()


# ================================
# SHARED RESPONSE MODELS
# ================================

class StandardResponse(BaseModel):
    status_code: int
    is_success: bool
    details: str
    data: Optional[dict] = None


# ================================
# AUTHENTICATION UTILITIES
# ================================

def hash_password(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(email: str) -> str:
    """Create JWT token"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.access_token_expire_days)
    to_encode = {"sub": email, "exp": expire, "iat": datetime.now(timezone.utc)}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str) -> str | None:
    """Verify JWT token and return email"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        email = payload.get("sub")
        exp = payload.get("exp")

        if exp and datetime.now(timezone.utc).timestamp() > exp:
            return None
        return email
    except JWTError:
        return None


def get_current_user_email(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract email from JWT token using FastAPI's HTTPBearer"""
    try:
        email = verify_token(credentials.credentials)
        if not email:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return email
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token format")


def get_current_user_id(current_email: str = Depends(get_current_user_email), db: Session = Depends(get_db)) -> int:
    """Get current user ID from JWT token"""
    from app.models import User
    user = db.query(User).filter(User.email == current_email, User.is_verified == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.id


# ================================
# VALIDATION UTILITIES
# ================================

def validate_password(password: str) -> bool:
    """Validate password strength"""
    return len(password) >= 6


def validate_vocabulary_item(word: str, translation: str) -> dict:
    """Validate vocabulary item"""
    errors = []
    if not word or len(word.strip()) < 1:
        errors.append("Word cannot be empty")
    if not translation or len(translation.strip()) < 1:
        errors.append("Translation cannot be empty")
    if len(word) > 100:
        errors.append("Word too long (max 100 chars)")
    if len(translation) > 200:
        errors.append("Translation too long (max 200 chars)")

    return {"is_valid": len(errors) == 0, "errors": errors}


# ================================
# FOLDER UTILITIES
# ================================

def generate_share_code() -> str:
    """Generate unique 6-character share code"""
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('0', '').replace('O', '').replace('1', '').replace('I', '')
    return ''.join(random.choices(chars, k=6))


def generate_username(name: str, email: str) -> str:
    """Generate username from name and email"""
    email_part = email.split('@')[0]
    name_part = name.lower().replace(' ', '')
    base = f"{name_part}_{email_part}"[:15]
    random_num = random.randint(100, 999)
    return f"{base}{random_num}"


def check_folder_access(folder, user_id: int, db: Session) -> bool:
    """Check if user can access folder (owns it or copied it)"""
    from app.models import FolderCopy

    if folder.owner_id == user_id:
        return True

    copy_exists = db.query(FolderCopy).filter(
        FolderCopy.original_folder_id == folder.id,
        FolderCopy.copied_by_user_id == user_id
    ).first()

    return copy_exists is not None


def update_folder_word_count(folder, db: Session):
    """Update folder's word count"""
    from app.models import VocabItem
    count = db.query(VocabItem).filter(VocabItem.folder_id == folder.id).count()
    folder.total_words = count
    db.commit()


# ================================
# QUIZ UTILITIES
# ================================

def calculate_quiz_score(correct_answers: int, total_questions: int) -> float:
    """Calculate quiz score as percentage"""
    if total_questions == 0:
        return 0.0
    return round((correct_answers / total_questions) * 100, 1)


def generate_otp() -> str:
    """Generate 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))


# ================================
# FILE UPLOAD UTILITIES
# ================================

def save_avatar(file: UploadFile, user_id: int, old_avatar_url: str = None) -> str:
    """Save uploaded avatar and return file path. Deletes old avatar if exists."""
    if not file.content_type.startswith('image/'):
        raise HTTPException(400, "File must be an image")

    # Create uploads directory
    upload_dir = "app/static/uploads/avatars"
    os.makedirs(upload_dir, exist_ok=True)

    # Delete old avatar file if exists
    if old_avatar_url:
        try:
            # Convert URL to file path: "/static/uploads/avatars/filename.jpg" -> "app/static/uploads/avatars/filename.jpg"
            old_file_path = old_avatar_url.replace("/static/", "app/static/")
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
                logger.info(f"🗑️ Deleted old avatar: {old_file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Could not delete old avatar: {str(e)}")

    # Generate unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"user_{user_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
    file_path = os.path.join(upload_dir, filename)

    # Save new file
    with open(file_path, "wb") as buffer:
        content = file.file.read()
        buffer.write(content)

    logger.info(f"✅ Saved new avatar: {file_path}")
    return f"/static/uploads/avatars/{filename}"


# ================================
# CLEANUP UTILITIES
# ================================

def cleanup_expired_otps(db: Session):
    """Clean up expired OTPs"""
    from app.models import OTP
    expired = db.query(OTP).filter(OTP.expires_at <= datetime.utcnow()).all()
    for otp in expired:
        db.delete(otp)
    db.commit()


def cleanup_unverified_users(db: Session):
    """Delete unverified users older than 5 minutes"""
    from app.models import User, OTP
    cutoff = datetime.utcnow() - timedelta(minutes=settings.otp_expire_minutes)
    unverified = db.query(User).filter(
        User.is_verified == False,
        User.created_at <= cutoff
    ).all()

    for user in unverified:
        db.query(OTP).filter(OTP.email == user.email).delete()
        db.delete(user)

    db.commit()
    return len(unverified)


def cleanup_orphaned_avatars(db: Session):
    """Clean up avatar files that are no longer referenced in database"""
    from app.models import User

    avatar_dir = "app/static/uploads/avatars"
    if not os.path.exists(avatar_dir):
        return 0

    # Get all avatar files
    avatar_files = glob.glob(os.path.join(avatar_dir, "*.jpg")) + \
                   glob.glob(os.path.join(avatar_dir, "*.png")) + \
                   glob.glob(os.path.join(avatar_dir, "*.jpeg")) + \
                   glob.glob(os.path.join(avatar_dir, "*.webp"))

    # Get all avatar URLs from database
    users_with_avatars = db.query(User.avatar_url).filter(User.avatar_url.isnot(None)).all()
    db_avatar_files = set()
    for user in users_with_avatars:
        if user.avatar_url:
            file_path = user.avatar_url.replace("/static/", "app/static/")
            db_avatar_files.add(file_path)

    # Delete orphaned files
    deleted_count = 0
    for file_path in avatar_files:
        if file_path not in db_avatar_files:
            try:
                os.remove(file_path)
                deleted_count += 1
                logger.info(f"🗑️ Deleted orphaned avatar: {file_path}")
            except Exception as e:
                logger.warning(f"⚠️ Could not delete orphaned avatar: {str(e)}")

    return deleted_count