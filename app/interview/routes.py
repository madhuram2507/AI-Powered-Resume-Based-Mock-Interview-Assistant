# app/interview/routes.py  v6.1
from fastapi import APIRouter, Depends, HTTPException, Security, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import json

from app.database import get_db
from app.models import User, Interview, InterviewQuestion, Skill, UserSkill
from app.auth import get_current_user
from app.ai.llm_service import generate_interview_questions
from app.ai.answer_evaluator import evaluate_answer, generate_overall_feedback
from app.ai.speech_to_text import transcribe_audio
from app.ai.confidence_analyzer import analyze_confidence, compute_interview_confidence

router = APIRouter(prefix="/interview", tags=["Interview"])
QUESTIONS_PER_INTERVIEW = 5

# ── Schemas ───────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    skill: Optional[str] = None
    difficulty: str = "medium"
    mode: str = "single"          # single | general | hr

class SubmitAnswerRequest(BaseModel):
    interview_id: int
    question_id: int
    answer_text: str

class BulkAnswer(BaseModel):
    question_id: int
    answer_text: str

class BulkSubmitRequest(BaseModel):
    interview_id: int
    answers: List[BulkAnswer]

# ── HR questions bank ─────────────────────────────────────────
HR_QUESTIONS = [
    "Tell me about yourself and your background.",
    "Where do you see yourself in 5 years?",
    "What is your greatest strength, and how have you used it?",
    "Describe a challenge you faced at work and how you overcame it.",
    "Why do you want to work in this field?",
    "How do you handle working under pressure or tight deadlines?",
    "Tell me about a time you worked in a team and faced a conflict.",
    "What motivates you to do your best work?",
    "How would your previous colleagues or teachers describe you?",
    "Do you have any questions for us?",
]

# ── 1. My Skills ──────────────────────────────────────────────
@router.get("/my-skills")
def get_my_skills(current_user: User = Security(get_current_user), db: Session = Depends(get_db)):
    skills = (db.query(Skill.name, UserSkill.source)
              .join(UserSkill).filter(UserSkill.user_id == current_user.id).all())
    return {"skills": [{"name": s[0], "source": s[1]} for s in skills]}

# ── 2. Generate ───────────────────────────────────────────────
@router.post("/generate")
def generate_interview(payload: GenerateRequest,
                       current_user: User = Security(get_current_user),
                       db: Session = Depends(get_db)):

    if payload.mode == "hr":
        import random
        questions_list  = random.sample(HR_QUESTIONS, QUESTIONS_PER_INTERVIEW)
        interview_skill = "HR / Behavioral"

    elif payload.mode == "general":
        user_skills = (db.query(Skill.name).join(UserSkill)
                       .filter(UserSkill.user_id == current_user.id).all())
        skill_names = [s[0] for s in user_skills]
        if not skill_names:
            raise HTTPException(400, "No skills found. Upload your resume first.")
        questions_list  = _generate_general_questions(skill_names, payload.difficulty)
        interview_skill = "General (" + ", ".join(skill_names[:4]) + ("…" if len(skill_names) > 4 else "") + ")"

    else:
        if not payload.skill:
            raise HTTPException(400, "Skill is required for single-skill mode.")
        try:
            questions_list = generate_interview_questions(
                skill=payload.skill, difficulty=payload.difficulty,
                num_questions=QUESTIONS_PER_INTERVIEW)
        except Exception as e:
            raise HTTPException(500, f"Question generation failed: {e}")
        interview_skill = payload.skill

    if not questions_list:
        raise HTTPException(500, "No questions generated.")

    interview = Interview(user_id=current_user.id, skill=interview_skill,
                          difficulty=payload.difficulty, mode=payload.mode)
    db.add(interview); db.commit(); db.refresh(interview)

    saved = []
    for q_text in questions_list[:QUESTIONS_PER_INTERVIEW]:
        q = InterviewQuestion(interview_id=interview.id, question=q_text)
        db.add(q); db.flush()
        saved.append({"question_id": q.id, "question": q_text})
    db.commit()

    return {"interview_id": interview.id, "skill": interview.skill,
            "difficulty": interview.difficulty, "mode": payload.mode, "questions": saved}


def _generate_general_questions(skills: list, difficulty: str) -> list:
    import os, re
    from groq import Groq
    from dotenv import load_dotenv
    load_dotenv()
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    skills_str = ", ".join(skills)
    prompt = f"""You are an expert technical interviewer.
The candidate has these skills: {skills_str}
Generate exactly {QUESTIONS_PER_INTERVIEW} interview questions covering DIFFERENT skills.
Difficulty: {difficulty}
Return ONLY JSON: {{"questions": ["q1","q2","q3","q4","q5"]}}"""
    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":"Return only valid JSON."},
                  {"role":"user","content":prompt}],
        temperature=0.7, max_tokens=600)
    text = res.choices[0].message.content.strip()
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        return json.loads(m.group()).get("questions", [])
    return [l.strip("- •123456789.)\t ").strip() for l in text.split("\n")
            if len(l.strip()) > 20][:QUESTIONS_PER_INTERVIEW]

