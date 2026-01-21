# app/resume/skills.py
from pathlib import Path
from typing import List, Set


SKILLS_FILE = Path("data/skills_master.txt")


def load_master_skills() -> List[str]:
    if not SKILLS_FILE.exists():
        return []
    skills = []
    for line in SKILLS_FILE.read_text(encoding="utf-8").splitlines():
        skill = line.strip()
        if skill:
            skills.append(skill)
    return skills


def extract_skills_from_text(text: str, master_skills: List[str] | None = None) -> List[str]:
    """
    Basic but clean skill extraction:
    - lowercases resume text
    - matches full skill words/phrases from master list
    - returns unique, sorted skill names
    """
    if master_skills is None:
        master_skills = load_master_skills()

    text_lower = text.lower()
    found: Set[str] = set()

    # To avoid false positives like 'C' matching every 'c' in words,
    # we handle short skills specially
    # For multi-word skills, we do substring match.
    import re

    # Create a set to speed up lookups
    for skill in master_skills:
        if not skill:
            continue

        skill_lower = skill.lower()

        # Very short skills like "C", "R" → use word boundary regex
        if len(skill_lower) <= 2:
            pattern = r"\b" + re.escape(skill_lower) + r"\b"
            if re.search(pattern, text_lower):
                found.add(skill)
        else:
            # Longer skills: simple substring check is usually okay
            if skill_lower in text_lower:
                found.add(skill)

    return sorted(found)
