from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from . import ai, setup_validation


QUALITY_MIN_LENGTHS = {
    "company_description": 80,
    "value_proposition": 50,
    "credibility_points": 40,
    "description": 80,
    "ideal_customer": 40,
    "use_cases": 30,
    "proof_points": 40,
    "signature": 20,
}


def check_setup_readiness(conn: sqlite3.Connection, use_llm: bool = False) -> dict[str, Any]:
    summary = collect_setup_summary(conn)
    blockers = setup_blockers(conn, summary)
    warnings = setup_warnings(summary)
    recommendations = setup_recommendations(summary)
    ai_used = False
    ai_error = ""

    if use_llm:
        try:
            ai_recommendations = llm_setup_recommendations(conn, summary, blockers, warnings)
            if ai_recommendations:
                recommendations = ai_recommendations
                ai_used = True
        except Exception as exc:  # noqa: BLE001
            ai_error = str(exc)

    return {
        "ready": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "recommendations": recommendations,
        "summary": summary,
        "ai_used": ai_used,
        "ai_error": ai_error,
    }


def collect_setup_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    campaign = _latest(conn, "campaigns", "campaign_id", "is_active = 1")
    business = product = sender = account = llm = None
    if campaign:
        business = _by_id(conn, "business_profiles", "business_profile_id", campaign["business_profile_id"])
        product = _by_id(
            conn,
            "product_service_profiles",
            "product_service_profile_id",
            campaign["product_service_profile_id"],
        )
        sender = _by_id(conn, "sender_profiles", "sender_profile_id", campaign["sender_profile_id"])
        if sender:
            account = _latest(
                conn,
                "email_accounts",
                "email_account_id",
                "is_active = 1 AND lower(sender_email) = lower(?)",
                (sender["sender_email"],),
            )
    llm = _latest(conn, "llm_settings", "llm_settings_id", "is_active = 1")
    counts = {
        table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in [
            "business_profiles",
            "product_service_profiles",
            "sender_profiles",
            "campaigns",
            "email_accounts",
            "llm_settings",
            "leads",
            "ai_email_drafts",
            "send_queue",
        ]
    }
    return {
        "counts": counts,
        "campaign": _public_row(campaign),
        "business": _public_row(business),
        "product": _public_row(product),
        "sender": _public_row(sender),
        "email_account": _public_row(account, exclude={"password_env_name"}),
        "llm_settings": _public_row(llm, exclude={"secret_env_name"}),
    }


