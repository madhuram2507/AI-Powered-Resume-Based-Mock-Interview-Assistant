# app/ai/confidence_analyzer.py
import re

FILLER_WORDS = [
    "um", "uh", "like", "basically", "literally",
    "you know", "kind of", "sort of", "i mean",
    "hmm", "err", "erm", "right", "okay so", "well so"
]


def analyze_confidence(text: str, is_voice: bool = False) -> dict:
    """
    Analyze an answer for confidence indicators.

    is_voice=True  -> filler words heavily penalised (spoken answer via mic)
    is_voice=False -> scored on length, structure, detail (typed answer)

    Returns dict: confidence_score (0-10), filler_count, word_count, note
    """
    if not text or not text.strip():
        return {"confidence_score": 0, "filler_count": 0, "word_count": 0,
                "note": "No answer provided."}

    text_lower = text.lower().strip()
    words      = text_lower.split()
    word_count = len(words)

    # ── Filler detection (word-boundary regex) ──
    filler_count = 0
    for filler in FILLER_WORDS:
        pattern = r'\b' + re.escape(filler) + r'\b'
        filler_count += len(re.findall(pattern, text_lower))

    # ── Sentence analysis ──
    sentences        = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    sentence_count   = max(len(sentences), 1)
    avg_sentence_len = word_count / sentence_count

    # ── Score (start at 10, deduct) ──
    score = 10.0

    if is_voice:
        # Voice: filler words are a real problem
        filler_ratio = filler_count / max(word_count, 1)
        if filler_ratio > 0.15:    score -= 3.5
        elif filler_ratio > 0.08:  score -= 2.0
        elif filler_ratio > 0.03:  score -= 1.0
    else:
        # Typed: small penalty only for excessive fillers
        if filler_count > 8:   score -= 1.0
        elif filler_count > 4: score -= 0.5

    # Length penalty (both modes)
    if word_count < 15:    score -= 4.0
    elif word_count < 30:  score -= 2.5
    elif word_count < 50:  score -= 1.5
    elif word_count < 70:  score -= 0.5

    # Structure bonus
    if sentence_count >= 3 and avg_sentence_len >= 10:
        score += 0.5
    if word_count >= 100:
        score += 0.5

    score = round(max(0.0, min(10.0, score)), 1)

    # ── Feedback note ──
    notes = []
    if is_voice:
        if filler_count > 5:
            notes.append(f"Too many filler words ({filler_count}) — pause instead of saying 'um/uh'.")
        elif filler_count > 2:
            notes.append(f"{filler_count} filler words — minor, keep practising.")

    if word_count < 20:
        notes.append("Answer too short — add examples or more detail.")
    elif word_count < 50:
        notes.append("Could be more detailed — try adding a real example.")
    elif word_count >= 80 and filler_count <= 2:
        notes.append("Well-structured and detailed answer!")

    if not notes:
        notes.append("Good clarity and structure." if not is_voice else "Clear spoken answer.")

    return {
        "confidence_score": score,
        "filler_count":     filler_count,
        "word_count":       word_count,
        "note":             " ".join(notes),
    }


def compute_interview_confidence(questions: list) -> dict:
    """
    Aggregate confidence score across all answered questions.
    questions: list of InterviewQuestion ORM objects
    """
    if not questions:
        return {"confidence_score": 0, "total_fillers": 0, "avg_words": 0}

    answered = [q for q in questions if q.answer_text]
    if not answered:
        return {"confidence_score": 0, "total_fillers": 0, "avg_words": 0}

    total_fillers = sum(q.filler_words or 0 for q in answered)
    total_words   = sum(q.word_count   or 0 for q in answered)
    avg_words     = round(total_words / len(answered), 1)

    filler_ratio = total_fillers / max(total_words, 1)
    confidence   = 10.0

    if filler_ratio > 0.10:    confidence -= 3.0
    elif filler_ratio > 0.05:  confidence -= 1.5

    if avg_words < 20:    confidence -= 3.0
    elif avg_words < 40:  confidence -= 2.0
    elif avg_words < 60:  confidence -= 1.0

    return {
        "confidence_score": round(max(0.0, min(10.0, confidence)), 1),
        "total_fillers":    total_fillers,
        "avg_words":        avg_words,
    }
