from __future__ import annotations

from nusapitch import db


def test_init_db_tracks_schema_migration_version(tmp_path):
    db_path = tmp_path / "app.db"

    db.init_db(db_path)

    with db.connect(db_path) as conn:
        migrations = conn.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall()

        assert db.get_schema_version(conn) == db.SCHEMA_VERSION
        assert [(row["version"], row["name"]) for row in migrations] == [
            (1, "initial_core_schema")
        ]


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "app.db"

    db.init_db(db_path)
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]

    assert count == 1
