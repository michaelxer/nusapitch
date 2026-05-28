from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nusapitch import ai, db, imports, privacy, profiles, research  # noqa: E402
from nusapitch import queue as send_queue  # noqa: E402
from nusapitch.paths import DATA_DIR, default_db_path, ensure_runtime_dirs  # noqa: E402


st.set_page_config(page_title="NusaPitch", page_icon=None, layout="wide")

ensure_runtime_dirs()
DB_PATH = db.init_db()


def connection():
    return db.connect(DB_PATH)


def main() -> None:
    st.title("NusaPitch")
    st.caption("Local AI cold email writer and sender")

    page = st.sidebar.radio(
        "Workspace",
        [
            "Dashboard",
            "Profiles",
            "Settings",
            "Lead Import",
            "Research & Drafts",
            "Review Queue",
            "Diagnostics",
        ],
    )

    with connection() as conn:
        if page == "Dashboard":
            dashboard(conn)
        elif page == "Profiles":
            profile_page(conn)
        elif page == "Settings":
            settings_page(conn)
        elif page == "Lead Import":
            lead_import_page(conn)
        elif page == "Research & Drafts":
            research_drafts_page(conn)
        elif page == "Review Queue":
            review_queue_page(conn)
        else:
            diagnostics_page(conn)


def dashboard(conn) -> None:
    counts = {
        "Total leads": scalar(conn, "SELECT COUNT(*) FROM leads"),
        "Researched": scalar(conn, "SELECT COUNT(*) FROM leads WHERE status = 'researched'"),
        "Drafts": scalar(conn, "SELECT COUNT(*) FROM ai_email_drafts"),
        "Queued": scalar(conn, "SELECT COUNT(*) FROM send_queue WHERE status = 'queued'"),
        "Sent today": scalar(conn, "SELECT COUNT(*) FROM daily_send_ledger WHERE date_local = date('now')"),
        "Suppressed": scalar(conn, "SELECT COUNT(*) FROM suppression_list"),
    }
    cols = st.columns(6)
    for col, (label, value) in zip(cols, counts.items()):
        col.metric(label, value)

    st.subheader("Operational Warnings")
    warnings = []
    if scalar(conn, "SELECT COUNT(*) FROM llm_settings WHERE is_active = 1") == 0:
        warnings.append("No active LLM settings saved.")
    if scalar(conn, "SELECT COUNT(*) FROM email_accounts WHERE is_active = 1") == 0:
        warnings.append("No active email account saved.")
    if scalar(conn, "SELECT COUNT(*) FROM campaigns WHERE is_active = 1") == 0:
        warnings.append("No active campaign saved.")
    if warnings:
        for warning in warnings:
            st.warning(warning)
    else:
        st.success("Core setup records exist.")

    st.subheader("Recent Leads")
    show_query(conn, "SELECT lead_id, company_name, email, website, status, created_at FROM leads ORDER BY lead_id DESC LIMIT 20")


