"""Migrations must be atomic: an upgrade that dies midway leaves nothing behind."""

import sqlite3

import pytest
from alembic import command
from alembic.config import Config

from app.config import get_settings
from app.db import API_DIR, run_migrations


def _config() -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    return config


def _tables(path) -> set[str]:
    with sqlite3.connect(path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_failed_upgrade_rolls_back_completely(tmp_path, monkeypatch):
    db = tmp_path / "broken.db"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    get_settings.cache_clear()
    try:
        # Make recording the revision fail, i.e. die after the tables are created.
        from alembic.runtime.migration import HeadMaintainer

        def boom(self, *args, **kwargs):
            raise RuntimeError("killed mid-migration")

        monkeypatch.setattr(HeadMaintainer, "update_to_step", boom)
        with pytest.raises(RuntimeError):
            command.upgrade(_config(), "head")
        assert "users" not in _tables(db)

        # With the fault gone, the same database upgrades cleanly.
        monkeypatch.undo()
        monkeypatch.setenv("DATABASE_PATH", str(db))
        get_settings.cache_clear()
        command.upgrade(_config(), "head")
        assert {"users", "games", "groups", "friendships", "alembic_version"} <= _tables(db)
        # And running it again is a no-op.
        command.upgrade(_config(), "head")
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_downgrade_to_base_and_back(tmp_path, monkeypatch):
    db = tmp_path / "roundtrip.db"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    get_settings.cache_clear()
    try:
        command.upgrade(_config(), "head")
        command.downgrade(_config(), "base")
        assert _tables(db) <= {"alembic_version"}
        command.upgrade(_config(), "head")
        assert "users" in _tables(db)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_rolled_back_release_starts_on_a_newer_database(tmp_path, monkeypatch):
    """After a deploy is rolled back, the older code meets a database a newer release migrated."""
    db = tmp_path / "newer.db"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    get_settings.cache_clear()
    try:
        run_migrations()  # a new file is created and brought up to date as usual
        assert "users" in _tables(db)
        with sqlite3.connect(db) as conn:
            conn.execute("UPDATE alembic_version SET version_num = '9999_from_a_newer_release'")
        run_migrations()  # must neither fail nor touch the file
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT version_num FROM alembic_version").fetchall() == [
                ("9999_from_a_newer_release",)
            ]
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
