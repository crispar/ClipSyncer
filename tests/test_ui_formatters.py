"""Tests for HistoryItemFormatter - the presentation helpers for entries."""

from datetime import datetime
from types import SimpleNamespace

from src.core.clipboard.history import ClipboardEntry
from src.ui.history.formatters import (
    DEFAULT_CATEGORY_DISPLAY,
    DEFAULT_CATEGORY_ICON,
    HistoryItemFormatter,
    LIST_ITEM_HEIGHT,
    PREVIEW_LENGTH,
)


def _entry(content="sample content", category="text", ts=None) -> ClipboardEntry:
    return ClipboardEntry(
        content=content,
        timestamp=ts or datetime(2024, 5, 17, 14, 30, 0),
        content_hash=ClipboardEntry.calculate_hash(content + category),
        category=category,
    )


class TestPreviewText:
    def test_preview_collapses_newlines(self):
        assert HistoryItemFormatter.preview_text("a\nb\nc") == "a b c"

    def test_preview_truncates_at_default_length(self):
        long_text = "x" * (PREVIEW_LENGTH + 25)
        preview = HistoryItemFormatter.preview_text(long_text)
        assert preview.endswith("...")
        assert len(preview) == PREVIEW_LENGTH + 3

    def test_preview_short_text_unchanged(self):
        assert HistoryItemFormatter.preview_text("short") == "short"

    def test_preview_empty_string(self):
        assert HistoryItemFormatter.preview_text("") == ""

    def test_preview_none(self):
        assert HistoryItemFormatter.preview_text(None) == ""


class TestFormatTime:
    def test_format_time_includes_hour_and_day(self):
        ts = datetime(2024, 5, 17, 14, 30, 0)
        formatted = HistoryItemFormatter.format_time(ts)
        assert "14:30" in formatted
        assert "May" in formatted
        assert "17" in formatted

    def test_format_time_none_is_empty(self):
        assert HistoryItemFormatter.format_time(None) == ""


class TestCategoryHelpers:
    def test_known_category_icons(self):
        assert HistoryItemFormatter.category_icon("text") != DEFAULT_CATEGORY_ICON
        assert HistoryItemFormatter.category_icon("url") != DEFAULT_CATEGORY_ICON
        assert HistoryItemFormatter.category_icon("file_path") != DEFAULT_CATEGORY_ICON
        assert HistoryItemFormatter.category_icon("email") != DEFAULT_CATEGORY_ICON

    def test_unknown_category_icon_fallback(self):
        assert HistoryItemFormatter.category_icon("mystery") == DEFAULT_CATEGORY_ICON

    def test_known_category_display_names(self):
        assert HistoryItemFormatter.category_display("file_path") == "File"
        assert HistoryItemFormatter.category_display("url") == "Link"

    def test_unknown_category_display_fallback(self):
        assert HistoryItemFormatter.category_display("mystery") == DEFAULT_CATEGORY_DISPLAY


class TestListItemText:
    def test_item_text_includes_preview_and_category(self):
        entry = _entry(content="Hello world", category="text")
        text = HistoryItemFormatter.list_item_text(entry)
        assert "Hello world" in text
        assert "Text" in text
        assert "11 chars" in text

    def test_item_text_tolerates_missing_attributes(self):
        entry = SimpleNamespace(content="x", timestamp=None, category=None)
        # Should not raise - format_time handles None, category falls back.
        text = HistoryItemFormatter.list_item_text(entry)
        assert "x" in text
        assert DEFAULT_CATEGORY_DISPLAY in text

    def test_list_item_height_is_positive(self):
        assert LIST_ITEM_HEIGHT > 0


class TestMetadataText:
    def test_metadata_contains_all_fields(self):
        entry = _entry(content="abc", category="file_path")
        text = HistoryItemFormatter.metadata_text(entry)

        assert "Type: File Path" in text
        assert "Time: 2024-05-17 14:30:00" in text
        assert "Size: 3 characters" in text
        assert text.count("...") == 1  # truncated ID

    def test_metadata_without_timestamp(self):
        entry = SimpleNamespace(
            content="abc", category="text", timestamp=None, content_hash=""
        )
        text = HistoryItemFormatter.metadata_text(entry)
        assert "Time:" in text
        assert "Size: 3 characters" in text
