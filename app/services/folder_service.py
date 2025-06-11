# app/services/folder_service.py
from sqlalchemy.orm import Session
from app.models.folder import Folder, VocabItem, FolderCopy
from app.models.user import User
from app.core.utils import generate_share_code, validate_vocabulary_item, update_folder_word_count
from typing import List, Dict, Optional


def create_folder(db: Session, user_id: int, title: str, description: str = None) -> Dict:
    """Create new folder"""
    try:
        # Generate unique share code
        share_code = generate_share_code()

        # Ensure share code is unique
        while db.query(Folder).filter(Folder.share_code == share_code).first():
            share_code = generate_share_code()

        # Create folder
        folder = Folder(
            title=title.strip(),
            description=description.strip() if description else None,
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

        return {
            "success": True,
            "message": "Folder created successfully",
            "folder": folder
        }

    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "message": f"Error creating folder: {str(e)}"
        }


def get_user_folders(db: Session, user_id: int) -> List[Folder]:
    """Get all folders owned by user"""
    return db.query(Folder).filter(Folder.owner_id == user_id).all()


def get_folder_by_id(db: Session, folder_id: int) -> Optional[Folder]:
    """Get folder by ID"""
    return db.query(Folder).filter(Folder.id == folder_id).first()


def get_folder_by_share_code(db: Session, share_code: str) -> Optional[Folder]:
    """Get folder by share code"""
    return db.query(Folder).filter(
        Folder.share_code == share_code.upper(),
        Folder.is_shareable == True
    ).first()


def update_folder(db: Session, folder_id: int, user_id: int, title: str = None, description: str = None) -> Dict:
    """Update folder (owner only)"""
    try:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()

        if not folder:
            return {"success": False, "message": "Folder not found"}

        if folder.owner_id != user_id:
            return {"success": False, "message": "Not authorized to edit this folder"}

        # Update fields
        if title:
            folder.title = title.strip()
        if description is not None:
            folder.description = description.strip() if description else None

        db.commit()
        db.refresh(folder)

        return {
            "success": True,
            "message": "Folder updated successfully",
            "folder": folder
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error updating folder: {str(e)}"}


def delete_folder(db: Session, folder_id: int, user_id: int) -> Dict:
    """Delete folder (owner only)"""
    try:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()

        if not folder:
            return {"success": False, "message": "Folder not found"}

        if folder.owner_id != user_id:
            return {"success": False, "message": "Not authorized to delete this folder"}

        # Delete folder (cascade will delete vocab items and copies)
        db.delete(folder)
        db.commit()

        # Update user stats
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.total_folders_created > 0:
            user.total_folders_created -= 1
            db.commit()

        return {"success": True, "message": "Folder deleted successfully"}

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error deleting folder: {str(e)}"}


def copy_folder_by_share_code(db: Session, user_id: int, share_code: str) -> Dict:
    """Copy folder using share code"""
    try:
        # Find original folder
        original_folder = get_folder_by_share_code(db, share_code)

        if not original_folder:
            return {"success": False, "message": "Invalid share code or folder not shareable"}

        # Check if user already copied this folder
        existing_copy = db.query(FolderCopy).filter(
            FolderCopy.original_folder_id == original_folder.id,
            FolderCopy.copied_by_user_id == user_id
        ).first()

        if existing_copy:
            return {"success": False, "message": "You already copied this folder"}

        # Can't copy your own folder
        if original_folder.owner_id == user_id:
            return {"success": False, "message": "You cannot copy your own folder"}

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

        return {
            "success": True,
            "message": "Folder copied successfully",
            "copied_folder": new_folder,
            "original_folder": original_folder
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error copying folder: {str(e)}"}


def add_vocabulary_item(db: Session, folder_id: int, user_id: int, word: str,
                        translation: str, definition: str = None, example_sentence: str = None) -> Dict:
    """Add vocabulary item to folder"""
    try:
        # Check folder ownership
        folder = db.query(Folder).filter(Folder.id == folder_id).first()

        if not folder:
            return {"success": False, "message": "Folder not found"}

        if folder.owner_id != user_id:
            return {"success": False, "message": "Not authorized to edit this folder"}

        # Validate input
        validation = validate_vocabulary_item(word, translation)
        if not validation["is_valid"]:
            return {"success": False, "message": ", ".join(validation["errors"])}

        # Get next order index
        max_order = db.query(VocabItem).filter(VocabItem.folder_id == folder_id).count()

        # Create vocabulary item
        vocab_item = VocabItem(
            folder_id=folder_id,
            word=word.strip(),
            translation=translation.strip(),
            definition=definition.strip() if definition else None,
            example_sentence=example_sentence.strip() if example_sentence else None,
            order_index=max_order + 1
        )

        db.add(vocab_item)
        db.commit()
        db.refresh(vocab_item)

        # Update folder word count
        update_folder_word_count(folder, db)

        return {
            "success": True,
            "message": "Vocabulary item added successfully",
            "vocab_item": vocab_item
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error adding vocabulary: {str(e)}"}


def get_folder_vocabulary(db: Session, folder_id: int, user_id: int) -> Dict:
    """Get all vocabulary items in folder"""
    try:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()

        if not folder:
            return {"success": False, "message": "Folder not found"}

        # Check access (owner or copied)
        from app.core.utils import check_folder_access
        if not check_folder_access(folder, user_id, db):
            return {"success": False, "message": "Not authorized to view this folder"}

        vocab_items = db.query(VocabItem).filter(
            VocabItem.folder_id == folder_id
        ).order_by(VocabItem.order_index).all()

        return {
            "success": True,
            "vocab_items": vocab_items,
            "folder": folder
        }

    except Exception as e:
        return {"success": False, "message": f"Error getting vocabulary: {str(e)}"}


def get_folder_copiers(db: Session, folder_id: int, user_id: int) -> Dict:
    """Get list of users who copied this folder"""
    try:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()

        if not folder:
            return {"success": False, "message": "Folder not found"}

        if folder.owner_id != user_id:
            return {"success": False, "message": "Not authorized to view this information"}

        copiers = db.query(FolderCopy, User).join(
            User, FolderCopy.copied_by_user_id == User.id
        ).filter(
            FolderCopy.original_folder_id == folder_id
        ).all()

        copier_list = [
            {
                "user_id": copy.FolderCopy.copied_by_user_id,
                "username": copy.User.username,
                "name": copy.User.name,
                "copied_at": copy.FolderCopy.copied_at
            }
            for copy in copiers
        ]

        return {
            "success": True,
            "copiers": copier_list,
            "total_copies": len(copier_list)
        }

    except Exception as e:
        return {"success": False, "message": f"Error getting copiers: {str(e)}"}