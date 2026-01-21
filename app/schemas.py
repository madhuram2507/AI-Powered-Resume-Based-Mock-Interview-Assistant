from datetime import datetime
from pydantic import BaseModel


# =========================
# INTERVIEW GENERATION
# =========================
class InterviewGenerateRequest(BaseModel):
    skill: str
    difficulty: str


class InterviewGenerateResponse(BaseModel):
    interview_id: int
    skill: str
    difficulty: str
    questions: list[str]


# =========================
# INTERVIEW HISTORY
# =========================
class InterviewHistoryItem(BaseModel):
    interview_id: int
    skill: str
    difficulty: str
    created_at: datetime
    questions: list[str]
