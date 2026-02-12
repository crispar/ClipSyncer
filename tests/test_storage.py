"""Tests for DatabaseManager and ClipboardRepository"""

import os
from datetime import datetime, timedelta
import pytest

from src.core.storage.database import DatabaseManager, ClipboardEntryDB, Base
from src.core.storage.repository_improved import ClipboardRepository
from src.core.clipboard.history import ClipboardEntry
from src.core.encryption.manager import EncryptionManager


class TestDatabaseManager:
    """Tests for DatabaseManager"""

    def test_init_creates_db(self, tmp_path):
        db_path = str(tmp_path / "test_init.db")
        dm = DatabaseManager(db_path=db_path)
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
        assert size > 0  # DB file should exist

    def test_backup(self, db_manager, tmp_path):
        backup_path = str(tmp_path / "backup.db")
        db_manager.backup(backup_path)
        assert os.path.exists(backup_path)

    def test_vacuum(self, db_manager):
        # Should not raise
        db_manager.vacuum()

    def test_reset(self, db_manager):
        # Add some data first
        session = db_manager.get_session()
        entry = ClipboardEntryDB(
            content_hash="abc123",
            encrypted_content="ct",
            encrypted_nonce="nc",
            encrypted_tag="tg",
            timestamp=datetime.now(),
            category="text"
        )
        session.add(entry)
        session.commit()
        count = session.query(ClipboardEntryDB).count()
        session.close()
        assert count == 1

        # Reset
        db_manager.reset()
        session = db_manager.get_session()
        count = session.query(ClipboardEntryDB).count()
        session.close()
        assert count == 0

    def test_close(self, tmp_path):
        db_path = str(tmp_path / "test_close.db")
        dm = DatabaseManager(db_path=db_path)
        dm.close()
        # Engine should be disposed


