from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PRIVATE_DIR = PROJECT_ROOT / "private"
CREDENTIALS_DIR = PROJECT_ROOT / ".credentials"

RUNTIME_DIRS = [
    DATA_DIR,
    DATA_DIR / "backups",
    DATA_DIR / "exports",
    DATA_DIR / "imports_original",
    DATA_DIR / "logs",
    DATA_DIR / "cache",
    DATA_DIR / "temp",
    PRIVATE_DIR,
    CREDENTIALS_DIR,
]


def ensure_runtime_dirs() -> None:
    for folder in RUNTIME_DIRS:
        folder.mkdir(parents=True, exist_ok=True)


def load_local_env() -> None:
    for env_file in [PROJECT_ROOT / ".env", CREDENTIALS_DIR / "llm.env", CREDENTIALS_DIR / "email.env"]:
        load_dotenv(env_file, override=False)


def default_db_path() -> Path:
    return DATA_DIR / "app.db"
