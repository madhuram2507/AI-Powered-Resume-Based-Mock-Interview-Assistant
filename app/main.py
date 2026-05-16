# app/main.py  v6.0 — Replace your existing main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import json

from app.database import engine, get_db
from app import models
from app.models import User, Skill, UserSkill, ATSScore
from app.auth import hash_password, verify_password, create_access_token, get_current_user
from app.resume.extractor import extract_text_from_file_bytes
from app.resume.skills import extract_skills_from_text, load_master_skills
from app.resume.contact import extract_name, extract_email, extract_phone
from app.ai.ats_analyzer import analyze_resume_ats
from app.interview.routes import router as interview_router

app = FastAPI(title="AI Interview Portal", version="6.0.0")
app.include_router(interview_router)
models.Base.metadata.create_all(bind=engine)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# ── Schemas ───────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

class DirectRegisterRequest(BaseModel):
    email: str
    name: str
    password: str

class GoogleAuthRequest(BaseModel):
    email: str
    name: str
    google_id: str
    picture: Optional[str] = None

class AddSkillsRequest(BaseModel):
    skills: List[str]

class RemoveSkillRequest(BaseModel):
    skill: str

# ── Root ──────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"app": "AI Interview Portal", "status": "running", "version": "6.0.0"}

# ── Auth ──────────────────────────────────────────────────────
@app.post("/auth/register-direct")
def register_direct(payload: DirectRegisterRequest, db=Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(400, "Email already registered.")
    user = User(name=payload.name, email=payload.email, phone=None,
                password_hash=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer",
            "user": {"name": user.name, "email": user.email, "phone": user.phone}}

@app.post("/auth/login")
def login(payload: LoginRequest, db=Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password.")
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer",
            "user": {"name": user.name, "email": user.email, "phone": user.phone}}

@app.post("/auth/google")
def google_auth(payload: GoogleAuthRequest, db=Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        user = User(name=payload.name, email=payload.email, phone=None,
                    password_hash=hash_password(payload.google_id))
        db.add(user); db.commit(); db.refresh(user)
    token = create_access_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer",
            "user": {"name": user.name, "email": user.email, "phone": user.phone}}

@app.get("/auth/me")
def me(current_user: User = Security(get_current_user)):
    return {"id": current_user.id, "name": current_user.name,
            "email": current_user.email, "phone": current_user.phone}

# ── Resume Parse + ATS ────────────────────────────────────────
@app.post("/resume/parse")
async def parse_resume(file: UploadFile = File(...),
                       current_user: User = Security(get_current_user),
                       db=Depends(get_db)):
    allowed = {"application/pdf", "application/msword",
               "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
               "text/plain"}
    if file.content_type not in allowed:
        raise HTTPException(400, "Only PDF, DOCX, TXT allowed.")
    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(400, "File too large. Max 5MB.")
    text = extract_text_from_file_bytes(file_bytes, file.filename)
    if not text.strip():
        raise HTTPException(400, "Could not extract text.")

    name  = extract_name(text)
    email = extract_email(text)
    phone = extract_phone(text)

    extracted_skills = extract_skills_from_text(text, load_master_skills())
    for sn in extracted_skills:
        skill = db.query(Skill).filter(Skill.name == sn).first()
        if not skill:
            skill = Skill(name=sn); db.add(skill); db.flush()
        if not db.query(UserSkill).filter_by(user_id=current_user.id, skill_id=skill.id).first():
            db.add(UserSkill(user_id=current_user.id, skill_id=skill.id, source="resume"))

    # ATS Analysis via Groq
    ats = analyze_resume_ats(text)
    db.add(ATSScore(
        user_id=current_user.id, filename=file.filename,
        ats_score=ats["ats_score"],
        strengths=json.dumps(ats["strengths"]),
        improvements=json.dumps(ats["improvements"]),
        missing_sections=json.dumps(ats["missing_sections"]),
        keywords_found=json.dumps(ats["keywords_found"]),
        resume_text=text[:5000],
    ))
    db.commit()

    return {
        "filename": file.filename,
        "detected_in_resume": {"name": name, "email": email, "phone": phone},
        "extracted_skills":   extracted_skills,
        "total_skills_found": len(extracted_skills),
        "ats_analysis": {
            "ats_score":        ats["ats_score"],
            "summary":          ats.get("summary", ""),
            "strengths":        ats["strengths"],
            "improvements":     ats["improvements"],
            "missing_sections": ats["missing_sections"],
            "keywords_found":   ats["keywords_found"],
        },
    }

@app.get("/resume/ats-history")
def ats_history(current_user: User = Security(get_current_user), db=Depends(get_db)):
    records = db.query(ATSScore).filter(ATSScore.user_id == current_user.id)\
               .order_by(ATSScore.created_at.desc()).limit(5).all()
    return {"history": [{
        "id": r.id, "filename": r.filename, "ats_score": r.ats_score,
        "strengths":        json.loads(r.strengths        or "[]"),
        "improvements":     json.loads(r.improvements     or "[]"),
        "missing_sections": json.loads(r.missing_sections or "[]"),
        "keywords_found":   json.loads(r.keywords_found   or "[]"),
        "created_at":       r.created_at.isoformat(),
    } for r in records]}

# ── Skills ────────────────────────────────────────────────────
@app.get("/skills")
def get_my_skills(current_user: User = Security(get_current_user), db=Depends(get_db)):
    skills = db.query(Skill.name, UserSkill.source).join(UserSkill)\
               .filter(UserSkill.user_id == current_user.id).all()
    return {"email": current_user.email,
            "skills": [{"name": s[0], "source": s[1]} for s in skills]}

@app.post("/skills/add")
def add_skills(payload: AddSkillsRequest,
               current_user: User = Security(get_current_user), db=Depends(get_db)):
    added = []
    for name in payload.skills:
        name = name.strip()
        if not name: continue
        skill = db.query(Skill).filter(Skill.name == name).first()
        if not skill:
            skill = Skill(name=name); db.add(skill); db.flush()
        if not db.query(UserSkill).filter_by(user_id=current_user.id, skill_id=skill.id).first():
            db.add(UserSkill(user_id=current_user.id, skill_id=skill.id, source="manual"))
            added.append(name)
    db.commit()
    return {"message": "Skills added.", "added": added}

@app.delete("/skills/remove")
def remove_skill(payload: RemoveSkillRequest,
                 current_user: User = Security(get_current_user), db=Depends(get_db)):
    skill = db.query(Skill).filter(Skill.name == payload.skill).first()
    if not skill: raise HTTPException(404, "Skill not found.")
    m = db.query(UserSkill).filter_by(user_id=current_user.id, skill_id=skill.id).first()
    if m: db.delete(m); db.commit()
    return {"message": f"'{payload.skill}' removed."}
