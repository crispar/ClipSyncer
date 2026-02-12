"""Tests for ClipboardHistory and ClipboardEntry"""

import json
import threading
from datetime import datetime, timedelta
import pytest

from src.core.clipboard.history import ClipboardHistory, ClipboardEntry


class TestClipboardEntry:
    """Tests for ClipboardEntry dataclass"""

    def test_create_entry(self):
        entry = ClipboardEntry(
            content="hello",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("hello")
        )
        assert entry.content == "hello"
        assert entry.category == "text"
        assert entry.metadata == {}

    def test_hash_calculation(self):
        hash1 = ClipboardEntry.calculate_hash("hello")
        hash2 = ClipboardEntry.calculate_hash("hello")
        hash3 = ClipboardEntry.calculate_hash("world")
        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 64  # SHA-256 hex digest

    def test_auto_hash_generation(self):
        entry = ClipboardEntry(content="auto", timestamp=datetime.now(), content_hash="")
        assert entry.content_hash == ClipboardEntry.calculate_hash("auto")

    def test_to_dict(self):
        ts = datetime(2025, 1, 15, 12, 0, 0)
        entry = ClipboardEntry(
            content="test",
            timestamp=ts,
            content_hash=ClipboardEntry.calculate_hash("test"),
            category="url"
        )
        d = entry.to_dict()
        assert d['content'] == "test"
        assert d['timestamp'] == "2025-01-15T12:00:00"
        assert d['category'] == "url"

    def test_from_dict_roundtrip(self):
        original = ClipboardEntry(
            content="roundtrip",
            timestamp=datetime(2025, 6, 1, 10, 30),
            content_hash=ClipboardEntry.calculate_hash("roundtrip"),
            category="email",
            metadata={"source": "test"}
        )
        d = original.to_dict()
        restored = ClipboardEntry.from_dict(d)
        assert restored.content == original.content
        assert restored.content_hash == original.content_hash
        assert restored.category == original.category
        assert restored.metadata == original.metadata

    def test_equality(self):
        hash_val = ClipboardEntry.calculate_hash("same")
        e1 = ClipboardEntry(content="same", timestamp=datetime.now(), content_hash=hash_val)
        e2 = ClipboardEntry(content="same", timestamp=datetime.now(), content_hash=hash_val)
        e3 = ClipboardEntry(content="diff", timestamp=datetime.now(),
                            content_hash=ClipboardEntry.calculate_hash("diff"))
        assert e1 == e2
        assert e1 != e3
        assert e1 != "not an entry"


