"""Pure-Python filter logic for clipboard history.

Kept Qt-free so it can be exercised by unit tests without an event loop.
"""

from typing import Callable, Iterable, List, Optional

# Display labels shown in the category combo box mapped to the internal
# category value persisted on each `ClipboardEntry`. `None` means no
# category constraint; the sentinel `__favorites__` requests favorites-only.
CATEGORY_LABEL_TO_INTERNAL = {
    "All": None,
    "Favorites": "__favorites__",
    "Text": "text",
    "URL": "url",
    "File Path": "file_path",
    "Email": "email",
}

CATEGORY_LABELS: List[str] = list(CATEGORY_LABEL_TO_INTERNAL.keys())

FAVORITES_LABEL = "Favorites"


class HistoryFilter:
    """Apply search text and category filter to a list of clipboard entries.

    The filter is intentionally stateless: callers pass current entries and
    filter criteria, and receive a filtered list. Favorite membership is
    looked up through an injected resolver so this module stays free of any
    storage dependency.
    """

    def __init__(self, favorite_resolver: Optional[Callable[[str], bool]] = None):
        self._favorite_resolver = favorite_resolver or (lambda _hash: False)

    def set_favorite_resolver(self, resolver: Callable[[str], bool]) -> None:
        self._favorite_resolver = resolver or (lambda _hash: False)

    def apply(
        self,
        entries: Iterable,
        search_text: str = "",
        category_label: str = "All",
    ) -> List:
        """Return entries that match both the search text and category label.

        - search_text is case-insensitive substring match on `entry.content`.
        - category_label must be one of CATEGORY_LABELS; unknown labels fall
          back to "All" to keep the UI resilient to stale state.
        """
        query = (search_text or "").strip().lower()
        internal = CATEGORY_LABEL_TO_INTERNAL.get(category_label, None)

        results = []
        for entry in entries:
            if entry is None:
                continue

            content = getattr(entry, "content", "") or ""
            if query and query not in content.lower():
                continue

            if internal is None:
                pass
            elif internal == "__favorites__":
                entry_hash = getattr(entry, "content_hash", "") or ""
                if not self._favorite_resolver(entry_hash):
                    continue
            else:
                if getattr(entry, "category", None) != internal:
                    continue

            results.append(entry)

        return results
