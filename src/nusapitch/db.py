from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .paths import default_db_path, ensure_runtime_dirs


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS llm_settings (
        llm_settings_id INTEGER PRIMARY KEY AUTOINCREMENT,
        provider_name TEXT NOT NULL DEFAULT '',
        base_url TEXT NOT NULL DEFAULT '',
        secret_env_name TEXT NOT NULL DEFAULT 'NUSAPITCH_LLM_SECRET',
        model_name TEXT NOT NULL DEFAULT '',
        temperature REAL NOT NULL DEFAULT 0.3,
        max_tokens INTEGER NOT NULL DEFAULT 1200,
        timeout_seconds INTEGER NOT NULL DEFAULT 60,
        retry_count INTEGER NOT NULL DEFAULT 1,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS email_accounts (
        email_account_id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_name TEXT NOT NULL DEFAULT '',
        sender_email TEXT NOT NULL DEFAULT '',
        password_env_name TEXT NOT NULL DEFAULT 'NUSAPITCH_EMAIL_SECRET',
        smtp_host TEXT NOT NULL DEFAULT '',
        smtp_port INTEGER NOT NULL DEFAULT 465,
        smtp_security TEXT NOT NULL DEFAULT 'SSL',
        imap_host TEXT NOT NULL DEFAULT '',
        imap_port INTEGER NOT NULL DEFAULT 993,
        imap_security TEXT NOT NULL DEFAULT 'SSL',
        sent_folder_name TEXT NOT NULL DEFAULT 'Sent',
        inbox_folder_name TEXT NOT NULL DEFAULT 'INBOX',
        enable_save_to_sent INTEGER NOT NULL DEFAULT 1,
        enable_bcc_self_backup INTEGER NOT NULL DEFAULT 0,
        bcc_backup_email TEXT NOT NULL DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS business_profiles (
        business_profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_name TEXT NOT NULL DEFAULT '',
        brand_name TEXT NOT NULL DEFAULT '',
        website TEXT NOT NULL DEFAULT '',
        company_description TEXT NOT NULL DEFAULT '',
        country TEXT NOT NULL DEFAULT '',
        city_region TEXT NOT NULL DEFAULT '',
        business_address TEXT NOT NULL DEFAULT '',
        company_phone TEXT NOT NULL DEFAULT '',
        company_email TEXT NOT NULL DEFAULT '',
        company_linkedin TEXT NOT NULL DEFAULT '',
        business_type TEXT NOT NULL DEFAULT '',
        target_market TEXT NOT NULL DEFAULT '',
        value_proposition TEXT NOT NULL DEFAULT '',
        credibility_points TEXT NOT NULL DEFAULT '',
        private_notes TEXT NOT NULL DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        is_archived INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sender_profiles (
        sender_profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_name TEXT NOT NULL DEFAULT '',
        sender_position TEXT NOT NULL DEFAULT '',
        sender_email TEXT NOT NULL DEFAULT '',
        sender_phone TEXT NOT NULL DEFAULT '',
        sender_linkedin TEXT NOT NULL DEFAULT '',
        signature TEXT NOT NULL DEFAULT '',
        opt_out_line TEXT NOT NULL DEFAULT 'If this is not relevant, reply "no" and I will not follow up.',
        is_active INTEGER NOT NULL DEFAULT 1,
        is_archived INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS product_service_profiles (
        product_service_profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_profile_id INTEGER,
        name TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        ideal_customer TEXT NOT NULL DEFAULT '',
        use_cases TEXT NOT NULL DEFAULT '',
        proof_points TEXT NOT NULL DEFAULT '',
        constraints TEXT NOT NULL DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        is_archived INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (business_profile_id) REFERENCES business_profiles (business_profile_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS campaigns (
        campaign_id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_profile_id INTEGER,
        sender_profile_id INTEGER,
        product_service_profile_id INTEGER,
        campaign_name TEXT NOT NULL DEFAULT '',
        sender_email_daily_limit INTEGER NOT NULL DEFAULT 20,
        sender_domain_daily_limit INTEGER NOT NULL DEFAULT 30,
        campaign_daily_limit INTEGER NOT NULL DEFAULT 10,
        mode TEXT NOT NULL DEFAULT 'review',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS import_batches (
        import_batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
        total_rows INTEGER NOT NULL DEFAULT 0,
        new_leads INTEGER NOT NULL DEFAULT 0,
        duplicate_leads INTEGER NOT NULL DEFAULT 0,
        invalid_emails INTEGER NOT NULL DEFAULT 0,
        skipped_rows INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS leads (
        lead_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL DEFAULT '',
        normalized_company_name TEXT NOT NULL DEFAULT '',
        website TEXT NOT NULL DEFAULT '',
        domain TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '',
        normalized_email TEXT NOT NULL DEFAULT '',
        linkedin_url TEXT NOT NULL DEFAULT '',
        country TEXT NOT NULL DEFAULT '',
        phone TEXT NOT NULL DEFAULT '',
        industry TEXT NOT NULL DEFAULT '',
        contact_page_url TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        source_url TEXT NOT NULL DEFAULT '',
        original_fit_score TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'new',
        import_batch_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (import_batch_id) REFERENCES import_batches (import_batch_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recipient_research (
        recipient_research_id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        company_summary TEXT NOT NULL DEFAULT '',
        industry TEXT NOT NULL DEFAULT '',
        likely_buyer_type TEXT NOT NULL DEFAULT '',
        relevant_use_cases TEXT NOT NULL DEFAULT '',
        evidence_snippets TEXT NOT NULL DEFAULT '',
        contact_route TEXT NOT NULL DEFAULT '',
        confidence_score_0_100 INTEGER NOT NULL DEFAULT 0,
        risk_notes TEXT NOT NULL DEFAULT '',
        research_status TEXT NOT NULL DEFAULT 'pending',
        research_source_urls TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads (lead_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_email_drafts (
        ai_email_draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER NOT NULL,
        business_profile_id INTEGER,
        product_service_profile_id INTEGER,
        campaign_id INTEGER,
        relevance_score_0_100 INTEGER NOT NULL DEFAULT 0,
        recommended_product_or_service TEXT NOT NULL DEFAULT '',
        buyer_type TEXT NOT NULL DEFAULT '',
        email_angle TEXT NOT NULL DEFAULT '',
        personalization_reason TEXT NOT NULL DEFAULT '',
        risk_notes TEXT NOT NULL DEFAULT '',
        send_recommendation TEXT NOT NULL DEFAULT 'review',
        subject TEXT NOT NULL DEFAULT '',
        email_body TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft_created',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lead_id) REFERENCES leads (lead_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS send_queue (
        send_queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
        ai_email_draft_id INTEGER NOT NULL,
        lead_id INTEGER NOT NULL,
        campaign_id INTEGER,
        sender_email TEXT NOT NULL DEFAULT '',
        recipient_email TEXT NOT NULL DEFAULT '',
        subject TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'queued',
        scheduled_at TEXT,
        sent_at TEXT,
        error_message TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ai_email_draft_id) REFERENCES ai_email_drafts (ai_email_draft_id),
        FOREIGN KEY (lead_id) REFERENCES leads (lead_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sent_history (
        sent_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
        send_queue_id INTEGER,
        lead_id INTEGER,
        campaign_id INTEGER,
        sender_email TEXT NOT NULL DEFAULT '',
        recipient_email TEXT NOT NULL DEFAULT '',
        subject TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL DEFAULT '',
        sent_at_utc TEXT NOT NULL DEFAULT '',
        smtp_message_id TEXT NOT NULL DEFAULT '',
        app_message_id TEXT NOT NULL DEFAULT '',
        smtp_result TEXT NOT NULL DEFAULT '',
        imap_save_result TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_send_ledger (
        send_ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_local TEXT NOT NULL,
        timezone TEXT NOT NULL DEFAULT 'Asia/Jakarta',
        sent_at_utc TEXT NOT NULL,
        sent_at_local TEXT NOT NULL,
        sender_email TEXT NOT NULL,
        sender_domain TEXT NOT NULL,
        business_profile_id INTEGER,
        campaign_id INTEGER,
        lead_id INTEGER,
        recipient_email TEXT NOT NULL,
        subject TEXT NOT NULL,
        status TEXT NOT NULL,
        smtp_message_id TEXT NOT NULL DEFAULT '',
        app_message_id TEXT NOT NULL DEFAULT '',
        error_message TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reply_history (
        reply_history_id INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id INTEGER,
        campaign_id INTEGER,
        sender_email TEXT NOT NULL DEFAULT '',
        recipient_email TEXT NOT NULL DEFAULT '',
        subject TEXT NOT NULL DEFAULT '',
        message_id TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT '',
        body_preview TEXT NOT NULL DEFAULT '',
        received_at TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS suppression_list (
        suppression_id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL DEFAULT '',
        domain TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        audit_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        entity_type TEXT NOT NULL DEFAULT '',
        entity_id TEXT NOT NULL DEFAULT '',
        message TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_leads_email ON leads (normalized_email)",
    "CREATE INDEX IF NOT EXISTS idx_leads_domain ON leads (domain)",
    "CREATE INDEX IF NOT EXISTS idx_leads_company ON leads (normalized_company_name)",
    "CREATE INDEX IF NOT EXISTS idx_queue_status ON send_queue (status)",
    "CREATE INDEX IF NOT EXISTS idx_ledger_date_sender ON daily_send_ledger (date_local, sender_email)",
    "CREATE INDEX IF NOT EXISTS idx_suppression_email ON suppression_list (email)",
    "CREATE INDEX IF NOT EXISTS idx_suppression_domain ON suppression_list (domain)",
]


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    ensure_runtime_dirs()
    path = Path(db_path) if db_path else default_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    ensure_runtime_dirs()
    with connect(path) as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)
        conn.commit()
    return path


def fetch_all(conn: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return list(conn.execute(query, tuple(params)).fetchall())


def fetch_one(conn: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
    return conn.execute(query, tuple(params)).fetchone()


def execute(conn: sqlite3.Connection, query: str, params: Iterable[Any] = ()) -> int:
    cur = conn.execute(query, tuple(params))
    conn.commit()
    return int(cur.lastrowid or 0)


def upsert_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
        """,
        (key, value),
    )
    conn.commit()


def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = fetch_one(conn, "SELECT value FROM app_settings WHERE key = ?", (key,))
    return str(row["value"]) if row else default


def audit(conn: sqlite3.Connection, event_type: str, message: str, entity_type: str = "", entity_id: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log (event_type, entity_type, entity_id, message) VALUES (?, ?, ?, ?)",
        (event_type, entity_type, entity_id, message),
    )
    conn.commit()
