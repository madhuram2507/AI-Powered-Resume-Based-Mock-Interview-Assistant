from app.ai.llm_service import generate_interview_questions

qs = generate_interview_questions("Python", "Medium")

for q in qs:
    print("-", q)
