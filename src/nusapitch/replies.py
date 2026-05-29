from __future__ import annotations

import sqlite3

from . import email_client, suppression
from .imports import normalize_domain, normalize_email


BOUNCE_MARKERS = (
    "mailer-daemon",
    "postmaster",
    "delivery status notification",
    "undeliverable",
    "delivery failure",
    "mail delivery failed",
    "returned mail",
)


def sync_replies_and_bounces(conn: sqlite3.Connection, account: sqlite3.Row, limit: int = 50) -> dict[str, int]:
    messages = email_client.fetch_recent_messages(account, limit=limit)
    counts = {"reply": 0, "bounce": 0, "duplicate": 0}
    for message in messages:
        status = classify_message(message.sender_email, message.subject)
        match = _match_sent_history(conn, account["sender_email"], message.sender_email, message.in_reply_to)
        if _already_recorded(conn, message.message_id, message.sender_email, message.subject):
            counts["duplicate"] += 1
            continue
        conn.execute(
            """
            INSERT INTO reply_history (
                lead_id, campaign_id, sender_email, recipient_email, subject,
                message_id, status, body_preview, received_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match["lead_id"] if match else None,
                match["campaign_id"] if match else None,
                normalize_email(account["sender_email"]),
                normalize_email(message.sender_email),
                message.subject,
                message.message_id,
                status,
                message.body_preview,
                message.received_at,
            ),
        )
        if status == "bounce":
            suppression.add_suppression(
                conn,
                email=message.sender_email,
                domain=normalize_domain(message.sender_email),
                reason="bounce",
                source="imap",
                notes=message.subject,
            )
        counts[status] += 1
    conn.commit()
    return counts


def classify_message(sender_email: str, subject: str) -> str:
    haystack = f"{sender_email} {subject}".lower()
    return "bounce" if any(marker in haystack for marker in BOUNCE_MARKERS) else "reply"


def _match_sent_history(
    conn: sqlite3.Connection,
    sender_email: str,
    recipient_email: str,
    in_reply_to: str,
) -> sqlite3.Row | None:
    sender = normalize_email(sender_email)
    recipient = normalize_email(recipient_email)
    if in_reply_to:
        row = conn.execute(
            """
            SELECT * FROM sent_history
            WHERE sender_email = ? AND smtp_message_id = ?
            ORDER BY sent_history_id DESC
            LIMIT 1
            """,
            (sender, in_reply_to),
        ).fetchone()
        if row:
            return row
    return conn.execute(
        """
        SELECT * FROM sent_history
        WHERE sender_email = ? AND recipient_email = ?
        ORDER BY sent_history_id DESC
        LIMIT 1
        """,
        (sender, recipient),
    ).fetchone()


def _already_recorded(conn: sqlite3.Connection, message_id: str, sender_email: str, subject: str) -> bool:
    if message_id:
        row = conn.execute("SELECT reply_history_id FROM reply_history WHERE message_id = ? LIMIT 1", (message_id,)).fetchone()
        if row:
            return True
    row = conn.execute(
        """
        SELECT reply_history_id FROM reply_history
        WHERE recipient_email = ? AND subject = ?
        LIMIT 1
        """,
        (normalize_email(sender_email), subject),
    ).fetchone()
    return row is not None
