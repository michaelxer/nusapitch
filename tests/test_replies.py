from __future__ import annotations

from dataclasses import dataclass

from nusapitch import db, replies


@dataclass
class FakeInboxMessage:
    sender_email: str
    subject: str
    message_id: str
    in_reply_to: str
    body_preview: str
    received_at: str


def _seed_account_and_history(conn):
    conn.execute(
        """
        INSERT INTO email_accounts (
            account_name, sender_email, password_env_name, imap_host, imap_port, imap_security, inbox_folder_name
        )
        VALUES ('Demo', 'sender@example.test', 'NUSAPITCH_TEST_EMAIL_SECRET', 'imap.example.test', 993, 'SSL', 'INBOX')
        """
    )
    conn.execute(
        """
        INSERT INTO sent_history (
            lead_id, campaign_id, sender_email, recipient_email, subject, body,
            sent_at_utc, smtp_message_id, app_message_id, smtp_result
        )
        VALUES (3, 7, 'sender@example.test', 'buyer@example.test', 'Hello', 'Body',
                '2026-01-01T00:00:00Z', '<sent-id@example.test>', 'app-id', 'ok')
        """
    )
    conn.commit()
    return conn.execute("SELECT * FROM email_accounts").fetchone()


def test_sync_records_reply_and_matches_sent_history(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        account = _seed_account_and_history(conn)
        monkeypatch.setattr(
            replies.email_client,
            "fetch_recent_messages",
            lambda account, limit=50: [
                FakeInboxMessage(
                    "buyer@example.test",
                    "Re: Hello",
                    "<reply-id@example.test>",
                    "<sent-id@example.test>",
                    "Sounds interesting.",
                    "Fri, 01 Jan 2026 01:00:00 +0000",
                )
            ],
        )

        counts = replies.sync_replies_and_bounces(conn, account)
        row = conn.execute("SELECT * FROM reply_history").fetchone()

    assert counts == {"reply": 1, "bounce": 0, "duplicate": 0}
    assert row["lead_id"] == 3
    assert row["campaign_id"] == 7
    assert row["status"] == "reply"


def test_sync_records_bounce_and_suppresses_sender(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        account = _seed_account_and_history(conn)
        monkeypatch.setattr(
            replies.email_client,
            "fetch_recent_messages",
            lambda account, limit=50: [
                FakeInboxMessage(
                    "mailer-daemon@example.test",
                    "Delivery Status Notification Failure",
                    "<bounce-id@example.test>",
                    "",
                    "Could not deliver.",
                    "Fri, 01 Jan 2026 01:00:00 +0000",
                )
            ],
        )

        counts = replies.sync_replies_and_bounces(conn, account)
        suppression_count = conn.execute("SELECT COUNT(*) FROM suppression_list WHERE reason = 'bounce'").fetchone()[0]

    assert counts["bounce"] == 1
    assert suppression_count == 1
