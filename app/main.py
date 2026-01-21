# app/main.py

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Depends,
    Security
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from app.database import SessionLocal, engine
from app import models
from app.models import User, Skill, UserSkill
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

from app.resume.extractor import extract_text_from_file_bytes
from app.resume.skills import extract_skills_from_text, load_master_skills
from app.resume.contact import extract_name, extract_email, extract_phone
from app.interview.routes import router as interview_router



# -------------------------------------------------
# CREATE APP (MUST BE FIRST)
# -------------------------------------------------
app = FastAPI(
    title="AI Interview Portal Backend",
    version="2.0.0",
    description="Resume Parsing + Auth + Skill Management"
)
app.include_router(interview_router)

# -------------------------------------------------
# DATABASE INIT
# -------------------------------------------------
models.Base.metadata.create_all(bind=engine)

# -------------------------------------------------
# MIDDLEWARE
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# SCHEMAS
# -------------------------------------------------
class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AddSkillsRequest(BaseModel):
    email: str
    skills: List[str]


class RemoveSkillRequest(BaseModel):
    email: str
    skill: str

# -------------------------------------------------
# ROOT
# -------------------------------------------------
@app.get("/")
def root():
    return {"message": "AI Interview Portal Backend is running"}

# -------------------------------------------------
# AUTH ROUTES
# -------------------------------------------------
@app.post("/auth/register")
def register(payload: RegisterRequest):
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            password_hash=hash_password(payload.password)
        )
        db.add(user)
        db.commit()

        return {"message": "User registered successfully"}
    finally:
        db.close()


@app.post("/auth/login")
def login(payload: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload.email).first()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_access_token({"sub": user.email})
        return {
            "access_token": token,
            "token_type": "bearer"
        }
    finally:
        db.close()

# -------------------------------------------------
# RESUME PARSE (PROTECTED)
# -------------------------------------------------
@app.post("/resume/parse")
async def parse_resume(
    file: UploadFile = File(...),
    current_user: User = Security(get_current_user)
):
    file_bytes = await file.read()
    text = extract_text_from_file_bytes(file_bytes, file.filename)

    name = extract_name(text)
    email = extract_email(text)
    phone = extract_phone(text)

    master_skills = load_master_skills()
    extracted_skills = extract_skills_from_text(text, master_skills)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(name=name, email=email, phone=phone)
            db.add(user)
            db.commit()
            db.refresh(user)

        for skill_name in extracted_skills:
            skill = db.query(Skill).filter(Skill.name == skill_name).first()
            if not skill:
                skill = Skill(name=skill_name)
                db.add(skill)
                db.commit()
                db.refresh(skill)

            exists = db.query(UserSkill).filter_by(
                user_id=user.id,
                skill_id=skill.id
            ).first()

            if not exists:
                db.add(UserSkill(
                    user_id=user.id,
                    skill_id=skill.id,
                    source="resume"
                ))

        db.commit()

        return {
            "filename": file.filename,
            "candidate": {
                "name": name,
                "email": email,
                "phone": phone
            },
            "extracted_skills": extracted_skills,
            "total_skills_found": len(extracted_skills)
        }
    finally:
        db.close()

# -------------------------------------------------
# SKILLS APIs (PROTECTED)
# -------------------------------------------------
@app.get("/skills/{email}")
def get_skills(
    email: str,
    current_user: User = Security(get_current_user)
):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        skills = db.query(Skill.name, UserSkill.source)\
            .join(UserSkill)\
            .filter(UserSkill.user_id == user.id)\
            .all()

        return {
            "email": email,
            "skills": [
                {"name": s[0], "source": s[1]} for s in skills
            ]
        }
    finally:
        db.close()


@app.post("/skills/add")
def add_skills(
    payload: AddSkillsRequest,
    current_user: User = Security(get_current_user)
):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        for skill_name in payload.skills:
            skill = db.query(Skill).filter(Skill.name == skill_name).first()
            if not skill:
                skill = Skill(name=skill_name)
                db.add(skill)
                db.commit()
                db.refresh(skill)

            if not db.query(UserSkill).filter_by(
                user_id=user.id,
                skill_id=skill.id
            ).first():
                db.add(UserSkill(
                    user_id=user.id,
                    skill_id=skill.id,
                    source="manual"
                ))

        db.commit()
        return {"message": "Skills added successfully"}
    finally:
        db.close()


@app.delete("/skills/remove")
def remove_skill(
    payload: RemoveSkillRequest,
    current_user: User = Security(get_current_user)
):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == payload.email).first()
        skill = db.query(Skill).filter(Skill.name == payload.skill).first()

        if not user or not skill:
            raise HTTPException(status_code=404, detail="User or skill not found")

        mapping = db.query(UserSkill).filter_by(
            user_id=user.id,
            skill_id=skill.id
        ).first()

        if mapping:
            db.delete(mapping)
            db.commit()

        return {"message": "Skill removed successfully"}
    finally:
        db.close()
