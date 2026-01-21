from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from collections import defaultdict

from app.database import get_db
from app.auth import get_current_user
from app.models import Interview, InterviewQuestion, User
from app.schemas import (
    InterviewGenerateRequest,
    InterviewGenerateResponse,
    InterviewHistoryItem,
)
from app.ai.llm_service import generate_interview_questions
from app.ai.speech_to_text import transcribe_audio
from app.ai.answer_evaluator import evaluate_answer

router = APIRouter(prefix="/interview", tags=["Interview"])


# ==================================================
# GENERATE INTERVIEW (AI + DB)
# ==================================================
@router.post("/generate", response_model=InterviewGenerateResponse)
def generate_interview(
    payload: InterviewGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    questions = generate_interview_questions(
        payload.skill,
        payload.difficulty
    )

    if not questions:
        raise HTTPException(status_code=400, detail="No questions generated")

    interview = Interview(
        user_id=current_user.id,
        skill=payload.skill,
        difficulty=payload.difficulty,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    for q in questions:
        db.add(
            InterviewQuestion(
                interview_id=interview.id,
                question=q
            )
        )

    db.commit()

    return InterviewGenerateResponse(
        interview_id=interview.id,
        skill=payload.skill,
        difficulty=payload.difficulty,
        questions=questions,
    )


# ==================================================
# INTERVIEW HISTORY
# ==================================================
@router.get("/history", response_model=List[InterviewHistoryItem])
def interview_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    interviews = (
        db.query(Interview)
        .filter(Interview.user_id == current_user.id)
        .order_by(Interview.created_at.desc())
        .all()
    )

    return [
        InterviewHistoryItem(
            interview_id=i.id,
            skill=i.skill,
            difficulty=i.difficulty,
            created_at=i.created_at,
            questions=[q.question for q in i.questions],
        )
        for i in interviews
    ]


# ==================================================
# SUBMIT VOICE ANSWER (PHASE-4)
# ==================================================
@router.post("/answer/{question_id}")
def submit_voice_answer(
    question_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    iq = db.query(InterviewQuestion).filter(
        InterviewQuestion.id == question_id
    ).first()

    if not iq:
        raise HTTPException(status_code=404, detail="Question not found")

    audio_bytes = file.file.read()
    answer_text = transcribe_audio(audio_bytes)

    score, feedback = evaluate_answer(
        iq.question,
        answer_text
    )

    iq.answer_text = answer_text
    iq.score = score
    iq.feedback = feedback

    db.commit()

    return {
        "question": iq.question,
        "answer": answer_text,
        "score": score,
        "feedback": feedback,
    }
# ==================================================
# INTERVIEW SUMMARY (PHASE-5A)
# ==================================================
@router.get("/{interview_id}/summary")
def interview_summary(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1️⃣ Fetch interview (ensure ownership)
    interview = (
        db.query(Interview)
        .filter(
            Interview.id == interview_id,
            Interview.user_id == current_user.id
        )
        .first()
    )

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    # 2️⃣ Fetch evaluated questions
    questions = (
        db.query(InterviewQuestion)
        .filter(
            InterviewQuestion.interview_id == interview_id,
            InterviewQuestion.score.isnot(None)
        )
        .all()
    )

    if not questions:
        raise HTTPException(
            status_code=400,
            detail="No evaluated answers found for this interview"
        )

    # 3️⃣ Average score
    scores = [q.score for q in questions]
    average_score = round(sum(scores) / len(scores), 2)

    # 4️⃣ Strengths & weak areas (single-skill interview)
    strengths = []
    weak_areas = []

    if average_score >= 7.5:
        strengths.append(interview.skill)
    elif average_score < 6:
        weak_areas.append(interview.skill)

    # 5️⃣ Hire / No-Hire decision
    decision = "Hire"
    if average_score < 7 or weak_areas:
        decision = "No Hire"

    return {
        "interview_id": interview.id,
        "skill": interview.skill,
        "difficulty": interview.difficulty,
        "questions_attempted": len(scores),
        "average_score": average_score,
        "strengths": strengths,
        "weak_areas": weak_areas,
        "decision": decision,
    }

