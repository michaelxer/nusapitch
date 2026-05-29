from __future__ import annotations

from nusapitch import backups, db


def test_create_sqlite_backup_copies_database(tmp_path):
    db_path = tmp_path / "app.db"
    backup_dir = tmp_path / "backups"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        conn.execute("INSERT INTO leads (company_name, email) VALUES ('Demo Buyer', 'buyer@example.test')")
        conn.commit()

    backup_path = backups.create_sqlite_backup(db_path, backup_dir)

    with db.connect(backup_path) as backup_conn:
        count = backup_conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]

    assert backup_path.exists()
    assert count == 1


def test_export_table_csv_writes_header_and_rows(tmp_path):
    db_path = tmp_path / "app.db"
    export_dir = tmp_path / "exports"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        conn.execute("INSERT INTO leads (company_name, email) VALUES ('Demo Buyer', 'buyer@example.test')")
        conn.commit()

        export_path = backups.export_table_csv(conn, "leads", export_dir)

    content = export_path.read_text(encoding="utf-8")

    assert "company_name" in content
    assert "Demo Buyer" in content
