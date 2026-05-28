from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .imports import normalize_domain, normalize_email


DEFAULT_TZ = "Asia/Jakarta"


@dataclass
class LimitStatus:
    date_local: str
    timezone: str
    sender_email: str
    sender_domain: str
    campaign_id: int | None
    sent_by_sender: int
    sent_by_domain: int
    sent_by_campaign: int
    sender_limit: int
    domain_limit: int
    campaign_limit: int
    effective_remaining: int


def approve_draft_to_queue(conn: sqlite3.Connection, draft_id: int, sender_email: str) -> int:
    draft = conn.execute("SELECT * FROM ai_email_drafts WHERE ai_email_draft_id = ?", (draft_id,)).fetchone()
    if draft is None:
        raise ValueError("Draft not found")
    lead = conn.execute("SELECT * FROM leads WHERE lead_id = ?", (draft["lead_id"],)).fetchone()
    if lead is None:
        raise ValueError("Lead not found")
    if not lead["normalized_email"]:
        raise ValueError("Lead has no valid recipient email")
    cur = conn.execute(
        """
        INSERT INTO send_queue (
            ai_email_draft_id, lead_id, campaign_id, sender_email,
            recipient_email, subject, body, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'queued')
        """,
        (
            draft_id,
            draft["lead_id"],
            draft["campaign_id"],
            sender_email,
            lead["normalized_email"],
            draft["subject"],
            draft["email_body"],
        ),
    )
    conn.execute("UPDATE ai_email_drafts SET status = 'approved', updated_at = CURRENT_TIMESTAMP WHERE ai_email_draft_id = ?", (draft_id,))
    conn.execute("UPDATE leads SET status = 'queued', updated_at = CURRENT_TIMESTAMP WHERE lead_id = ?", (draft["lead_id"],))
    conn.commit()
    return int(cur.lastrowid)


def get_limit_status(
    conn: sqlite3.Connection,
    sender_email: str,
    campaign_id: int | None,
    timezone: str = DEFAULT_TZ,
    sender_limit: int = 20,
    domain_limit: int = 30,
    campaign_limit: int = 10,
) -> LimitStatus:
    sender = normalize_email(sender_email)
    domain = normalize_domain(sender)
    today = datetime.now(ZoneInfo(timezone)).date().isoformat()
    sent_by_sender = _count_ledger(conn, "sender_email = ?", (today, sender))
    sent_by_domain = _count_ledger(conn, "sender_domain = ?", (today, domain))
    if campaign_id:
        sent_by_campaign = _count_ledger(conn, "campaign_id = ?", (today, campaign_id))
    else:
        sent_by_campaign = 0
    remaining = min(
        sender_limit - sent_by_sender,
        domain_limit - sent_by_domain,
        campaign_limit - sent_by_campaign if campaign_id else campaign_limit,
    )
    return LimitStatus(
        date_local=today,
        timezone=timezone,
        sender_email=sender,
        sender_domain=domain,
        campaign_id=campaign_id,
        sent_by_sender=sent_by_sender,
        sent_by_domain=sent_by_domain,
        sent_by_campaign=sent_by_campaign,
        sender_limit=sender_limit,
        domain_limit=domain_limit,
        campaign_limit=campaign_limit,
        effective_remaining=max(0, remaining),
    )


def safety_check_queue_item(conn: sqlite3.Connection, send_queue_id: int, timezone: str = DEFAULT_TZ) -> tuple[bool, list[str]]:
    item = conn.execute("SELECT * FROM send_queue WHERE send_queue_id = ?", (send_queue_id,)).fetchone()
    if item is None:
        return False, ["Queue item not found"]
    lead = conn.execute("SELECT * FROM leads WHERE lead_id = ?", (item["lead_id"],)).fetchone()
    if lead is None:
        return False, ["Lead not found"]

    problems: list[str] = []
    recipient = normalize_email(item["recipient_email"])
    domain = normalize_domain(recipient)
    if item["status"] != "queued":
        problems.append("Queue item is not queued")
    if not recipient:
        problems.append("Missing recipient email")
    if _is_suppressed(conn, recipient, domain):
        problems.append("Recipient or domain is suppressed")
    if _already_sent(conn, recipient, domain):
        problems.append("Recipient or domain was already contacted")

    limits = get_limit_status(conn, item["sender_email"], item["campaign_id"], timezone)
    if limits.effective_remaining <= 0:
        problems.append("Daily sending limit reached")
    return not problems, problems


def record_dry_run_send(conn: sqlite3.Connection, send_queue_id: int, timezone: str = DEFAULT_TZ) -> None:
    item = conn.execute("SELECT * FROM send_queue WHERE send_queue_id = ?", (send_queue_id,)).fetchone()
    if item is None:
        raise ValueError("Queue item not found")
    now_local = datetime.now(ZoneInfo(timezone))
    now_utc = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    sender = normalize_email(item["sender_email"])
    sender_domain = normalize_domain(sender)
    conn.execute(
        """
        INSERT INTO daily_send_ledger (
            date_local, timezone, sent_at_utc, sent_at_local, sender_email, sender_domain,
            campaign_id, lead_id, recipient_email, subject, status, app_message_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'dry_run', ?)
        """,
        (
            now_local.date().isoformat(),
            timezone,
            now_utc,
            now_local.isoformat(timespec="seconds"),
            sender,
            sender_domain,
            item["campaign_id"],
            item["lead_id"],
            item["recipient_email"],
            item["subject"],
            f"nusapitch-dry-run-{send_queue_id}",
        ),
    )
    conn.execute(
        "UPDATE send_queue SET status = 'sent', sent_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE send_queue_id = ?",
        (send_queue_id,),
    )
    conn.execute("UPDATE leads SET status = 'sent', updated_at = CURRENT_TIMESTAMP WHERE lead_id = ?", (item["lead_id"],))
    conn.commit()


def _count_ledger(conn: sqlite3.Connection, condition: str, params: tuple[object, ...]) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) AS count FROM daily_send_ledger WHERE date_local = ? AND status IN ('sent', 'dry_run') AND {condition}",
        params,
    ).fetchone()
    return int(row["count"] if row else 0)


def _is_suppressed(conn: sqlite3.Connection, email: str, domain: str) -> bool:
    row = conn.execute(
        "SELECT suppression_id FROM suppression_list WHERE email = ? OR domain = ? LIMIT 1",
        (email, domain),
    ).fetchone()
    return row is not None


def _already_sent(conn: sqlite3.Connection, email: str, domain: str) -> bool:
    row = conn.execute(
        """
        SELECT send_ledger_id FROM daily_send_ledger
        WHERE recipient_email = ? OR recipient_email LIKE ?
        LIMIT 1
        """,
        (email, f"%@{domain}"),
    ).fetchone()
    return row is not None
