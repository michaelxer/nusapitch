from __future__ import annotations

import os

from nusapitch import paths


def test_load_local_env_reads_credentials_files_without_overriding(tmp_path, monkeypatch):
    project_root = tmp_path
    credentials_dir = project_root / ".credentials"
    credentials_dir.mkdir()
    (credentials_dir / "llm.env").write_text("NUSAPITCH_TEST_ENV=from-file\n", encoding="utf-8")
    (credentials_dir / "email.env").write_text("NUSAPITCH_EXISTING_ENV=from-email-file\n", encoding="utf-8")

    monkeypatch.setattr(paths, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(paths, "CREDENTIALS_DIR", credentials_dir)
    monkeypatch.setenv("NUSAPITCH_EXISTING_ENV", "already-set")
    monkeypatch.delenv("NUSAPITCH_TEST_ENV", raising=False)

    paths.load_local_env()

    assert os.getenv("NUSAPITCH_TEST_ENV") == "from-file"
    assert os.getenv("NUSAPITCH_EXISTING_ENV") == "already-set"
