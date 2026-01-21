from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Text
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


# =========================
# USERS
# =========================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    password_hash = Column(String)

    skills = relationship("UserSkill", back_populates="user")
    interviews = relationship("Interview", back_populates="user")


# =========================
# SKILLS MASTER
# =========================
class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    users = relationship("UserSkill", back_populates="skill")


# =========================
# USER ↔ SKILLS
# =========================
class UserSkill(Base):
    __tablename__ = "user_skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    skill_id = Column(Integer, ForeignKey("skills.id"))
    source = Column(String)  # resume / manual

    user = relationship("User", back_populates="skills")
    skill = relationship("Skill", back_populates="users")


# =========================
# INTERVIEW SESSION
# =========================
class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    skill = Column(String)
    difficulty = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="interviews")
    questions = relationship(
        "InterviewQuestion",
        back_populates="interview",
        cascade="all, delete"
    )


# =========================
# INTERVIEW QUESTIONS (PHASE-4 UPDATED)
# =========================
class InterviewQuestion(Base):
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"))
    question = Column(Text)

    # Phase-4 fields
    answer_text = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    feedback = Column(Text, nullable=True)

    interview = relationship("Interview", back_populates="questions")
