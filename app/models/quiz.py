# app/models/quiz.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=False)

    # QUIZ CONFIG
    quiz_type = Column(String, default="mixed")  # mixed, translation, definition
    question_count = Column(Integer, nullable=False)

    # SESSION STATUS
    status = Column(String, default="active")  # active, completed, abandoned
    current_question = Column(Integer, default=1)

    # RESULTS
    score = Column(Float, default=0.0)  # percentage 0-100
    correct_answers = Column(Integer, default=0)
    total_answers = Column(Integer, default=0)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # RELATIONSHIPS
    user = relationship("User")
    folder = relationship("Folder")
    answers = relationship("QuizAnswer", back_populates="quiz_session", cascade="all, delete-orphan")


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"

    id = Column(Integer, primary_key=True, index=True)
    quiz_session_id = Column(Integer, ForeignKey("quiz_sessions.id"), nullable=False)
    vocab_item_id = Column(Integer, ForeignKey("vocab_items.id"), nullable=False)

    # QUESTION DATA
    question_type = Column(String, nullable=False)  # translation, definition, multiple_choice
    question_text = Column(String, nullable=False)
    correct_answer = Column(String, nullable=False)

    # USER RESPONSE
    user_answer = Column(String, nullable=True)
    is_correct = Column(Boolean, nullable=False)

    answered_at = Column(DateTime(timezone=True), server_default=func.now())

    # RELATIONSHIPS
    quiz_session = relationship("QuizSession", back_populates="answers")
    vocab_item = relationship("VocabItem")