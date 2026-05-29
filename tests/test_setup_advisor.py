from __future__ import annotations

import json

from nusapitch import db, setup_advisor


def test_setup_readiness_blocks_without_campaign(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        result = setup_advisor.check_setup_readiness(conn)

    assert not result["ready"]
    assert "Profiles > Campaign is required before operation." in result["blockers"]


def test_setup_readiness_reports_quality_recommendations(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO business_profiles (
                business_name, brand_name, website, company_description, country,
                target_market, value_proposition, credibility_points
            )
            VALUES ('Demo', 'Demo', 'https://demo.example', 'Short', 'ID', 'B2B', 'Short', 'Short')
            """
        )
        conn.execute(
            """
            INSERT INTO sender_profiles (sender_name, sender_position, sender_email, signature, opt_out_line)
            VALUES ('Sender', 'Sales', 'sender@example.test', 'Sender', 'Reply no.')
            """
        )
        conn.execute(
            """
            INSERT INTO product_service_profiles (
                business_profile_id, name, description, ideal_customer, use_cases, proof_points
            )
            VALUES (1, 'Product', 'Short', 'Buyers', 'Use', 'Proof')
            """
        )
        conn.execute(
            """
            INSERT INTO email_accounts (
                account_name, sender_email, password_env_name, smtp_host, smtp_port,
                smtp_security, imap_host, imap_port, imap_security, sent_folder_name, inbox_folder_name
            )
            VALUES (
                'Email', 'sender@example.test', 'NUSAPITCH_EMAIL_SECRET',
                'smtp.example.test', 465, 'SSL', 'imap.example.test', 993, 'SSL', 'Sent', 'INBOX'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO campaigns (
                business_profile_id, sender_profile_id, product_service_profile_id,
                campaign_name, sender_email_daily_limit, sender_domain_daily_limit, campaign_daily_limit
            )
            VALUES (1, 1, 1, 'Campaign', 20, 30, 10)
            """
        )
        conn.commit()

        result = setup_advisor.check_setup_readiness(conn)

    assert result["ready"]
    assert any("add more specific detail" in item for item in result["recommendations"])


def test_setup_readiness_can_use_llm_advisor(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO llm_settings (provider_name, base_url, secret_env_name, model_name)
            VALUES ('Fake', 'https://llm.example/v1', 'NUSAPITCH_TEST_LLM_SECRET', 'demo-model')
            """
        )
        conn.commit()
        monkeypatch.setenv("NUSAPITCH_TEST_LLM_SECRET", "fake-secret")
        monkeypatch.setattr(
            setup_advisor.ai,
            "_chat_completion",
            lambda settings, secret, messages: json.dumps({"recommendations": ["Profiles > Business: add proof points."]}),
        )

        result = setup_advisor.check_setup_readiness(conn, use_llm=True)

    assert result["ai_used"]
    assert result["recommendations"] == ["Profiles > Business: add proof points."]
