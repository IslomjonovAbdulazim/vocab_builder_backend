from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.services import auth_service
from app.services.email_service import email_service
import asyncio

router = APIRouter()


# Request Models
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


# Response Model
class AuthResponse(BaseModel):
    status_code: int
    details: str
    is_success: bool
    token: str | None = None


def create_response(result: dict, success_code: int = 200) -> AuthResponse:
    """Create standardized response"""
    return AuthResponse(
        status_code=success_code if result["success"] else 400,
        details=result["message"],
        is_success=result["success"],
        token=result.get("token")
    )


async def send_otp_background(email: str, otp_code: str, purpose: str):
    """Background task to send OTP email"""
    result = await email_service.send_otp_email(email, otp_code, purpose)
    if not result.success:
        # Log the error
        print(f"Failed to send OTP email to {email}: {result.error_details}")


@router.post("/register", response_model=AuthResponse)
async def register(
        request: RegisterRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """Register new user"""
    result = auth_service.register_user(
        db=db,
        email=request.email,
        password=request.password,
        name=request.name
    )

    # If registration was successful, OTP was created and email task was queued
    # No additional action needed here

    return create_response(result, 201)


@router.post("/login", response_model=AuthResponse)
async def login(
        request: LoginRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """User login"""
    result = auth_service.login_user(
        db=db,
        email=request.email,
        password=request.password
    )

    return create_response(result)


@router.post("/verify-email", response_model=AuthResponse)
async def verify_email(
        request: VerifyEmailRequest,
        db: Session = Depends(get_db)
):
    """Verify email with OTP"""
    result = auth_service.verify_user_email(
        db=db,
        email=request.email,
        otp_code=request.otp_code
    )
    return create_response(result)


@router.post("/forgot-password", response_model=AuthResponse)
async def forgot_password(
        request: ForgotPasswordRequest,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    """Send password reset OTP"""
    result = auth_service.forgot_password(
        db=db,
        email=request.email
    )

    return create_response(result)


@router.post("/reset-password", response_model=AuthResponse)
async def reset_password(
        request: ResetPasswordRequest,
        db: Session = Depends(get_db)
):
    """Reset password"""
    result = auth_service.reset_password(
        db=db,
        email=request.email,
        new_password=request.new_password
    )
    return create_response(result)


@router.get("/email-stats")
async def get_email_stats():
    """Get email service statistics (for monitoring)"""
    stats = await email_service.get_stats()
    return {
        "status_code": 200,
        "details": "Email service statistics",
        "is_success": True,
        "stats": stats
    }


@router.get("/health/email")
async def email_health_check():
    """Check email service health"""
    is_healthy = await email_service.health_check()
    return {
        "status_code": 200 if is_healthy else 503,
        "details": "Email service is healthy" if is_healthy else "Email service is unhealthy",
        "is_success": is_healthy
    }