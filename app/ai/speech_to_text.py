# app/ai/speech_to_text.py
# ─────────────────────────────────────────────────────────────
# Upgraded transcription — 4 accuracy improvements:
#   1. Groq Whisper API (large-v3 model, most accurate)
#   2. Fallback to local Whisper "small" model if Groq fails
#   3. Proper webm → wav conversion via ffmpeg
#   4. Language + prompt hints for technical interview context
# ─────────────────────────────────────────────────────────────

import os
import tempfile
import subprocess
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Groq client ───────────────────────────────────────────────
_groq_client = None

def get_groq_client():
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client


# ── Local Whisper fallback ────────────────────────────────────
_local_model = None

def get_local_model():
    global _local_model
    if _local_model is None:
        import whisper
        # "small" is 4x more accurate than "base", still fast on CPU
        # Change to "medium" for even better accuracy (slower)
        logger.info("Loading local Whisper small model...")
        _local_model = whisper.load_model("small")
    return _local_model


# ── Audio conversion: webm/any → wav ─────────────────────────
def convert_to_wav(input_path: str) -> str:
    """
    Convert any audio format to 16kHz mono WAV using ffmpeg.
    Whisper works best with 16kHz mono WAV.
    Returns path to converted wav file.
    """
    output_path = input_path.replace(".webm", ".wav").replace(".mp4", ".wav")
    if not output_path.endswith(".wav"):
        output_path = input_path + ".wav"

    try:
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", input_path,
            "-ar", "16000",      # 16kHz sample rate (Whisper's native)
            "-ac", "1",          # mono channel
            "-c:a", "pcm_s16le", # 16-bit PCM
            output_path
        ], capture_output=True, timeout=30)

        if result.returncode != 0:
            logger.warning(f"ffmpeg conversion failed: {result.stderr.decode()}")
            return input_path  # use original if conversion fails
        return output_path

    except (subprocess.TimeoutExpired, FileNotFoundError):
        # ffmpeg not installed — use original file
        logger.warning("ffmpeg not found, using original audio file")
        return input_path


# ── Main transcription function ───────────────────────────────
def transcribe_audio(file_bytes: bytes, question_context: str = "") -> str:
    """
    Transcribe audio bytes to text with maximum accuracy.

    Priority:
      1. Groq Whisper API (whisper-large-v3) — fastest & most accurate
      2. Local Whisper small model — fallback if Groq fails

    Args:
        file_bytes: Raw audio bytes from browser (webm format)
        question_context: The interview question being answered
                         (helps Whisper understand technical terms)
    """
    if not file_bytes:
        return ""

    # Save raw audio to temp file
    tmp_input = None
    tmp_wav   = None

    try:
        # Write incoming bytes to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as f:
            f.write(file_bytes)
            tmp_input = f.name

        # Convert to clean 16kHz WAV
        tmp_wav = convert_to_wav(tmp_input)

        # ── Try Groq Whisper API first ────────────────────────
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                result = _transcribe_groq(tmp_wav, question_context)
                if result and result.strip():
                    logger.info(f"Groq transcription success: {len(result)} chars")
                    return result.strip()
            except Exception as e:
                logger.warning(f"Groq transcription failed, falling back: {e}")

        # ── Fallback: local Whisper small model ───────────────
        result = _transcribe_local(tmp_wav, question_context)
        return result.strip()

    finally:
        # Clean up temp files
        for path in [tmp_input, tmp_wav]:
            if path and os.path.exists(path) and path != tmp_input:
                try: os.remove(path)
                except: pass
        if tmp_input and os.path.exists(tmp_input):
            try: os.remove(tmp_input)
            except: pass


def _transcribe_groq(audio_path: str, question_context: str = "") -> str:
    """
    Use Groq's Whisper large-v3 API.
    This is the most accurate option — same as OpenAI Whisper large
    but runs on Groq's fast hardware for free.
    """
    client = get_groq_client()

    # Build a prompt to help Whisper understand technical terms
    prompt = "This is a technical job interview answer."
    if question_context:
        prompt += f" The question was: {question_context[:200]}"
    prompt += " The speaker may use technical terms like: API, algorithm, database, React, Python, SQL, machine learning, neural network, OOP, REST, HTTP."

    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-large-v3",   # Most accurate Whisper model
            file=audio_file,
            language="en",              # Force English — no guessing
            prompt=prompt,              # Context hint for accuracy
            response_format="text",
            temperature=0.0,            # 0 = most deterministic/accurate
        )

    # Groq returns string directly with response_format="text"
    return str(response) if response else ""


def _transcribe_local(audio_path: str, question_context: str = "") -> str:
    """
    Use local Whisper small model as fallback.
    More accurate than base, reasonable speed on CPU.
    """
    model = get_local_model()

    prompt = "Technical interview answer about programming, algorithms, databases, or software engineering."
    if question_context:
        prompt += f" Question: {question_context[:150]}"

    result = model.transcribe(
        audio_path,
        language="en",          # Force English
        initial_prompt=prompt,  # Context hint
        temperature=0.0,        # Most accurate
        fp16=False,             # CPU-safe
        verbose=False,
    )

    return result.get("text", "")
