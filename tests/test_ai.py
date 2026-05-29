from __future__ import annotations

import json

from nusapitch import ai, db


VALID_DRAFT = {
    "relevance_score_0_100": 88,
    "recommended_product_or_service": "Demo sourcing support",
    "buyer_type": "Procurement team",
    "email_angle": "Relevant supplier introduction",
    "personalization_reason": "The company imports industrial materials.",
    "risk_notes": "",
    "send_recommendation": "review",
    "subject": "Question for Demo Buyer",
    "email_body": "Hi Team,\n\nI noticed your sourcing work and wanted to ask a quick question.\n\nBest regards,",
}


def test_parse_json_object_handles_markdown_fence():
    parsed = ai._parse_json_object(f"```json\n{json.dumps(VALID_DRAFT)}\n```")

    assert parsed["subject"] == "Question for Demo Buyer"


def test_normalize_draft_rejects_missing_required_fields():
    incomplete = dict(VALID_DRAFT)
    incomplete.pop("email_body")

    try:
        ai._normalize_draft(incomplete)
    except ai.DraftValidationError as exc:
        assert "email_body" in str(exc)
    else:
        raise AssertionError("Expected invalid draft to be rejected")


def test_generate_with_llm_retries_invalid_json(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)
    calls = []

    with db.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO llm_settings (
                provider_name, base_url, secret_env_name, model_name, retry_count
            )
            VALUES ('Fake', 'https://llm.example/v1', 'NUSAPITCH_TEST_LLM_SECRET', 'demo-model', 1)
            """
        )
        conn.execute(
            "INSERT INTO leads (company_name, email, normalized_email, status) VALUES (?, ?, ?, 'new')",
            ("Demo Buyer", "buyer@example.test", "buyer@example.test"),
        )
        conn.commit()
        monkeypatch.setenv("NUSAPITCH_TEST_LLM_SECRET", "fake-secret")

        def fake_chat_completion(settings, secret, messages):
            calls.append(messages)
            if len(calls) == 1:
                return '{"subject": "Missing fields"}'
            return json.dumps(VALID_DRAFT)

        monkeypatch.setattr(ai, "_chat_completion", fake_chat_completion)

        draft_id = ai.generate_email_draft(conn, 1, use_llm=True)
        draft = conn.execute("SELECT subject FROM ai_email_drafts WHERE ai_email_draft_id = ?", (draft_id,)).fetchone()

    assert len(calls) == 2
    assert draft["subject"] == "Question for Demo Buyer"
