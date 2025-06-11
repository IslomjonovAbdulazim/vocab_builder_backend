# app/services/__init__.py
"""
Import all services for easy access
"""

from app.services import auth_service
from app.services import email_service
from app.services import folder_service
from app.services import quiz_service

# Export services
__all__ = [
    "auth_service",
    "email_service",
    "folder_service",
    "quiz_service"
]