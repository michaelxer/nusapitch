from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

from .paths import DATA_DIR, default_db_path, ensure_runtime_dirs


EXPORTABLE_TABLES = {
    "leads",
    "recipient_research",
    "ai_email_drafts",
    "send_queue",
    "sent_history",
    "daily_send_ledger",
    "reply_history",
    "suppression_list",
    "audit_log",
}


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def create_sqlite_backup(
    source_db_path: str | Path | None = None,
    output_dir: str | Path | None = None,
) -> Path:
    ensure_runtime_dirs()
    source = Path(source_db_path) if source_db_path else default_db_path()
    target_dir = Path(output_dir) if output_dir else DATA_DIR / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"nusapitch-backup-{timestamp_slug()}.db"

    with sqlite3.connect(source) as source_conn, sqlite3.connect(target) as target_conn:
        source_conn.backup(target_conn)
    return target


def export_table_csv(
    conn: sqlite3.Connection,
    table: str,
    output_dir: str | Path | None = None,
) -> Path:
    if table not in EXPORTABLE_TABLES:
        raise ValueError(f"Table is not exportable: {table}")
    ensure_runtime_dirs()
    target_dir = Path(output_dir) if output_dir else DATA_DIR / "exports"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{table}-{timestamp_slug()}.csv"

    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row[column] for column in columns})
    return target


def export_all_csv(conn: sqlite3.Connection, output_dir: str | Path | None = None) -> list[Path]:
    return [export_table_csv(conn, table, output_dir) for table in sorted(EXPORTABLE_TABLES)]
