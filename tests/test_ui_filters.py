"""Tests for the Qt-free HistoryFilter used by the history viewer.

These cover the contract of the filter independent of any widget so UI
behaviour can be validated in pure Python CI runs.
"""

from datetime import datetime

import pytest

from src.core.clipboard.history import ClipboardEntry
from src.ui.history.filters import (
    CATEGORY_LABELS,
    CATEGORY_LABEL_TO_INTERNAL,
    FAVORITES_LABEL,
    HistoryFilter,
)


def _entry(content: str, category: str = "text") -> ClipboardEntry:
    return ClipboardEntry(
        content=content,
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        content_hash=ClipboardEntry.calculate_hash(content + category),
        category=category,
    )


@pytest.fixture
def sample_entries():
    return [
        _entry("Hello world", "text"),
        _entry("https://example.com", "url"),
        _entry("C:\\Users\\me\\file.txt", "file_path"),
        _entry("user@example.com", "email"),
        _entry("Another plain text entry", "text"),
    ]


class TestCategoryLabels:
    def test_labels_contain_all_and_favorites_first(self):
        assert CATEGORY_LABELS[0] == "All"
        assert FAVORITES_LABEL in CATEGORY_LABELS

    def test_every_label_maps_to_internal(self):
        for label in CATEGORY_LABELS:
            assert label in CATEGORY_LABEL_TO_INTERNAL

    def test_all_label_maps_to_none(self):
        assert CATEGORY_LABEL_TO_INTERNAL["All"] is None


class TestHistoryFilterBasic:
    def test_no_criteria_returns_all(self, sample_entries):
        result = HistoryFilter().apply(sample_entries)
        assert result == sample_entries

    def test_search_is_case_insensitive(self, sample_entries):
        result = HistoryFilter().apply(sample_entries, search_text="HELLO")
        assert len(result) == 1
        assert result[0].content == "Hello world"

    def test_search_substring_matches_multiple(self, sample_entries):
        result = HistoryFilter().apply(sample_entries, search_text="example")
        contents = [e.content for e in result]
        assert "https://example.com" in contents
        assert "user@example.com" in contents
        assert len(result) == 2

    def test_search_with_no_match(self, sample_entries):
        result = HistoryFilter().apply(sample_entries, search_text="nonexistent-xyz")
        assert result == []

    def test_whitespace_only_search_returns_all(self, sample_entries):
        result = HistoryFilter().apply(sample_entries, search_text="   ")
        assert result == sample_entries

    def test_category_filter_single(self, sample_entries):
        result = HistoryFilter().apply(sample_entries, category_label="URL")
        assert len(result) == 1
        assert result[0].category == "url"

    def test_category_filter_file_path(self, sample_entries):
        result = HistoryFilter().apply(sample_entries, category_label="File Path")
        assert len(result) == 1
        assert result[0].category == "file_path"

    def test_category_all_returns_all(self, sample_entries):
        result = HistoryFilter().apply(sample_entries, category_label="All")
        assert result == sample_entries

    def test_unknown_category_falls_back_to_all(self, sample_entries):
        result = HistoryFilter().apply(sample_entries, category_label="Nope")
        assert result == sample_entries

    def test_search_and_category_combined(self, sample_entries):
        result = HistoryFilter().apply(
            sample_entries, search_text="text", category_label="Text"
        )
        assert len(result) == 1
        assert result[0].content == "Another plain text entry"

    def test_none_entry_is_skipped(self, sample_entries):
        entries = [None] + sample_entries + [None]
        result = HistoryFilter().apply(entries)
        assert result == sample_entries

    def test_empty_input_returns_empty(self):
        assert HistoryFilter().apply([]) == []


class TestHistoryFilterFavorites:
    def test_favorites_filter_without_resolver_returns_empty(self, sample_entries):
        result = HistoryFilter().apply(sample_entries, category_label="Favorites")
        assert result == []

    def test_favorites_filter_uses_resolver(self, sample_entries):
        starred = {sample_entries[0].content_hash, sample_entries[3].content_hash}

        f = HistoryFilter(favorite_resolver=lambda h: h in starred)
        result = f.apply(sample_entries, category_label="Favorites")

        assert {e.content_hash for e in result} == starred

    def test_favorites_with_search(self, sample_entries):
        # Mark every entry as favorite; search narrows it down.
        f = HistoryFilter(favorite_resolver=lambda _h: True)
        result = f.apply(
            sample_entries, search_text="example", category_label="Favorites"
        )
        contents = [e.content for e in result]
        assert "https://example.com" in contents
        assert "user@example.com" in contents
        assert len(result) == 2

    def test_set_favorite_resolver_updates_behaviour(self, sample_entries):
        f = HistoryFilter()
        assert f.apply(sample_entries, category_label="Favorites") == []

        f.set_favorite_resolver(lambda _h: True)
        assert len(f.apply(sample_entries, category_label="Favorites")) == len(
            sample_entries
        )

        # Resetting to None is safe and falls back to "no favorites".
        f.set_favorite_resolver(None)
        assert f.apply(sample_entries, category_label="Favorites") == []

    def test_favorites_resolver_exception_propagates(self, sample_entries):
        def boom(_h):
            raise RuntimeError("db down")

        f = HistoryFilter(favorite_resolver=boom)
        with pytest.raises(RuntimeError):
            f.apply(sample_entries, category_label="Favorites")
