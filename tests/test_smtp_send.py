from __future__ import annotations

from nusapitch import db
from nusapitch import queue as send_queue


def _seed_queued_email(conn):
    conn.execute(
        """
        INSERT INTO email_accounts (
            account_name, sender_email, password_env_name, smtp_host, smtp_port, smtp_security, is_active
        )
        VALUES ('Demo SMTP', 'sender@example.test', 'NUSAPITCH_TEST_EMAIL_SECRET', 'smtp.example.test', 465, 'SSL', 1)
        """
    )
    conn.execute(
        """
        INSERT INTO leads (company_name, email, normalized_email, domain, status)
        VALUES ('Demo Buyer', 'buyer@example.test', 'buyer@example.test', 'example.test', 'queued')
        """
    )
    conn.execute(
        """
        INSERT INTO ai_email_drafts (lead_id, subject, email_body, status)
        VALUES (1, 'Hello', 'Body', 'approved')
        """
    )
    conn.execute(
        """
        INSERT INTO send_queue (
            ai_email_draft_id, lead_id, sender_email, recipient_email, subject, body, status
        )
        VALUES (1, 1, 'sender@example.test', 'buyer@example.test', 'Hello', 'Body', 'queued')
        """
    )
    conn.commit()


def test_real_send_requires_explicit_confirmation(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        _seed_queued_email(conn)

        ok, problems = send_queue.send_real_email(conn, 1)
        status = conn.execute("SELECT status FROM send_queue WHERE send_queue_id = 1").fetchone()["status"]

    assert not ok
    assert "confirmation" in problems[0]
    assert status == "queued"


def test_real_send_records_ledger_and_history(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        _seed_queued_email(conn)

        def fake_send_smtp(account, message):
            assert account["sender_email"] == "sender@example.test"
            assert message["To"] == "buyer@example.test"
            return "<smtp-id@example.test>", "SMTP send accepted"

        monkeypatch.setattr(send_queue.email_client, "send_smtp", fake_send_smtp)

        ok, messages = send_queue.send_real_email(conn, 1, confirm_real_send=True)

        queue_status = conn.execute("SELECT status FROM send_queue WHERE send_queue_id = 1").fetchone()["status"]
        history_count = conn.execute("SELECT COUNT(*) FROM sent_history").fetchone()[0]
        ledger = conn.execute("SELECT status, smtp_message_id FROM daily_send_ledger").fetchone()

    assert ok
    assert messages == ["SMTP send accepted"]
    assert queue_status == "sent"
    assert history_count == 1
    assert ledger["status"] == "sent"
    assert ledger["smtp_message_id"] == "<smtp-id@example.test>"
