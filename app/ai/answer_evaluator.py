from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def evaluate_answer(question: str, answer: str):
    prompt = f"""
You are an interview evaluator.

Question:
{question}

Candidate Answer:
{answer}

Evaluate on a scale of 0 to 10.
Give short constructive feedback.

Return format:
Score: <number>
Feedback: <text>
"""

    res = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=200,
    )

    text = res.choices[0].message.content

    score = int(text.split("Score:")[1].split("\n")[0].strip())
    feedback = text.split("Feedback:")[1].strip()

    return score, feedback
