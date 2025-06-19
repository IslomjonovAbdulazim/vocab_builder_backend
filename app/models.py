# app/models.py - Updated models with fixed folder sharing
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


# ================================
# USER MODELS
# ================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)

    # Stats
    total_folders_created = Column(Integer, default=0)
    total_quizzes_taken = Column(Integer, default=0)

    # Status
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owned_folders = relationship("Folder", back_populates="owner")


class OTP(Base):
    __tablename__ = "otps"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False)
    code = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)


# ================================
# FOLDER MODELS
# ================================

class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    share_code = Column(String, unique=True, index=True, nullable=False)
    is_shareable = Column(Boolean, default=True)
    shared_at = Column(DateTime(timezone=True), server_default=func.now())  # Track when sharing was enabled

    # Stats
    total_words = Column(Integer, default=0)
    total_followers = Column(Integer, default=0)  # Changed from total_copies to total_followers
    total_quizzes = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="owned_folders")
    vocab_items = relationship("VocabItem", back_populates="folder", cascade="all, delete-orphan")


class VocabItem(Base):
    __tablename__ = "vocab_items"

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=False)
    word = Column(String, nullable=False, index=True)
    translation = Column(String, nullable=False)
    definition = Column(Text, nullable=True)
    example_sentence = Column(Text, nullable=True)
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    folder = relationship("Folder", back_populates="vocab_items")


class FolderAccess(Base):  # Renamed from FolderCopy to FolderAccess
    __tablename__ = "folder_access"  # Renamed table

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=False)  # Reference to original folder only
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who has access
    accessed_at = Column(DateTime(timezone=True), server_default=func.now())  # When they got access

    # Relationships
    folder = relationship("Folder")
    user = relationship("User")

    # Constraints - user can only have access to a folder once
    __table_args__ = (UniqueConstraint('folder_id', 'user_id', name='_unique_folder_access'),)


# ================================
# QUIZ MODELS
# ================================

class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=False)
    quiz_type = Column(String, default="mixed")  # mixed, translation, definition
    question_count = Column(Integer, nullable=False)
    status = Column(String, default="active")  # active, completed, abandoned
    current_question = Column(Integer, default=1)

    # Results
    score = Column(Float, default=0.0)
    correct_answers = Column(Integer, default=0)
    total_answers = Column(Integer, default=0)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User")
    folder = relationship("Folder")
    answers = relationship("QuizAnswer", back_populates="quiz_session", cascade="all, delete-orphan")


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id = Column(Integer, primary_key=True, index=True)
    quiz_session_id = Column(Integer, ForeignKey("quiz_sessions.id"), nullable=False)
    vocab_item_id = Column(Integer, ForeignKey("vocab_items.id"), nullable=False)
    question_type = Column(String, nullable=False)
    question_text = Column(String, nullable=False)
    correct_answer = Column(String, nullable=False)
    user_answer = Column(String, nullable=True)
    is_correct = Column(Boolean, nullable=False)
    answered_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    quiz_session = relationship("QuizSession", back_populates="answers")
    vocab_item = relationship("VocabItem")