from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nusapitch import ai, backups, db, email_client, imports, privacy, profiles, replies, research, setup_validation, suppression  # noqa: E402
from nusapitch import queue as send_queue  # noqa: E402
from nusapitch.paths import DATA_DIR, default_db_path, ensure_runtime_dirs, load_local_env  # noqa: E402


st.set_page_config(page_title="NusaPitch", page_icon=None, layout="wide")

ensure_runtime_dirs()
load_local_env()
DB_PATH = db.init_db()


FIELD_SPECS = {
    "business_profiles": [
        {"name": "business_name", "label": "Business name", "kind": "text"},
        {"name": "brand_name", "label": "Brand name", "kind": "text"},
        {"name": "website", "label": "Website", "kind": "text"},
        {"name": "company_description", "label": "Company description", "kind": "textarea"},
        {"name": "country", "label": "Country", "kind": "text"},
        {"name": "city_region", "label": "City/region", "kind": "text"},
        {"name": "business_address", "label": "Business address", "kind": "text"},
        {"name": "company_phone", "label": "Company phone", "kind": "text"},
        {"name": "company_email", "label": "Company email", "kind": "text"},
        {"name": "company_linkedin", "label": "Company LinkedIn", "kind": "text"},
        {"name": "business_type", "label": "Business type", "kind": "text"},
        {"name": "target_market", "label": "Target market", "kind": "text"},
        {"name": "value_proposition", "label": "Value proposition", "kind": "textarea"},
        {"name": "credibility_points", "label": "Credibility points", "kind": "textarea"},
        {"name": "private_notes", "label": "Private notes", "kind": "textarea"},
    ],
    "product_service_profiles": [
        {
            "name": "business_profile_id",
            "label": "Business profile",
            "kind": "fk",
            "table": "business_profiles",
            "id_col": "business_profile_id",
            "label_col": "business_name",
        },
        {"name": "name", "label": "Name", "kind": "text"},
        {"name": "category", "label": "Category", "kind": "text"},
        {"name": "description", "label": "Description", "kind": "textarea"},
        {"name": "ideal_customer", "label": "Ideal customer", "kind": "textarea"},
        {"name": "use_cases", "label": "Use cases", "kind": "textarea"},
        {"name": "proof_points", "label": "Proof points", "kind": "textarea"},
        {"name": "constraints", "label": "Constraints", "kind": "textarea"},
    ],
    "sender_profiles": [
        {"name": "sender_name", "label": "Sender name", "kind": "text"},
        {"name": "sender_position", "label": "Sender position", "kind": "text"},
        {"name": "sender_email", "label": "Sender email", "kind": "text"},
        {"name": "sender_phone", "label": "Sender phone", "kind": "text"},
        {"name": "sender_linkedin", "label": "Sender LinkedIn", "kind": "text"},
        {"name": "signature", "label": "Signature", "kind": "textarea"},
        {"name": "opt_out_line", "label": "Opt-out line", "kind": "text"},
    ],
    "campaigns": [
        {"name": "campaign_name", "label": "Campaign name", "kind": "text"},
        {
            "name": "business_profile_id",
            "label": "Business profile",
            "kind": "fk",
            "table": "business_profiles",
            "id_col": "business_profile_id",
            "label_col": "business_name",
        },
        {
            "name": "sender_profile_id",
            "label": "Sender profile",
            "kind": "fk",
            "table": "sender_profiles",
            "id_col": "sender_profile_id",
            "label_col": "sender_email",
        },
        {
            "name": "product_service_profile_id",
            "label": "Product/service",
            "kind": "fk",
            "table": "product_service_profiles",
            "id_col": "product_service_profile_id",
            "label_col": "name",
        },
        {"name": "sender_email_daily_limit", "label": "Sender email daily limit", "kind": "int", "min": 1},
        {"name": "sender_domain_daily_limit", "label": "Sender domain daily limit", "kind": "int", "min": 1},
        {"name": "campaign_daily_limit", "label": "Campaign daily limit", "kind": "int", "min": 1},
        {"name": "mode", "label": "Mode", "kind": "choice", "choices": ["review", "draft-only", "auto-send"]},
    ],
    "llm_settings": [
        {"name": "provider_name", "label": "Provider name", "kind": "text"},
        {"name": "base_url", "label": "Base URL", "kind": "text"},
        {"name": "secret_env_name", "label": "LLM secret env var", "kind": "text"},
        {"name": "model_name", "label": "Model name", "kind": "text"},
        {"name": "temperature", "label": "Temperature", "kind": "float", "min": 0.0, "max": 1.0, "step": 0.1},
        {"name": "max_tokens", "label": "Max tokens", "kind": "int", "min": 100},
        {"name": "timeout_seconds", "label": "Timeout seconds", "kind": "int", "min": 5},
        {"name": "retry_count", "label": "Retry count", "kind": "int", "min": 0},
    ],
    "email_accounts": [
        {"name": "account_name", "label": "Account name", "kind": "text"},
        {"name": "sender_email", "label": "Sender email", "kind": "text"},
        {"name": "password_env_name", "label": "Email secret env var", "kind": "text"},
        {"name": "smtp_host", "label": "SMTP host", "kind": "text"},
        {"name": "smtp_port", "label": "SMTP port", "kind": "int", "min": 1},
        {"name": "smtp_security", "label": "SMTP security", "kind": "choice", "choices": ["SSL", "STARTTLS", "NONE"]},
        {"name": "imap_host", "label": "IMAP host", "kind": "text"},
        {"name": "imap_port", "label": "IMAP port", "kind": "int", "min": 1},
        {"name": "imap_security", "label": "IMAP security", "kind": "choice", "choices": ["SSL"]},
        {"name": "sent_folder_name", "label": "Sent folder", "kind": "text"},
        {"name": "inbox_folder_name", "label": "Inbox folder", "kind": "text"},
        {"name": "enable_save_to_sent", "label": "Save to IMAP Sent", "kind": "bool"},
        {"name": "enable_bcc_self_backup", "label": "BCC self backup", "kind": "bool"},
        {"name": "bcc_backup_email", "label": "BCC backup email", "kind": "text"},
    ],
}


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
            "Suppression",
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
        elif page == "Suppression":
            suppression_page(conn)
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
        st.caption("Fields marked * are required before this setup can be saved or used for sending.")
        with st.form("business_form"):
            data = {
                "business_name": st.text_input(field_label("business_profiles", "business_name", "Business name")),
                "brand_name": st.text_input(field_label("business_profiles", "brand_name", "Brand name")),
                "website": st.text_input(field_label("business_profiles", "website", "Website")),
                "company_description": st.text_area(field_label("business_profiles", "company_description", "Company description")),
                "country": st.text_input(field_label("business_profiles", "country", "Country")),
                "city_region": st.text_input("City/region"),
                "business_address": st.text_input("Business address"),
                "company_phone": st.text_input("Company phone"),
                "company_email": st.text_input("Company email"),
                "company_linkedin": st.text_input("Company LinkedIn"),
                "business_type": st.text_input("Business type"),
                "target_market": st.text_input(field_label("business_profiles", "target_market", "Target market")),
                "value_proposition": st.text_area(field_label("business_profiles", "value_proposition", "Value proposition")),
                "credibility_points": st.text_area(field_label("business_profiles", "credibility_points", "Credibility points")),
                "private_notes": st.text_area("Private notes"),
            }
            if st.form_submit_button("Save business profile"):
                create_record_or_show_errors(conn, "business_profiles", data, "Business profile saved.")
        manage_records(conn, "business_profiles", "business_profile_id", ["business_name", "website"], FIELD_SPECS["business_profiles"])

    with tabs[1]:
        st.subheader("Product/Service Profiles")
        st.caption("Fields marked * are required before this setup can be saved or used for sending.")
        business_options = id_options(conn, "business_profiles", "business_profile_id", "business_name")
        with st.form("product_form"):
            data = {
                "business_profile_id": st.selectbox(field_label("product_service_profiles", "business_profile_id", "Business profile"), options=list(business_options.keys()), format_func=business_options.get) if business_options else None,
                "name": st.text_input(field_label("product_service_profiles", "name", "Name")),
                "category": st.text_input("Category"),
                "description": st.text_area(field_label("product_service_profiles", "description", "Description")),
                "ideal_customer": st.text_area(field_label("product_service_profiles", "ideal_customer", "Ideal customer")),
                "use_cases": st.text_area(field_label("product_service_profiles", "use_cases", "Use cases")),
                "proof_points": st.text_area(field_label("product_service_profiles", "proof_points", "Proof points")),
                "constraints": st.text_area("Constraints"),
            }
            if st.form_submit_button("Save product/service"):
                create_record_or_show_errors(conn, "product_service_profiles", data, "Product/service profile saved.")
        manage_records(conn, "product_service_profiles", "product_service_profile_id", ["name", "category"], FIELD_SPECS["product_service_profiles"])

    with tabs[2]:
        st.subheader("Sender Profiles")
        st.caption("Fields marked * are required before this setup can be saved or used for sending.")
        with st.form("sender_form"):
            data = {
                "sender_name": st.text_input(field_label("sender_profiles", "sender_name", "Sender name")),
                "sender_position": st.text_input(field_label("sender_profiles", "sender_position", "Sender position")),
                "sender_email": st.text_input(field_label("sender_profiles", "sender_email", "Sender email")),
                "sender_phone": st.text_input("Sender phone"),
                "sender_linkedin": st.text_input("Sender LinkedIn"),
                "signature": st.text_area(field_label("sender_profiles", "signature", "Signature")),
                "opt_out_line": st.text_input(field_label("sender_profiles", "opt_out_line", "Opt-out line"), value='If this is not relevant, reply "no" and I will not follow up.'),
            }
            if st.form_submit_button("Save sender profile"):
                create_record_or_show_errors(conn, "sender_profiles", data, "Sender profile saved.")
        manage_records(conn, "sender_profiles", "sender_profile_id", ["sender_name", "sender_email"], FIELD_SPECS["sender_profiles"])

    with tabs[3]:
        st.subheader("Campaigns")
        st.caption("Fields marked * are required before this setup can be saved or used for sending.")
        business_options = id_options(conn, "business_profiles", "business_profile_id", "business_name")
        sender_options = id_options(conn, "sender_profiles", "sender_profile_id", "sender_email")
        product_options = id_options(conn, "product_service_profiles", "product_service_profile_id", "name")
        with st.form("campaign_form"):
            data = {
                "campaign_name": st.text_input(field_label("campaigns", "campaign_name", "Campaign name")),
                "business_profile_id": select_or_none(field_label("campaigns", "business_profile_id", "Business profile"), business_options),
                "sender_profile_id": select_or_none(field_label("campaigns", "sender_profile_id", "Sender profile"), sender_options),
                "product_service_profile_id": select_or_none(field_label("campaigns", "product_service_profile_id", "Product/service"), product_options),
                "sender_email_daily_limit": st.number_input(field_label("campaigns", "sender_email_daily_limit", "Sender email daily limit"), min_value=1, value=20),
                "sender_domain_daily_limit": st.number_input(field_label("campaigns", "sender_domain_daily_limit", "Sender domain daily limit"), min_value=1, value=30),
                "campaign_daily_limit": st.number_input(field_label("campaigns", "campaign_daily_limit", "Campaign daily limit"), min_value=1, value=10),
                "mode": st.selectbox("Mode", ["review", "draft-only", "auto-send"]),
            }
            if st.form_submit_button("Save campaign"):
                create_record_or_show_errors(conn, "campaigns", data, "Campaign saved.")
        manage_records(conn, "campaigns", "campaign_id", ["campaign_name", "mode"], FIELD_SPECS["campaigns"])


