# app/quiz.py - Quiz system
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict
import random

from app.database import get_db
from app.models import QuizSession, QuizAnswer, Folder, VocabItem, User
from app.utils import StandardResponse, get_current_user_id, check_folder_access, calculate_quiz_score

router = APIRouter()


# ================================
# REQUEST MODELS
# ================================

class QuizStartRequest(BaseModel):
    quiz_type: str = "mixed"  # mixed, translation, definition
    question_count: int = 10


class QuizAnswerRequest(BaseModel):
    answer: str


# ================================
# QUIZ LOGIC
# ================================

def generate_next_question(db: Session, quiz_session_id: int) -> Optional[Dict]:
    """Generate the next question for the quiz"""
    try:
        quiz = db.query(QuizSession).filter(QuizSession.id == quiz_session_id).first()

        if not quiz or quiz.status != "active":
            return None

        # Get vocabulary items from the folder
        vocab_items = db.query(VocabItem).filter(VocabItem.folder_id == quiz.folder_id).all()

        if not vocab_items:
            return None

        # Get already asked vocabulary items in this quiz
        asked_vocab_ids = db.query(QuizAnswer.vocab_item_id).filter(
            QuizAnswer.quiz_session_id == quiz_session_id
        ).all()
        asked_ids = [item[0] for item in asked_vocab_ids]

        # Filter out already asked items
        available_vocab = [item for item in vocab_items if item.id not in asked_ids]

        if not available_vocab:
            return None

        # Select random vocabulary item
        vocab_item = random.choice(available_vocab)

        # Generate question based on quiz type
        question = create_question(vocab_item, quiz.quiz_type)
        question["quiz_session_id"] = quiz_session_id
        question["vocab_item_id"] = vocab_item.id

        return question

    except Exception:
        return None


def create_question(vocab_item: VocabItem, quiz_type: str) -> Dict:
    """Create a question for the vocabulary item"""
    if quiz_type == "translation":
        return {
            "type": "translation",
            "text": f"What is the Uzbek translation of '{vocab_item.word}'?",
            "word": vocab_item.word,
            "correct_answer": vocab_item.translation.lower().strip()
        }

    elif quiz_type == "definition":
        if vocab_item.definition:
            return {
                "type": "definition",
                "text": f"What does '{vocab_item.word}' mean?",
                "word": vocab_item.word,
                "correct_answer": vocab_item.definition.lower().strip()
            }
        else:
            # Fallback to translation if no definition
            return create_question(vocab_item, "translation")

    elif quiz_type == "mixed":
        # Randomly choose between translation and definition
        if vocab_item.definition and random.choice([True, False]):
            return create_question(vocab_item, "definition")
        else:
            return create_question(vocab_item, "translation")

    else:
        # Default to translation
        return create_question(vocab_item, "translation")


# ================================
# QUIZ ENDPOINTS
# ================================

