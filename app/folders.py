# app/folders.py - Folder and vocabulary management
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models import Folder, VocabItem, FolderCopy, User
from app.utils import (
    StandardResponse, get_current_user_id, generate_share_code,
    validate_vocabulary_item, check_folder_access, update_folder_word_count,
    is_folder_share_valid, refresh_folder_share
)

router = APIRouter()


# ================================
# REQUEST MODELS
# ================================

class FolderCreate(BaseModel):
    title: str
    description: Optional[str] = None


class FolderUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class VocabItemCreate(BaseModel):
    word: str
    translation: str
    definition: Optional[str] = None
    example_sentence: Optional[str] = None


class VocabItemUpdate(BaseModel):
    word: Optional[str] = None
    translation: Optional[str] = None
    definition: Optional[str] = None
    example_sentence: Optional[str] = None


class FolderCopyRequest(BaseModel):
    share_code: str


# ================================
# FOLDER MANAGEMENT
# ================================

@router.get("/my", response_model=StandardResponse)
async def get_my_folders(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Get user's owned folders"""
    folders = db.query(Folder).filter(Folder.owner_id == user_id).all()

    folder_list = [
        {
            "id": folder.id,
            "title": folder.title,
            "description": folder.description,
            "share_code": folder.share_code,
            "is_shareable": folder.is_shareable,
            "is_share_valid": is_folder_share_valid(folder),
            "total_words": folder.total_words,
            "total_copies": folder.total_copies,
            "total_quizzes": folder.total_quizzes,
            "created_at": folder.created_at,
            "updated_at": folder.updated_at,
            "shared_at": folder.shared_at
        }
        for folder in folders
    ]

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Folders retrieved successfully",
        data={"folders": folder_list}
    )


