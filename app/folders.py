# app/folders.py - Updated folder management with proper sharing system
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.models import Folder, VocabItem, FolderAccess, User
from app.utils import (
    StandardResponse, get_current_user_id, generate_share_code,
    validate_vocabulary_item, update_folder_word_count,
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


class FolderFollowRequest(BaseModel):
    share_code: str


# ================================
# UPDATED UTILITIES
# ================================

def check_folder_access(folder, user_id: int, db: Session) -> bool:
    """Check if user can access folder (owns it or has access to it)"""
    try:
        # Check if user owns the folder
        if folder.owner_id == user_id:
            return True

        # Check if user has access to the folder
        access_exists = db.query(FolderAccess).filter(
            FolderAccess.folder_id == folder.id,
            FolderAccess.user_id == user_id
        ).first()

        return access_exists is not None
    except Exception:
        return folder.owner_id == user_id  # Fallback to ownership check


# ================================
# FOLDER MANAGEMENT
# ================================

@router.get("/my", response_model=StandardResponse)
async def get_my_folders(user_id: int = Depends(get_current_user_id), db: Session = Depends(get_db)):
    """Get user's owned and followed folders combined in one list"""

    # Get owned folders
    owned_folders = db.query(Folder).filter(Folder.owner_id == user_id).all()

    # Get followed folders (folders user has access to)
    followed_query = db.query(Folder, FolderAccess).join(
        FolderAccess, Folder.id == FolderAccess.folder_id
    ).filter(
        FolderAccess.user_id == user_id,
        Folder.owner_id != user_id  # Exclude owned folders from followed list
    ).all()

    # Create combined list
    all_folders = []

    # Add owned folders
    for folder in owned_folders:
        all_folders.append({
            "id": folder.id,
            "title": folder.title,
            "description": folder.description,
            "share_code": folder.share_code,
            "is_shareable": folder.is_shareable,
            "is_share_valid": is_folder_share_valid(folder),
            "total_words": folder.total_words,
            "total_followers": folder.total_followers,
            "total_quizzes": folder.total_quizzes,
            "is_owner": True,
            "owner": {
                "username": folder.owner.username,
                "name": folder.owner.name
            },
            "created_at": folder.created_at,
            "updated_at": folder.updated_at,
            "shared_at": folder.shared_at,
            "accessed_at": None
        })

    # Add followed folders
    for result in followed_query:
        all_folders.append({
            "id": result.Folder.id,
            "title": result.Folder.title,
            "description": result.Folder.description,
            "share_code": None,  # Don't show share code for followed folders
            "is_shareable": result.Folder.is_shareable,
            "is_share_valid": is_folder_share_valid(result.Folder),
            "total_words": result.Folder.total_words,
            "total_followers": result.Folder.total_followers,
            "total_quizzes": result.Folder.total_quizzes,
            "is_owner": False,
            "owner": {
                "username": result.Folder.owner.username,
                "name": result.Folder.owner.name
            },
            "created_at": result.Folder.created_at,
            "updated_at": result.Folder.updated_at,
            "shared_at": result.Folder.shared_at,
            "accessed_at": result.FolderAccess.accessed_at
        })

    # Sort by title (case-insensitive)
    all_folders.sort(key=lambda x: x["title"].lower())

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Folders retrieved successfully",
        data={
            "folders": all_folders
        }
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
                "is_owner": True,
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

    # Get access info if user is a follower
    access_info = None
    if folder.owner_id != user_id:
        folder_access = db.query(FolderAccess).filter(
            FolderAccess.folder_id == folder_id,
            FolderAccess.user_id == user_id
        ).first()
        if folder_access:
            access_info = folder_access.accessed_at

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
            "total_followers": folder.total_followers,
            "total_quizzes": folder.total_quizzes,
            "is_owner": folder.owner_id == user_id,
            "owner": {
                "username": folder.owner.username,
                "name": folder.owner.name
            },
            "created_at": folder.created_at,
            "updated_at": folder.updated_at,
            "shared_at": folder.shared_at,
            "accessed_at": access_info
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
        raise HTTPException(403, "Only the folder owner can edit this folder")

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
            details="Folder updated successfully. Changes are visible to all followers.",
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
    """Delete folder (owner only) - removes access for all followers"""
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Only the folder owner can delete this folder")

    try:
        # Get number of followers before deletion
        followers_count = db.query(FolderAccess).filter(FolderAccess.folder_id == folder_id).count()

        # Delete folder (cascade will delete vocab items and folder_access records)
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
            details=f"Folder deleted successfully. Removed access for {followers_count} followers."
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error deleting folder: {str(e)}")


# ================================
# SHARE SYSTEM (UPDATED)
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
        raise HTTPException(403, "Only the folder owner can refresh share link")

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


@router.post("/follow", response_model=StandardResponse)
async def follow_folder(
        follow_request: FolderFollowRequest,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Follow folder using share code (replaces copy_folder)"""
    try:
        # Find original folder
        folder = db.query(Folder).filter(
            Folder.share_code == follow_request.share_code.upper(),
            Folder.is_shareable == True
        ).first()

        if not folder:
            raise HTTPException(400, "Invalid share code or folder not shareable")

        # Check if share is still valid (within 24 hours)
        if not is_folder_share_valid(folder):
            raise HTTPException(400, "Share link has expired (24 hours limit)")

        # Can't follow your own folder
        if folder.owner_id == user_id:
            raise HTTPException(400, "You cannot follow your own folder")

        # Check if user already follows this folder
        existing_access = db.query(FolderAccess).filter(
            FolderAccess.folder_id == folder.id,
            FolderAccess.user_id == user_id
        ).first()

        if existing_access:
            raise HTTPException(400, "You are already following this folder")

        # Create folder access record
        folder_access = FolderAccess(
            folder_id=folder.id,
            user_id=user_id
        )
        db.add(folder_access)

        # Update folder stats
        folder.total_followers += 1

        db.commit()

        return StandardResponse(
            status_code=201,
            is_success=True,
            details="Folder followed successfully! You now have access to this folder and will see any updates made by the owner.",
            data={
                "folder": {
                    "id": folder.id,
                    "title": folder.title,
                    "description": folder.description,
                    "total_words": folder.total_words,
                    "total_followers": folder.total_followers,
                    "owner": {
                        "username": folder.owner.username,
                        "name": folder.owner.name
                    }
                },
                "accessed_at": folder_access.accessed_at
            }
        )

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(400, f"Error following folder: {str(e)}")


@router.delete("/{folder_id}/unfollow", response_model=StandardResponse)
async def unfollow_folder(
        folder_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Unfollow folder (remove access)"""
    try:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()

        if not folder:
            raise HTTPException(404, "Folder not found")

        # Can't unfollow your own folder
        if folder.owner_id == user_id:
            raise HTTPException(400, "You cannot unfollow your own folder. Use delete instead.")

        # Find and remove access record
        folder_access = db.query(FolderAccess).filter(
            FolderAccess.folder_id == folder_id,
            FolderAccess.user_id == user_id
        ).first()

        if not folder_access:
            raise HTTPException(400, "You are not following this folder")

        # Remove access
        db.delete(folder_access)

        # Update folder stats
        if folder.total_followers > 0:
            folder.total_followers -= 1

        db.commit()

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Folder unfollowed successfully. You no longer have access to this folder."
        )

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(400, f"Error unfollowing folder: {str(e)}")


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
            "total_followers": folder.total_followers,
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
# VOCABULARY MANAGEMENT (OWNER ONLY)
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

    # Check access (owner or follower)
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
                "title": folder.title,
                "is_owner": folder.owner_id == user_id
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
    """Add vocabulary item to folder (owner only)"""
    # Check folder ownership
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Only the folder owner can add vocabulary items")

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
            details="Vocabulary item added successfully. All followers will see this new word.",
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
    """Update vocabulary item (owner only)"""
    # Check folder ownership
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Only the folder owner can edit vocabulary items")

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
            details="Vocabulary item updated successfully. All followers will see this change.",
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
    """Delete vocabulary item (owner only)"""
    # Check folder ownership
    folder = db.query(Folder).filter(Folder.id == folder_id).first()

    if not folder:
        raise HTTPException(404, "Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(403, "Only the folder owner can delete vocabulary items")

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
            details="Vocabulary item deleted successfully. All followers will see this change."
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(400, f"Error deleting vocabulary: {str(e)}")