@router.post("/{folder_id}/start", response_model=StandardResponse)
async def start_quiz(
    folder_id: int,
    quiz_request: QuizStartRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Start new quiz session"""
    # Validate quiz type
    valid_types = ["mixed", "translation", "definition"]
    if quiz_request.quiz_type not in valid_types:
        raise HTTPException(400, f"Invalid quiz type. Must be one of: {valid_types}")

    # Validate question count
    if quiz_request.question_count < 1 or quiz_request.question_count > 50:
        raise HTTPException(400, "Question count must be between 1 and 50")

    try:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()

        if not folder:
            raise HTTPException(404, "Folder not found")

        # Check if user can access this folder
        if not check_folder_access(folder, user_id, db):
            raise HTTPException(403, "Not authorized to quiz this folder")

        # Check if folder has enough vocabulary
        vocab_count = db.query(VocabItem).filter(VocabItem.folder_id == folder_id).count()

        if vocab_count == 0:
            raise HTTPException(400, "This folder has no vocabulary items")

        # Limit question count to available vocabulary
        question_count = min(quiz_request.question_count, vocab_count)

        # Create quiz session
        quiz_session = QuizSession(
            user_id=user_id,
            folder_id=folder_id,
            quiz_type=quiz_request.quiz_type,
            question_count=question_count,
            current_question=1
        )

        db.add(quiz_session)
        db.commit()
        db.refresh(quiz_session)

        # Generate first question
        first_question = generate_next_question(db, quiz_session.id)

        return StandardResponse(
            status_code=201,
            is_success=True,
            details="Quiz started successfully",
            data={
                "quiz_id": quiz_session.id,
                "folder_id": quiz_session.folder_id,
                "quiz_type": quiz_session.quiz_type,
                "question_count": quiz_session.question_count,
                "current_question": quiz_session.current_question,
                "question": {
                    "type": first_question["type"],
                    "text": first_question["text"],
                    "word": first_question.get("word")
                }
            }
        )

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(400, f"Error starting quiz: {str(e)}")


@router.post("/{quiz_id}/answer", response_model=StandardResponse)
async def submit_quiz_answer(
    quiz_id: int,
    answer_request: QuizAnswerRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Submit answer to current quiz question"""
    if not answer_request.answer or len(answer_request.answer.strip()) == 0:
        raise HTTPException(400, "Answer cannot be empty")

    try:
        quiz = db.query(QuizSession).filter(
            QuizSession.id == quiz_id,
            QuizSession.user_id == user_id,
            QuizSession.status == "active"
        ).first()

        if not quiz:
            raise HTTPException(404, "Quiz session not found or not active")

        # Generate current question
        current_question = generate_next_question(db, quiz_id)

        if not current_question:
            raise HTTPException(400, "No more questions available")

        # Check if answer is correct
        user_answer = answer_request.answer.lower().strip()
        correct_answer = current_question["correct_answer"]
        is_correct = user_answer == correct_answer

        # Save the answer
        quiz_answer = QuizAnswer(
            quiz_session_id=quiz_id,
            vocab_item_id=current_question["vocab_item_id"],
            question_type=current_question["type"],
            question_text=current_question["text"],
            correct_answer=correct_answer,
            user_answer=user_answer,
            is_correct=is_correct
        )

        db.add(quiz_answer)

        # Update quiz session
        quiz.total_answers += 1
        if is_correct:
            quiz.correct_answers += 1

        # Check if quiz is complete
        if quiz.total_answers >= quiz.question_count:
            # Quiz is complete
            quiz.status = "completed"
            quiz.completed_at = datetime.utcnow()
            quiz.score = calculate_quiz_score(quiz.correct_answers, quiz.total_answers)

            # Update user and folder stats
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.total_quizzes_taken += 1

            folder = db.query(Folder).filter(Folder.id == quiz.folder_id).first()
            if folder:
                folder.total_quizzes += 1

            db.commit()

            return StandardResponse(
                status_code=200,
                is_success=True,
                details="Answer submitted successfully",
                data={
                    "is_correct": is_correct,
                    "correct_answer": correct_answer,
                    "quiz_completed": True,
                    "final_score": quiz.score,
                    "message": "Quiz completed! 🎉"
                }
            )

        else:
            # Move to next question
            quiz.current_question += 1
            db.commit()

            # Generate next question
            next_question = generate_next_question(db, quiz_id)

            return StandardResponse(
                status_code=200,
                is_success=True,
                details="Answer submitted successfully",
                data={
                    "is_correct": is_correct,
                    "correct_answer": correct_answer,
                    "quiz_completed": False,
                    "current_question": quiz.current_question,
                    "total_questions": quiz.question_count,
                    "next_question": {
                        "type": next_question["type"],
                        "text": next_question["text"],
                        "word": next_question.get("word")
                    } if next_question else None
                }
            )

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(400, f"Error submitting answer: {str(e)}")


@router.get("/{quiz_id}/results", response_model=StandardResponse)
async def get_quiz_results(
    quiz_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Get detailed quiz results"""
    try:
        quiz = db.query(QuizSession).filter(
            QuizSession.id == quiz_id,
            QuizSession.user_id == user_id
        ).first()

        if not quiz:
            raise HTTPException(404, "Quiz session not found")

        folder = db.query(Folder).filter(Folder.id == quiz.folder_id).first()

        # Get all answers for review
        answers = db.query(QuizAnswer, VocabItem).join(
            VocabItem, QuizAnswer.vocab_item_id == VocabItem.id
        ).filter(
            QuizAnswer.quiz_session_id == quiz_id
        ).all()

        answer_details = [
            {
                "word": answer.VocabItem.word,
                "question": answer.QuizAnswer.question_text,
                "correct_answer": answer.QuizAnswer.correct_answer,
                "user_answer": answer.QuizAnswer.user_answer,
                "is_correct": answer.QuizAnswer.is_correct,
                "translation": answer.VocabItem.translation,
                "definition": answer.VocabItem.definition
            }
            for answer in answers
        ]

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Quiz results retrieved successfully",
            data={
                "quiz_id": quiz.id,
                "folder_title": folder.title if folder else "Unknown",
                "quiz_type": quiz.quiz_type,
                "status": quiz.status,
                "score": quiz.score,
                "correct_answers": quiz.correct_answers,
                "total_questions": quiz.total_answers,
                "started_at": quiz.started_at,
                "completed_at": quiz.completed_at,
                "answers": answer_details
            }
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(400, f"Error getting quiz results: {str(e)}")


@router.post("/{quiz_id}/finish", response_model=StandardResponse)
async def finish_quiz(
    quiz_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Finish quiz early or get final results"""
    try:
        quiz = db.query(QuizSession).filter(
            QuizSession.id == quiz_id,
            QuizSession.user_id == user_id
        ).first()

        if not quiz:
            raise HTTPException(404, "Quiz session not found")

        if quiz.status == "completed":
            # Already completed, just return score
            return StandardResponse(
                status_code=200,
                is_success=True,
                details="Quiz results retrieved",
                data={
                    "quiz_id": quiz.id,
                    "final_score": quiz.score,
                    "correct_answers": quiz.correct_answers,
                    "total_answered": quiz.total_answers,
                    "status": "completed"
                }
            )

        elif quiz.status == "active":
            # Force complete the quiz
            quiz.status = "completed"
            quiz.completed_at = datetime.utcnow()
            quiz.score = calculate_quiz_score(quiz.correct_answers, quiz.total_answers)

            # Update user and folder stats
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                user.total_quizzes_taken += 1

            folder = db.query(Folder).filter(Folder.id == quiz.folder_id).first()
            if folder:
                folder.total_quizzes += 1

            db.commit()

            return StandardResponse(
                status_code=200,
                is_success=True,
                details="Quiz completed successfully",
                data={
                    "quiz_id": quiz.id,
                    "final_score": quiz.score,
                    "correct_answers": quiz.correct_answers,
                    "total_answered": quiz.total_answers,
                    "status": "completed"
                }
            )

        else:
            raise HTTPException(400, "Quiz cannot be finished")

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(400, f"Error finishing quiz: {str(e)}")


@router.delete("/{quiz_id}", response_model=StandardResponse)
async def abandon_quiz(
    quiz_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Abandon active quiz session"""
    try:
        quiz = db.query(QuizSession).filter(
            QuizSession.id == quiz_id,
            QuizSession.user_id == user_id,
            QuizSession.status == "active"
        ).first()

        if not quiz:
            raise HTTPException(404, "Active quiz session not found")

        quiz.status = "abandoned"
        quiz.completed_at = datetime.utcnow()

        db.commit()

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Quiz abandoned successfully"
        )

    except Exception as e:
        db.rollback()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(400, f"Error abandoning quiz: {str(e)}")


# ================================
# QUIZ HISTORY
# ================================

@router.get("/history", response_model=StandardResponse)
async def get_user_quiz_history(
    limit: int = 20,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Get user's recent quiz history"""
    if limit < 1 or limit > 100:
        raise HTTPException(400, "Limit must be between 1 and 100")

    try:
        quizzes = db.query(QuizSession, Folder).join(
            Folder, QuizSession.folder_id == Folder.id
        ).filter(
            QuizSession.user_id == user_id,
            QuizSession.status == "completed"
        ).order_by(
            QuizSession.completed_at.desc()
        ).limit(limit).all()

        quiz_history = [
            {
                "quiz_id": quiz.QuizSession.id,
                "folder_title": quiz.Folder.title,
                "folder_id": quiz.Folder.id,
                "quiz_type": quiz.QuizSession.quiz_type,
                "score": quiz.QuizSession.score,
                "correct_answers": quiz.QuizSession.correct_answers,
                "total_questions": quiz.QuizSession.total_answers,
                "completed_at": quiz.QuizSession.completed_at
            }
            for quiz in quizzes
        ]

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Quiz history retrieved successfully",
            data={"quiz_history": quiz_history}
        )

    except Exception as e:
        raise HTTPException(400, f"Error getting quiz history: {str(e)}")


@router.get("/{folder_id}/history", response_model=StandardResponse)
async def get_folder_quiz_history(
    folder_id: int,
    limit: int = 10,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """Get quiz history for specific folder"""
    if limit < 1 or limit > 50:
        raise HTTPException(400, "Limit must be between 1 and 50")

    try:
        # Check if user has access to this folder
        folder = db.query(Folder).filter(Folder.id == folder_id).first()
        if not folder:
            raise HTTPException(404, "Folder not found")

        if not check_folder_access(folder, user_id, db):
            raise HTTPException(403, "Not authorized to view this folder")

        # Get quiz history for this folder
        quizzes = db.query(QuizSession).filter(
            QuizSession.user_id == user_id,
            QuizSession.folder_id == folder_id,
            QuizSession.status == "completed"
        ).order_by(
            QuizSession.completed_at.desc()
        ).limit(limit).all()

        quiz_history = [
            {
                "quiz_id": quiz.id,
                "quiz_type": quiz.quiz_type,
                "score": quiz.score,
                "correct_answers": quiz.correct_answers,
                "total_questions": quiz.total_answers,
                "completed_at": quiz.completed_at
            }
            for quiz in quizzes
        ]

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Folder quiz history retrieved successfully",
            data={
                "folder_title": folder.title,
                "quiz_history": quiz_history
            }
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(400, f"Error getting folder quiz history: {str(e)}")