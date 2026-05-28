from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from nusapitch import db
from nusapitch import queue as send_queue


def test_limit_status_uses_sender_domain_and_campaign(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)
    conn = db.connect(db_path)
    today = datetime.now(ZoneInfo("Asia/Jakarta")).date().isoformat()
    conn.execute(
        """
        INSERT INTO daily_send_ledger (
            date_local, timezone, sent_at_utc, sent_at_local, sender_email,
            sender_domain, campaign_id, recipient_email, subject, status
        )
        VALUES (?, 'Asia/Jakarta', '2026-01-01T00:00:00Z', '2026-01-01T07:00:00', ?, ?, 7, ?, 'Hi', 'sent')
        """,
        (today, "sales@example.com", "example.com", "buyer@example.net"),
    )
    conn.commit()

    limits = send_queue.get_limit_status(
        conn,
        "sales@example.com",
        7,
        sender_limit=2,
        domain_limit=3,
        campaign_limit=4,
    )

    assert limits.sent_by_sender == 1
    assert limits.sent_by_domain == 1
    assert limits.sent_by_campaign == 1
    assert limits.effective_remaining == 1
