from pydantic import BaseModel


class InterviewGenerateRequest(BaseModel):
    skill: str
    difficulty: str


class InterviewGenerateResponse(BaseModel):
    interview_id: int
    skill: str
    difficulty: str
    questions: list[str]
