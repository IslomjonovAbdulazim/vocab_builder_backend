from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Annotated
from app.database import get_db
from app.core.security import verify_token
from app.services.auth_service import get_user_by_email

router = APIRouter()


# Response Models
class UserProfile(BaseModel):
    email: str
    name: str
    is_verified: bool
    created_at: str


class ProfileResponse(BaseModel):
    status_code: int
    details: str
    is_success: bool
    user: UserProfile | None = None


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
        email=user.email,
        name=user.name,
        is_verified=user.is_verified,
        created_at=user.created_at.strftime("%Y-%m-%d %H:%M:%S")
    )

    return ProfileResponse(
        status_code=200,
        details="Profile retrieved successfully",
        is_success=True,
        user=user_profile
    )