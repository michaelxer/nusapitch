from __future__ import annotations

import sqlite3

from .imports import normalize_domain, normalize_email


def add_suppression(
    conn: sqlite3.Connection,
    email: str = "",
    domain: str = "",
    reason: str = "",
    source: str = "manual",
    notes: str = "",
) -> int:
    clean_email = normalize_email(email)
    clean_domain = normalize_domain(domain or clean_email)
    if not clean_email and not clean_domain:
        raise ValueError("Suppression requires an email or domain")
    cur = conn.execute(
        """
        INSERT INTO suppression_list (email, domain, reason, source, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (clean_email, clean_domain, reason.strip(), source.strip(), notes.strip()),
    )
    conn.commit()
    return int(cur.lastrowid)


def remove_suppression(conn: sqlite3.Connection, suppression_id: int) -> None:
    conn.execute("DELETE FROM suppression_list WHERE suppression_id = ?", (suppression_id,))
    conn.commit()


def list_suppressions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT suppression_id, email, domain, reason, source, notes, created_at
            FROM suppression_list
            ORDER BY suppression_id DESC
            """
        ).fetchall()
    )
