"""
_profile_store.py — Shared in-memory resume text store
Allows resume_parser tool to access the uploaded resume text without circular imports.
"""
_resume_text: str = ""


def set_resume_text(text: str) -> None:
    global _resume_text
    _resume_text = text


def get_resume_text() -> str:
    return _resume_text
