from __future__ import annotations

from nusapitch import db, profiles


def test_update_archive_restore_profile_record(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        record_id = profiles.create_record(
            conn,
            "business_profiles",
            {"business_name": "Original Demo", "website": "https://original.example"},
        )

        profiles.update_record(conn, "business_profiles", record_id, {"business_name": "Updated Demo"})
        profiles.archive_record(conn, "business_profiles", record_id)
        archived = profiles.get_record(conn, "business_profiles", record_id)

        assert archived["business_name"] == "Updated Demo"
        assert archived["is_archived"] == 1
        assert profiles.list_records(conn, "business_profiles") == []

        profiles.restore_record(conn, "business_profiles", record_id)
        restored = profiles.get_record(conn, "business_profiles", record_id)

        assert restored["is_archived"] == 0
        assert len(profiles.list_records(conn, "business_profiles")) == 1


def test_set_record_active_for_campaign(tmp_path):
    db_path = tmp_path / "app.db"
    db.init_db(db_path)

    with db.connect(db_path) as conn:
        campaign_id = profiles.create_record(conn, "campaigns", {"campaign_name": "Demo Campaign"})

        profiles.set_record_active(conn, "campaigns", campaign_id, False)
        campaign = profiles.get_record(conn, "campaigns", campaign_id)

        assert campaign["is_active"] == 0
