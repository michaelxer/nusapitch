from __future__ import annotations

from pathlib import Path


DEFAULT_PRIVATE_KEYWORDS = [
    "smtp_password",
    "email_password",
    "private_key",
    "secret_access_key",
    "sk_live_",
    "sk_test_",
]

IGNORED_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".credentials",
    "private",
    "data",
    "HANDOFF_DOC",
}

IGNORED_FILES = {
    "NusaPitch_full_agent_prompt.md",
    "privacy.py",
}


def scan_text(text: str, keywords: list[str] | None = None) -> list[str]:
    keywords = keywords or DEFAULT_PRIVATE_KEYWORDS
    lowered = text.lower()
    return [keyword for keyword in keywords if keyword in lowered]


def scan_public_files(root: Path) -> dict[str, list[str]]:
    findings: dict[str, list[str]] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in IGNORED_FILES:
            continue
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        matches = scan_text(text)
        if matches:
            findings[str(path.relative_to(root))] = matches
    return findings
