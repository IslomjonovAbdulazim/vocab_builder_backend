from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Annotated, Optional
from app.database import get_db
from app.core.security import verify_token
from app.services.auth_service import get_user_by_email
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Simple Response Model - just user data
class UserProfile(BaseModel):
    email: str
    name: str
    is_verified: bool
    created_at: str


def get_current_user_email(authorization: Annotated[Optional[str], Header()] = None):
    """Extract and verify JWT token from Authorization header"""

    logger.info("=" * 50)
    logger.info("🔐 STARTING AUTHENTICATION PROCESS")
    logger.info("=" * 50)

    # Debug logging
    logger.info(f"📥 Authorization header received: {authorization}")
    logger.info(f"📏 Authorization header length: {len(authorization) if authorization else 0}")

    if not authorization:
        logger.error("❌ No authorization header provided")
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )

    # Check if it starts with "Bearer "
    if not authorization.startswith("Bearer "):
        logger.error(f"❌ Invalid authorization format: {authorization}")
        logger.error("💡 Expected format: 'Bearer <token>'")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Use 'Bearer <token>'"
        )

    # Extract token
    try:
        parts = authorization.split(" ")
        logger.info(f"🔪 Split authorization into {len(parts)} parts: {parts}")

        if len(parts) != 2:
            logger.error(f"❌ Expected 2 parts, got {len(parts)}")
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization format. Use 'Bearer <token>'"
            )

        token = parts[1]
        logger.info(f"🎫 Extracted token: {token[:30]}...")
        logger.info(f"📏 Token length: {len(token)}")

    except IndexError as e:
        logger.error(f"❌ Failed to extract token from authorization header: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format. Use 'Bearer <token>'"
        )

    # Verify token
    logger.info("🔍 Starting token verification...")
    email = verify_token(token)
    logger.info(f"🔍 Token verification result: {email}")

    if not email:
        logger.error("❌ Token verification failed - returning 401")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    logger.info(f"✅ Authentication successful for: {email}")
    logger.info("=" * 50)
    return email


@router.get("/profile", response_model=UserProfile)
async def get_profile(
        current_email: str = Depends(get_current_user_email),
        db: Session = Depends(get_db)
):
    """Get user profile - returns just user data"""
    logger.info("=" * 50)
    logger.info("👤 STARTING PROFILE RETRIEVAL")
    logger.info("=" * 50)
    logger.info(f"📧 Getting profile for user: {current_email}")

    user = get_user_by_email(db, current_email)
    logger.info(f"🔍 Database query result: {user}")

    if not user:
        logger.error(f"❌ User not found in database: {current_email}")
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    logger.info(f"✅ User found: {user.email}, verified: {user.is_verified}")

    profile = UserProfile(
        email=user.email,
        name=user.name,
        is_verified=user.is_verified,
        created_at=user.created_at.strftime("%Y-%m-%d %H:%M:%S")
    )

    logger.info(f"📤 Returning profile: {profile}")
    logger.info("=" * 50)
    return profile