# ── 3. Submit text answer ─────────────────────────────────────
@router.post("/answer")
def submit_answer(payload: SubmitAnswerRequest,
                  current_user: User = Security(get_current_user),
                  db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(
        Interview.id == payload.interview_id,
        Interview.user_id == current_user.id).first()
    if not interview: raise HTTPException(404, "Interview not found.")
    q = db.query(InterviewQuestion).filter(
        InterviewQuestion.id == payload.question_id,
        InterviewQuestion.interview_id == payload.interview_id).first()
    if not q: raise HTTPException(404, "Question not found.")

    is_hr = (interview.mode == "hr")
    score, feedback, missed = evaluate_answer(
        question=q.question, answer=payload.answer_text,
        skill=interview.skill, difficulty=interview.difficulty)

    conf = analyze_confidence(payload.answer_text, is_voice=False)

    q.answer_text     = payload.answer_text
    q.score           = score
    q.feedback        = feedback
    q.filler_words    = conf["filler_count"]
    q.word_count      = conf["word_count"]
    q.confidence_note = conf["note"]
    db.commit()

    return {"question_id": q.id, "question": q.question,
            "score": score, "feedback": feedback,
            "missed_key_points": missed,
            "confidence": {"score": conf["confidence_score"],
                           "filler_count": conf["filler_count"],
                           "word_count": conf["word_count"],
                           "note": conf["note"]}}

# ── 4. Voice answer — FIXED: Depends instead of Security ──────
@router.post("/answer/voice")
async def submit_voice_answer(
        interview_id: int,
        question_id: int,
        audio: UploadFile = File(...),
        current_user: User = Depends(get_current_user),   # ← FIX: was Security()
        db: Session = Depends(get_db)):

    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.user_id == current_user.id).first()
    if not interview: raise HTTPException(404, "Interview not found.")
    q = db.query(InterviewQuestion).filter(
        InterviewQuestion.id == question_id,
        InterviewQuestion.interview_id == interview_id).first()
    if not q: raise HTTPException(404, "Question not found.")

    audio_bytes = await audio.read()
    try:
        transcribed = transcribe_audio(audio_bytes, question_context=q.question)
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {e}")
    if not transcribed.strip():
        raise HTTPException(400, "Could not transcribe audio. Speak clearly.")

    score, feedback, missed = evaluate_answer(
        question=q.question, answer=transcribed,
        skill=interview.skill, difficulty=interview.difficulty)

    conf = analyze_confidence(transcribed, is_voice=True)

    q.answer_text     = transcribed
    q.score           = score
    q.feedback        = feedback
    q.filler_words    = conf["filler_count"]
    q.word_count      = conf["word_count"]
    q.confidence_note = conf["note"]
    db.commit()

    return {"question_id": q.id, "question": q.question,
            "transcribed_answer": transcribed,
            "score": score, "feedback": feedback,
            "missed_key_points": missed,
            "confidence": {"score": conf["confidence_score"],
                           "filler_count": conf["filler_count"],
                           "word_count": conf["word_count"],
                           "note": conf["note"]}}

