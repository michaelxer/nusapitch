from __future__ import annotations

from nusapitch import db, suppression
from nusapitch import queue as send_queue


def test_add_suppression_normalizes_email_and_domain(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        suppression_id = suppression.add_suppression(
            conn,
            email=" Buyer@Example.Test ",
            reason="opt-out",
            source="manual",
        )
        row = conn.execute("SELECT * FROM suppression_list WHERE suppression_id = ?", (suppression_id,)).fetchone()

    assert row["email"] == "buyer@example.test"
    assert row["domain"] == "example.test"


def test_suppression_blocks_queue_safety_check(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        suppression.add_suppression(conn, domain="example.test", reason="manual block")
        conn.execute(
            "INSERT INTO leads (company_name, email, normalized_email, domain, status) VALUES (?, ?, ?, ?, 'queued')",
            ("Demo Buyer", "buyer@example.test", "buyer@example.test", "example.test"),
        )
        conn.execute("INSERT INTO ai_email_drafts (lead_id, subject, email_body, status) VALUES (1, 'Hi', 'Body', 'approved')")
        conn.execute(
            """
            INSERT INTO send_queue (
                ai_email_draft_id, lead_id, sender_email, recipient_email, subject, body, status
            )
            VALUES (1, 1, 'sender@example.test', 'buyer@example.test', 'Hi', 'Body', 'queued')
            """
        )
        conn.commit()

        ok, problems = send_queue.safety_check_queue_item(conn, 1)

    assert not ok
    assert "suppressed" in "\n".join(problems)
