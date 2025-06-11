# app/api/users.py (Enhanced)
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Annotated, Optional
from app.database import get_db
from app.core.security import verify_token
from app.services.auth_service import get_user_by_email
from app.core.utils import save_avatar
from app.models.user import User

router = APIRouter()


# Request Models
class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None


# Response Models
class UserProfile(BaseModel):
    id: int
    email: str
    name: str
    username: str
    bio: Optional[str]
    avatar_url: Optional[str]
    is_verified: bool
    total_folders_created: int
    total_quizzes_taken: int
    created_at: str


class ProfileResponse(BaseModel):
    status_code: int
    details: str
    is_success: bool
    user: UserProfile | None = None


class StandardResponse(BaseModel):
    status_code: int
    is_success: bool
    details: str
    data: Optional[dict] = None


def get_current_user_email(authorization: Annotated[str | None, Header()] = None):
    """Extract and verify JWT token from Authorization header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")

    token = authorization.split(" ")[1]
    email = verify_token(token)

    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return email


def get_current_user_id(current_email: str = Depends(get_current_user_email), db: Session = Depends(get_db)) -> int:
    """Get current user ID from JWT token"""
    user = get_user_by_email(db, current_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.id


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
        current_email: str = Depends(get_current_user_email),
        db: Session = Depends(get_db)
):
    """Get user profile"""
    user = get_user_by_email(db, current_email)

    if not user:
        return ProfileResponse(
            status_code=404,
            details="User not found",
            is_success=False
        )

    user_profile = UserProfile(
        id=user.id,
        email=user.email,
        name=user.name,
        username=user.username,
        bio=user.bio,
        avatar_url=user.avatar_url,
        is_verified=user.is_verified,
        total_folders_created=user.total_folders_created,
        total_quizzes_taken=user.total_quizzes_taken,
        created_at=user.created_at.strftime("%Y-%m-%d %H:%M:%S")
    )

    return ProfileResponse(
        status_code=200,
        details="Profile retrieved successfully",
        is_success=True,
        user=user_profile
    )


@router.put("/profile", response_model=StandardResponse)
async def update_profile(
        profile_data: UserProfileUpdate,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Update user profile"""
    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update fields if provided
        if profile_data.name:
            if len(profile_data.name.strip()) < 1:
                raise HTTPException(status_code=400, detail="Name cannot be empty")
            user.name = profile_data.name.strip()

        if profile_data.username:
            username = profile_data.username.strip().lower()

            # Validate username format
            if len(username) < 3:
                raise HTTPException(status_code=400, detail="Username must be at least 3 characters")

            if len(username) > 20:
                raise HTTPException(status_code=400, detail="Username must be less than 20 characters")

            # Check if username is already taken
            existing_user = db.query(User).filter(
                User.username == username,
                User.id != user_id
            ).first()

            if existing_user:
                raise HTTPException(status_code=400, detail="Username is already taken")

            user.username = username

        if profile_data.bio is not None:
            if len(profile_data.bio) > 500:
                raise HTTPException(status_code=400, detail="Bio must be less than 500 characters")
            user.bio = profile_data.bio.strip() if profile_data.bio.strip() else None

        db.commit()
        db.refresh(user)

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Profile updated successfully",
            data={
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "bio": user.bio,
                "updated_at": user.updated_at
            }
        )

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"Error updating profile: {str(e)}")


@router.post("/avatar", response_model=StandardResponse)
async def upload_avatar(
        file: UploadFile = File(...),
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Upload user avatar"""
    try:
        # Validate file
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Check file size (5MB limit)
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning

        if file_size > 5 * 1024 * 1024:  # 5MB
            raise HTTPException(status_code=400, detail="File size must be less than 5MB")

        # Save avatar
        avatar_url = save_avatar(file, user_id)

        # Update user record
        from app.models.user import User
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.avatar_url = avatar_url
        db.commit()

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Avatar uploaded successfully",
            data={
                "avatar_url": avatar_url
            }
        )

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"Error uploading avatar: {str(e)}")


@router.get("/stats", response_model=StandardResponse)
async def get_user_stats(
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Get user statistics"""
    try:
        from app.models.user import User
        from app.models.folder import Folder
        from app.models.quiz import QuizSession

        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

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

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=400, detail=f"Error getting user stats: {str(e)}")