def settings_page(conn) -> None:
    tabs = st.tabs(["LLM", "Email"])
    with tabs[0]:
        st.subheader("OpenAI-Compatible LLM")
        st.caption("Fields marked * are required before these settings can be saved.")
        st.info("Store the real LLM secret in an environment variable or `.credentials/llm.env`, not in this database form.")
        with st.form("llm_form"):
            data = {
                "provider_name": st.text_input(field_label("llm_settings", "provider_name", "Provider name"), value="OpenAI-compatible"),
                "base_url": st.text_input(field_label("llm_settings", "base_url", "Base URL"), value="https://api.example.com/v1"),
                "secret_env_name": st.text_input(field_label("llm_settings", "secret_env_name", "LLM secret env var"), value="NUSAPITCH_LLM_SECRET"),
                "model_name": st.text_input(field_label("llm_settings", "model_name", "Model name")),
                "temperature": st.slider("Temperature", 0.0, 1.0, 0.3, 0.1),
                "max_tokens": st.number_input("Max tokens", min_value=100, value=1200),
                "timeout_seconds": st.number_input("Timeout seconds", min_value=5, value=60),
                "retry_count": st.number_input("Retry count", min_value=0, value=1),
            }
            if st.form_submit_button("Save LLM settings"):
                create_record_or_show_errors(conn, "llm_settings", data, "LLM settings saved.")
        if st.button("Test LLM connection"):
            ok, message = ai.test_llm_connection(conn)
            st.success(message) if ok else st.error(message)
        manage_records(conn, "llm_settings", "llm_settings_id", ["provider_name", "model_name"], FIELD_SPECS["llm_settings"])

    with tabs[1]:
        st.subheader("SMTP/IMAP Email Account")
        st.caption("Fields marked * are required before these settings can be saved or used for sending.")
        st.info("Store the real email password in an environment variable or `.credentials/email.env`, not in this database form.")
        with st.form("email_form"):
            data = {
                "account_name": st.text_input(field_label("email_accounts", "account_name", "Account name")),
                "sender_email": st.text_input(field_label("email_accounts", "sender_email", "Sender email")),
                "password_env_name": st.text_input(field_label("email_accounts", "password_env_name", "Email secret env var"), value="NUSAPITCH_EMAIL_SECRET"),
                "smtp_host": st.text_input(field_label("email_accounts", "smtp_host", "SMTP host")),
                "smtp_port": st.number_input(field_label("email_accounts", "smtp_port", "SMTP port"), min_value=1, value=465),
                "smtp_security": st.selectbox(field_label("email_accounts", "smtp_security", "SMTP security"), ["SSL", "STARTTLS", "NONE"]),
                "imap_host": st.text_input(field_label("email_accounts", "imap_host", "IMAP host")),
                "imap_port": st.number_input(field_label("email_accounts", "imap_port", "IMAP port"), min_value=1, value=993),
                "imap_security": st.selectbox(field_label("email_accounts", "imap_security", "IMAP security"), ["SSL"]),
                "sent_folder_name": st.text_input(field_label("email_accounts", "sent_folder_name", "Sent folder"), value="Sent"),
                "inbox_folder_name": st.text_input(field_label("email_accounts", "inbox_folder_name", "Inbox folder"), value="INBOX"),
                "enable_save_to_sent": int(st.checkbox("Save to IMAP Sent", value=True)),
                "enable_bcc_self_backup": int(st.checkbox("BCC self backup", value=False)),
                "bcc_backup_email": st.text_input("BCC backup email"),
            }
            if st.form_submit_button("Save email account"):
                create_record_or_show_errors(conn, "email_accounts", data, "Email account saved.")
        active_account = conn.execute(
            "SELECT * FROM email_accounts WHERE is_active = 1 ORDER BY email_account_id DESC LIMIT 1"
        ).fetchone()
        test_cols = st.columns(2)
        if test_cols[0].button("Test active SMTP"):
            if active_account is None:
                st.error("No active email account saved.")
            else:
                ok, message = email_client.test_smtp(active_account)
                st.success(message) if ok else st.error(message)
        if test_cols[1].button("Test active IMAP"):
            if active_account is None:
                st.error("No active email account saved.")
            else:
                ok, message = email_client.test_imap(active_account)
                st.success(message) if ok else st.error(message)
        manage_records(conn, "email_accounts", "email_account_id", ["account_name", "sender_email"], FIELD_SPECS["email_accounts"])


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
            try:
                queue_id = send_queue.approve_draft_to_queue(conn, draft_id, sender_email)
                st.success(f"Queued email: {queue_id}")
            except ValueError as exc:
                st.error(str(exc))
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
        confirm_real_send = st.checkbox("Enable real SMTP send for selected queued email")
        if st.button("Send selected through SMTP"):
            ok, messages = send_queue.send_real_email(conn, queue_id, confirm_real_send=confirm_real_send)
            if ok:
                st.success("\n".join(messages))
            else:
                st.error("\n".join(messages))
    else:
        st.info("No queued emails.")