# ── 5. Submit all ─────────────────────────────────────────────
@router.post("/submit-all")
def submit_all_answers(payload: BulkSubmitRequest,
                       current_user: User = Security(get_current_user),
                       db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(
        Interview.id == payload.interview_id,
        Interview.user_id == current_user.id).first()
    if not interview: raise HTTPException(404, "Interview not found.")

    evaluated  = []
    qa_summary = []

    for ans in payload.answers:
        q = db.query(InterviewQuestion).filter(
            InterviewQuestion.id == ans.question_id,
            InterviewQuestion.interview_id == payload.interview_id).first()
        if not q: continue

        try:
            score, feedback, missed = evaluate_answer(
                question=q.question, answer=ans.answer_text,
                skill=interview.skill, difficulty=interview.difficulty)
        except Exception:
            score, feedback, missed = 0, "Evaluation failed.", []

        conf = analyze_confidence(ans.answer_text, is_voice=False)

        q.answer_text     = ans.answer_text
        q.score           = score
        q.feedback        = feedback
        q.filler_words    = conf["filler_count"]
        q.word_count      = conf["word_count"]
        q.confidence_note = conf["note"]

        evaluated.append({"question_id": ans.question_id, "question": q.question,
                          "answer_text": ans.answer_text, "score": score,
                          "feedback": feedback, "missed_key_points": missed,
                          "confidence": {"score": conf["confidence_score"],
                                         "filler_count": conf["filler_count"],
                                         "note": conf["note"]}})
        qa_summary.append({"question": q.question, "answer": ans.answer_text,
                           "score": score, "feedback": feedback})

    db.commit()

    all_qs   = db.query(InterviewQuestion).filter(
        InterviewQuestion.interview_id == payload.interview_id).all()
    scores   = [q.score for q in all_qs if q.score is not None]
    total    = sum(scores)
    max_sc   = len(all_qs) * 10
    pct      = round((total / max_sc) * 100) if max_sc else 0

    conf_agg = compute_interview_confidence(all_qs)
    interview.confidence_score     = conf_agg["confidence_score"]
    interview.filler_word_count    = conf_agg["total_fillers"]
    interview.avg_words_per_answer = conf_agg["avg_words"]

    try:
        overall_fb = generate_overall_feedback(
            skill=interview.skill, difficulty=interview.difficulty, qa_pairs=qa_summary)
    except Exception:
        overall_fb = "Interview complete. Review individual feedback above."
    interview.overall_feedback = overall_fb
    db.commit()

    perf = ("Excellent" if pct >= 80 else "Good" if pct >= 60
            else "Average" if pct >= 40 else "Needs Improvement")

    return {"interview_id": interview.id, "skill": interview.skill,
            "difficulty": interview.difficulty, "mode": interview.mode,
            "evaluated_answers": evaluated,
            "total_score": total, "max_score": max_sc, "percentage": pct,
            "performance": perf, "overall_feedback": overall_fb,
            "confidence_summary": {"score": conf_agg["confidence_score"],
                                   "total_fillers": conf_agg["total_fillers"],
                                   "avg_words_per_answer": conf_agg["avg_words"]}}

# ── 6. Result ─────────────────────────────────────────────────
@router.get("/result/{interview_id}")
def get_result(interview_id: int,
               current_user: User = Security(get_current_user),
               db: Session = Depends(get_db)):
    interview = db.query(Interview).filter(
        Interview.id == interview_id, Interview.user_id == current_user.id).first()
    if not interview: raise HTTPException(404, "Not found.")
    questions = db.query(InterviewQuestion).filter(
        InterviewQuestion.interview_id == interview_id).all()
    scores = [q.score for q in questions if q.score is not None]
    total  = sum(scores); max_sc = len(questions) * 10
    pct    = round((total / max_sc) * 100) if max_sc else 0
    perf   = ("Excellent" if pct >= 80 else "Good" if pct >= 60
              else "Average" if pct >= 40 else "Needs Improvement")
    return {"interview_id": interview.id, "skill": interview.skill,
            "difficulty": interview.difficulty, "mode": interview.mode,
            "created_at": interview.created_at.isoformat(),
            "questions": [{"question_id": q.id, "question": q.question,
                           "answer_text": q.answer_text, "score": q.score,
                           "feedback": q.feedback, "filler_words": q.filler_words,
                           "word_count": q.word_count, "confidence_note": q.confidence_note}
                          for q in questions],
            "total_score": total, "max_score": max_sc, "percentage": pct,
            "performance": perf, "overall_feedback": interview.overall_feedback,
            "confidence_summary": {"score": interview.confidence_score,
                                   "total_fillers": interview.filler_word_count,
                                   "avg_words": interview.avg_words_per_answer}}

# ── 7. Dashboard — FIXED: timeline per interview not per week ─
@router.get("/dashboard")
def dashboard(current_user: User = Security(get_current_user), db: Session = Depends(get_db)):
    interviews = db.query(Interview).filter(
        Interview.user_id == current_user.id).order_by(Interview.created_at.asc()).all()

    history = []
    skill_scores: dict = {}

    for iv in interviews:
        qs  = db.query(InterviewQuestion).filter(InterviewQuestion.interview_id == iv.id).all()
        sc  = [q.score for q in qs if q.score is not None]
        tot = sum(sc); mx = len(qs) * 10
        pct = round((tot / mx) * 100) if mx else 0
        history.append({
            "interview_id": iv.id, "skill": iv.skill,
            "difficulty": iv.difficulty, "mode": iv.mode,
            "created_at": iv.created_at.isoformat(),
            "total_score": tot, "max_score": mx, "percentage": pct,
            "questions_answered": len([q for q in qs if q.answer_text]),
            "total_questions": len(qs),
            "overall_feedback": iv.overall_feedback,
            "confidence_score": iv.confidence_score,
        })
        key = iv.skill
        if key not in skill_scores: skill_scores[key] = []
        if pct: skill_scores[key].append(pct)

    skill_summary = sorted([{
        "skill": k,
        "interviews_taken":      len(v),
        "average_score_percent": round(sum(v)/len(v)) if v else 0,
        "best_score_percent":    max(v) if v else 0,
    } for k, v in skill_scores.items()], key=lambda x: x["average_score_percent"], reverse=True)

    all_pcts = [h["percentage"] for h in history if h["percentage"]]
    overall  = round(sum(all_pcts)/len(all_pcts)) if all_pcts else 0

    # ── FIX: timeline per interview (not per week) ─────────────
    # Each interview is one point on the chart — works even if all
    # interviews are in the same day/week.
    timeline = [
        {
            "avg": h["percentage"],
            "label": f"#{h['interview_id']}",
            "skill": h["skill"],
            "date": h["created_at"][:10],
        }
        for h in history          # history is already sorted oldest→newest
        if h["percentage"] > 0    # skip interviews with 0% (unanswered)
    ]

    return {
        "user":    {"name": current_user.name, "email": current_user.email},
        "stats":   {"total_interviews": len(history),
                    "overall_average_percent": overall,
                    "skills_practiced": len(skill_summary)},
        "skill_summary":     skill_summary,
        "interview_history": list(reversed(history)),  # newest first for UI
        "progress_timeline": timeline,
    }