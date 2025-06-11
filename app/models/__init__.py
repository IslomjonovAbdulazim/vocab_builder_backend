# app/models/__init__.py
"""
Import all models to ensure they are registered with SQLAlchemy
"""

from app.models.user import User
from app.models.otp import OTP
from app.models.folder import Folder, VocabItem, FolderCopy
from app.models.quiz import QuizSession, QuizAnswer

# Export all models
__all__ = [
    "User",
    "OTP",
    "Folder",
    "VocabItem",
    "FolderCopy",
    "QuizSession",
    "QuizAnswer"
]