def suppression_page(conn) -> None:
    st.subheader("Suppression List")
    with st.form("suppression_form"):
        data = {
            "email": st.text_input("Email"),
            "domain": st.text_input("Domain"),
            "reason": st.selectbox("Reason", ["opt-out", "bounce", "manual block", "duplicate", "other"]),
            "source": st.text_input("Source", value="manual"),
            "notes": st.text_area("Notes"),
        }
        if st.form_submit_button("Add suppression"):
            try:
                suppression_id = suppression.add_suppression(conn, **data)
                st.success(f"Suppression added: {suppression_id}")
            except ValueError as exc:
                st.error(str(exc))

    rows = suppression.list_suppressions(conn)
    show_rows(rows)
    if rows:
        options = {
            int(row["suppression_id"]): f"{row['suppression_id']} - {row['email'] or row['domain']} - {row['reason']}"
            for row in rows
        }
        suppression_id = st.selectbox("Suppression record", list(options.keys()), format_func=options.get)
        if st.button("Remove selected suppression"):
            suppression.remove_suppression(conn, suppression_id)
            st.success("Suppression removed.")
            st.rerun()


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
    st.subheader("Backups and Exports")
    col_a, col_b, col_c = st.columns(3)
    if col_a.button("Create SQLite backup"):
        backup_path = backups.create_sqlite_backup(DB_PATH)
        st.success(f"Backup created: {backup_path}")
    if col_b.button("Export leads CSV"):
        export_path = backups.export_table_csv(conn, "leads")
        st.success(f"Export created: {export_path}")
    if col_c.button("Export all CSV"):
        exported = backups.export_all_csv(conn)
        st.success(f"Created {len(exported)} CSV exports.")
    st.subheader("Inbox Sync")
    active_account = conn.execute(
        "SELECT * FROM email_accounts WHERE is_active = 1 ORDER BY email_account_id DESC LIMIT 1"
    ).fetchone()
    if st.button("Check active inbox for replies/bounces"):
        if active_account is None:
            st.error("No active email account saved.")
        else:
            try:
                counts = replies.sync_replies_and_bounces(conn, active_account)
                st.success(
                    f"Replies: {counts['reply']}, bounces: {counts['bounce']}, duplicates: {counts['duplicate']}."
                )
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
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


