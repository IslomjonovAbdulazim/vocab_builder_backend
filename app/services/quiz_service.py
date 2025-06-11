# app/services/quiz_service.py
import random
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.quiz import QuizSession, QuizAnswer
from app.models.folder import Folder, VocabItem
from app.models.user import User
from app.core.utils import check_folder_access, calculate_quiz_score
from typing import Dict, List, Optional


def start_quiz(db: Session, user_id: int, folder_id: int, quiz_type: str = "mixed",
               question_count: int = 10) -> Dict:
    """Start a new quiz session"""
    try:
        folder = db.query(Folder).filter(Folder.id == folder_id).first()

        if not folder:
            return {"success": False, "message": "Folder not found"}

        # Check if user can access this folder
        if not check_folder_access(folder, user_id, db):
            return {"success": False, "message": "Not authorized to quiz this folder"}

        # Check if folder has enough vocabulary
        vocab_count = db.query(VocabItem).filter(VocabItem.folder_id == folder_id).count()

        if vocab_count == 0:
            return {"success": False, "message": "This folder has no vocabulary items"}

        # Limit question count to available vocabulary
        question_count = min(question_count, vocab_count)

        # Create quiz session
        quiz_session = QuizSession(
            user_id=user_id,
            folder_id=folder_id,
            quiz_type=quiz_type,
            question_count=question_count,
            current_question=1
        )

        db.add(quiz_session)
        db.commit()
        db.refresh(quiz_session)

        # Generate first question
        first_question = generate_next_question(db, quiz_session.id)

        return {
            "success": True,
            "message": "Quiz started successfully",
            "quiz_session": quiz_session,
            "question": first_question
        }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error starting quiz: {str(e)}"}


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

    except Exception as e:
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


def submit_answer(db: Session, quiz_session_id: int, user_id: int, answer: str) -> Dict:
    """Submit answer to current quiz question"""
    try:
        quiz = db.query(QuizSession).filter(
            QuizSession.id == quiz_session_id,
            QuizSession.user_id == user_id,
            QuizSession.status == "active"
        ).first()

        if not quiz:
            return {"success": False, "message": "Quiz session not found or not active"}

        # Generate current question
        current_question = generate_next_question(db, quiz_session_id)

        if not current_question:
            return {"success": False, "message": "No more questions available"}

        # Check if answer is correct
        user_answer = answer.lower().strip()
        correct_answer = current_question["correct_answer"]
        is_correct = user_answer == correct_answer

        # Save the answer
        quiz_answer = QuizAnswer(
            quiz_session_id=quiz_session_id,
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

            return {
                "success": True,
                "is_correct": is_correct,
                "correct_answer": correct_answer,
                "quiz_completed": True,
                "final_score": quiz.score,
                "message": "Quiz completed!"
            }

        else:
            # Move to next question
            quiz.current_question += 1
            db.commit()

            # Generate next question
            next_question = generate_next_question(db, quiz_session_id)

            return {
                "success": True,
                "is_correct": is_correct,
                "correct_answer": correct_answer,
                "quiz_completed": False,
                "next_question": next_question,
                "current_question": quiz.current_question,
                "total_questions": quiz.question_count
            }

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error submitting answer: {str(e)}"}


def get_quiz_results(db: Session, quiz_session_id: int, user_id: int) -> Dict:
    """Get quiz results"""
    try:
        quiz = db.query(QuizSession).filter(
            QuizSession.id == quiz_session_id,
            QuizSession.user_id == user_id
        ).first()

        if not quiz:
            return {"success": False, "message": "Quiz session not found"}

        folder = db.query(Folder).filter(Folder.id == quiz.folder_id).first()

        # Get all answers for review
        answers = db.query(QuizAnswer, VocabItem).join(
            VocabItem, QuizAnswer.vocab_item_id == VocabItem.id
        ).filter(
            QuizAnswer.quiz_session_id == quiz_session_id
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

        return {
            "success": True,
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

    except Exception as e:
        return {"success": False, "message": f"Error getting quiz results: {str(e)}"}


def get_user_quiz_history(db: Session, user_id: int, limit: int = 20) -> Dict:
    """Get user's recent quiz history"""
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

        return {
            "success": True,
            "quiz_history": quiz_history,
            "total_count": len(quiz_history)
        }

    except Exception as e:
        return {"success": False, "message": f"Error getting quiz history: {str(e)}"}


def abandon_quiz(db: Session, quiz_session_id: int, user_id: int) -> Dict:
    """Abandon an active quiz session"""
    try:
        quiz = db.query(QuizSession).filter(
            QuizSession.id == quiz_session_id,
            QuizSession.user_id == user_id,
            QuizSession.status == "active"
        ).first()

        if not quiz:
            return {"success": False, "message": "Active quiz session not found"}

        quiz.status = "abandoned"
        quiz.completed_at = datetime.utcnow()

        db.commit()

        return {"success": True, "message": "Quiz abandoned successfully"}

    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"Error abandoning quiz: {str(e)}"}