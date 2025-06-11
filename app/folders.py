# app/folders.py - Folder and vocabulary management
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models import Folder, VocabItem, FolderCopy, User
from app.utils import (
    StandardResponse, get_current_user_id, generate_share_code,
    validate_vocabulary_item, check_folder_access, update_folder_word_count
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


class BulkVocabImport(BaseModel):
    items: List[VocabItemCreate]


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
            "total_words": folder.total_words,
            "total_copies": folder.total_copies,
            "total_quizzes": folder.total_quizzes,
            "created_at": folder.created_at,
            "updated_at": folder.updated_at
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
                "total_words": folder.total_words,
                "created_at": folder.created_at
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
            "total_words": folder.total_words,
            "total_copies": folder.total_copies,
            "total_quizzes": folder.total_quizzes,
            "is_owner": folder.owner_id == user_id,
            "owner": {
                "username": folder.owner.username,
                "name": folder.owner.name
            },
            "created_at": folder.created_at,
            "updated_at": folder.updated_at
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
            "created_at": folder.created_at
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
            "created_at": item.created_at
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
                "created_at": vocab_item.created_at
            }
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error adding vocabulary: {str(e)}")


@router.post("/{folder_id}/vocab/bulk", response_model=StandardResponse)
async def bulk_import_vocabulary(
    folder_id: int,
    bulk_data: BulkVocabImport,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Bulk import vocabulary items"""
    # Check folder ownership
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Not authorized to edit this folder")

    imported_count = 0
    failed_items = []

    try:
        for item_data in bulk_data.items:
            # Validate each item
            validation = validate_vocabulary_item(item_data.word, item_data.translation)
            if not validation["is_valid"]:
                failed_items.append({
                    "word": item_data.word,
                    "error": ", ".join(validation["errors"])
                })
                continue

            # Get next order index
            max_order = db.query(VocabItem).filter(VocabItem.folder_id == folder_id).count()

            # Create vocabulary item
            vocab_item = VocabItem(
                folder_id=folder_id,
                word=item_data.word.strip(),
                translation=item_data.translation.strip(),
                definition=item_data.definition.strip() if item_data.definition else None,
                example_sentence=item_data.example_sentence.strip() if item_data.example_sentence else None,
                order_index=max_order + imported_count + 1
            )

            db.add(vocab_item)
            imported_count += 1

        db.commit()

        # Update folder word count
        update_folder_word_count(folder, db)

        return StandardResponse(
            status_code=201,
            is_success=True,
            details=f"Bulk import completed. {imported_count} items imported successfully.",
            data={
                "imported_count": imported_count,
                "failed_count": len(failed_items),
                "failed_items": failed_items
            }
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error during bulk import: {str(e)}")