def profile_page(conn) -> None:
    tabs = st.tabs(["Business", "Product/Service", "Sender", "Campaign"])
    with tabs[0]:
        st.subheader("Business Profiles")
        with st.form("business_form"):
            data = {
                "business_name": st.text_input("Business name"),
                "brand_name": st.text_input("Brand name"),
                "website": st.text_input("Website"),
                "company_description": st.text_area("Company description"),
                "country": st.text_input("Country"),
                "city_region": st.text_input("City/region"),
                "business_address": st.text_input("Business address"),
                "company_phone": st.text_input("Company phone"),
                "company_email": st.text_input("Company email"),
                "company_linkedin": st.text_input("Company LinkedIn"),
                "business_type": st.text_input("Business type"),
                "target_market": st.text_input("Target market"),
                "value_proposition": st.text_area("Value proposition"),
                "credibility_points": st.text_area("Credibility points"),
                "private_notes": st.text_area("Private notes"),
            }
            if st.form_submit_button("Save business profile"):
                profiles.create_record(conn, "business_profiles", data)
                st.success("Business profile saved.")
        show_records(conn, "business_profiles")

    with tabs[1]:
        st.subheader("Product/Service Profiles")
        business_options = id_options(conn, "business_profiles", "business_profile_id", "business_name")
        with st.form("product_form"):
            data = {
                "business_profile_id": st.selectbox("Business profile", options=list(business_options.keys()), format_func=business_options.get) if business_options else None,
                "name": st.text_input("Name"),
                "category": st.text_input("Category"),
                "description": st.text_area("Description"),
                "ideal_customer": st.text_area("Ideal customer"),
                "use_cases": st.text_area("Use cases"),
                "proof_points": st.text_area("Proof points"),
                "constraints": st.text_area("Constraints"),
            }
            if st.form_submit_button("Save product/service"):
                profiles.create_record(conn, "product_service_profiles", data)
                st.success("Product/service profile saved.")
        show_records(conn, "product_service_profiles")

    with tabs[2]:
        st.subheader("Sender Profiles")
        with st.form("sender_form"):
            data = {
                "sender_name": st.text_input("Sender name"),
                "sender_position": st.text_input("Sender position"),
                "sender_email": st.text_input("Sender email"),
                "sender_phone": st.text_input("Sender phone"),
                "sender_linkedin": st.text_input("Sender LinkedIn"),
                "signature": st.text_area("Signature"),
                "opt_out_line": st.text_input("Opt-out line", value='If this is not relevant, reply "no" and I will not follow up.'),
            }
            if st.form_submit_button("Save sender profile"):
                profiles.create_record(conn, "sender_profiles", data)
                st.success("Sender profile saved.")
        show_records(conn, "sender_profiles")

    with tabs[3]:
        st.subheader("Campaigns")
        business_options = id_options(conn, "business_profiles", "business_profile_id", "business_name")
        sender_options = id_options(conn, "sender_profiles", "sender_profile_id", "sender_email")
        product_options = id_options(conn, "product_service_profiles", "product_service_profile_id", "name")
        with st.form("campaign_form"):
            data = {
                "campaign_name": st.text_input("Campaign name"),
                "business_profile_id": select_or_none("Business profile", business_options),
                "sender_profile_id": select_or_none("Sender profile", sender_options),
                "product_service_profile_id": select_or_none("Product/service", product_options),
                "sender_email_daily_limit": st.number_input("Sender email daily limit", min_value=1, value=20),
                "sender_domain_daily_limit": st.number_input("Sender domain daily limit", min_value=1, value=30),
                "campaign_daily_limit": st.number_input("Campaign daily limit", min_value=1, value=10),
                "mode": st.selectbox("Mode", ["review", "draft-only", "auto-send"]),
            }
            if st.form_submit_button("Save campaign"):
                profiles.create_record(conn, "campaigns", data)
                st.success("Campaign saved.")
        show_records(conn, "campaigns")


def settings_page(conn) -> None:
    tabs = st.tabs(["LLM", "Email"])
    with tabs[0]:
        st.subheader("OpenAI-Compatible LLM")
        st.info("Store the real LLM secret in an environment variable or `.credentials/llm.env`, not in this database form.")
        with st.form("llm_form"):
            data = {
                "provider_name": st.text_input("Provider name", value="OpenAI-compatible"),
                "base_url": st.text_input("Base URL", value="https://api.example.com/v1"),
                "secret_env_name": st.text_input("LLM secret env var", value="NUSAPITCH_LLM_SECRET"),
                "model_name": st.text_input("Model name"),
                "temperature": st.slider("Temperature", 0.0, 1.0, 0.3, 0.1),
                "max_tokens": st.number_input("Max tokens", min_value=100, value=1200),
                "timeout_seconds": st.number_input("Timeout seconds", min_value=5, value=60),
                "retry_count": st.number_input("Retry count", min_value=0, value=1),
            }
            if st.form_submit_button("Save LLM settings"):
                profiles.create_record(conn, "llm_settings", data)
                st.success("LLM settings saved.")
        if st.button("Test LLM connection"):
            ok, message = ai.test_llm_connection(conn)
            st.success(message) if ok else st.error(message)
        show_query(conn, "SELECT llm_settings_id, provider_name, base_url, secret_env_name, model_name, is_active FROM llm_settings ORDER BY llm_settings_id DESC")

    with tabs[1]:
        st.subheader("SMTP/IMAP Email Account")
        st.info("Store the real email password in an environment variable or `.credentials/email.env`, not in this database form.")
        with st.form("email_form"):
            data = {
                "account_name": st.text_input("Account name"),
                "sender_email": st.text_input("Sender email"),
                "password_env_name": st.text_input("Email secret env var", value="NUSAPITCH_EMAIL_SECRET"),
                "smtp_host": st.text_input("SMTP host"),
                "smtp_port": st.number_input("SMTP port", min_value=1, value=465),
                "smtp_security": st.selectbox("SMTP security", ["SSL", "STARTTLS", "NONE"]),
                "imap_host": st.text_input("IMAP host"),
                "imap_port": st.number_input("IMAP port", min_value=1, value=993),
                "imap_security": st.selectbox("IMAP security", ["SSL"]),
                "sent_folder_name": st.text_input("Sent folder", value="Sent"),
                "inbox_folder_name": st.text_input("Inbox folder", value="INBOX"),
                "enable_save_to_sent": int(st.checkbox("Save to IMAP Sent", value=True)),
                "enable_bcc_self_backup": int(st.checkbox("BCC self backup", value=False)),
                "bcc_backup_email": st.text_input("BCC backup email"),
            }
            if st.form_submit_button("Save email account"):
                profiles.create_record(conn, "email_accounts", data)
                st.success("Email account saved.")
        show_query(conn, "SELECT email_account_id, account_name, sender_email, password_env_name, smtp_host, smtp_port, imap_host, imap_port FROM email_accounts ORDER BY email_account_id DESC")


