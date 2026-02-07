"""Tests for DatabaseManager and SQLAlchemy models"""

import os
import pytest
from datetime import datetime
from src.core.storage.database import DatabaseManager, ClipboardEntryDB, SettingsDB


class TestDatabaseManager:
    """Tests for DatabaseManager"""

    def test_init_creates_db(self, temp_dir):
        db_path = str(temp_dir / "test.db")
        dm = DatabaseManager(db_path)
        assert os.path.exists(db_path)
        dm.close()

    def test_get_session(self, db_manager):
        session = db_manager.get_session()
        assert session is not None
        session.close()

    def test_get_session_before_init_raises(self):
        dm = DatabaseManager.__new__(DatabaseManager)
        dm.SessionLocal = None
        with pytest.raises(RuntimeError, match="Database not initialized"):
            dm.get_session()

    def test_get_size(self, db_manager):
        size = db_manager.get_size()
        assert size > 0  # SQLite creates the file on init

    def test_vacuum(self, db_manager):
        # Should not raise
        db_manager.vacuum()

    def test_reset(self, db_manager):
        # Add an entry
        session = db_manager.get_session()
        entry = ClipboardEntryDB(
            content_hash="testhash",
            encrypted_content="ct",
            encrypted_nonce="nonce",
            encrypted_tag="tag",
            timestamp=datetime.now(),
            category="text"
        )
        session.add(entry)
        session.commit()
        session.close()

        # Reset should clear all data
        db_manager.reset()

        session = db_manager.get_session()
        count = session.query(ClipboardEntryDB).count()
        session.close()
        assert count == 0

    def test_backup(self, db_manager, temp_dir):
        backup_path = str(temp_dir / "backup.db")
        db_manager.backup(backup_path)
        assert os.path.exists(backup_path)


class TestClipboardEntryDB:
    """Tests for the ClipboardEntryDB model"""

    def test_create_entry(self, db_manager):
        session = db_manager.get_session()
        entry = ClipboardEntryDB(
            content_hash="hash123",
            encrypted_content="encrypted_ct",
            encrypted_nonce="nonce_val",
            encrypted_tag="tag_val",
            timestamp=datetime(2024, 1, 1),
            category="text",
            is_favorite=False
        )
        session.add(entry)
        session.commit()

        retrieved = session.query(ClipboardEntryDB).filter_by(content_hash="hash123").first()
        assert retrieved is not None
        assert retrieved.category == "text"
        assert retrieved.is_favorite is False
        session.close()

    def test_unique_content_hash(self, db_manager):
        from sqlalchemy.exc import IntegrityError
        session = db_manager.get_session()
        e1 = ClipboardEntryDB(
            content_hash="duplicate",
            encrypted_content="a", encrypted_nonce="b", encrypted_tag="c",
            timestamp=datetime.now(), category="text"
        )
        e2 = ClipboardEntryDB(
            content_hash="duplicate",
            encrypted_content="d", encrypted_nonce="e", encrypted_tag="f",
            timestamp=datetime.now(), category="text"
        )
        session.add(e1)
        session.commit()
        session.add(e2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()

    def test_favorite_toggle(self, db_manager):
        session = db_manager.get_session()
        entry = ClipboardEntryDB(
            content_hash="fav_test",
            encrypted_content="a", encrypted_nonce="b", encrypted_tag="c",
            timestamp=datetime.now(), category="text", is_favorite=False
        )
        session.add(entry)
        session.commit()

        entry.is_favorite = True
        session.commit()

        retrieved = session.query(ClipboardEntryDB).filter_by(content_hash="fav_test").first()
        assert retrieved.is_favorite is True
        session.close()


class TestSettingsDB:
    """Tests for the SettingsDB model"""

    def test_create_setting(self, db_manager):
        session = db_manager.get_session()
        setting = SettingsDB(
            key="theme",
            value='"dark"',
            updated_at=datetime.now()
        )
        session.add(setting)
        session.commit()

        retrieved = session.query(SettingsDB).filter_by(key="theme").first()
        assert retrieved is not None
        assert retrieved.value == '"dark"'
        session.close()