def manage_records(conn, table: str, id_col: str, label_cols: list[str], fields: list[dict]) -> None:
    rows = profiles.list_records(conn, table, include_archived=True)
    show_rows(rows)
    if not rows:
        return

    st.markdown("#### Manage existing")
    options = {int(row[id_col]): record_label(row, id_col, label_cols) for row in rows}
    record_id = st.selectbox(
        "Record",
        list(options.keys()),
        format_func=options.get,
        key=f"manage_select_{table}",
    )
    record = profiles.get_record(conn, table, record_id)
    if record is None:
        st.warning("Selected record no longer exists.")
        return

    values = dict(record)
    with st.form(f"manage_form_{table}_{record_id}"):
        data = render_record_fields(conn, table, fields, values, f"manage_{table}_{record_id}")
        button_cols = st.columns(5)
        with button_cols[0]:
            update_clicked = st.form_submit_button("Update")
        with button_cols[1]:
            duplicate_clicked = st.form_submit_button("Duplicate")
        archive_clicked = restore_clicked = False
        deactivate_clicked = reactivate_clicked = False
        if "is_archived" in values:
            archived = bool(values["is_archived"])
            with button_cols[2]:
                if archived:
                    restore_clicked = st.form_submit_button("Restore")
                else:
                    archive_clicked = st.form_submit_button("Archive")
        if "is_active" in values:
            active = bool(values["is_active"])
            with button_cols[3]:
                if active:
                    deactivate_clicked = st.form_submit_button("Deactivate")
                else:
                    reactivate_clicked = st.form_submit_button("Reactivate")

    if update_clicked:
        problems = setup_validation.validate_record_data(table, data)
        if problems:
            show_validation_errors(problems)
        else:
            profiles.update_record(conn, table, record_id, data)
            st.success("Record updated.")
            st.rerun()
    if duplicate_clicked:
        new_id = profiles.duplicate_record(conn, table, record_id)
        st.success(f"Record duplicated: {new_id}.")
        st.rerun()
    if archive_clicked:
        profiles.archive_record(conn, table, record_id)
        st.success("Record archived.")
        st.rerun()
    if restore_clicked:
        profiles.restore_record(conn, table, record_id)
        st.success("Record restored.")
        st.rerun()
    if deactivate_clicked:
        profiles.set_record_active(conn, table, record_id, False)
        st.success("Record deactivated.")
        st.rerun()
    if reactivate_clicked:
        profiles.set_record_active(conn, table, record_id, True)
        st.success("Record reactivated.")
        st.rerun()