def lead_import_page(conn) -> None:
    st.subheader("Import Leads")
    uploaded = st.file_uploader("Upload CSV/XLSX", type=["csv", "xlsx", "xls"])
    if not uploaded:
        show_query(conn, "SELECT lead_id, company_name, email, website, domain, status FROM leads ORDER BY lead_id DESC LIMIT 50")
        return

    temp_path = DATA_DIR / "temp" / uploaded.name
    temp_path.write_bytes(uploaded.getbuffer())
    df = imports.read_lead_file(temp_path)
    st.write(f"Rows: {len(df)}")
    st.dataframe(df.head(20), use_container_width=True)

    inferred = imports.infer_mapping(list(df.columns))
    st.subheader("Column Mapping")
    mapping = {}
    columns = [""] + list(df.columns)
    for field in imports.INTERNAL_FIELDS:
        default_col = inferred.get(field, "")
        default_index = columns.index(default_col) if default_col in columns else 0
        selected = st.selectbox(field, columns, index=default_index, key=f"map_{field}")
        if selected:
            mapping[field] = selected

    if st.button("Import into SQLite"):
        saved = imports.save_original_import(temp_path)
        result = imports.import_leads(conn, df, mapping, saved.name)
        st.success(
            f"Imported batch {result.import_batch_id}: {result.new_leads} new, "
            f"{result.duplicate_leads} duplicates, {result.invalid_emails} invalid emails, "
            f"{result.skipped_rows} skipped."
        )


def research_drafts_page(conn) -> None:
    st.subheader("Research and Drafts")
    leads = conn.execute(
        "SELECT lead_id, company_name, email, website, status FROM leads WHERE status != 'sent' ORDER BY lead_id DESC LIMIT 200"
    ).fetchall()
    if not leads:
        st.info("No leads imported yet.")
        return
    lead_options = {row["lead_id"]: f"{row['lead_id']} - {row['company_name']} - {row['status']}" for row in leads}
    lead_id = st.selectbox("Lead", list(lead_options.keys()), format_func=lead_options.get)
    col_a, col_b = st.columns(2)
    if col_a.button("Research selected lead"):
        result = research.research_lead(conn, lead_id)
        st.success(f"Research status: {result.research_status}")
        st.write(result.company_summary)

    business_options = id_options(conn, "business_profiles", "business_profile_id", "business_name")
    product_options = id_options(conn, "product_service_profiles", "product_service_profile_id", "name")
    campaign_options = id_options(conn, "campaigns", "campaign_id", "campaign_name")
    business_id = select_or_none("Business profile for draft", business_options)
    product_id = select_or_none("Product/service for draft", product_options)
    campaign_id = select_or_none("Campaign for draft", campaign_options)
    use_llm = st.checkbox("Use LLM if configured", value=False)
    if col_b.button("Generate draft"):
        draft_id = ai.generate_email_draft(conn, lead_id, business_id, product_id, campaign_id, use_llm=use_llm)
        st.success(f"Draft created: {draft_id}")

    show_query(
        conn,
        """
        SELECT ai_email_draft_id, lead_id, relevance_score_0_100, send_recommendation,
               subject, status, created_at
        FROM ai_email_drafts
        ORDER BY ai_email_draft_id DESC
        LIMIT 50
        """,
    )


