from __future__ import annotations

import sqlite3
from typing import Any


PROFILE_TABLES = {
    "llm_settings": "llm_settings_id",
    "email_accounts": "email_account_id",
    "business_profiles": "business_profile_id",
    "sender_profiles": "sender_profile_id",
    "product_service_profiles": "product_service_profile_id",
    "campaigns": "campaign_id",
}


def _id_column(table: str) -> str:
    if table not in PROFILE_TABLES:
        raise ValueError(f"Unsupported profile table: {table}")
    return PROFILE_TABLES[table]


def list_records(conn: sqlite3.Connection, table: str, include_archived: bool = False) -> list[sqlite3.Row]:
    id_column = _id_column(table)
    where = "" if include_archived or table == "campaigns" else "WHERE is_archived = 0"
    return list(conn.execute(f"SELECT * FROM {table} {where} ORDER BY {id_column} DESC").fetchall())


def get_record(conn: sqlite3.Connection, table: str, record_id: int) -> sqlite3.Row | None:
    id_column = _id_column(table)
    return conn.execute(f"SELECT * FROM {table} WHERE {id_column} = ?", (record_id,)).fetchone()


def create_record(conn: sqlite3.Connection, table: str, data: dict[str, Any]) -> int:
    _id_column(table)
    allowed = _table_columns(conn, table)
    clean = {k: v for k, v in data.items() if k in allowed}
    if not clean:
        raise ValueError("No valid fields supplied")
    fields = ", ".join(clean.keys())
    placeholders = ", ".join("?" for _ in clean)
    cur = conn.execute(
        f"INSERT INTO {table} ({fields}) VALUES ({placeholders})",
        tuple(clean.values()),
    )
    conn.commit()
    return int(cur.lastrowid)


def update_record(conn: sqlite3.Connection, table: str, record_id: int, data: dict[str, Any]) -> None:
    id_column = _id_column(table)
    allowed = _table_columns(conn, table)
    clean = {k: v for k, v in data.items() if k in allowed and k != id_column}
    if not clean:
        return
    assignments = ", ".join(f"{key} = ?" for key in clean)
    conn.execute(
        f"UPDATE {table} SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE {id_column} = ?",
        tuple(clean.values()) + (record_id,),
    )
    conn.commit()


def archive_record(conn: sqlite3.Connection, table: str, record_id: int) -> None:
    id_column = _id_column(table)
    conn.execute(f"UPDATE {table} SET is_archived = 1, updated_at = CURRENT_TIMESTAMP WHERE {id_column} = ?", (record_id,))
    conn.commit()


def duplicate_record(conn: sqlite3.Connection, table: str, record_id: int, suffix: str = " copy") -> int:
    row = get_record(conn, table, record_id)
    if row is None:
        raise ValueError("Record not found")
    id_column = _id_column(table)
    data = {key: row[key] for key in row.keys() if key not in {id_column, "created_at", "updated_at"}}
    for name_field in ("business_name", "sender_name", "name", "campaign_name"):
        if name_field in data and data[name_field]:
            data[name_field] = f"{data[name_field]}{suffix}"
            break
    return create_record(conn, table, data)


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
