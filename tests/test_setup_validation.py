from __future__ import annotations

from nusapitch import db, setup_validation
from nusapitch import queue as send_queue


def test_validate_record_data_lists_required_screen_and_field():
    problems = setup_validation.validate_record_data(
        "business_profiles",
        {"business_name": "", "website": "https://example.test"},
    )

    assert "Profiles > Business > Business name is required." in problems
    assert "Profiles > Business > Company description is required." in problems


def test_required_label_adds_marker_only_for_required_fields():
    assert setup_validation.required_label("business_profiles", "business_name", "Business name") == "Business name *"
    assert setup_validation.required_label("business_profiles", "private_notes", "Private notes") == "Private notes"


def test_safety_check_reports_incomplete_imported_setup(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
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
    assert "Profiles > Campaign is required" in "\n".join(problems)