def review_queue_page(conn) -> None:
    st.subheader("Review Queue")
    drafts = conn.execute(
        """
        SELECT d.ai_email_draft_id, l.company_name, l.email, d.subject, d.status
        FROM ai_email_drafts d
        JOIN leads l ON l.lead_id = d.lead_id
        WHERE d.status IN ('draft_created', 'approved')
        ORDER BY d.ai_email_draft_id DESC
        LIMIT 100
        """
    ).fetchall()
    if drafts:
        draft_options = {row["ai_email_draft_id"]: f"{row['ai_email_draft_id']} - {row['company_name']} - {row['subject']}" for row in drafts}
        draft_id = st.selectbox("Draft", list(draft_options.keys()), format_func=draft_options.get)
        draft = conn.execute("SELECT * FROM ai_email_drafts WHERE ai_email_draft_id = ?", (draft_id,)).fetchone()
        st.text_input("Subject", value=draft["subject"], disabled=True)
        st.text_area("Email body", value=draft["email_body"], height=260, disabled=True)
        sender_email = st.text_input("Sender email for queue")
        if st.button("Approve and add to queue"):
            queue_id = send_queue.approve_draft_to_queue(conn, draft_id, sender_email)
            st.success(f"Queued email: {queue_id}")
    else:
        st.info("No draft emails waiting for review.")

    st.subheader("Queued Emails")
    queue_rows = conn.execute(
        "SELECT send_queue_id, recipient_email, subject, sender_email, campaign_id, status FROM send_queue ORDER BY send_queue_id DESC LIMIT 100"
    ).fetchall()
    if queue_rows:
        show_rows(queue_rows)
        queue_options = {row["send_queue_id"]: f"{row['send_queue_id']} - {row['recipient_email']} - {row['status']}" for row in queue_rows}
        queue_id = st.selectbox("Queue item", list(queue_options.keys()), format_func=queue_options.get)
        if st.button("Run safety check"):
            ok, problems = send_queue.safety_check_queue_item(conn, queue_id)
            st.success("Safety check passed.") if ok else st.error("\n".join(problems))
        if st.button("Dry-run send selected"):
            ok, problems = send_queue.safety_check_queue_item(conn, queue_id)
            if ok:
                send_queue.record_dry_run_send(conn, queue_id)
                st.success("Dry-run send recorded in daily ledger.")
            else:
                st.error("\n".join(problems))
    else:
        st.info("No queued emails.")


def diagnostics_page(conn) -> None:
    st.subheader("Diagnostics")
    st.write(f"Database: `{default_db_path()}`")
    if st.button("Ensure runtime folders"):
        ensure_runtime_dirs()
        st.success("Runtime folders checked.")
    if st.button("Run privacy scan on public files"):
        findings = privacy.scan_public_files(ROOT)
        if findings:
            st.error("Private keyword findings detected.")
            st.json(findings)
        else:
            st.success("No private keywords found in public files.")
    st.subheader("Recent Audit Log")
    show_query(conn, "SELECT event_type, entity_type, entity_id, message, created_at FROM audit_log ORDER BY audit_log_id DESC LIMIT 50")


def scalar(conn, query: str, params: tuple = ()) -> int:
    row = conn.execute(query, params).fetchone()
    if row is None:
        return 0
    return int(row[0] or 0)


def id_options(conn, table: str, id_col: str, label_col: str) -> dict[int, str]:
    rows = conn.execute(f"SELECT {id_col}, {label_col} FROM {table} ORDER BY {id_col} DESC").fetchall()
    return {int(row[id_col]): str(row[label_col] or row[id_col]) for row in rows}


def select_or_none(label: str, options: dict[int, str]) -> int | None:
    if not options:
        st.selectbox(label, ["No records available"], disabled=True)
        return None
    return st.selectbox(label, list(options.keys()), format_func=options.get)


def show_records(conn, table: str) -> None:
    rows = profiles.list_records(conn, table, include_archived=True)
    show_rows(rows)


def show_query(conn, query: str, params: tuple = ()) -> None:
    rows = conn.execute(query, params).fetchall()
    show_rows(rows)


def show_rows(rows) -> None:
    if not rows:
        st.info("No records yet.")
        return
    st.dataframe(pd.DataFrame([dict(row) for row in rows]), use_container_width=True)


if __name__ == "__main__":
    main()
