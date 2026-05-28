from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

import requests


def generate_email_draft(
    conn: sqlite3.Connection,
    lead_id: int,
    business_profile_id: int | None = None,
    product_service_profile_id: int | None = None,
    campaign_id: int | None = None,
    use_llm: bool = False,
) -> int:
    lead = conn.execute("SELECT * FROM leads WHERE lead_id = ?", (lead_id,)).fetchone()
    if lead is None:
        raise ValueError("Lead not found")
    business = _optional_row(conn, "business_profiles", "business_profile_id", business_profile_id)
    product = _optional_row(conn, "product_service_profiles", "product_service_profile_id", product_service_profile_id)
    research = conn.execute(
        "SELECT * FROM recipient_research WHERE lead_id = ? ORDER BY recipient_research_id DESC LIMIT 1",
        (lead_id,),
    ).fetchone()

    if use_llm:
        draft = _generate_with_llm(conn, lead, business, product, research)
    else:
        draft = _template_draft(lead, business, product, research)

    cur = conn.execute(
        """
        INSERT INTO ai_email_drafts (
            lead_id, business_profile_id, product_service_profile_id, campaign_id,
            relevance_score_0_100, recommended_product_or_service, buyer_type,
            email_angle, personalization_reason, risk_notes, send_recommendation,
            subject, email_body, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead_id,
            business_profile_id,
            product_service_profile_id,
            campaign_id,
            draft["relevance_score_0_100"],
            draft["recommended_product_or_service"],
            draft["buyer_type"],
            draft["email_angle"],
            draft["personalization_reason"],
            draft["risk_notes"],
            draft["send_recommendation"],
            draft["subject"],
            draft["email_body"],
            "draft_created",
        ),
    )
    conn.execute("UPDATE leads SET status = 'draft_created', updated_at = CURRENT_TIMESTAMP WHERE lead_id = ?", (lead_id,))
    conn.commit()
    return int(cur.lastrowid)


def test_llm_connection(conn: sqlite3.Connection) -> tuple[bool, str]:
    settings = conn.execute("SELECT * FROM llm_settings WHERE is_active = 1 ORDER BY llm_settings_id DESC LIMIT 1").fetchone()
    if settings is None:
        return False, "No active LLM settings saved."
    secret = os.getenv(settings["secret_env_name"], "")
    if not secret:
        return False, f"Missing LLM secret environment variable: {settings['secret_env_name']}"
    try:
        _chat_completion(settings, secret, [{"role": "user", "content": "Reply with OK."}])
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return True, "LLM connection succeeded."


def _generate_with_llm(conn: sqlite3.Connection, lead: sqlite3.Row, business: sqlite3.Row | None, product: sqlite3.Row | None, research: sqlite3.Row | None) -> dict[str, Any]:
    settings = conn.execute("SELECT * FROM llm_settings WHERE is_active = 1 ORDER BY llm_settings_id DESC LIMIT 1").fetchone()
    if settings is None:
        return _template_draft(lead, business, product, research)
    secret = os.getenv(settings["secret_env_name"], "")
    if not secret:
        return _template_draft(lead, business, product, research)

    prompt = {
        "lead": dict(lead),
        "business_profile": dict(business) if business else {},
        "product_service_profile": dict(product) if product else {},
        "recipient_research": dict(research) if research else {},
        "rules": [
            "Return JSON only.",
            "Do not invent facts.",
            "Keep email body plain text and 80-140 words.",
            "Use send_recommendation as send, review, or skip.",
        ],
    }
    messages = [
        {"role": "system", "content": "You write safe, factual B2B cold email drafts as JSON."},
        {"role": "user", "content": json.dumps(prompt)},
    ]
    try:
        response_text = _chat_completion(settings, secret, messages)
        parsed = json.loads(response_text)
        return _normalize_draft(parsed)
    except Exception:
        return _template_draft(lead, business, product, research)


def _chat_completion(settings: sqlite3.Row, secret: str, messages: list[dict[str, str]]) -> str:
    base_url = str(settings["base_url"]).rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": settings["model_name"],
        "messages": messages,
        "temperature": float(settings["temperature"]),
        "max_tokens": int(settings["max_tokens"]),
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
        json=payload,
        timeout=int(settings["timeout_seconds"]),
    )
    response.raise_for_status()
    data = response.json()
    return str(data["choices"][0]["message"]["content"])


def _template_draft(lead: sqlite3.Row, business: sqlite3.Row | None, product: sqlite3.Row | None, research: sqlite3.Row | None) -> dict[str, Any]:
    company = lead["company_name"] or "your team"
    product_name = product["name"] if product and product["name"] else "our product or service"
    brand = business["brand_name"] if business and business["brand_name"] else (business["business_name"] if business else "our company")
    proof = product["proof_points"] if product and product["proof_points"] else (business["credibility_points"] if business else "")
    reason = research["company_summary"][:180] if research else (lead["notes"] or "your company may be relevant")
    subject = f"Question for {company}"
    body_lines = [
        "Hi Team,",
        "",
        f"I came across {company} and wanted to ask if this is relevant for your team.",
        "",
        f"{brand} can support B2B buyers with {product_name}. {proof}".strip(),
        "",
        "Would you be the right person to discuss this, or should I contact someone in procurement?",
        "",
        "Best regards,",
    ]
    return {
        "relevance_score_0_100": 50 if research else 30,
        "recommended_product_or_service": product_name,
        "buyer_type": research["likely_buyer_type"] if research else "B2B company",
        "email_angle": "Introductory sourcing question",
        "personalization_reason": reason,
        "risk_notes": "Template draft. Review before sending.",
        "send_recommendation": "review",
        "subject": subject,
        "email_body": "\n".join(body_lines),
    }


def _normalize_draft(parsed: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "relevance_score_0_100": 0,
        "recommended_product_or_service": "",
        "buyer_type": "",
        "email_angle": "",
        "personalization_reason": "",
        "risk_notes": "",
        "send_recommendation": "review",
        "subject": "",
        "email_body": "",
    }
    defaults.update({key: parsed.get(key, value) for key, value in defaults.items()})
    return defaults


def _optional_row(conn: sqlite3.Connection, table: str, id_column: str, record_id: int | None) -> sqlite3.Row | None:
    if not record_id:
        return None
    return conn.execute(f"SELECT * FROM {table} WHERE {id_column} = ?", (record_id,)).fetchone()
