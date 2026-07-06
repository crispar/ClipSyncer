"""Pure-Python presentation helpers for clipboard history entries.

Centralises every string shown in the history list / preview so it can be
tested without instantiating Qt widgets.
"""

from datetime import datetime
from typing import Optional

CATEGORY_ICONS = {
    "text": "\U0001F4DD",
    "url": "\U0001F310",
    "file_path": "\U0001F4C1",
    "email": "\u2709\ufe0f",
}
DEFAULT_CATEGORY_ICON = "\U0001F4CB"

CATEGORY_DISPLAY_NAMES = {
    "text": "Text",
    "url": "Link",
    "file_path": "File",
    "email": "Email",
}
DEFAULT_CATEGORY_DISPLAY = "Other"

PREVIEW_LENGTH = 80
LIST_ITEM_HEIGHT = 75


class HistoryItemFormatter:
    """Format a `ClipboardEntry` for display in list / preview widgets."""

    @staticmethod
    def preview_text(content: str, length: int = PREVIEW_LENGTH) -> str:
        """One-line preview: newlines collapsed, truncated with ellipsis."""
        flat = (content or "").replace("\n", " ")
        if len(flat) > length:
            return flat[:length] + "..."
        return flat

    @staticmethod
    def format_time(timestamp: Optional[datetime]) -> str:
        if timestamp is None:
            return ""
        return timestamp.strftime("%H:%M \u00b7 %b %d")

    @staticmethod
    def category_icon(category: str) -> str:
        return CATEGORY_ICONS.get(category, DEFAULT_CATEGORY_ICON)

    @staticmethod
    def category_display(category: str) -> str:
        return CATEGORY_DISPLAY_NAMES.get(category, DEFAULT_CATEGORY_DISPLAY)

    @classmethod
    def list_item_text(cls, entry) -> str:
        """Text shown for a list item: icon + time / preview / category + size."""
        icon = cls.category_icon(getattr(entry, "category", "text"))
        time_str = cls.format_time(getattr(entry, "timestamp", None))
        preview = cls.preview_text(getattr(entry, "content", ""))
        category_name = cls.category_display(getattr(entry, "category", "text"))
        char_count = len(getattr(entry, "content", "") or "")
        return f"{icon} {time_str}\n{preview}\n{category_name} \u00b7 {char_count} chars"

    @classmethod
    def metadata_text(cls, entry) -> str:
        """One-line metadata string shown in the preview footer."""
        category_raw = getattr(entry, "category", "text") or "text"
        category_human = category_raw.replace("_", " ").title()
        ts = getattr(entry, "timestamp", None)
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        size = len(getattr(entry, "content", "") or "")
        entry_hash = getattr(entry, "content_hash", "") or ""
        id_str = f"{entry_hash[:16]}..." if entry_hash else ""
        parts = [
            f"Type: {category_human}",
            f"Time: {ts_str}",
            f"Size: {size} characters",
            f"ID: {id_str}",
        ]
        return " \u00b7 ".join(parts)