@router.post("/", response_model=StandardResponse)
async def create_folder(
    folder_data: FolderCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Create new folder"""
    if not folder_data.title or len(folder_data.title.strip()) < 1:
        raise HTTPException(400, "Folder title is required")

    if len(folder_data.title) > 100:
        raise HTTPException(400, "Folder title too long (max 100 characters)")

    try:
        # Generate unique share code
        share_code = generate_share_code()
        while db.query(Folder).filter(Folder.share_code == share_code).first():
            share_code = generate_share_code()

        # Create folder
        folder = Folder(
            title=folder_data.title.strip(),
            description=folder_data.description.strip() if folder_data.description else None,
            owner_id=user_id,
            share_code=share_code
        )

        db.add(folder)
        db.commit()
        db.refresh(folder)

        # Update user stats
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.total_folders_created += 1
            db.commit()

        return StandardResponse(
            status_code=201,
            is_success=True,
            details="Folder created successfully",
            data={
                "id": folder.id,
                "title": folder.title,
                "description": folder.description,
                "share_code": folder.share_code,
                "is_shareable": folder.is_shareable,
                "is_share_valid": is_folder_share_valid(folder),
                "total_words": folder.total_words,
                "created_at": folder.created_at,
                "shared_at": folder.shared_at
            }
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error creating folder: {str(e)}")


@router.get("/{folder_id}", response_model=StandardResponse)
async def get_folder(
    folder_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Get folder details"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    # Check access permission
    if not check_folder_access(folder, user_id, db):
        raise HTTPException(403, "Not authorized to view this folder")

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Folder retrieved successfully",
        data={
            "id": folder.id,
            "title": folder.title,
            "description": folder.description,
            "share_code": folder.share_code if folder.owner_id == user_id else None,
            "is_shareable": folder.is_shareable,
            "is_share_valid": is_folder_share_valid(folder),
            "total_words": folder.total_words,
            "total_copies": folder.total_copies,
            "total_quizzes": folder.total_quizzes,
            "is_owner": folder.owner_id == user_id,
            "owner": {
                "username": folder.owner.username,
                "name": folder.owner.name
            },
            "created_at": folder.created_at,
            "updated_at": folder.updated_at,
            "shared_at": folder.shared_at
        }
    )


@router.put("/{folder_id}", response_model=StandardResponse)
async def update_folder(
    folder_id: int,
    folder_data: FolderUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Update folder (owner only)"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Not authorized to edit this folder")

    try:
        # Update fields
        if folder_data.title:
            folder.title = folder_data.title.strip()
        if folder_data.description is not None:
            folder.description = folder_data.description.strip() if folder_data.description else None

        db.commit()
        db.refresh(folder)

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Folder updated successfully",
            data={
                "id": folder.id,
                "title": folder.title,
                "description": folder.description,
                "updated_at": folder.updated_at
            }
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error updating folder: {str(e)}")


@router.delete("/{folder_id}", response_model=StandardResponse)
async def delete_folder(
    folder_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Delete folder (owner only)"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Not authorized to delete this folder")

    try:
        # Delete folder (cascade will delete vocab items and copies)
        db.delete(folder)
        db.commit()

        # Update user stats
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.total_folders_created > 0:
            user.total_folders_created -= 1
            db.commit()

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Folder deleted successfully"
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error deleting folder: {str(e)}")


# ================================
# SHARE SYSTEM
# ================================

@router.post("/{folder_id}/refresh-share", response_model=StandardResponse)
async def refresh_share_link(
    folder_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Refresh share link (reset 24-hour timer)"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Not authorized to refresh share link")

    try:
        # Refresh share timestamp
        refresh_folder_share(folder, db)

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Share link refreshed successfully. Valid for 24 hours.",
            data={
                "share_code": folder.share_code,
                "shared_at": folder.shared_at,
                "is_share_valid": is_folder_share_valid(folder)
            }
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error refreshing share link: {str(e)}")


@router.post("/copy", response_model=StandardResponse)
async def copy_folder(
    copy_request: FolderCopyRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Copy folder using share code"""
    try:
        # Find original folder
        original_folder = db.query(Folder).filter(
            Folder.share_code == copy_request.share_code.upper(),
            Folder.is_shareable == True
        ).first()

        if not original_folder:
            raise HTTPException(400, "Invalid share code or folder not shareable")

        # Check if share is still valid (within 24 hours)
        if not is_folder_share_valid(original_folder):
            raise HTTPException(400, "Share link has expired (24 hours limit)")

        # Check if user already copied this folder
        existing_copy = db.query(FolderCopy).filter(
            FolderCopy.original_folder_id == original_folder.id,
            FolderCopy.copied_by_user_id == user_id
        ).first()

        if existing_copy:
            raise HTTPException(400, "You already copied this folder")

        # Can't copy your own folder
        if original_folder.owner_id == user_id:
            raise HTTPException(400, "You cannot copy your own folder")

        # Create new folder
        new_folder = Folder(
            title=f"{original_folder.title} (Copy)",
            description=original_folder.description,
            owner_id=user_id,
            share_code=generate_share_code(),
            total_words=original_folder.total_words
        )

        # Ensure unique share code
        while db.query(Folder).filter(Folder.share_code == new_folder.share_code).first():
            new_folder.share_code = generate_share_code()

        db.add(new_folder)
        db.flush()

        # Copy all vocabulary items
        vocab_items = db.query(VocabItem).filter(
            VocabItem.folder_id == original_folder.id
        ).order_by(VocabItem.order_index).all()

        for item in vocab_items:
            new_item = VocabItem(
                folder_id=new_folder.id,
                word=item.word,
                translation=item.translation,
                definition=item.definition,
                example_sentence=item.example_sentence,
                order_index=item.order_index
            )
            db.add(new_item)

        # Track the copy
        folder_copy = FolderCopy(
            original_folder_id=original_folder.id,
            copied_folder_id=new_folder.id,
            copied_by_user_id=user_id
        )
        db.add(folder_copy)

        # Update stats
        original_folder.total_copies += 1

        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.total_folders_created += 1

        db.commit()
        db.refresh(new_folder)

        return StandardResponse(
            status_code=201,
            is_success=True,
            details="Folder copied successfully",
            data={
                "copied_folder": {
                    "id": new_folder.id,
                    "title": new_folder.title,
                    "description": new_folder.description,
                    "share_code": new_folder.share_code,
                    "total_words": new_folder.total_words
                },
                "original_folder": {
                    "id": original_folder.id,
                    "title": original_folder.title,
                    "owner": {
                        "username": original_folder.owner.username,
                        "name": original_folder.owner.name
                    }
                }
            }
        )

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(400, f"Error copying folder: {str(e)}")


@router.get("/{folder_id}/share-info", response_model=StandardResponse)
async def get_share_info(folder_id: int, db: Session = Depends(get_db)):
    """Get folder share info (public preview)"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder or not folder.is_shareable:
        raise HTTPException(404, "Folder not found or not shareable")

    # Check if share is still valid (within 24 hours)
    if not is_folder_share_valid(folder):
        raise HTTPException(410, "Share link has expired (24 hours limit)")

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Share info retrieved successfully",
        data={
            "id": folder.id,
            "title": folder.title,
            "description": folder.description,
            "total_words": folder.total_words,
            "total_copies": folder.total_copies,
            "owner": {
                "username": folder.owner.username,
                "name": folder.owner.name
            },
            "created_at": folder.created_at,
            "shared_at": folder.shared_at,
            "is_share_valid": is_folder_share_valid(folder)
        }
    )


# ================================
# VOCABULARY MANAGEMENT
# ================================

@router.get("/{folder_id}/vocab", response_model=StandardResponse)
async def get_folder_vocabulary(
    folder_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Get all vocabulary items in folder"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    # Check access (owner or copied)
    if not check_folder_access(folder, user_id, db):
        raise HTTPException(403, "Not authorized to view this folder")

    vocab_items = db.query(VocabItem).filter(
        VocabItem.folder_id == folder_id
    ).order_by(VocabItem.order_index).all()

    vocab_list = [
        {
            "id": item.id,
            "word": item.word,
            "translation": item.translation,
            "definition": item.definition,
            "example_sentence": item.example_sentence,
            "order_index": item.order_index,
            "created_at": item.created_at,
            "updated_at": item.updated_at
        }
        for item in vocab_items
    ]

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Vocabulary retrieved successfully",
        data={
            "vocabulary": vocab_list,
            "folder": {
                "id": folder.id,
                "title": folder.title
            }
        }
    )


@router.post("/{folder_id}/vocab", response_model=StandardResponse)
async def add_vocabulary_item(
    folder_id: int,
    vocab_data: VocabItemCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Add vocabulary item to folder"""
    # Check folder ownership
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Not authorized to edit this folder")

    # Validate input
    validation = validate_vocabulary_item(vocab_data.word, vocab_data.translation)
    if not validation["is_valid"]:
        raise HTTPException(400, ", ".join(validation["errors"]))

    try:
        # Get next order index
        max_order = db.query(VocabItem).filter(VocabItem.folder_id == folder_id).count()

        # Create vocabulary item
        vocab_item = VocabItem(
            folder_id=folder_id,
            word=vocab_data.word.strip(),
            translation=vocab_data.translation.strip(),
            definition=vocab_data.definition.strip() if vocab_data.definition else None,
            example_sentence=vocab_data.example_sentence.strip() if vocab_data.example_sentence else None,
            order_index=max_order + 1
        )

        db.add(vocab_item)
        db.commit()
        db.refresh(vocab_item)

        # Update folder word count
        update_folder_word_count(folder, db)

        return StandardResponse(
            status_code=201,
            is_success=True,
            details="Vocabulary item added successfully",
            data={
                "id": vocab_item.id,
                "word": vocab_item.word,
                "translation": vocab_item.translation,
                "definition": vocab_item.definition,
                "example_sentence": vocab_item.example_sentence,
                "order_index": vocab_item.order_index,
                "created_at": vocab_item.created_at,
                "updated_at": vocab_item.updated_at
            }
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error adding vocabulary: {str(e)}")


@router.put("/{folder_id}/vocab/{vocab_id}", response_model=StandardResponse)
async def update_vocabulary_item(
    folder_id: int,
    vocab_id: int,
    vocab_data: VocabItemUpdate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Update vocabulary item"""
    # Check folder ownership
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Not authorized to edit this folder")

    # Find vocabulary item
    vocab_item = db.query(VocabItem).filter(
        VocabItem.id == vocab_id,
        VocabItem.folder_id == folder_id
    ).first()

    if not vocab_item:
        raise HTTPException(404, "Vocabulary item not found")

    try:
        # Update fields if provided
        if vocab_data.word is not None:
            if not vocab_data.word.strip():
                raise HTTPException(400, "Word cannot be empty")
            vocab_item.word = vocab_data.word.strip()

        if vocab_data.translation is not None:
            if not vocab_data.translation.strip():
                raise HTTPException(400, "Translation cannot be empty")
            vocab_item.translation = vocab_data.translation.strip()

        if vocab_data.definition is not None:
            vocab_item.definition = vocab_data.definition.strip() if vocab_data.definition.strip() else None

        if vocab_data.example_sentence is not None:
            vocab_item.example_sentence = vocab_data.example_sentence.strip() if vocab_data.example_sentence.strip() else None

        # Validate updated data
        validation = validate_vocabulary_item(vocab_item.word, vocab_item.translation)
        if not validation["is_valid"]:
            raise HTTPException(400, ", ".join(validation["errors"]))

        db.commit()
        db.refresh(vocab_item)

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Vocabulary item updated successfully",
            data={
                "id": vocab_item.id,
                "word": vocab_item.word,
                "translation": vocab_item.translation,
                "definition": vocab_item.definition,
                "example_sentence": vocab_item.example_sentence,
                "order_index": vocab_item.order_index,
                "created_at": vocab_item.created_at,
                "updated_at": vocab_item.updated_at
            }
        )

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(400, f"Error updating vocabulary: {str(e)}")


@router.delete("/{folder_id}/vocab/{vocab_id}", response_model=StandardResponse)
async def delete_vocabulary_item(
    folder_id: int,
    vocab_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Delete vocabulary item"""
    # Check folder ownership
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Not authorized to edit this folder")

    # Find vocabulary item
    vocab_item = db.query(VocabItem).filter(
        VocabItem.id == vocab_id,
        VocabItem.folder_id == folder_id
    ).first()

    if not vocab_item:
        raise HTTPException(404, "Vocabulary item not found")

    try:
        # Delete vocabulary item
        db.delete(vocab_item)
        db.commit()

        # Update folder word count
        update_folder_word_count(folder, db)

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Vocabulary item deleted successfully"
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error deleting vocabulary: {str(e)}")