class TestClipboardHistory:
    """Tests for ClipboardHistory"""

    def test_add_entry(self, clipboard_history):
        added, removed = clipboard_history.add_entry("hello world")
        assert added is True
        assert removed is None
        assert clipboard_history.size == 1

    def test_add_empty_content(self, clipboard_history):
        added, removed = clipboard_history.add_entry("")
        assert added is False
        assert clipboard_history.size == 0

    def test_add_none_content(self, clipboard_history):
        added, removed = clipboard_history.add_entry(None)
        assert added is False

    def test_newest_first_ordering(self, clipboard_history):
        clipboard_history.add_entry("first")
        clipboard_history.add_entry("second")
        clipboard_history.add_entry("third")
        entries = clipboard_history.get_entries()
        assert entries[0].content == "third"
        assert entries[1].content == "second"
        assert entries[2].content == "first"

    def test_duplicate_detection(self, clipboard_history):
        added1, _ = clipboard_history.add_entry("duplicate")
        added2, _ = clipboard_history.add_entry("duplicate")
        assert added1 is True
        assert added2 is False  # duplicate
        assert clipboard_history.size == 1

    def test_duplicate_moves_to_top(self, clipboard_history):
        clipboard_history.add_entry("first")
        clipboard_history.add_entry("second")
        clipboard_history.add_entry("first")  # re-add duplicate
        entries = clipboard_history.get_entries()
        assert entries[0].content == "first"  # moved to top
        assert entries[1].content == "second"

    def test_max_size_enforcement(self):
        history = ClipboardHistory(max_size=3, dedupe_enabled=True)
        for i in range(5):
            history.add_entry(f"entry_{i}")
        assert history.size == 3
        entries = history.get_entries()
        # Newest entries should be kept
        assert entries[0].content == "entry_4"
        assert entries[2].content == "entry_2"

    def test_max_size_returns_removed_entry(self):
        history = ClipboardHistory(max_size=2)
        history.add_entry("keep1")
        history.add_entry("keep2")
        added, removed = history.add_entry("new")
        assert added is True
        assert removed is not None
        assert removed.content == "keep1"  # oldest removed

    def test_get_entries_with_limit(self, clipboard_history):
        for i in range(5):
            clipboard_history.add_entry(f"entry_{i}")
        limited = clipboard_history.get_entries(limit=2)
        assert len(limited) == 2

    def test_search_case_insensitive(self, clipboard_history):
        clipboard_history.add_entry("Hello World")
        clipboard_history.add_entry("goodbye world")
        clipboard_history.add_entry("no match")
        results = clipboard_history.search("hello")
        assert len(results) == 1
        assert results[0].content == "Hello World"

    def test_search_case_sensitive(self, clipboard_history):
        clipboard_history.add_entry("Hello World")
        clipboard_history.add_entry("hello world")
        results = clipboard_history.search("Hello", case_sensitive=True)
        assert len(results) == 1
        assert results[0].content == "Hello World"

    def test_search_partial_match(self, clipboard_history):
        clipboard_history.add_entry("Hello World")
        clipboard_history.add_entry("World Peace")
        results = clipboard_history.search("world")
        assert len(results) == 2

    def test_clear(self, clipboard_history):
        clipboard_history.add_entry("entry1")
        clipboard_history.add_entry("entry2")
        clipboard_history.clear()
        assert clipboard_history.size == 0
        assert clipboard_history.get_entries() == []

    def test_remove_duplicates(self):
        """With dedup disabled, duplicates can exist. remove_duplicates should clean them."""
        # Dedup is disabled so duplicates are allowed
        # But remove_duplicates only works when dedupe_enabled is True
        # So we manually create a history with duplicates
        history = ClipboardHistory(max_size=100, dedupe_enabled=True)
        # Force duplicates by directly manipulating internal state
        entry = ClipboardEntry(
            content="dup",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("dup")
        )
        entry2 = ClipboardEntry(
            content="dup",
            timestamp=datetime.now() - timedelta(hours=1),
            content_hash=ClipboardEntry.calculate_hash("dup")
        )
        history._entries = [entry, entry2]
        history._hash_index = {entry.content_hash: entry}
        removed = history.remove_duplicates()
        assert removed == 1
        assert len(history._entries) == 1

    def test_cleanup_old_entries(self, clipboard_history):
        now = datetime.now()
        clipboard_history.add_entry("recent")
        # Manually add old entry
        old_entry = ClipboardEntry(
            content="old",
            timestamp=now - timedelta(days=60),
            content_hash=ClipboardEntry.calculate_hash("old")
        )
        clipboard_history._entries.append(old_entry)
        clipboard_history._hash_index[old_entry.content_hash] = old_entry

        removed = clipboard_history.cleanup_old_entries(days=30)
        assert removed == 1
        assert clipboard_history.size == 1
        assert clipboard_history.get_entries()[0].content == "recent"

    def test_import_entry(self, clipboard_history):
        entry = ClipboardEntry(
            content="imported",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("imported")
        )
        result = clipboard_history.import_entry(entry)
        assert result is True
        assert clipboard_history.size == 1

    def test_import_duplicate_rejected(self, clipboard_history):
        clipboard_history.add_entry("exists")
        entry = ClipboardEntry(
            content="exists",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("exists")
        )
        result = clipboard_history.import_entry(entry)
        assert result is False
        assert clipboard_history.size == 1

    def test_import_entry_none(self, clipboard_history):
        assert clipboard_history.import_entry(None) is False

    def test_import_entry_no_hash(self, clipboard_history):
        entry = ClipboardEntry(content="x", timestamp=datetime.now(), content_hash="")
        # content_hash will be auto-generated in __post_init__
        result = clipboard_history.import_entry(entry)
        assert result is True

    def test_import_entry_respects_max_size(self):
        history = ClipboardHistory(max_size=2)
        history.add_entry("first")
        history.add_entry("second")
        entry = ClipboardEntry(
            content="third_import",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("third_import")
        )
        result = history.import_entry(entry)
        assert result is True
        assert history.size == 2
        # import_entry appends to end and pops from front when over max
        entries = history.get_entries()
        contents = [e.content for e in entries]
        assert "third_import" in contents

    def test_import_entry_added_to_history(self):
        history = ClipboardHistory(max_size=10)
        history.add_entry("existing")
        entry = ClipboardEntry(
            content="imported",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("imported")
        )
        history.import_entry(entry)
        assert history.size == 2
        # import_entry appends to end of internal list
        entries = history.get_entries()
        contents = [e.content for e in entries]
        assert "imported" in contents
        assert "existing" in contents

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
        clipboard_history.add_entry("check this")
        h = ClipboardEntry.calculate_hash("check this")
        assert clipboard_history.has_entry(h) is True
        assert clipboard_history.has_entry("nonexistent") is False

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
        clipboard_history.add_entry("just plain text")
        entry = clipboard_history.get_entries()[0]
        assert entry.category == "text"

    def test_to_json(self, clipboard_history):
        clipboard_history.add_entry("json test")
        json_str = clipboard_history.to_json()
        data = json.loads(json_str)
        assert 'entries' in data
        assert len(data['entries']) == 1
        assert data['entries'][0]['content'] == "json test"

    def test_from_json(self, clipboard_history):
        clipboard_history.add_entry("entry1")
        clipboard_history.add_entry("entry2")
        json_str = clipboard_history.to_json()

        new_history = ClipboardHistory()
        new_history.from_json(json_str)
        assert new_history.size == 2

    def test_thread_safety_concurrent_adds(self):
        """Test that concurrent adds don't corrupt state"""
        history = ClipboardHistory(max_size=500)
        errors = []

        def add_entries(start, count):
            try:
                for i in range(count):
                    history.add_entry(f"thread_{start}_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_entries, args=(t, 50)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert history.size == 250  # 5 threads * 50 entries
