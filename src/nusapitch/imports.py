from __future__ import annotations

import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

from .paths import DATA_DIR


INTERNAL_FIELDS = [
    "company_name",
    "website",
    "email",
    "linkedin_url",
    "country",
    "phone",
    "industry",
    "contact_page_url",
    "notes",
    "source_url",
    "fit_score",
]

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class ImportResult:
    import_batch_id: int
    total_rows: int
    new_leads: int
    duplicate_leads: int
    invalid_emails: int
    skipped_rows: int


def read_lead_file(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if file_path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(file_path)
    return pd.read_csv(file_path)


def infer_mapping(columns: list[str]) -> dict[str, str]:
    normalized = {col: _simplify(col) for col in columns}
    candidates = {
        "company_name": ["company", "companyname", "name", "business"],
        "website": ["website", "url", "site"],
        "email": ["email", "mail", "recipientemail"],
        "linkedin_url": ["linkedin", "linkedinurl"],
        "country": ["country", "location"],
        "phone": ["phone", "telephone", "whatsapp"],
        "industry": ["industry", "sector"],
        "contact_page_url": ["contact", "contactpage"],
        "notes": ["notes", "note", "evidence", "description"],
        "source_url": ["source", "sourceurl"],
        "fit_score": ["fitscore", "score"],
    }
    mapping: dict[str, str] = {}
    for internal, names in candidates.items():
        for original, simple in normalized.items():
            if simple in names or any(name in simple for name in names):
                mapping[internal] = original
                break
    return mapping


def import_leads(conn: sqlite3.Connection, df: pd.DataFrame, mapping: dict[str, str], filename: str) -> ImportResult:
    total_rows = len(df)
    batch_id = _create_batch(conn, filename, total_rows)
    new_leads = duplicate_leads = invalid_emails = skipped_rows = 0

    for _, row in df.iterrows():
        lead = _mapped_row(row, mapping)
        if not lead["company_name"] or not (lead["email"] or lead["website"] or lead["linkedin_url"]):
            skipped_rows += 1
            continue

        lead["normalized_company_name"] = normalize_company(lead["company_name"])
        lead["normalized_email"] = normalize_email(lead["email"])
        lead["domain"] = normalize_domain(lead["website"] or lead["email"])
        lead["original_fit_score"] = lead.pop("fit_score", "")
        lead["import_batch_id"] = batch_id

        if lead["email"] and not is_valid_email(lead["email"]):
            invalid_emails += 1
            lead["status"] = "needs_manual_review"
        else:
            lead["status"] = "new"

        if _is_duplicate(conn, lead):
            duplicate_leads += 1
            continue

        _insert_lead(conn, lead)
        new_leads += 1

    conn.execute(
        """
        UPDATE import_batches
        SET new_leads = ?, duplicate_leads = ?, invalid_emails = ?, skipped_rows = ?
        WHERE import_batch_id = ?
        """,
        (new_leads, duplicate_leads, invalid_emails, skipped_rows, batch_id),
    )
    conn.commit()
    return ImportResult(batch_id, total_rows, new_leads, duplicate_leads, invalid_emails, skipped_rows)


def save_original_import(uploaded_path: str | Path) -> Path:
    source = Path(uploaded_path)
    target_dir = DATA_DIR / "imports_original"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return target


def normalize_email(value: object) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("mailto:"):
        text = text[7:]
    return text.strip(" <>;,")


def normalize_company(value: object) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_domain(value: object) -> str:
    text = str(value or "").strip().lower()
    if "@" in text and not text.startswith("http"):
        text = text.split("@", 1)[1]
    if text and not text.startswith(("http://", "https://")):
        text = "https://" + text
    parsed = urlparse(text)
    domain = parsed.netloc or parsed.path
    return domain.removeprefix("www.").strip("/")


def is_valid_email(value: object) -> bool:
    email = normalize_email(value)
    if not EMAIL_RE.match(email):
        return False
    placeholders = ("example.com", "youremail.com", "yourdomain.com")
    return not any(email.endswith("@" + domain) for domain in placeholders)


def _simplify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _mapped_row(row: pd.Series, mapping: dict[str, str]) -> dict[str, str]:
    lead: dict[str, str] = {}
    for field in INTERNAL_FIELDS:
        source = mapping.get(field)
        value = "" if not source else row.get(source, "")
        if pd.isna(value):
            value = ""
        lead[field] = str(value).strip()
    return lead


def _create_batch(conn: sqlite3.Connection, filename: str, total_rows: int) -> int:
    cur = conn.execute(
        "INSERT INTO import_batches (filename, total_rows) VALUES (?, ?)",
        (filename, total_rows),
    )
    conn.commit()
    return int(cur.lastrowid)


def _is_duplicate(conn: sqlite3.Connection, lead: dict[str, str]) -> bool:
    checks = [
        ("normalized_email", lead.get("normalized_email", "")),
        ("domain", lead.get("domain", "")),
        ("normalized_company_name", lead.get("normalized_company_name", "")),
        ("linkedin_url", lead.get("linkedin_url", "")),
    ]
    for field, value in checks:
        if not value:
            continue
        found = conn.execute(f"SELECT lead_id FROM leads WHERE {field} = ? LIMIT 1", (value,)).fetchone()
        if found:
            return True
    return False


def _insert_lead(conn: sqlite3.Connection, lead: dict[str, str]) -> int:
    fields = [
        "company_name",
        "normalized_company_name",
        "website",
        "domain",
        "email",
        "normalized_email",
        "linkedin_url",
        "country",
        "phone",
        "industry",
        "contact_page_url",
        "notes",
        "source_url",
        "original_fit_score",
        "status",
        "import_batch_id",
    ]
    values = [lead.get(field, "") for field in fields]
    placeholders = ", ".join("?" for _ in fields)
    cur = conn.execute(f"INSERT INTO leads ({', '.join(fields)}) VALUES ({placeholders})", values)
    conn.commit()
    return int(cur.lastrowid)
