# app/resume/extractor.py
from pathlib import Path
import pdfplumber
from docx import Document
import tempfile
import os


def extract_text_from_file_bytes(file_bytes: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()

    # IMPORTANT: delete=False for Windows
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(file_bytes)
        tmp.close()  # 🔴 critical on Windows

        if suffix == ".pdf":
            return extract_from_pdf(tmp.name)
        elif suffix == ".docx":
            return extract_from_docx(tmp.name)
        elif suffix == ".txt":
            return Path(tmp.name).read_text(encoding="utf-8", errors="ignore")
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    finally:
        # Clean up temp file manually
        if os.path.exists(tmp.name):
            os.remove(tmp.name)


def extract_from_pdf(path: str) -> str:
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def extract_from_docx(path: str) -> str:
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)