def render_record_fields(conn, table: str, fields: list[dict], values: dict, key_prefix: str) -> dict:
    data = {}
    for spec in fields:
        name = spec["name"]
        label = field_label(table, name, spec["label"])
        kind = spec["kind"]
        current = values.get(name, spec.get("default", ""))
        key = f"{key_prefix}_{name}"
        if kind == "textarea":
            data[name] = st.text_area(label, value=str(current or ""), key=key)
        elif kind == "int":
            data[name] = int(
                st.number_input(
                    label,
                    min_value=int(spec.get("min", 0)),
                    value=int(current or spec.get("min", 0)),
                    key=key,
                )
            )
        elif kind == "float":
            data[name] = float(
                st.number_input(
                    label,
                    min_value=float(spec.get("min", 0.0)),
                    max_value=float(spec.get("max", 100.0)),
                    value=float(current or spec.get("min", 0.0)),
                    step=float(spec.get("step", 0.1)),
                    key=key,
                )
            )
        elif kind == "bool":
            data[name] = int(st.checkbox(label, value=bool(current), key=key))
        elif kind == "choice":
            choices = list(spec["choices"])
            selected = str(current or choices[0])
            index = choices.index(selected) if selected in choices else 0
            data[name] = st.selectbox(label, choices, index=index, key=key)
        elif kind == "fk":
            data[name] = foreign_key_input(conn, spec, current, key)
        else:
            data[name] = st.text_input(label, value=str(current or ""), key=key)
    return data


