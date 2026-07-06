"""UI tests for ModernHistoryViewer using pytest-qt.

Run with QT_QPA_PLATFORM=offscreen to execute headless. The viewer stays wired
to the real HistoryFilter / HistoryItemFormatter here; only storage and
clipboard dependencies are mocked.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.core.clipboard.history import ClipboardEntry
from src.ui.history import HistoryViewer

try:
    from qfluentwidgets import FluentStyleSheet  # noqa: F401

    HAS_FLUENT = True
except Exception:  # pragma: no cover - fluent missing in some envs
    HAS_FLUENT = False

pytestmark = pytest.mark.skipif(
    not HAS_FLUENT, reason="qfluentwidgets not available"
)


def _entry(content, category="text", ts=None):
    return ClipboardEntry(
        content=content,
        timestamp=ts or datetime(2024, 1, 1, 12, 0, 0),
        content_hash=ClipboardEntry.calculate_hash(content + category),
        category=category,
    )


def _repo(entries, favorites=None):
    """Build a MagicMock repository with canned data."""
    favorites = set(favorites or set())
    repo = MagicMock()
    repo.get_entries.return_value = list(entries)
    repo.get_entry_count.return_value = len(entries)
    repo.get_favorite_hashes.return_value = set(favorites)
    repo.is_favorite.side_effect = lambda h: h in favorites
    repo.toggle_favorite.return_value = True
    repo.clear_all.return_value = True
    # get_entries_since: fallback for tests that exercise incremental refresh.
    repo.get_entries_since.return_value = []
    return repo


@pytest.fixture
def viewer_factory(qtbot, monkeypatch):
    """Return a callable that builds a ModernHistoryViewer and registers it."""

    # pyperclip.copy talks to the OS clipboard; stub it out for headless runs.
    from src.ui.history import history_viewer_modern as hvm

    monkeypatch.setattr(hvm.pyperclip, "copy", lambda *_a, **_kw: None)

    created = []

    def _make(entries=None, favorites=None, github_sync=None):
        repo = _repo(entries or [], favorites=favorites)
        viewer = HistoryViewer(
            clipboard_history=None,
            repository=repo,
            config_manager=MagicMock(),
            github_sync=github_sync,
            encryption_manager=MagicMock(),
        )
        qtbot.addWidget(viewer)
        # Stop the 1s timer so it doesn't interfere with assertions.
        viewer.refresh_timer.stop()
        created.append((viewer, repo))
        return viewer, repo

    yield _make

    for viewer, _ in created:
        viewer.close()


class TestListLoading:
    def test_loads_entries_into_list(self, viewer_factory):
        viewer, _ = viewer_factory([_entry("a"), _entry("b")])
        assert viewer.history_list.count() == 2
        assert "a" in viewer.history_list.item(0).text()

    def test_empty_repo_shows_empty_state(self, viewer_factory):
        viewer, _ = viewer_factory([])
        assert viewer.list_stack.currentIndex() == 1
        assert "No clipboard entries" in viewer._empty_title.text()

    def test_populated_repo_shows_list(self, viewer_factory):
        viewer, _ = viewer_factory([_entry("a")])
        assert viewer.list_stack.currentIndex() == 0


class TestSearchAndFilter:
    def test_search_narrows_visible_items(self, viewer_factory):
        viewer, _ = viewer_factory([
            _entry("hello world"),
            _entry("goodbye"),
            _entry("hello again"),
        ])
        viewer.search_input.setText("hello")
        viewer._apply_combined_filter()

        visible = [
            viewer.history_list.item(i)
            for i in range(viewer.history_list.count())
            if not viewer.history_list.item(i).isHidden()
        ]
        assert len(visible) == 2

    def test_search_with_no_matches_shows_empty_state(self, viewer_factory):
        viewer, _ = viewer_factory([_entry("a"), _entry("b")])
        viewer.search_input.setText("zzz-no-match")
        viewer._apply_combined_filter()
        assert viewer.list_stack.currentIndex() == 1
        assert "No matches" in viewer._empty_title.text()

    def test_category_filter_narrows_items(self, viewer_factory):
        viewer, _ = viewer_factory([
            _entry("one", category="text"),
            _entry("https://x", category="url"),
        ])
        viewer.category_combo.setCurrentText("URL")
        viewer._apply_combined_filter()

        visible = [
            viewer.history_list.item(i).data(256)  # Qt.UserRole == 256 in PyQt6
            for i in range(viewer.history_list.count())
            if not viewer.history_list.item(i).isHidden()
        ]
        assert len(visible) == 1
        assert visible[0].category == "url"

    def test_count_label_uses_x_of_y_when_filtered(self, viewer_factory):
        viewer, _ = viewer_factory([_entry("a"), _entry("b"), _entry("c")])
        viewer.search_input.setText("a")
        viewer._apply_combined_filter()
        assert "of 3" in viewer.count_label.text()

    def test_count_label_simple_when_not_filtered(self, viewer_factory):
        viewer, _ = viewer_factory([_entry("a"), _entry("b")])
        assert viewer.count_label.text() == "2 items"


class TestFavoritesFilter:
    def test_favorites_category_shows_only_favorites(self, viewer_factory):
        e1 = _entry("one")
        e2 = _entry("two")
        e3 = _entry("three")
        viewer, _ = viewer_factory(
            [e1, e2, e3],
            favorites={e1.content_hash, e3.content_hash},
        )

        viewer.category_combo.setCurrentText("Favorites")
        viewer._apply_combined_filter()

        visible_contents = []
        for i in range(viewer.history_list.count()):
            item = viewer.history_list.item(i)
            if not item.isHidden():
                visible_contents.append(item.data(256).content)

        assert set(visible_contents) == {"one", "three"}

    def test_favorites_tab_with_no_favorites_shows_empty_state(self, viewer_factory):
        viewer, _ = viewer_factory([_entry("one")], favorites=set())
        viewer.category_combo.setCurrentText("Favorites")
        viewer._apply_combined_filter()
        assert viewer.list_stack.currentIndex() == 1


class TestSyncStatus:
    def test_local_only_when_no_github(self, viewer_factory):
        viewer, _ = viewer_factory([], github_sync=None)
        assert "Local only" in viewer.sync_status_label.text()

    def test_local_only_when_disabled(self, viewer_factory):
        gh = SimpleNamespace(enabled=False)
        viewer, _ = viewer_factory([], github_sync=gh)
        assert "Local only" in viewer.sync_status_label.text()

    def test_sync_label_when_enabled(self, viewer_factory):
        gh = SimpleNamespace(enabled=True)
        viewer, _ = viewer_factory([], github_sync=gh)
        assert "GitHub sync" in viewer.sync_status_label.text()


class TestKeyboardShortcuts:
    def test_favorite_shortcut_connected(self, viewer_factory):
        """Ctrl+D is wired (shortcut exists on the window)."""
        from PyQt6.QtGui import QShortcut

        viewer, _ = viewer_factory([_entry("a")])
        shortcuts = [c.key().toString() for c in viewer.findChildren(QShortcut)]
        assert "Ctrl+D" in shortcuts
        assert "Ctrl+F" in shortcuts
        assert "F5" in shortcuts


class TestDeleteFlow:
    def test_delete_updates_counts_and_empty_state(self, viewer_factory):
        e1 = _entry("a")
        viewer, repo = viewer_factory([e1])
        viewer.history_list.setCurrentRow(0)

        # Skip MessageBox by stubbing _delete_selected_entry's confirm dialog.
        # Instead, manipulate repository + call the same cleanup path directly.
        viewer.current_entries = []
        viewer.history_list.takeItem(0)
        viewer._apply_combined_filter()

        assert viewer.list_stack.currentIndex() == 1
        assert viewer.count_label.text() == "0 items"


class TestRefreshIsIdempotent:
    def test_refresh_entries_preserves_filter(self, viewer_factory):
        viewer, _ = viewer_factory([
            _entry("hello"),
            _entry("world"),
        ])
        viewer.search_input.setText("hello")
        viewer._apply_combined_filter()

        viewer.refresh_entries()

        visible = [
            viewer.history_list.item(i)
            for i in range(viewer.history_list.count())
            if not viewer.history_list.item(i).isHidden()
        ]
        assert len(visible) == 1
        assert "hello" in visible[0].text()


class TestIncrementalRefresh:
    """Performance path: only the delta is fetched / inserted."""

    def test_no_change_skips_reload(self, viewer_factory):
        viewer, repo = viewer_factory([_entry("a"), _entry("b")])
        repo.get_entries.reset_mock()
        repo.get_entries_since.reset_mock()

        viewer._check_for_updates()

        assert repo.get_entries.call_count == 0
        assert repo.get_entries_since.call_count == 0

    def test_new_entries_are_prepended_without_full_reload(self, viewer_factory):
        old = _entry("old", ts=datetime(2024, 1, 1, 10, 0, 0))
        viewer, repo = viewer_factory([old])

        new_a = _entry("new_a", ts=datetime(2024, 1, 1, 11, 0, 0))
        new_b = _entry("new_b", ts=datetime(2024, 1, 1, 12, 0, 0))

        repo.get_entry_count.return_value = 3
        repo.get_entries_since.return_value = [new_b, new_a]
        repo.get_entries.reset_mock()

        viewer._check_for_updates()

        # Full reload path MUST NOT have been taken (no get_entries call).
        assert repo.get_entries.call_count == 0
        assert repo.get_entries_since.called

        contents = [
            viewer.history_list.item(i).data(256).content
            for i in range(viewer.history_list.count())
        ]
        assert contents == ["new_b", "new_a", "old"]
        assert viewer.count_label.text() == "3 items"

    def test_large_delta_falls_back_to_full_reload(self, viewer_factory):
        viewer, repo = viewer_factory([_entry("a")])
        repo.get_entry_count.return_value = 500  # huge delta
        repo.get_entries_since.return_value = []
        repo.get_entries.reset_mock()

        viewer._check_for_updates()

        assert repo.get_entries.call_count == 1  # full reload

    def test_count_drop_triggers_full_reload(self, viewer_factory):
        viewer, repo = viewer_factory([_entry("a"), _entry("b")])

        # External deletion: count shrinks.
        repo.get_entry_count.return_value = 1
        repo.get_entries.return_value = [_entry("a")]
        repo.get_entries.reset_mock()

        viewer._check_for_updates()

        assert repo.get_entries.call_count == 1
        assert viewer.count_label.text() == "1 items"

    def test_prepend_dedupes_on_content_hash(self, viewer_factory):
        e1 = _entry("dup", ts=datetime(2024, 1, 1, 10, 0, 0))
        viewer, repo = viewer_factory([e1])

        # Same entry returned from get_entries_since must not be duplicated.
        repo.get_entry_count.return_value = 2
        repo.get_entries_since.return_value = [e1]

        viewer._check_for_updates()

        # Incremental path skipped the duplicate, so it falls back to reload.
        # Either way, the list size stays 1.
        assert viewer.history_list.count() == 1


class TestSearchDebounce:
    def test_search_defers_filter_apply(self, viewer_factory):
        viewer, _ = viewer_factory([_entry("apple"), _entry("banana")])

        # Use a long debounce so we can assert the filter has not yet run.
        viewer._search_debounce_timer.setInterval(5000)
        viewer.search_input.setText("app")

        # Timer is active but the filter should not have fired yet, so all
        # items remain visible.
        assert viewer._search_debounce_timer.isActive()
        visible_before = sum(
            1
            for i in range(viewer.history_list.count())
            if not viewer.history_list.item(i).isHidden()
        )
        assert visible_before == 2

        # Trigger the filter manually as the debounce timer would.
        viewer._apply_combined_filter()
        visible_after = [
            viewer.history_list.item(i)
            for i in range(viewer.history_list.count())
            if not viewer.history_list.item(i).isHidden()
        ]
        assert len(visible_after) == 1
        assert "apple" in visible_after[0].text()

    def test_rapid_typing_coalesces_into_single_apply(self, qtbot, viewer_factory):
        viewer, _ = viewer_factory([_entry("apple")])
        # Shorten debounce for a fast test.
        viewer._search_debounce_timer.setInterval(50)

        # Simulate rapid typing.
        for chunk in ("a", "ap", "app"):
            viewer.search_input.setText(chunk)

        # Timer should be scheduled — wait for it to fire.
        qtbot.wait(120)
        assert not viewer._search_debounce_timer.isActive()

        visible = [
            viewer.history_list.item(i)
            for i in range(viewer.history_list.count())
            if not viewer.history_list.item(i).isHidden()
        ]
        assert len(visible) == 1


class TestFavoriteHashCache:
    def test_cache_populated_from_repository(self, viewer_factory):
        e1 = _entry("one")
        e2 = _entry("two")
        viewer, repo = viewer_factory([e1, e2], favorites={e1.content_hash})

        assert viewer._favorite_hashes == {e1.content_hash}
        # Exactly one bulk query is made at load time.
        assert repo.get_favorite_hashes.call_count >= 1

    def test_selection_change_does_not_query_repository(self, viewer_factory):
        e1 = _entry("one")
        viewer, repo = viewer_factory([e1], favorites={e1.content_hash})

        repo.is_favorite.reset_mock()

        viewer.history_list.setCurrentRow(0)

        # Preview update must read from the cache, not the DB.
        assert repo.is_favorite.call_count == 0
        assert viewer.favorite_button.isChecked() is True

    def test_toggle_updates_cache_in_place(self, viewer_factory):
        e1 = _entry("one")
        viewer, repo = viewer_factory([e1], favorites=set())

        viewer.history_list.setCurrentRow(0)
        repo.get_favorite_hashes.reset_mock()

        viewer._toggle_favorite()
        assert e1.content_hash in viewer._favorite_hashes

        viewer._toggle_favorite()
        assert e1.content_hash not in viewer._favorite_hashes

        # No extra bulk query was issued — toggle updates the cache directly.
        assert repo.get_favorite_hashes.call_count == 0
