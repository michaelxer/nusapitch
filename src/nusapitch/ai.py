from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

import requests

from . import db


REQUIRED_DRAFT_FIELDS = {
    "relevance_score_0_100",
    "recommended_product_or_service",
    "buyer_type",
    "email_angle",
    "personalization_reason",
    "risk_notes",
    "send_recommendation",
    "subject",
    "email_body",
}

ALLOWED_SEND_RECOMMENDATIONS = {"send", "review", "skip"}


class DraftValidationError(ValueError):
    pass


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


def _generate_with_llm(
    conn: sqlite3.Connection,
    lead: sqlite3.Row,
    business: sqlite3.Row | None,
    product: sqlite3.Row | None,
    research: sqlite3.Row | None,
) -> dict[str, Any]:
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
    max_attempts = max(1, int(settings["retry_count"]) + 1)
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        response_text = ""
        try:
            response_text = _chat_completion(settings, secret, messages)
            parsed = _parse_json_object(response_text)
            return _normalize_draft(parsed)
        except (DraftValidationError, json.JSONDecodeError, KeyError, requests.RequestException, ValueError) as exc:
            last_error = str(exc)
            if attempt == max_attempts:
                break
            messages.append({"role": "assistant", "content": response_text[:2000] if response_text else ""})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Your previous response was invalid: {last_error}. "
                        "Return one JSON object only with all required fields and no markdown."
                    ),
                }
            )

    fallback = _template_draft(lead, business, product, research)
    fallback["risk_notes"] = (
        f"{fallback['risk_notes']} LLM fallback after {max_attempts} attempt(s): {last_error}"
    ).strip()
    db.audit(conn, "llm_fallback", fallback["risk_notes"], "lead", str(lead["lead_id"]))
    return fallback


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
    content = data["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise DraftValidationError("LLM response content was empty")
    return content.strip()


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
    if not isinstance(parsed, dict):
        raise DraftValidationError("LLM draft must be a JSON object")
    missing = sorted(REQUIRED_DRAFT_FIELDS - set(parsed))
    if missing:
        raise DraftValidationError(f"Missing required draft fields: {', '.join(missing)}")

    draft = {}
    try:
        score = int(float(parsed["relevance_score_0_100"]))
    except (TypeError, ValueError) as exc:
        raise DraftValidationError("relevance_score_0_100 must be numeric") from exc
    draft["relevance_score_0_100"] = max(0, min(100, score))

    for key in REQUIRED_DRAFT_FIELDS - {"relevance_score_0_100", "send_recommendation"}:
        value = str(parsed.get(key, "")).strip()
        if key in {"subject", "email_body"} and not value:
            raise DraftValidationError(f"{key} cannot be empty")
        draft[key] = value

    recommendation = str(parsed["send_recommendation"]).strip().lower()
    if recommendation not in ALLOWED_SEND_RECOMMENDATIONS:
        raise DraftValidationError("send_recommendation must be send, review, or skip")
    draft["send_recommendation"] = recommendation
    draft["subject"] = draft["subject"][:180]
    draft["email_body"] = draft["email_body"][:4000]
    return draft


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise DraftValidationError("LLM draft must be a JSON object")
    return parsed


def _optional_row(conn: sqlite3.Connection, table: str, id_column: str, record_id: int | None) -> sqlite3.Row | None:
    if not record_id:
        return None
    return conn.execute(f"SELECT * FROM {table} WHERE {id_column} = ?", (record_id,)).fetchone()
