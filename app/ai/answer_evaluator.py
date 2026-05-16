# app/ai/answer_evaluator.py

import os
import re
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def evaluate_answer(question: str, answer: str, skill: str = "", difficulty: str = "medium"):
    """
    Evaluates a candidate's answer using LLaMA via Groq.
    Returns: (score: int, feedback: str, missed_points: list[str])
    """

    prompt = f"""You are a strict but fair technical interview evaluator.

Skill being tested: {skill}
Difficulty: {difficulty}

Question: {question}

Candidate Answer: {answer}

Evaluate the answer carefully. Identify ALL key technical concepts that should be mentioned for a complete answer.

Return your evaluation in EXACTLY this format (no extra text):
Score: <number from 0 to 10>
Feedback: <2-3 sentences: what was good, what was wrong>
Missed: <comma-separated list of key concepts the candidate missed, or "None" if nothing missed>
"""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=300,
    )

    text = res.choices[0].message.content.strip()

    # Parse score
    score = 5  # default
    score_match = re.search(r"Score:\s*(\d+)", text)
    if score_match:
        score = min(10, max(0, int(score_match.group(1))))

    # Parse feedback
    feedback = ""
    feedback_match = re.search(r"Feedback:\s*(.+?)(?=Missed:|$)", text, re.DOTALL)
    if feedback_match:
        feedback = feedback_match.group(1).strip()

    # Parse missed points
    missed_points = []
    missed_match = re.search(r"Missed:\s*(.+)", text, re.DOTALL)
    if missed_match:
        missed_raw = missed_match.group(1).strip()
        if missed_raw.lower() != "none":
            missed_points = [p.strip() for p in missed_raw.split(",") if p.strip()]

    return score, feedback, missed_points


def generate_overall_feedback(skill: str, difficulty: str, qa_pairs: list[dict]) -> str:
    """
    Generates an overall interview performance summary.
    qa_pairs: [{"question": str, "answer": str, "score": int, "feedback": str}, ...]
    """
    summary_lines = []
    for i, qa in enumerate(qa_pairs, 1):
        summary_lines.append(
            f"Q{i}: {qa['question']}\n"
            f"Answer: {qa.get('answer', 'Not answered')}\n"
            f"Score: {qa.get('score', 0)}/10\n"
            f"Feedback: {qa.get('feedback', '')}"
        )

    summary = "\n\n".join(summary_lines)

    prompt = f"""You are a senior technical interviewer reviewing a mock interview session.

Skill: {skill}
Difficulty: {difficulty}

Interview Summary:
{summary}

Write a constructive overall performance review (4-6 sentences) covering:
1. Overall performance level
2. Strongest areas shown
3. Key areas needing improvement
4. One specific study recommendation

Be direct, specific, and encouraging."""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=400,
    )

    return res.choices[0].message.content.strip()