def setup_blockers(conn: sqlite3.Connection, summary: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    campaign = _latest(conn, "campaigns", "campaign_id", "is_active = 1")
    if campaign is None:
        blockers.append("Profiles > Campaign is required before operation.")
        return blockers

    blockers.extend(setup_validation.validate_record_row("campaigns", campaign))
    linked_records = [
        ("business_profiles", "business_profile_id", campaign["business_profile_id"], "Profiles > Campaign > Business profile"),
        (
            "product_service_profiles",
            "product_service_profile_id",
            campaign["product_service_profile_id"],
            "Profiles > Campaign > Product/service",
        ),
        ("sender_profiles", "sender_profile_id", campaign["sender_profile_id"], "Profiles > Campaign > Sender profile"),
    ]
    sender = None
    for table, id_col, record_id, label in linked_records:
        row = _by_id(conn, table, id_col, record_id)
        if row is None:
            blockers.append(f"{label} points to a missing record.")
            continue
        blockers.extend(setup_validation.validate_record_row(table, row))
        if table == "sender_profiles":
            sender = row

    if sender is None:
        blockers.append("Profiles > Sender is required before sending.")
    else:
        account = _latest(
            conn,
            "email_accounts",
            "email_account_id",
            "is_active = 1 AND lower(sender_email) = lower(?)",
            (sender["sender_email"],),
        )
        if account is None:
            blockers.append("Settings > Email needs an active email account matching the selected sender profile.")
        else:
            blockers.extend(setup_validation.validate_record_row("email_accounts", account))
    return list(dict.fromkeys(blockers))


def setup_warnings(summary: dict[str, Any]) -> list[str]:
    warnings = []
    counts = summary["counts"]
    if counts["leads"] == 0:
        warnings.append("Lead Import has no leads yet. Import CSV/XLSX leads before generating drafts.")
    if not summary["llm_settings"]:
        warnings.append("Settings > LLM is not configured. Drafts can still use the template fallback, but AI quality will be limited.")
    return warnings


def setup_recommendations(summary: dict[str, Any]) -> list[str]:
    recommendations = []
    for section, fields in [
        ("business", ["company_description", "value_proposition", "credibility_points"]),
        ("product", ["description", "ideal_customer", "use_cases", "proof_points"]),
        ("sender", ["signature"]),
    ]:
        row = summary.get(section) or {}
        for field in fields:
            value = str(row.get(field, "") or "")
            minimum = QUALITY_MIN_LENGTHS[field]
            if len(value.strip()) < minimum:
                label = setup_validation.FIELD_LABELS[field]
                screen = _section_screen(section)
                recommendations.append(f"{screen} > {label}: add more specific detail to improve email personalization.")
    if summary["counts"]["leads"] > 0 and summary["counts"]["ai_email_drafts"] == 0:
        recommendations.append("Research & Drafts: research a few imported leads before generating drafts for better personalization.")
    if not recommendations:
        recommendations.append("Setup looks ready. Start with a small lead batch, generate drafts, review manually, then use dry-run before real SMTP sending.")
    return recommendations


def llm_setup_recommendations(
    conn: sqlite3.Connection,
    summary: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> list[str]:
    settings = conn.execute("SELECT * FROM llm_settings WHERE is_active = 1 ORDER BY llm_settings_id DESC LIMIT 1").fetchone()
    if settings is None:
        raise ValueError("No active LLM settings saved.")
    secret = os.getenv(settings["secret_env_name"], "")
    if not secret:
        raise ValueError(f"Missing LLM secret environment variable: {settings['secret_env_name']}")
    prompt = {
        "setup_summary": summary,
        "blockers": blockers,
        "warnings": warnings,
        "task": (
            "Review this B2B cold-email app setup. Return JSON only with a recommendations array. "
            "Each recommendation must be specific, actionable, and reference the app area to edit. "
            "Do not invent facts about the company."
        ),
    }
    response = ai._chat_completion(  # noqa: SLF001
        settings,
        secret,
        [
            {"role": "system", "content": "You are a careful setup advisor for a local B2B outreach tool."},
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )
    parsed = ai._parse_json_object(response)  # noqa: SLF001
    recommendations = parsed.get("recommendations", [])
    if not isinstance(recommendations, list):
        raise ValueError("LLM advisor returned invalid recommendations.")
    return [str(item).strip() for item in recommendations if str(item).strip()]


def _latest(
    conn: sqlite3.Connection,
    table: str,
    id_col: str,
    where: str = "1 = 1",
    params: tuple[Any, ...] = (),
) -> sqlite3.Row | None:
    return conn.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY {id_col} DESC LIMIT 1", params).fetchone()


def _by_id(conn: sqlite3.Connection, table: str, id_col: str, record_id: Any) -> sqlite3.Row | None:
    if record_id in (None, "", 0):
        return None
    return conn.execute(f"SELECT * FROM {table} WHERE {id_col} = ?", (record_id,)).fetchone()


def _public_row(row: sqlite3.Row | None, exclude: set[str] | None = None) -> dict[str, Any]:
    if row is None:
        return {}
    excluded = exclude or set()
    return {key: row[key] for key in row.keys() if key not in excluded and not key.endswith("_id")}


def _section_screen(section: str) -> str:
    return {
        "business": "Profiles > Business",
        "product": "Profiles > Product/Service",
        "sender": "Profiles > Sender",
    }.get(section, section)
