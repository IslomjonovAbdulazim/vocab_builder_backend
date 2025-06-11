# app/api/quiz.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.services import quiz_service
from app.api.users import get_current_user_email

router = APIRouter()


# REQUEST MODELS
class QuizStartRequest(BaseModel):
    quiz_type: str = "mixed"  # mixed, translation, definition
    question_count: int = 10


class QuizAnswerRequest(BaseModel):
    answer: str


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


# QUIZ SESSION ENDPOINTS

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
        raise HTTPException(status_code=400, detail=f"Invalid quiz type. Must be one of: {valid_types}")

    # Validate question count
    if quiz_request.question_count < 1 or quiz_request.question_count > 50:
        raise HTTPException(status_code=400, detail="Question count must be between 1 and 50")

    result = quiz_service.start_quiz(
        db=db,
        user_id=user_id,
        folder_id=folder_id,
        quiz_type=quiz_request.quiz_type,
        question_count=quiz_request.question_count
    )

    if not result["success"]:
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        elif "not authorized" in result["message"].lower():
            raise HTTPException(status_code=403, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    quiz_session = result["quiz_session"]
    question = result["question"]

    return StandardResponse(
        status_code=201,
        is_success=True,
        details=result["message"],
        data={
            "quiz_id": quiz_session.id,
            "folder_id": quiz_session.folder_id,
            "quiz_type": quiz_session.quiz_type,
            "question_count": quiz_session.question_count,
            "current_question": quiz_session.current_question,
            "question": {
                "type": question["type"],
                "text": question["text"],
                "word": question.get("word")
            }
        }
    )


@router.get("/{quiz_id}/question", response_model=StandardResponse)
async def get_current_question(
        quiz_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Get current quiz question"""
    # Check if quiz exists and belongs to user
    from app.models.quiz import QuizSession
    quiz = db.query(QuizSession).filter(
        QuizSession.id == quiz_id,
        QuizSession.user_id == user_id
    ).first()

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz session not found")

    if quiz.status != "active":
        raise HTTPException(status_code=400, detail="Quiz is not active")

    # Generate current question
    question = quiz_service.generate_next_question(db, quiz_id)

    if not question:
        raise HTTPException(status_code=400, detail="No more questions available")

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Current question retrieved",
        data={
            "quiz_id": quiz.id,
            "current_question": quiz.current_question,
            "total_questions": quiz.question_count,
            "question": {
                "type": question["type"],
                "text": question["text"],
                "word": question.get("word")
            }
        }
    )


@router.post("/{quiz_id}/answer", response_model=StandardResponse)
async def submit_quiz_answer(
        quiz_id: int,
        answer_request: QuizAnswerRequest,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Submit answer to current quiz question"""
    if not answer_request.answer or len(answer_request.answer.strip()) == 0:
        raise HTTPException(status_code=400, detail="Answer cannot be empty")

    result = quiz_service.submit_answer(
        db=db,
        quiz_session_id=quiz_id,
        user_id=user_id,
        answer=answer_request.answer
    )

    if not result["success"]:
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    response_data = {
        "is_correct": result["is_correct"],
        "correct_answer": result["correct_answer"],
        "quiz_completed": result["quiz_completed"]
    }

    if result["quiz_completed"]:
        # Quiz is finished
        response_data["final_score"] = result["final_score"]
        response_data["message"] = "Quiz completed successfully!"
    else:
        # More questions available
        response_data["current_question"] = result["current_question"]
        response_data["total_questions"] = result["total_questions"]

        if result["next_question"]:
            response_data["next_question"] = {
                "type": result["next_question"]["type"],
                "text": result["next_question"]["text"],
                "word": result["next_question"].get("word")
            }

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Answer submitted successfully",
        data=response_data
    )


@router.post("/{quiz_id}/finish", response_model=StandardResponse)
async def finish_quiz(
        quiz_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Finish quiz early or get final results"""
    # Check if quiz exists and belongs to user
    from app.models.quiz import QuizSession
    from datetime import datetime

    quiz = db.query(QuizSession).filter(
        QuizSession.id == quiz_id,
        QuizSession.user_id == user_id
    ).first()

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz session not found")

    if quiz.status == "completed":
        # Already completed, just return results
        result = quiz_service.get_quiz_results(db, quiz_id, user_id)

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["message"])

        return StandardResponse(
            status_code=200,
            is_success=True,
            details="Quiz results retrieved",
            data=result
        )

    elif quiz.status == "active":
        # Force complete the quiz
        quiz.status = "completed"
        quiz.completed_at = datetime.utcnow()

        # Calculate score based on answered questions
        from app.core.utils import calculate_quiz_score
        quiz.score = calculate_quiz_score(quiz.correct_answers, quiz.total_answers)

        # Update user and folder stats
        from app.models.user import User
        from app.models.folder import Folder

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
        raise HTTPException(status_code=400, detail="Quiz cannot be finished")


@router.get("/{quiz_id}/results", response_model=StandardResponse)
async def get_quiz_results(
        quiz_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Get detailed quiz results"""
    result = quiz_service.get_quiz_results(db, quiz_id, user_id)

    if not result["success"]:
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Quiz results retrieved successfully",
        data=result
    )


@router.delete("/{quiz_id}", response_model=StandardResponse)
async def abandon_quiz(
        quiz_id: int,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Abandon active quiz session"""
    result = quiz_service.abandon_quiz(db, quiz_id, user_id)

    if not result["success"]:
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])

    return StandardResponse(
        status_code=200,
        is_success=True,
        details=result["message"]
    )


# QUIZ HISTORY ENDPOINTS

@router.get("/history", response_model=StandardResponse)
async def get_user_quiz_history(
        limit: int = 20,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Get user's recent quiz history"""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")

    result = quiz_service.get_user_quiz_history(db, user_id, limit)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return StandardResponse(
        status_code=200,
        is_success=True,
        details="Quiz history retrieved successfully",
        data={
            "quiz_history": result["quiz_history"]
        }
    )


@router.get("/{folder_id}/history", response_model=StandardResponse)
async def get_folder_quiz_history(
        folder_id: int,
        limit: int = 10,
        user_id: int = Depends(get_current_user_id),
        db: Session = Depends(get_db)
):
    """Get quiz history for specific folder"""
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 50")

    # Check if user has access to this folder
    from app.services.folder_service import get_folder_by_id
    from app.core.utils import check_folder_access

    folder = get_folder_by_id(db, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if not check_folder_access(folder, user_id, db):
        raise HTTPException(status_code=403, detail="Not authorized to view this folder")

    # Get quiz history for this folder
    from app.models.quiz import QuizSession

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