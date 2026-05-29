from __future__ import annotations

from nusapitch import db, email_client


def test_email_connection_tests_require_secret_env(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO email_accounts (
                account_name, sender_email, password_env_name, smtp_host, smtp_port,
                smtp_security, imap_host, imap_port, imap_security
            )
            VALUES (
                'Demo', 'sender@example.test', 'NUSAPITCH_MISSING_EMAIL_SECRET',
                'smtp.example.test', 465, 'SSL', 'imap.example.test', 993, 'SSL'
            )
            """
        )
        conn.commit()
        account = conn.execute("SELECT * FROM email_accounts").fetchone()

        smtp_ok, smtp_message = email_client.test_smtp(account)
        imap_ok, imap_message = email_client.test_imap(account)

    assert not smtp_ok
    assert "NUSAPITCH_MISSING_EMAIL_SECRET" in smtp_message
    assert not imap_ok
    assert "NUSAPITCH_MISSING_EMAIL_SECRET" in imap_message


def test_build_message_sets_delivery_headers():
    message = email_client.build_message(
        "sender@example.test",
        "buyer@example.test",
        "Hello",
        "Body",
        bcc="archive@example.test",
    )

    assert message["From"] == "sender@example.test"
    assert message["To"] == "buyer@example.test"
    assert message["Bcc"] == "archive@example.test"
    assert message["Message-ID"]
