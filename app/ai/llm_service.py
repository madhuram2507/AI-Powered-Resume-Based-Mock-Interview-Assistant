import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not found in environment variables")

client = Groq(api_key=GROQ_API_KEY)


def generate_interview_questions(
    skill: str,
    difficulty: str,
    num_questions: int = 5
) -> list[str]:

    prompt = f"""
You are an experienced technical interviewer.

Generate {num_questions} {difficulty}-level interview questions for the skill "{skill}".

Rules:
- Only return questions
- No numbering
- No explanations
- One question per line
"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a professional interviewer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=500
    )

    text = response.choices[0].message.content

    return [
        q.strip("- ").strip()
        for q in text.split("\n")
        if q.strip()
    ]