def foreign_key_input(conn, spec: dict, current, key: str) -> int | None:
    options = id_options(conn, spec["table"], spec["id_col"], spec["label_col"])
    choices: list[int | None] = [None] + list(options.keys())
    if current and int(current) not in choices:
        choices.append(int(current))

    def format_choice(value: int | None) -> str:
        if value is None:
            return "None"
        return options.get(value, f"Missing record {value}")

    current_value = int(current) if current else None
    index = choices.index(current_value) if current_value in choices else 0
    return st.selectbox(spec["label"], choices, index=index, format_func=format_choice, key=key)


def record_label(row, id_col: str, label_cols: list[str]) -> str:
    parts = [str(row[col]) for col in label_cols if col in row.keys() and row[col]]
    status_parts = []
    if "is_archived" in row.keys() and row["is_archived"]:
        status_parts.append("archived")
    if "is_active" in row.keys() and not row["is_active"]:
        status_parts.append("inactive")
    status = f" ({', '.join(status_parts)})" if status_parts else ""
    label = " - ".join(parts) if parts else f"Record {row[id_col]}"
    return f"{row[id_col]} - {label}{status}"


def field_label(table: str, field: str, label: str) -> str:
    return setup_validation.required_label(table, field, label)


def create_record_or_show_errors(conn, table: str, data: dict, success_message: str) -> int | None:
    problems = setup_validation.validate_record_data(table, data)
    if problems:
        show_validation_errors(problems)
        return None
    record_id = profiles.create_record(conn, table, data)
    st.success(success_message)
    return record_id


def show_validation_errors(problems: list[str]) -> None:
    st.error("Please complete the required setup before saving:")
    for problem in problems:
        st.warning(problem)


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
