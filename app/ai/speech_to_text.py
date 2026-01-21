import whisper
import tempfile
import os

_model = None  # lazy-loaded model


def get_model():
    global _model
    if _model is None:
        _model = whisper.load_model("base")
    return _model


def transcribe_audio(file_bytes: bytes) -> str:
    model = get_model()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    result = model.transcribe(tmp_path)
    os.remove(tmp_path)

    return result["text"]
