"""Tests for ClipboardHistory"""

import pytest
import json
from datetime import datetime, timedelta
from src.core.clipboard.history import ClipboardHistory, ClipboardEntry


class TestClipboardHistory:
    """Tests for ClipboardHistory in-memory storage"""

    def test_add_entry(self, clipboard_history):
        added, removed = clipboard_history.add_entry("hello")
        assert added is True
        assert removed is None
        assert clipboard_history.size == 1

    def test_add_empty_content_rejected(self, clipboard_history):
        added, removed = clipboard_history.add_entry("")
        assert added is False
        assert clipboard_history.size == 0

    def test_add_none_content_rejected(self, clipboard_history):
        added, removed = clipboard_history.add_entry(None)
        assert added is False

    def test_duplicate_detection(self, clipboard_history):
        clipboard_history.add_entry("same")
        added, _ = clipboard_history.add_entry("same")
        assert added is False
        assert clipboard_history.size == 1

    def test_duplicate_moves_to_top(self, clipboard_history):
        clipboard_history.add_entry("first")
        clipboard_history.add_entry("second")
        clipboard_history.add_entry("first")  # duplicate
        entries = clipboard_history.get_entries()
        assert entries[0].content == "first"

    def test_max_size_enforcement(self):
        history = ClipboardHistory(max_size=3)
        history.add_entry("a")
        history.add_entry("b")
        history.add_entry("c")
        _, removed = history.add_entry("d")
        assert history.size == 3
        assert removed is not None
        assert removed.content == "a"

    def test_get_entries_newest_first(self, clipboard_history):
        clipboard_history.add_entry("old", datetime(2024, 1, 1))
        clipboard_history.add_entry("new", datetime(2024, 1, 2))
        entries = clipboard_history.get_entries()
        assert entries[0].content == "new"
        assert entries[1].content == "old"

    def test_get_entries_with_limit(self, clipboard_history):
        for i in range(10):
            clipboard_history.add_entry(f"entry_{i}")
        entries = clipboard_history.get_entries(limit=3)
        assert len(entries) == 3

    def test_search(self, clipboard_history):
        clipboard_history.add_entry("apple pie")
        clipboard_history.add_entry("banana split")
        clipboard_history.add_entry("apple sauce")
        results = clipboard_history.search("apple")
        assert len(results) == 2

    def test_search_case_insensitive(self, clipboard_history):
        clipboard_history.add_entry("Hello World")
        results = clipboard_history.search("hello")
        assert len(results) == 1

    def test_search_case_sensitive(self, clipboard_history):
        clipboard_history.add_entry("Hello World")
        results = clipboard_history.search("hello", case_sensitive=True)
        assert len(results) == 0

    def test_clear(self, clipboard_history):
        clipboard_history.add_entry("a")
        clipboard_history.add_entry("b")
        clipboard_history.clear()
        assert clipboard_history.size == 0

    def test_remove_entry(self, clipboard_history):
        clipboard_history.add_entry("to_remove")
        entry = clipboard_history.get_entries()[0]
        result = clipboard_history.remove_entry(entry.content_hash)
        assert result is True
        assert clipboard_history.size == 0

    def test_remove_entry_not_found(self, clipboard_history):
        result = clipboard_history.remove_entry("nonexistent_hash")
        assert result is False

    def test_has_entry(self, clipboard_history):
        clipboard_history.add_entry("exists")
        entry = clipboard_history.get_entries()[0]
        assert clipboard_history.has_entry(entry.content_hash) is True
        assert clipboard_history.has_entry("nonexistent") is False

    def test_import_entry(self, clipboard_history):
        entry = ClipboardEntry(
            content="imported",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("imported"),
            category="text"
        )
        result = clipboard_history.import_entry(entry)
        assert result is True
        assert clipboard_history.size == 1

    def test_import_entry_skip_duplicate(self, clipboard_history):
        clipboard_history.add_entry("existing")
        entry = ClipboardEntry(
            content="existing",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("existing"),
            category="text"
        )
        result = clipboard_history.import_entry(entry)
        assert result is False
        assert clipboard_history.size == 1

    def test_import_entry_none_rejected(self, clipboard_history):
        assert clipboard_history.import_entry(None) is False

    def test_cleanup_old_entries(self, clipboard_history):
        old_time = datetime.now() - timedelta(days=60)
        recent_time = datetime.now()
        clipboard_history.add_entry("old_entry", old_time)
        clipboard_history.add_entry("recent_entry", recent_time)
        removed = clipboard_history.cleanup_old_entries(days=30)
        assert removed == 1
        assert clipboard_history.size == 1

    def test_remove_duplicates(self):
        history = ClipboardHistory(dedupe_enabled=True)
        # Manually add duplicates (bypassing dedup by using _entries directly)
        entry = ClipboardEntry(
            content="dup",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("dup"),
        )
        history._entries.append(entry)
        history._entries.append(entry)
        history._hash_index[entry.content_hash] = entry
        removed = history.remove_duplicates()
        assert removed == 1

    def test_category_detection_url(self, clipboard_history):
        clipboard_history.add_entry("https://example.com")
        entry = clipboard_history.get_entries()[0]
        assert entry.category == "url"

    def test_category_detection_file_path(self, clipboard_history):
        clipboard_history.add_entry("C:\\Users\\test\\file.txt")
        entry = clipboard_history.get_entries()[0]
        assert entry.category == "file_path"

    def test_category_detection_email(self, clipboard_history):
        clipboard_history.add_entry("user@example.com")
        entry = clipboard_history.get_entries()[0]
        assert entry.category == "email"

    def test_category_detection_text(self, clipboard_history):
        clipboard_history.add_entry("just some text")
        entry = clipboard_history.get_entries()[0]
        assert entry.category == "text"

    def test_to_json_from_json_roundtrip(self, clipboard_history):
        clipboard_history.add_entry("entry1")
        clipboard_history.add_entry("entry2")
        json_str = clipboard_history.to_json()

        new_history = ClipboardHistory()
        new_history.from_json(json_str)
        assert new_history.size == 2

    def test_size_property(self, clipboard_history):
        assert clipboard_history.size == 0
        clipboard_history.add_entry("a")
        assert clipboard_history.size == 1
