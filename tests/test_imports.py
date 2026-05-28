from __future__ import annotations

import pandas as pd

from nusapitch import db, imports


def test_import_leads_deduplicates_same_file(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)
    conn = db.connect(db_path)
    df = pd.DataFrame(
        [
            {"Company": "GreenField Demo", "Email": "procurement@greenfield.example", "Website": "https://greenfield.example"},
            {"Company": "GreenField Demo", "Email": "procurement@greenfield.example", "Website": "https://greenfield.example"},
        ]
    )
    mapping = {"company_name": "Company", "email": "Email", "website": "Website"}

    first = imports.import_leads(conn, df, mapping, "sample.csv")
    second = imports.import_leads(conn, df, mapping, "sample.csv")

    assert first.new_leads == 1
    assert first.duplicate_leads == 1
    assert second.new_leads == 0
    assert second.duplicate_leads == 2
    assert conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == 1


def test_invalid_placeholder_email_goes_to_review(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)
    conn = db.connect(db_path)
    df = pd.DataFrame([{"Company": "Example Buyer", "Email": "sales@example.com"}])

    result = imports.import_leads(conn, df, {"company_name": "Company", "email": "Email"}, "sample.csv")
    lead = conn.execute("SELECT status FROM leads").fetchone()

    assert result.invalid_emails == 1
    assert lead["status"] == "needs_manual_review"
