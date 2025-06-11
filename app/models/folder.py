# app/models/folder.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # OWNERSHIP
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # SHARE SYSTEM
    share_code = Column(String, unique=True, index=True, nullable=False)
    is_shareable = Column(Boolean, default=True)

    # SIMPLE STATS
    total_words = Column(Integer, default=0)
    total_copies = Column(Integer, default=0)
    total_quizzes = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # RELATIONSHIPS
    owner = relationship("User", backref="owned_folders")
    vocab_items = relationship("VocabItem", back_populates="folder", cascade="all, delete-orphan")


class VocabItem(Base):
    __tablename__ = "vocab_items"

    id = Column(Integer, primary_key=True, index=True)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=False)

    # CORE DATA
    word = Column(String, nullable=False, index=True)
    translation = Column(String, nullable=False)
    definition = Column(Text, nullable=True)
    example_sentence = Column(Text, nullable=True)

    # SIMPLE ORDERING
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # RELATIONSHIPS
    folder = relationship("Folder", back_populates="vocab_items")


class FolderCopy(Base):
    __tablename__ = "folder_copies"

    id = Column(Integer, primary_key=True, index=True)
    original_folder_id = Column(Integer, ForeignKey("folders.id"), nullable=False)
    copied_folder_id = Column(Integer, ForeignKey("folders.id"), nullable=False)
    copied_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    copied_at = Column(DateTime(timezone=True), server_default=func.now())

    # RELATIONSHIPS
    original_folder = relationship("Folder", foreign_keys=[original_folder_id])
    copied_folder = relationship("Folder", foreign_keys=[copied_folder_id])
    copied_by = relationship("User")

    # UNIQUE CONSTRAINT - user can only copy same folder once
    __table_args__ = (UniqueConstraint('original_folder_id', 'copied_by_user_id', name='_unique_copy'),)