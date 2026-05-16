# app/models.py

from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class User(Base):
    __tablename__ = "users"
    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String, nullable=False)
    email         = Column(String, unique=True, index=True, nullable=False)
    phone         = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)
    skills        = relationship("UserSkill", back_populates="user")
    interviews    = relationship("Interview", back_populates="user")
    ats_scores    = relationship("ATSScore",  back_populates="user")


class Skill(Base):
    __tablename__ = "skills"
    id    = Column(Integer, primary_key=True, index=True)
    name  = Column(String, unique=True, index=True)
    users = relationship("UserSkill", back_populates="skill")


class UserSkill(Base):
    __tablename__ = "user_skills"
    id       = Column(Integer, primary_key=True, index=True)
    user_id  = Column(Integer, ForeignKey("users.id"))
    skill_id = Column(Integer, ForeignKey("skills.id"))
    source   = Column(String, default="manual")
    user     = relationship("User",  back_populates="skills")
    skill    = relationship("Skill", back_populates="users")


class Interview(Base):
    __tablename__ = "interviews"
    id                   = Column(Integer, primary_key=True, index=True)
    user_id              = Column(Integer, ForeignKey("users.id"))
    skill                = Column(String)
    difficulty           = Column(String, default="medium")
    mode                 = Column(String, default="single")   # single | general | hr
    overall_feedback     = Column(Text,    nullable=True)
    confidence_score     = Column(Float,   nullable=True)
    filler_word_count    = Column(Integer, nullable=True)
    avg_words_per_answer = Column(Float,   nullable=True)
    created_at           = Column(DateTime, default=datetime.utcnow)
    user      = relationship("User", back_populates="interviews")
    questions = relationship("InterviewQuestion", back_populates="interview")


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    id              = Column(Integer, primary_key=True, index=True)
    interview_id    = Column(Integer, ForeignKey("interviews.id"))
    question        = Column(Text)
    answer_text     = Column(Text,    nullable=True)
    score           = Column(Integer, nullable=True)
    feedback        = Column(Text,    nullable=True)
    filler_words    = Column(Integer, nullable=True, default=0)
    word_count      = Column(Integer, nullable=True, default=0)
    confidence_note = Column(Text,    nullable=True)
    interview       = relationship("Interview", back_populates="questions")


class ATSScore(Base):
    __tablename__ = "ats_scores"
    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id"))
    filename         = Column(String)
    ats_score        = Column(Integer)
    strengths        = Column(Text)        # JSON list
    improvements     = Column(Text)        # JSON list
    missing_sections = Column(Text)        # JSON list
    keywords_found   = Column(Text)        # JSON list
    resume_text      = Column(Text, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)
    user             = relationship("User", back_populates="ats_scores")
