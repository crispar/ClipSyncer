"""Tests for ClipboardEntry dataclass"""

import pytest
from datetime import datetime
from src.core.clipboard.history import ClipboardEntry


class TestClipboardEntry:
    """Tests for ClipboardEntry"""

    def test_create_entry(self):
        entry = ClipboardEntry(
            content="test content",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("test content"),
        )
        assert entry.content == "test content"
        assert entry.category == "text"
        assert entry.metadata == {}

    def test_auto_hash_if_empty(self):
        entry = ClipboardEntry(
            content="hello",
            timestamp=datetime.now(),
            content_hash="",
        )
        assert entry.content_hash == ClipboardEntry.calculate_hash("hello")

    def test_calculate_hash_deterministic(self):
        h1 = ClipboardEntry.calculate_hash("same content")
        h2 = ClipboardEntry.calculate_hash("same content")
        assert h1 == h2

    def test_calculate_hash_different_for_different_content(self):
        h1 = ClipboardEntry.calculate_hash("content A")
        h2 = ClipboardEntry.calculate_hash("content B")
        assert h1 != h2

    def test_to_dict(self):
        ts = datetime(2024, 6, 15, 10, 30, 0)
        entry = ClipboardEntry(
            content="test",
            timestamp=ts,
            content_hash="abc123",
            category="url",
            metadata={"source": "browser"}
        )
        d = entry.to_dict()
        assert d['content'] == "test"
        assert d['timestamp'] == ts.isoformat()
        assert d['content_hash'] == "abc123"
        assert d['category'] == "url"
        assert d['metadata'] == {"source": "browser"}

    def test_from_dict(self):
        data = {
            'content': "hello",
            'timestamp': "2024-06-15T10:30:00",
            'content_hash': "abc",
            'category': "text",
            'metadata': {}
        }
        entry = ClipboardEntry.from_dict(data)
        assert entry.content == "hello"
        assert entry.timestamp == datetime(2024, 6, 15, 10, 30, 0)
        assert entry.content_hash == "abc"

    def test_from_dict_does_not_mutate_input(self):
        data = {
            'content': "hello",
            'timestamp': "2024-06-15T10:30:00",
            'content_hash': "abc",
            'category': "text",
        }
        original_data = data.copy()
        ClipboardEntry.from_dict(data)
        assert data == original_data

    def test_from_dict_filters_unknown_keys(self):
        data = {
            'content': "hello",
            'timestamp': "2024-06-15T10:30:00",
            'content_hash': "abc",
            'category': "text",
            'unknown_field': "should be ignored"
        }
        entry = ClipboardEntry.from_dict(data)
        assert entry.content == "hello"
        assert not hasattr(entry, 'unknown_field')

    def test_equality_by_hash(self):
        e1 = ClipboardEntry(content="a", timestamp=datetime.now(), content_hash="hash1")
        e2 = ClipboardEntry(content="b", timestamp=datetime.now(), content_hash="hash1")
        e3 = ClipboardEntry(content="a", timestamp=datetime.now(), content_hash="hash2")
        assert e1 == e2
        assert e1 != e3

    def test_equality_with_non_entry(self):
        entry = ClipboardEntry(content="a", timestamp=datetime.now(), content_hash="h")
        assert entry != "not an entry"
        assert entry != 42

    def test_roundtrip_to_dict_from_dict(self):
        original = ClipboardEntry(
            content="roundtrip test",
            timestamp=datetime(2024, 1, 1, 0, 0, 0),
            content_hash=ClipboardEntry.calculate_hash("roundtrip test"),
            category="email",
            metadata={"key": "value"}
        )
        d = original.to_dict()
        restored = ClipboardEntry.from_dict(d)
        assert restored.content == original.content
        assert restored.content_hash == original.content_hash
        assert restored.category == original.category
        assert restored.metadata == original.metadata