class TestClipboardRepository:
    """Tests for ClipboardRepository"""

    def test_save_entry(self, repository):
        entry = ClipboardEntry(
            content="test content",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("test content")
        )
        result = repository.save_entry(entry)
        assert result is True

    def test_save_and_get_entry(self, repository):
        entry = ClipboardEntry(
            content="saved entry",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("saved entry")
        )
        repository.save_entry(entry)
        entries = repository.get_entries()
        assert len(entries) == 1
        assert entries[0].content == "saved entry"
        assert entries[0].content_hash == entry.content_hash

    def test_get_entries_ordered_by_timestamp(self, repository):
        now = datetime.now()
        for i in range(3):
            entry = ClipboardEntry(
                content=f"entry_{i}",
                timestamp=now - timedelta(hours=i),
                content_hash=ClipboardEntry.calculate_hash(f"entry_{i}")
            )
            repository.save_entry(entry)

        entries = repository.get_entries()
        assert len(entries) == 3
        assert entries[0].content == "entry_0"  # newest
        assert entries[2].content == "entry_2"  # oldest

    def test_get_entries_with_limit(self, repository):
        for i in range(5):
            entry = ClipboardEntry(
                content=f"limit_entry_{i}",
                timestamp=datetime.now() - timedelta(minutes=i),
                content_hash=ClipboardEntry.calculate_hash(f"limit_entry_{i}")
            )
            repository.save_entry(entry)

        entries = repository.get_entries(limit=2)
        assert len(entries) == 2

    def test_save_duplicate_updates_timestamp(self, repository):
        hash_val = ClipboardEntry.calculate_hash("dup_content")
        old_ts = datetime(2025, 1, 1)
        new_ts = datetime(2025, 6, 1)

        entry1 = ClipboardEntry(content="dup_content", timestamp=old_ts, content_hash=hash_val)
        repository.save_entry(entry1)

        entry2 = ClipboardEntry(content="dup_content", timestamp=new_ts, content_hash=hash_val)
        repository.save_entry(entry2)

        entries = repository.get_entries()
        assert len(entries) == 1
        assert entries[0].timestamp == new_ts

    def test_delete_entry(self, repository):
        entry = ClipboardEntry(
            content="to_delete",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("to_delete")
        )
        repository.save_entry(entry)
        result = repository.delete_entry(entry.content_hash)
        assert result is True
        assert repository.get_entry_count() == 0

    def test_delete_nonexistent_entry(self, repository):
        result = repository.delete_entry("nonexistent_hash")
        assert result is False

    def test_cleanup_old_entries(self, repository):
        now = datetime.now()
        # Recent entry
        recent = ClipboardEntry(
            content="recent",
            timestamp=now,
            content_hash=ClipboardEntry.calculate_hash("recent")
        )
        repository.save_entry(recent)
        # Old entry
        old = ClipboardEntry(
            content="old",
            timestamp=now - timedelta(days=60),
            content_hash=ClipboardEntry.calculate_hash("old")
        )
        repository.save_entry(old)

        deleted = repository.cleanup_old_entries(days=30)
        assert deleted == 1
        entries = repository.get_entries()
        assert len(entries) == 1
        assert entries[0].content == "recent"

    def test_get_entry_count(self, repository):
        assert repository.get_entry_count() == 0
        entry = ClipboardEntry(
            content="count",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("count")
        )
        repository.save_entry(entry)
        assert repository.get_entry_count() == 1

    def test_clear_all(self, repository):
        for i in range(3):
            entry = ClipboardEntry(
                content=f"clear_{i}",
                timestamp=datetime.now(),
                content_hash=ClipboardEntry.calculate_hash(f"clear_{i}")
            )
            repository.save_entry(entry)

        result = repository.clear_all()
        assert result is True
        assert repository.get_entry_count() == 0

    def test_toggle_favorite(self, repository):
        entry = ClipboardEntry(
            content="fav_test",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("fav_test")
        )
        repository.save_entry(entry)
        result = repository.toggle_favorite(entry.content_hash)
        assert result is True

    def test_save_and_get_setting(self, repository):
        repository.save_setting("theme", "dark")
        value = repository.get_setting("theme")
        assert value == "dark"

    def test_get_nonexistent_setting(self, repository):
        value = repository.get_setting("nonexistent", default="fallback")
        assert value == "fallback"

    def test_get_all_settings(self, repository):
        repository.save_setting("key1", "value1")
        repository.save_setting("key2", 42)
        settings = repository.get_all_settings()
        assert settings["key1"] == "value1"
        assert settings["key2"] == 42

    def test_encrypted_content_roundtrip(self, repository):
        """Verify content is encrypted in DB and decrypted on read"""
        entry = ClipboardEntry(
            content="secret data 🔑",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("secret data 🔑"),
            category="text",
            metadata={"source": "test"}
        )
        repository.save_entry(entry)

        # Read back
        entries = repository.get_entries()
        assert len(entries) == 1
        assert entries[0].content == "secret data 🔑"
        assert entries[0].metadata == {"source": "test"}

    def test_session_context_manager_commit(self, repository):
        """Test that context manager commits on success"""
        with repository.get_session() as session:
            entry = ClipboardEntryDB(
                content_hash="ctx_test",
                encrypted_content="ct",
                encrypted_nonce="nc",
                encrypted_tag="tg",
                timestamp=datetime.now(),
                category="text"
            )
            session.add(entry)

        # Should be committed
        assert repository.get_entry_count() == 1

    def test_session_context_manager_rollback_on_error(self, repository):
        """Test that context manager rolls back on error"""
        try:
            with repository.get_session() as session:
                entry = ClipboardEntryDB(
                    content_hash="rollback_test",
                    encrypted_content="ct",
                    encrypted_nonce="nc",
                    encrypted_tag="tg",
                    timestamp=datetime.now(),
                    category="text"
                )
                session.add(entry)
                raise ValueError("simulate error")
        except ValueError:
            pass

        # Should have been rolled back
        assert repository.get_entry_count() == 0
