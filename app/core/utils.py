# app/core/utils.py
import random
import string
import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session


def generate_share_code() -> str:
    """Generate unique 6-character share code (avoiding confusing chars)"""
    chars = string.ascii_uppercase + string.digits
    # Remove confusing characters: 0, O, 1, I
    chars = chars.replace('0', '').replace('O', '').replace('1', '').replace('I', '')

    while True:
        code = ''.join(random.choices(chars, k=6))
        return code  # In production, check DB for uniqueness


def generate_username(name: str, email: str) -> str:
    """Generate username from name and email"""
    # Take first part of email
    email_part = email.split('@')[0]

    # Clean name - remove spaces, convert to lowercase
    name_part = name.lower().replace(' ', '')

    # Combine and add random number
    base = f"{name_part}_{email_part}"[:15]  # Limit length
    random_num = random.randint(100, 999)

    return f"{base}{random_num}"


def save_avatar(file: UploadFile, user_id: int) -> str:
    """Save uploaded avatar and return file path"""
    if not file.content_type.startswith('image/'):
        raise HTTPException(400, "File must be an image")

    # Create uploads directory if it doesn't exist
    upload_dir = "app/static/uploads/avatars"
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"user_{user_id}_{uuid.uuid4().hex[:8]}.{file_extension}"
    file_path = os.path.join(upload_dir, filename)

    # Save file
    with open(file_path, "wb") as buffer:
        content = file.file.read()
        buffer.write(content)

    # Return relative path for database
    return f"/static/uploads/avatars/{filename}"


def validate_vocabulary_item(word: str, translation: str) -> dict:
    """Simple validation for vocabulary items"""
    errors = []

    if not word or len(word.strip()) < 1:
        errors.append("Word cannot be empty")

    if not translation or len(translation.strip()) < 1:
        errors.append("Translation cannot be empty")

    if len(word) > 100:
        errors.append("Word is too long (max 100 characters)")

    if len(translation) > 200:
        errors.append("Translation is too long (max 200 characters)")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors
    }


def calculate_quiz_score(correct_answers: int, total_questions: int) -> float:
    """Calculate quiz score as percentage"""
    if total_questions == 0:
        return 0.0
    return round((correct_answers / total_questions) * 100, 1)


def check_folder_ownership(folder, user_id: int) -> bool:
    """Check if user owns the folder"""
    return folder.owner_id == user_id


def check_folder_access(folder, user_id: int, db: Session) -> bool:
    """Check if user can access folder (owns it or copied it)"""
    from app.models.folder import FolderCopy

    # Owner can always access
    if folder.owner_id == user_id:
        return True

    # Check if user copied this folder
    copy_exists = db.query(FolderCopy).filter(
        FolderCopy.original_folder_id == folder.id,
        FolderCopy.copied_by_user_id == user_id
    ).first()

    return copy_exists is not None


def update_folder_word_count(folder, db: Session):
    """Update folder's word count"""
    from app.models.folder import VocabItem

    count = db.query(VocabItem).filter(VocabItem.folder_id == folder.id).count()
    folder.total_words = count
    db.commit()