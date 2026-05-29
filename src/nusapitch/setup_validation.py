from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any

from .imports import is_valid_email, normalize_email


TABLE_LABELS = {
    "business_profiles": "Profiles > Business",
    "product_service_profiles": "Profiles > Product/Service",
    "sender_profiles": "Profiles > Sender",
    "campaigns": "Profiles > Campaign",
    "llm_settings": "Settings > LLM",
    "email_accounts": "Settings > Email",
}

FIELD_LABELS = {
    "business_profile_id": "Business profile",
    "product_service_profile_id": "Product/service",
    "sender_profile_id": "Sender profile",
    "business_name": "Business name",
    "brand_name": "Brand name",
    "website": "Website",
    "company_description": "Company description",
    "country": "Country",
    "target_market": "Target market",
    "value_proposition": "Value proposition",
    "credibility_points": "Credibility points",
    "name": "Name",
    "description": "Description",
    "ideal_customer": "Ideal customer",
    "use_cases": "Use cases",
    "proof_points": "Proof points",
    "sender_name": "Sender name",
    "sender_position": "Sender position",
    "sender_email": "Sender email",
    "signature": "Signature",
    "opt_out_line": "Opt-out line",
    "campaign_name": "Campaign name",
    "sender_email_daily_limit": "Sender email daily limit",
    "sender_domain_daily_limit": "Sender domain daily limit",
    "campaign_daily_limit": "Campaign daily limit",
    "provider_name": "Provider name",
    "base_url": "Base URL",
    "secret_env_name": "Secret environment variable",
    "model_name": "Model name",
    "account_name": "Account name",
    "password_env_name": "Email password environment variable",
    "smtp_host": "SMTP host",
    "smtp_port": "SMTP port",
    "smtp_security": "SMTP security",
    "imap_host": "IMAP host",
    "imap_port": "IMAP port",
    "imap_security": "IMAP security",
    "sent_folder_name": "Sent folder",
    "inbox_folder_name": "Inbox folder",
}

REQUIRED_FIELDS = {
    "business_profiles": [
        "business_name",
        "brand_name",
        "website",
        "company_description",
        "country",
        "target_market",
        "value_proposition",
        "credibility_points",
    ],
    "product_service_profiles": [
        "business_profile_id",
        "name",
        "description",
        "ideal_customer",
        "use_cases",
        "proof_points",
    ],
    "sender_profiles": [
        "sender_name",
        "sender_position",
        "sender_email",
        "signature",
        "opt_out_line",
    ],
    "campaigns": [
        "campaign_name",
        "business_profile_id",
        "sender_profile_id",
        "product_service_profile_id",
        "sender_email_daily_limit",
        "sender_domain_daily_limit",
        "campaign_daily_limit",
    ],
    "llm_settings": ["provider_name", "base_url", "secret_env_name", "model_name"],
    "email_accounts": [
        "account_name",
        "sender_email",
        "password_env_name",
        "smtp_host",
        "smtp_port",
        "smtp_security",
        "imap_host",
        "imap_port",
        "imap_security",
        "sent_folder_name",
        "inbox_folder_name",
    ],
}


def is_required(table: str, field: str) -> bool:
    return field in REQUIRED_FIELDS.get(table, [])


def required_label(table: str, field: str, label: str) -> str:
    return f"{label} *" if is_required(table, field) else label


def validate_record_data(table: str, data: Mapping[str, Any]) -> list[str]:
    problems = [
        _field_problem(table, field)
        for field in REQUIRED_FIELDS.get(table, [])
        if _is_blank(data.get(field))
    ]
    email = data.get("sender_email")
    if table in {"sender_profiles", "email_accounts"} and email and not is_valid_email(email):
        problems.append(f"{TABLE_LABELS[table]} > Sender email must be a real email address.")
    return problems


def validate_setup_for_queue_item(conn: sqlite3.Connection, item: sqlite3.Row) -> list[str]:
    problems: list[str] = []
    if _is_blank(item["sender_email"]):
        problems.append("Review Queue > Sender email for queue is required before sending.")

    campaign = _row_by_id(conn, "campaigns", "campaign_id", item["campaign_id"])
    if campaign is None:
        problems.append("Profiles > Campaign is required. Generate or approve the draft with a campaign selected.")
        return problems
    problems.extend(validate_record_row("campaigns", campaign))

    business = _row_by_id(conn, "business_profiles", "business_profile_id", campaign["business_profile_id"])
    product = _row_by_id(
        conn,
        "product_service_profiles",
        "product_service_profile_id",
        campaign["product_service_profile_id"],
    )
    sender = _row_by_id(conn, "sender_profiles", "sender_profile_id", campaign["sender_profile_id"])
    if business is None:
        problems.append("Profiles > Campaign > Business profile points to a missing business profile.")
    else:
        problems.extend(validate_record_row("business_profiles", business))
    if product is None:
        problems.append("Profiles > Campaign > Product/service points to a missing product/service profile.")
    else:
        problems.extend(validate_record_row("product_service_profiles", product))
    if sender is None:
        problems.append("Profiles > Campaign > Sender profile points to a missing sender profile.")
    else:
        problems.extend(validate_record_row("sender_profiles", sender))
        if normalize_email(item["sender_email"]) != normalize_email(sender["sender_email"]):
            problems.append("Review Queue > Sender email must match Profiles > Sender > Sender email for the selected campaign.")

    account = _active_email_account(conn, item["sender_email"])
    if account is None:
        problems.append("Settings > Email needs an active email account with the same sender email as the queue item.")
    else:
        problems.extend(validate_record_row("email_accounts", account))
    return problems


def validate_record_row(table: str, row: sqlite3.Row) -> list[str]:
    return validate_record_data(table, {key: row[key] for key in row.keys()})


def _field_problem(table: str, field: str) -> str:
    screen = TABLE_LABELS.get(table, table)
    label = FIELD_LABELS.get(field, field.replace("_", " ").title())
    return f"{screen} > {label} is required."


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return value == 0


def _row_by_id(conn: sqlite3.Connection, table: str, id_column: str, row_id: Any) -> sqlite3.Row | None:
    if _is_blank(row_id):
        return None
    return conn.execute(f"SELECT * FROM {table} WHERE {id_column} = ?", (row_id,)).fetchone()


def _active_email_account(conn: sqlite3.Connection, sender_email: str) -> sqlite3.Row | None:
    sender = normalize_email(sender_email)
    if not sender:
        return None
    return conn.execute(
        """
        SELECT * FROM email_accounts
        WHERE is_active = 1 AND lower(sender_email) = ?
        ORDER BY email_account_id DESC
        LIMIT 1
        """,
        (sender,),
    ).fetchone()
