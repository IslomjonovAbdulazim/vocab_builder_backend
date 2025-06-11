# app/api/folders.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.core.security import verify_token
from app.services import folder_service
from app.api.users import get_current_user_email

router = APIRouter()


# REQUEST MODELS
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


# RESPONSE MODELS
class StandardResponse(BaseModel):
    status_code: int
    is_success: bool
    details: str
    data: Optional[dict] = None


def get_current_user_id(current_email: str = Depends(get_current_user_email), db: Session = Depends(get_db)) -> int:
    """Get current user ID from JWT token"""
    from app.services.auth_service import get_user_by_email
    user = get_user_by_email(db, current_email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.id


# FOLDER MANAGEMENT ENDPOINTS

@router.get("/my", response_model=StandardResponse)
async def get_my_folders(
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Get user's owned folders"""
    folders = folder_service.get_user_folders(db, user_id)

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
        raise HTTPException(status_code=400, detail="Folder title is required")

    if len(folder_data.title) > 100:
        raise HTTPException(status_code=400, detail="Folder title is too long (max 100 characters)")

    result = folder_service.create_folder(
        db=db,
        user_id=user_id,
        title=folder_data.title,
        description=folder_data.description
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    folder = result["folder"]

    return StandardResponse(
        status_code=201,
        is_success=True,
        details=result["message"],
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


@router.get("/{folder_id}", response_model=StandardResponse)
async def get_folder(
        folder_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Get folder details"""
    folder = folder_service.get_folder_by_id(db, folder_id)

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Check access permission
    from app.core.utils import check_folder_access
    if not check_folder_access(folder, user_id, db):
        raise HTTPException(status_code=403, detail="Not authorized to view this folder")

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
    result = folder_service.update_folder(
        db=db,
        folder_id=folder_id,
        user_id=user_id,
        title=folder_data.title,
        description=folder_data.description
    )

    if not result["success"]:
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        elif "not authorized" in result["message"].lower():
            raise HTTPException(status_code=403, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    folder = result["folder"]

    return StandardResponse(
        status_code=200,
        is_success=True,
        details=result["message"],
        data={
            "id": folder.id,
            "title": folder.title,
            "description": folder.description,
            "updated_at": folder.updated_at
        }
    )


@router.delete("/{folder_id}", response_model=StandardResponse)
async def delete_folder(
        folder_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Delete folder (owner only)"""
    result = folder_service.delete_folder(db, folder_id, user_id)

    if not result["success"]:
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        elif "not authorized" in result["message"].lower():
            raise HTTPException(status_code=403, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    return StandardResponse(
        status_code=200,
        is_success=True,
        details=result["message"]
    )


# SHARE SYSTEM ENDPOINTS

@router.post("/copy", response_model=StandardResponse)
async def copy_folder(
        copy_request: FolderCopyRequest,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Copy folder using share code"""
    result = folder_service.copy_folder_by_share_code(
        db=db,
        user_id=user_id,
        share_code=copy_request.share_code
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    copied_folder = result["copied_folder"]
    original_folder = result["original_folder"]

    return StandardResponse(
        status_code=201,
        is_success=True,
        details=result["message"],
        data={
            "copied_folder": {
                "id": copied_folder.id,
                "title": copied_folder.title,
                "description": copied_folder.description,
                "share_code": copied_folder.share_code,
                "total_words": copied_folder.total_words
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


@router.get("/{folder_id}/share-info", response_model=StandardResponse)
async def get_share_info(
        folder_id: int,
        db: Session = Depends(get_db)
):
    """Get folder share info (public preview)"""
    folder = folder_service.get_folder_by_id(db, folder_id)

    if not folder or not folder.is_shareable:
        raise HTTPException(status_code=404, detail="Folder not found or not shareable")

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


@router.get("/{folder_id}/copiers", response_model=StandardResponse)
async def get_folder_copiers(
        folder_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Get list of users who copied this folder (owner only)"""
    result = folder_service.get_folder_copiers(db, folder_id, user_id)

    if not result["success"]:
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        elif "not authorized" in result["message"].lower():
            raise HTTPException(status_code=403, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Copiers retrieved successfully",
        data={
            "copiers": result["copiers"]
        }
    )


# VOCABULARY MANAGEMENT ENDPOINTS

@router.get("/{folder_id}/vocab", response_model=StandardResponse)
async def get_folder_vocabulary(
        folder_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Get all vocabulary items in folder"""
    result = folder_service.get_folder_vocabulary(db, folder_id, user_id)

    if not result["success"]:
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        elif "not authorized" in result["message"].lower():
            raise HTTPException(status_code=403, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])

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
        for item in result["vocab_items"]
    ]

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Vocabulary retrieved successfully",
        data={
            "vocabulary": vocab_list,
            "folder": {
                "id": result["folder"].id,
                "title": result["folder"].title
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
    result = folder_service.add_vocabulary_item(
        db=db,
        folder_id=folder_id,
        user_id=user_id,
        word=vocab_data.word,
        translation=vocab_data.translation,
        definition=vocab_data.definition,
        example_sentence=vocab_data.example_sentence
    )

    if not result["success"]:
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        elif "not authorized" in result["message"].lower():
            raise HTTPException(status_code=403, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    vocab_item = result["vocab_item"]

    return StandardResponse(
        status_code=201,
        is_success=True,
        details=result["message"],
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


@router.post("/{folder_id}/vocab/bulk", response_model=StandardResponse)
async def bulk_import_vocabulary(
        folder_id: int,
        bulk_data: BulkVocabImport,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Bulk import vocabulary items"""
    # Check folder ownership
    folder = folder_service.get_folder_by_id(db, folder_id)

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if folder.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this folder")

    imported_count = 0
    failed_items = []

    for item_data in bulk_data.items:
        result = folder_service.add_vocabulary_item(
            db=db,
            folder_id=folder_id,
            user_id=user_id,
            word=item_data.word,
            translation=item_data.translation,
            definition=item_data.definition,
            example_sentence=item_data.example_sentence
        )

        if result["success"]:
            imported_count += 1
        else:
            failed_items.append({
                "word": item_data.word,
                "error": result["message"]
            })

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