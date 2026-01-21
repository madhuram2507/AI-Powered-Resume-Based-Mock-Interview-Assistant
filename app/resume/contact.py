# app/resume/contact.py
import re
from typing import Optional


EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"

# Matches:
# +91 9876543210
# 9876543210
# +91-9876543210
# 91 9876543210
PHONE_REGEX = r"(\+?\d[\d\s\-]{8,}\d)"


def extract_email(text: str) -> Optional[str]:
    match = re.search(EMAIL_REGEX, text)
    return match.group(0) if match else None


def extract_phone(text: str) -> Optional[str]:
    matches = re.finditer(PHONE_REGEX, text)
    for match in matches:
        raw_phone = match.group(0)

        # Remove spaces, hyphens, etc.
        digits_only = re.sub(r"\D", "", raw_phone)

        # Valid phone number check (India / international)
        if 10 <= len(digits_only) <= 13:
            # Restore + if country code exists
            if raw_phone.strip().startswith("+"):
                return "+" + digits_only
            return digits_only

    return None


def extract_name(text: str) -> Optional[str]:
    """
    Heuristic:
    - Look at top 5–7 lines
    - Ignore lines containing email/phone
    - Pick short capitalized line as name
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    top_lines = lines[:7]

    for line in top_lines:
        if (
            not re.search(EMAIL_REGEX, line)
            and not re.search(PHONE_REGEX, line)
            and 1 < len(line.split()) <= 5
        ):
            return line.title()

    return None
