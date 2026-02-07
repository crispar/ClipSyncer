"""Tests for ClipboardRepository"""

import json
import pytest
from datetime import datetime, timedelta
from src.core.clipboard.history import ClipboardEntry
from src.core.storage.repository_improved import ClipboardRepository


class TestClipboardRepository:
    """Tests for ClipboardRepository (data access layer)"""

    def _make_entry(self, content="test", timestamp=None, category="text"):
        if timestamp is None:
            timestamp = datetime.now()
        return ClipboardEntry(
            content=content,
            timestamp=timestamp,
            content_hash=ClipboardEntry.calculate_hash(content),
            category=category
        )

    def test_save_entry(self, repository):
        entry = self._make_entry("save test")
        result = repository.save_entry(entry)
        assert result is True

    def test_save_duplicate_updates_timestamp(self, repository):
        entry1 = self._make_entry("dup_test", datetime(2024, 1, 1))
        entry2 = self._make_entry("dup_test", datetime(2024, 6, 1))
        repository.save_entry(entry1)
        repository.save_entry(entry2)

        entries = repository.get_entries()
        assert len(entries) == 1
        assert entries[0].timestamp == datetime(2024, 6, 1)

    def test_get_entries(self, repository):
        for i in range(5):
            repository.save_entry(self._make_entry(f"entry_{i}"))
        entries = repository.get_entries()
        assert len(entries) == 5

    def test_get_entries_with_limit(self, repository):
        for i in range(10):
            repository.save_entry(self._make_entry(f"entry_{i}"))
        entries = repository.get_entries(limit=3)
        assert len(entries) == 3

    def test_get_entries_ordered_by_timestamp_desc(self, repository):
        repository.save_entry(self._make_entry("old", datetime(2024, 1, 1)))
        repository.save_entry(self._make_entry("new", datetime(2024, 6, 1)))
        entries = repository.get_entries()
        assert entries[0].content == "new"
        assert entries[1].content == "old"

    def test_delete_entry(self, repository):
        entry = self._make_entry("to_delete")
        repository.save_entry(entry)
        result = repository.delete_entry(entry.content_hash)
        assert result is True
        entries = repository.get_entries()
        assert len(entries) == 0

    def test_delete_nonexistent_entry(self, repository):
        result = repository.delete_entry("nonexistent_hash")
        assert result is False

    def test_toggle_favorite(self, repository):
        entry = self._make_entry("fav_test")
        repository.save_entry(entry)
        result = repository.toggle_favorite(entry.content_hash)
        assert result is True

    def test_is_favorite(self, repository):
        entry = self._make_entry("fav_check")
        repository.save_entry(entry)
        assert repository.is_favorite(entry.content_hash) is False
        repository.toggle_favorite(entry.content_hash)
        assert repository.is_favorite(entry.content_hash) is True

    def test_is_favorite_nonexistent(self, repository):
        assert repository.is_favorite("nonexistent") is False

    def test_get_favorites(self, repository):
        e1 = self._make_entry("fav1")
        e2 = self._make_entry("not_fav")
        repository.save_entry(e1)
        repository.save_entry(e2)
        repository.toggle_favorite(e1.content_hash)

        favorites = repository.get_favorites()
        assert len(favorites) == 1
        assert favorites[0].content == "fav1"

    def test_cleanup_old_entries(self, repository):
        old = self._make_entry("old", datetime.now() - timedelta(days=60))
        recent = self._make_entry("recent", datetime.now())
        repository.save_entry(old)
        repository.save_entry(recent)

        deleted = repository.cleanup_old_entries(30)
        assert deleted == 1
        entries = repository.get_entries()
        assert len(entries) == 1
        assert entries[0].content == "recent"

    def test_get_entry_count(self, repository):
        assert repository.get_entry_count() == 0
        repository.save_entry(self._make_entry("a"))
        repository.save_entry(self._make_entry("b"))
        assert repository.get_entry_count() == 2

    def test_clear_all(self, repository):
        for i in range(5):
            repository.save_entry(self._make_entry(f"entry_{i}"))
        result = repository.clear_all()
        assert result is True
        assert repository.get_entry_count() == 0

    def test_save_setting(self, repository):
        result = repository.save_setting("theme", "dark")
        assert result is True

    def test_get_setting(self, repository):
        repository.save_setting("theme", "dark")
        value = repository.get_setting("theme")
        assert value == "dark"

    def test_get_setting_default(self, repository):
        value = repository.get_setting("nonexistent", "default_val")
        assert value == "default_val"

    def test_get_all_settings(self, repository):
        repository.save_setting("key1", "val1")
        repository.save_setting("key2", "val2")
        settings = repository.get_all_settings()
        assert settings["key1"] == "val1"
        assert settings["key2"] == "val2"

    def test_save_entry_preserves_metadata(self, repository):
        entry = self._make_entry("meta_test")
        entry.metadata = {"source": "browser", "app": "chrome"}
        repository.save_entry(entry)

        entries = repository.get_entries()
        assert entries[0].metadata == {"source": "browser", "app": "chrome"}
