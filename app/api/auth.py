from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.services import auth_service

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


@router.post("/register", response_model=AuthResponse)
async def register(
        request: RegisterRequest,
        db: Session = Depends(get_db)
):
    """Register new user"""
    result = auth_service.register_user(
        db=db,
        email=request.email,
        password=request.password,
        name=request.name
    )
    return create_response(result, 201)


@router.post("/login", response_model=AuthResponse)
async def login(
        request: LoginRequest,
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