"""Modern history viewer with Windows 11 Fluent Design using PyQt6-Fluent-Widgets"""

import sys
import pyperclip
from typing import Optional, List
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QListWidgetItem, QLabel, QSplitter, QStackedWidget
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QFont, QShortcut, QKeySequence

# Import Fluent Design components
from qfluentwidgets import (
    ListWidget, TextEdit, PushButton, LineEdit,
    ComboBox, ToolButton, InfoBar, InfoBarPosition, Theme,
    setTheme, isDarkTheme, FluentIcon as FIF, SearchLineEdit,
    CardWidget, BodyLabel, SubtitleLabel, TitleLabel, CaptionLabel,
    TransparentToolButton, PrimaryPushButton, ToggleButton,
    MessageBox, Dialog, StateToolTip, setThemeColor,
    FluentStyleSheet, RoundMenu, Action
)
from loguru import logger

from .filters import HistoryFilter, CATEGORY_LABELS, FAVORITES_LABEL
from .formatters import HistoryItemFormatter, LIST_ITEM_HEIGHT


class ModernHistoryViewer(QMainWindow):
    """Modern history viewer window with Windows 11 Fluent Design"""

    def __init__(self, clipboard_history=None, repository=None, config_manager=None,
                 github_sync=None, encryption_manager=None,
                 on_github_settings_changed=None):
        """
        Initialize history viewer

        Args:
            clipboard_history: ClipboardHistory instance
            repository: ClipboardRepository instance
            config_manager: ConfigManager instance for settings reload
            github_sync: GitHubSyncService instance (for restore)
            encryption_manager: EncryptionManager instance (for restore)
            on_github_settings_changed: Callback(settings_dict) when GitHub settings change
        """
        super().__init__()
        self.clipboard_history = clipboard_history
        self.repository = repository
        self.config_manager = config_manager
        self.github_sync = github_sync
        self.encryption_manager = encryption_manager
        self._on_github_settings_changed = on_github_settings_changed
        self.current_entries = []
        self.last_entry_count = 0
        # Newest timestamp currently displayed; powers incremental refresh so
        # `_check_for_updates` only decrypts rows added after this point.
        self._last_seen_timestamp = None
        # In-memory mirror of favorite content_hashes; refreshed from the
        # repository on full reload / toggle so the list filter and preview
        # panel don't round-trip to the DB on every repaint.
        self._favorite_hashes: set = set()

        # Filter helper keeps search/category logic Qt-free and reusable from tests.
        self._filter = HistoryFilter(favorite_resolver=self._is_favorite_for_filter)

        # Set window properties
        self.setWindowTitle("Clipboard History")
        self.resize(1100, 750)

        # Apply Fluent Design theme
        self._setup_theme()

        self._init_ui()
        self._load_entries()

        # Debounce timer for the search box so we don't re-walk the list
        # on every keystroke while the user is still typing.
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(150)
        self._search_debounce_timer.timeout.connect(self._apply_combined_filter)

        # Setup auto-refresh timer (check every 1 second)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._check_for_updates)
        self.refresh_timer.start(1000)  # Check every second

    def _setup_theme(self):
        """Setup Fluent Design theme"""
        # Auto-detect and apply system theme
        if isDarkTheme():
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.LIGHT)

        # Set accent color (Windows 11 blue)
        setThemeColor("#0078D4")

        # Apply Fluent stylesheet to the window
        FluentStyleSheet.FLUENT_WINDOW.apply(self)

    def _init_ui(self):
        """Initialize modern UI with Fluent Design"""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Apply card-like background
        central_widget.setObjectName("centralWidget")
        central_widget.setStyleSheet("""
            #centralWidget {
                background-color: transparent;
            }
        """)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header section with title and actions
        header_card = CardWidget()
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(16, 12, 16, 12)

        # Title
        title = TitleLabel("Clipboard History")
        header_layout.addWidget(title)

        # Sync status indicator (updates via update_sync_status())
        self.sync_status_label = CaptionLabel("")
        self.sync_status_label.setToolTip("GitHub sync status")
        header_layout.addSpacing(12)
        header_layout.addWidget(self.sync_status_label)

        header_layout.addStretch()

        # Action buttons
        self.refresh_btn = TransparentToolButton(FIF.SYNC, self)
        self.refresh_btn.setToolTip("Refresh")
        self.refresh_btn.clicked.connect(self._load_entries)

        self.clear_btn = TransparentToolButton(FIF.DELETE, self)
        self.clear_btn.setToolTip("Clear All History")
        self.clear_btn.clicked.connect(self._clear_history)

        self.export_btn = TransparentToolButton(FIF.SAVE, self)
        self.export_btn.setToolTip("Export History")
        self.export_btn.clicked.connect(self._export_history)

        self.import_btn = TransparentToolButton(FIF.FOLDER_ADD, self)
        self.import_btn.setToolTip("Import History")
        self.import_btn.clicked.connect(self._import_history)

        self.settings_btn = TransparentToolButton(FIF.SETTING, self)
        self.settings_btn.setToolTip("Settings")
        self.settings_btn.clicked.connect(self._show_settings)

        header_layout.addWidget(self.refresh_btn)
        header_layout.addWidget(self.clear_btn)
        header_layout.addWidget(self.export_btn)
        header_layout.addWidget(self.import_btn)
        header_layout.addWidget(self.settings_btn)

        main_layout.addWidget(header_card)

        # Search and filter section
        search_card = CardWidget()
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(16, 12, 16, 12)

        # Search input with Fluent style
        self.search_input = SearchLineEdit()
        self.search_input.setPlaceholderText("Search clipboard history...")
        self.search_input.textChanged.connect(self._on_search)
        self.search_input.setFixedHeight(36)

        # Category filter (labels kept in sync with HistoryFilter's mapping)
        self.category_combo = ComboBox()
        self.category_combo.addItems(CATEGORY_LABELS)
        self.category_combo.currentTextChanged.connect(self._on_filter_change)
        self.category_combo.setFixedWidth(150)

        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(BodyLabel("Category:"))
        search_layout.addWidget(self.category_combo)

        main_layout.addWidget(search_card)

        # Create splitter for content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # History list card
        list_card = CardWidget()
        list_card.setMinimumWidth(300)
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(0)

        # List header
        list_header = QWidget()
        list_header.setFixedHeight(48)
        list_header_layout = QHBoxLayout(list_header)
        list_header_layout.setContentsMargins(16, 0, 16, 0)

        list_title = SubtitleLabel("History")
        self.count_label = CaptionLabel("0 items")

        list_header_layout.addWidget(list_title)
        list_header_layout.addStretch()
        list_header_layout.addWidget(self.count_label)

        list_layout.addWidget(list_header)

        # History list with Fluent style, wrapped in a stack so we can show
        # a friendly empty-state when there is nothing to display.
        self.history_list = ListWidget()
        self.history_list.currentItemChanged.connect(self._on_selection_changed)
        self.history_list.itemDoubleClicked.connect(self._copy_to_clipboard)

        self._empty_state = QWidget()
        empty_layout = QVBoxLayout(self._empty_state)
        empty_layout.setContentsMargins(24, 24, 24, 24)
        empty_layout.addStretch()
        self._empty_title = SubtitleLabel("No clipboard entries yet")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint = BodyLabel(
            "Copy something to start building your history, or adjust the filter above."
        )
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setWordWrap(True)
        empty_layout.addWidget(self._empty_title)
        empty_layout.addSpacing(8)
        empty_layout.addWidget(self._empty_hint)
        empty_layout.addStretch()

        self.list_stack = QStackedWidget()
        self.list_stack.addWidget(self.history_list)   # index 0
        self.list_stack.addWidget(self._empty_state)   # index 1
        list_layout.addWidget(self.list_stack)

        splitter.addWidget(list_card)

        # Preview section
        preview_card = CardWidget()
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        # Preview header with actions
        preview_header = QWidget()
        preview_header.setFixedHeight(48)
        preview_header_layout = QHBoxLayout(preview_header)
        preview_header_layout.setContentsMargins(16, 0, 16, 0)

        preview_title = SubtitleLabel("Preview")

        self.copy_button = PrimaryPushButton("Copy to Clipboard", self, FIF.COPY)
        self.copy_button.clicked.connect(self._copy_to_clipboard)

        self.favorite_button = ToggleButton("Favorite", self, FIF.HEART)
        self.favorite_button.clicked.connect(self._toggle_favorite)

        preview_header_layout.addWidget(preview_title)
        preview_header_layout.addStretch()
        preview_header_layout.addWidget(self.favorite_button)
        preview_header_layout.addWidget(self.copy_button)

        preview_layout.addWidget(preview_header)

        # Preview content area
        self.preview_text = TextEdit()
        self.preview_text.setReadOnly(True)
        preview_layout.addWidget(self.preview_text, 1)

        # Metadata section
        metadata_widget = QWidget()
        metadata_widget.setFixedHeight(100)
        metadata_layout = QVBoxLayout(metadata_widget)
        metadata_layout.setContentsMargins(16, 12, 16, 12)

        metadata_title = BodyLabel("Details")
        metadata_title.setStyleSheet("font-weight: bold;")
        metadata_layout.addWidget(metadata_title)

        self.metadata_label = CaptionLabel()
        self.metadata_label.setWordWrap(True)
        metadata_layout.addWidget(self.metadata_label)
        metadata_layout.addStretch()

        preview_layout.addWidget(metadata_widget)

        splitter.addWidget(preview_card)
        splitter.setSizes([450, 650])

        main_layout.addWidget(splitter, 1)

        # Setup keyboard shortcuts
        self._setup_shortcuts()

        # Setup context menu for history list
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._show_context_menu)

    def _load_entries(self):
        """Full reload: clears the list and re-adds every entry.

        Fast paths (new clipboard additions) are handled by
        ``_check_for_updates`` so this method now runs on initial load,
        manual refresh (F5), imports, restores and external count drops.
        """
        try:
            self.history_list.clear()

            if self.repository:
                # Load from database
                self.current_entries = self.repository.get_entries(limit=500)
            elif self.clipboard_history:
                # Load from memory
                self.current_entries = self.clipboard_history.get_entries(limit=500)
            else:
                self.current_entries = []

            # Refresh cached favorite hashes in a single query; cheap on SQLite
            # and avoids per-row `is_favorite()` round trips during filtering
            # and preview rendering.
            self._refresh_favorite_cache()

            # Add to list widget
            for entry in self.current_entries:
                self._add_entry_to_list(entry)

            # Record the newest timestamp so incremental refresh can query
            # only the rows added after this point.
            self._last_seen_timestamp = self._compute_newest_timestamp(self.current_entries)

            # Re-apply active filter so state survives a reload
            self._apply_combined_filter()

            # Update last entry count (use actual DB count to match _check_for_updates)
            if self.repository:
                self.last_entry_count = self.repository.get_entry_count()
            else:
                self.last_entry_count = len(self.current_entries)

            # Refresh sync status (label is a no-op if sync not configured)
            self.update_sync_status()

            # Show success notification only for manual refresh or initial load
            if not hasattr(self, '_initial_load_done'):
                InfoBar.success(
                    title="Loaded",
                    content=f"Loaded {len(self.current_entries)} entries",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )
                self._initial_load_done = True

            logger.info(f"Loaded {len(self.current_entries)} entries")

        except Exception as e:
            logger.error(f"Failed to load entries: {e}")
            InfoBar.error(
                title="Error",
                content=f"Failed to load entries: {str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def refresh_entries(self):
        """Public refresh API used by coordinators/main app."""
        self._load_entries()

    # Threshold above which an incremental prepend is abandoned in favour of
    # a full reload (e.g. a GitHub pull brought in a large batch).
    _INCREMENTAL_REFRESH_MAX_DELTA = 50

    def _check_for_updates(self):
        """Detect new entries and refresh the list.

        Fast path: if the count grew by a small delta, only fetch and prepend
        the rows newer than ``_last_seen_timestamp``. Selection is preserved
        because existing QListWidgetItems are never touched. Fall back to a
        full reload when the delta is large or the count shrinks (external
        delete / cleanup / clear).
        """
        try:
            if self.repository:
                current_count = self.repository.get_entry_count()
            elif self.clipboard_history:
                current_count = len(self.clipboard_history.get_entries())
            else:
                return

            if current_count == self.last_entry_count:
                return

            previous_count = self.last_entry_count

            if current_count < previous_count:
                # External deletion or cleanup; rebuild to stay correct.
                self._reload_preserving_selection()
                return

            delta = current_count - previous_count

            if (
                self.repository
                and self._last_seen_timestamp is not None
                and delta <= self._INCREMENTAL_REFRESH_MAX_DELTA
                and hasattr(self.repository, "get_entries_since")
            ):
                new_entries = self.repository.get_entries_since(
                    self._last_seen_timestamp, limit=self._INCREMENTAL_REFRESH_MAX_DELTA
                )
                if new_entries:
                    self._prepend_new_entries(new_entries)
                    self.last_entry_count = current_count
                    self._notify_new_entries()
                    return
                # Fallthrough: count grew but no newer rows (e.g. timestamp
                # ties). Full reload keeps state consistent.

            self._reload_preserving_selection()
            if current_count > previous_count:
                self._notify_new_entries()

        except Exception as e:
            logger.error(f"Error checking for updates: {e}")

    def _reload_preserving_selection(self) -> None:
        """Remember the selected entry, do a full reload, restore selection."""
        current_row = self.history_list.currentRow()
        current_item_content = None
        if 0 <= current_row < len(self.current_entries):
            current_item_content = self.current_entries[current_row].content

        self._load_entries()

        if current_item_content:
            for i, entry in enumerate(self.current_entries):
                if entry.content == current_item_content:
                    self.history_list.setCurrentRow(i)
                    return
        if self.history_list.count() > 0:
            self.history_list.setCurrentRow(0)

    def _prepend_new_entries(self, new_entries) -> None:
        """Insert freshly-arrived entries at the top without touching the
        existing items — preserves scroll position and selection.
        """
        # Guard against duplicates (e.g. overlapping timestamps).
        known_hashes = {e.content_hash for e in self.current_entries}
        added_any = False
        # Insert in chronological order so the newest ends up at index 0.
        for entry in reversed(new_entries):
            if entry.content_hash in known_hashes:
                continue
            self.current_entries.insert(0, entry)
            item = QListWidgetItem(HistoryItemFormatter.list_item_text(entry))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setSizeHint(QSize(0, LIST_ITEM_HEIGHT))
            self.history_list.insertItem(0, item)
            known_hashes.add(entry.content_hash)
            added_any = True

        if not added_any:
            return

        self._last_seen_timestamp = self._compute_newest_timestamp(self.current_entries)
        # Enforce the same 500-cap the initial load uses.
        while len(self.current_entries) > 500:
            self.current_entries.pop()
            overflow_row = self.history_list.count() - 1
            if overflow_row >= 0:
                self.history_list.takeItem(overflow_row)

        self._apply_combined_filter()

    def _notify_new_entries(self) -> None:
        InfoBar.success(
            title="New Entry",
            content="Clipboard history updated",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=1500,
            parent=self,
        )

    @staticmethod
    def _compute_newest_timestamp(entries):
        newest = None
        for entry in entries:
            ts = getattr(entry, "timestamp", None)
            if ts is None:
                continue
            if newest is None or ts > newest:
                newest = ts
        return newest

    def _add_entry_to_list(self, entry):
        """Add entry to list widget with modern styling"""
        item = QListWidgetItem(HistoryItemFormatter.list_item_text(entry))
        item.setData(Qt.ItemDataRole.UserRole, entry)
        item.setSizeHint(QSize(0, LIST_ITEM_HEIGHT))
        self.history_list.addItem(item)

    def _on_selection_changed(self, current, previous):
        """Handle selection change"""
        if not current:
            self.preview_text.clear()
            self.metadata_label.clear()
            self.favorite_button.setChecked(False)
            return

        entry = current.data(Qt.ItemDataRole.UserRole)
        if entry:
            # Update preview
            self.preview_text.setPlainText(entry.content)

            # Favorite state comes from the in-memory cache built once per
            # reload, avoiding a DB hit on every list-selection change.
            self.favorite_button.setChecked(
                entry.content_hash in self._favorite_hashes
            )

            # Update metadata with modern formatting
            self.metadata_label.setText(HistoryItemFormatter.metadata_text(entry))

    def _on_search(self, text):
        """Handle search input.

        Filtering is debounced (~150ms) so rapid typing does not iterate the
        entire list on every keystroke; category changes stay immediate since
        they fire far less often.
        """
        if hasattr(self, "_search_debounce_timer"):
            self._search_debounce_timer.start()
        else:
            self._apply_combined_filter()

    def _on_filter_change(self, category):
        """Handle category filter change - applies combined search + filter"""
        self._apply_combined_filter()

    def _apply_combined_filter(self):
        """Apply both search text and category filter together"""
        search_text = self.search_input.text()
        category_label = self.category_combo.currentText()

        visible_entries = set(
            id(e) for e in self._filter.apply(
                self.current_entries,
                search_text=search_text,
                category_label=category_label,
            )
        )

        visible_count = 0
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)
            if entry is not None and id(entry) in visible_entries:
                item.setHidden(False)
                visible_count += 1
            else:
                item.setHidden(True)

        self._update_count_label(visible_count)
        self._update_list_stack(visible_count)

    def _update_count_label(self, visible_count: int) -> None:
        total = len(self.current_entries)
        if visible_count == total:
            self.count_label.setText(f"{total} items")
        else:
            self.count_label.setText(f"{visible_count} of {total} items")

    def _update_list_stack(self, visible_count: int) -> None:
        """Toggle between the list and the empty-state placeholder."""
        if visible_count == 0:
            if len(self.current_entries) == 0:
                self._empty_title.setText("No clipboard entries yet")
                self._empty_hint.setText(
                    "Copy something to start building your history."
                )
            else:
                self._empty_title.setText("No matches")
                self._empty_hint.setText(
                    "Try a different search term or category filter."
                )
            self.list_stack.setCurrentIndex(1)
        else:
            self.list_stack.setCurrentIndex(0)

    def _is_favorite_for_filter(self, content_hash: str) -> bool:
        """Favorite resolver used by HistoryFilter; backed by the in-memory
        cache so filter passes stay O(1) per entry.
        """
        if not content_hash:
            return False
        return content_hash in self._favorite_hashes

    def _refresh_favorite_cache(self) -> None:
        """Reload favorite hashes from the repository, if it supports it.

        Falls back to a per-entry ``is_favorite`` scan for older backends so
        this layer stays duck-typed against ``StorageBackend``.
        """
        if not self.repository:
            self._favorite_hashes = set()
            return

        try:
            if hasattr(self.repository, "get_favorite_hashes"):
                self._favorite_hashes = set(self.repository.get_favorite_hashes())
                return
        except Exception as e:
            logger.warning(f"get_favorite_hashes() failed, falling back: {e}")

        fallback = set()
        try:
            is_fav = getattr(self.repository, "is_favorite", None)
            if callable(is_fav):
                for entry in self.current_entries:
                    try:
                        if is_fav(entry.content_hash):
                            fallback.add(entry.content_hash)
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"favorite fallback failed: {e}")
        self._favorite_hashes = fallback

    def update_sync_status(self) -> None:
        """Refresh the GitHub sync status indicator in the header."""
        if not hasattr(self, "sync_status_label"):
            return
        if self.github_sync is not None and getattr(self.github_sync, "enabled", False):
            self.sync_status_label.setText("\u25CF GitHub sync")
            self.sync_status_label.setToolTip("GitHub sync is enabled")
            self.sync_status_label.setStyleSheet("color: #2ea043;")
        else:
            self.sync_status_label.setText("\u25CB Local only")
            self.sync_status_label.setToolTip(
                "GitHub sync is not configured. Open Settings to enable it."
            )
            self.sync_status_label.setStyleSheet("color: #8a8a8a;")

    def _copy_to_clipboard(self):
        """Copy selected entry to clipboard"""
        current_item = self.history_list.currentItem()
        if current_item:
            entry = current_item.data(Qt.ItemDataRole.UserRole)
            if entry:
                pyperclip.copy(entry.content)

                # Show success notification
                InfoBar.success(
                    title="Copied",
                    content=f"Copied {len(entry.content)} characters to clipboard",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,
                    duration=2000,
                    parent=self
                )

                logger.info(f"Copied entry to clipboard: {entry.content_hash[:8]}")

    def _toggle_favorite(self):
        """Toggle favorite status of selected entry"""
        current_item = self.history_list.currentItem()
        if current_item and self.repository:
            entry = current_item.data(Qt.ItemDataRole.UserRole)
            if entry:
                success = self.repository.toggle_favorite(entry.content_hash)
                if success:
                    # Keep the in-memory favorite cache in sync without a
                    # follow-up DB query.
                    if entry.content_hash in self._favorite_hashes:
                        self._favorite_hashes.discard(entry.content_hash)
                        is_favorite_now = False
                    else:
                        self._favorite_hashes.add(entry.content_hash)
                        is_favorite_now = True
                    self.favorite_button.setChecked(is_favorite_now)

                    # If the favorites-only filter is active, visibility may
                    # change; re-apply the filter so the list stays honest.
                    if self.category_combo.currentText() == FAVORITES_LABEL:
                        self._apply_combined_filter()

                    # Show notification
                    InfoBar.success(
                        title="Updated",
                        content="Favorite status updated",
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM,
                        duration=2000,
                        parent=self
                    )

                    logger.info(f"Toggled favorite: {entry.content_hash[:8]}")

    def _clear_history(self):
        """Clear all history with confirmation dialog"""
        try:
            # Show modern confirmation dialog
            w = MessageBox(
                title="Clear History",
                content="Are you sure you want to clear all clipboard history?\nThis action cannot be undone.",
                parent=self
            )
            w.yesButton.setText("Clear")
            w.cancelButton.setText("Cancel")

            if w.exec():
                try:
                    # Clear from database if available
                    if self.repository:
                        success = self.repository.clear_all()
                        if not success:
                            logger.warning("Failed to clear database")

                    # Clear from memory - check if attribute exists
                    if hasattr(self, 'clipboard_history') and self.clipboard_history:
                        self.clipboard_history.clear()

                    # Clear UI
                    self.history_list.clear()
                    self.preview_text.clear()
                    self.metadata_label.clear()
                    self.current_entries = []
                    self.last_entry_count = 0
                    self._last_seen_timestamp = None
                    self._favorite_hashes.clear()
                    self._update_count_label(0)
                    self._update_list_stack(0)

                    # Show notification
                    InfoBar.success(
                        title="Cleared",
                        content="History has been cleared",
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=2000,
                        parent=self
                    )

                    logger.info("Clipboard history cleared successfully")

                except Exception as e:
                    logger.error(f"Error during clear operation: {e}")
                    InfoBar.error(
                        title="Clear Failed",
                        content=f"Failed to clear history: {str(e)}",
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.TOP,
                        duration=5000,
                        parent=self
                    )

        except Exception as e:
            logger.error(f"Error showing clear dialog: {e}")
            InfoBar.error(
                title="Error",
                content="Failed to show clear dialog",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def _export_history(self):
        """Export history to file"""
        from PyQt6.QtWidgets import QFileDialog
        import json

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export History",
            "",
            "JSON Files (*.json)"
        )

        if not filename:
            return

        # Show progress tooltip
        stateTooltip = StateToolTip("Exporting", "Please wait...", self)
        stateTooltip.move(self.geometry().center())
        stateTooltip.show()

        try:
            # Export from current entries (works with both DB and in-memory)
            entries_data = []
            for entry in self.current_entries:
                entries_data.append(entry.to_dict())

            export_data = {
                'entries': entries_data,
                'exported_at': datetime.now().isoformat(),
                'count': len(entries_data)
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            stateTooltip.setContent(f"Exported {len(entries_data)} entries")
            stateTooltip.setState(True)

            InfoBar.success(
                title="Exported",
                content=f"Exported {len(entries_data)} entries to file",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

            logger.info(f"History exported to {filename}")

        except Exception as e:
            stateTooltip.setContent(f"Export failed: {str(e)}")
            stateTooltip.setState(False)
            logger.error(f"Export failed: {e}")

        finally:
            stateTooltip.hide()

    def _import_history(self):
        """Import history from file"""
        from PyQt6.QtWidgets import QFileDialog
        import json
        from src.core.clipboard.history import ClipboardEntry

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import History",
            "",
            "JSON Files (*.json)"
        )

        if not filename:
            return

        # Show progress tooltip
        stateTooltip = StateToolTip("Importing", "Please wait...", self)
        stateTooltip.move(self.geometry().center())
        stateTooltip.show()

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)

            entries = data.get('entries', [])
            imported_count = 0

            for entry_data in entries:
                try:
                    entry = ClipboardEntry.from_dict(entry_data)

                    # Save to repository (DB) if available
                    if self.repository:
                        self.repository.save_entry(entry)

                    # Save to in-memory history if available
                    if self.clipboard_history:
                        self.clipboard_history.import_entry(entry)

                    imported_count += 1
                except Exception as e:
                    logger.warning(f"Failed to import entry: {e}")

            self._load_entries()

            stateTooltip.setContent(f"Imported {imported_count} entries")
            stateTooltip.setState(True)

            InfoBar.success(
                title="Imported",
                content=f"Imported {imported_count} of {len(entries)} entries",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

            logger.info(f"History imported from {filename}: {imported_count} entries")

        except Exception as e:
            stateTooltip.setContent(f"Import failed: {str(e)}")
            stateTooltip.setState(False)
            logger.error(f"Import failed: {e}")

        finally:
            stateTooltip.hide()

    def _show_settings(self):
        """Show settings menu"""
        menu = RoundMenu(parent=self)

        # App Settings action
        app_settings_action = Action(FIF.SETTING, "App Settings")
        app_settings_action.triggered.connect(self._show_app_settings)
        menu.addAction(app_settings_action)

        # GitHub Settings action
        github_settings_action = Action(FIF.GITHUB, "GitHub Sync Settings")
        github_settings_action.triggered.connect(self._show_github_settings)
        menu.addAction(github_settings_action)

        # Show menu at button position
        menu.exec(self.settings_btn.mapToGlobal(self.settings_btn.rect().bottomLeft()))

    def _show_app_settings(self):
        """Show app settings dialog"""
        try:
            from src.ui.dialogs.app_settings_dialog import AppSettingsDialog

            dialog = AppSettingsDialog(self)
            dialog.settings_saved.connect(self._on_app_settings_saved)
            dialog.exec()

        except Exception as e:
            logger.error(f"Failed to show app settings dialog: {e}")
            InfoBar.error(
                title="Error",
                content=f"Failed to open app settings: {str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def _on_app_settings_saved(self, settings):
        """Handle app settings being saved"""
        logger.info("App settings saved")
        # Reload config to apply changes immediately
        if self.config_manager:
            self.config_manager.reload()
            logger.info("Config reloaded after app settings change")

    def _show_github_settings(self):
        """Show GitHub settings dialog"""
        try:
            from src.ui.dialogs import GitHubSettingsDialog

            dialog = GitHubSettingsDialog(self)

            # Connect signal to handle saved settings
            dialog.settings_saved.connect(self._on_github_settings_saved)

            # Add restore from GitHub button handler
            dialog.restore_requested.connect(self._restore_from_github)

            dialog.exec()

        except ImportError as e:
            logger.error(f"Failed to import GitHubSettingsDialog: {e}")
            # Fallback to simple dialog
            from qfluentwidgets import Dialog

            w = Dialog(
                title="Settings",
                content="GitHub sync settings can be edited in:\n%APPDATA%\\ClipboardHistory\\github_settings.yaml\n\nSettings UI temporarily unavailable.",
                parent=self
            )
            w.yesButton.setText("OK")
            w.cancelButton.hide()
            w.exec()

        except Exception as e:
            logger.error(f"Failed to show settings dialog: {e}")
            InfoBar.error(
                title="Error",
                content=f"Failed to open settings: {str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def _on_github_settings_saved(self, settings):
        """Handle GitHub settings being saved - delegates to main app via callback"""
        logger.info("GitHub settings saved, notifying main app...")

        if self._on_github_settings_changed:
            try:
                self._on_github_settings_changed(settings)
                InfoBar.success(
                    title="GitHub Sync",
                    content="GitHub sync service has been updated with new settings",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            except Exception as e:
                logger.error(f"Failed to reinitialize GitHub sync: {e}")
                InfoBar.error(
                    title="Error",
                    content=f"Failed to update sync settings: {str(e)}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
        else:
            InfoBar.warning(
                title="Settings Saved",
                content="Restart the app to apply new GitHub settings",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

    def _restore_from_github(self):
        """Show dialog to restore from GitHub backup"""
        try:
            from src.ui.dialogs.restore_dialog import RestoreDialog

            if self.github_sync and self.github_sync.enabled:
                dialog = RestoreDialog(
                    self.github_sync,
                    self.repository,
                    self.encryption_manager,
                    self
                )

                # Connect signal to reload entries when restore is complete
                dialog.restore_completed.connect(self._load_entries)

                dialog.exec()
            else:
                InfoBar.warning(
                    title="GitHub Not Configured",
                    content="Please configure GitHub settings first",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

        except Exception as e:
            logger.error(f"Failed to show restore dialog: {e}")
            InfoBar.error(
                title="Error",
                content=f"Failed to restore: {str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Ctrl+C: Copy selected entry
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self._copy_to_clipboard)

        # Ctrl+F: Focus search input
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(lambda: self.search_input.setFocus())

        # Delete: Delete selected entry
        delete_shortcut = QShortcut(QKeySequence("Delete"), self)
        delete_shortcut.activated.connect(self._delete_selected_entry)

        # Escape: Close window
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.close)

        # F5: Refresh
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._load_entries)

        # Ctrl+D: Toggle favorite on selected entry
        favorite_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        favorite_shortcut.activated.connect(self._toggle_favorite)

    def _show_context_menu(self, position):
        """Show right-click context menu for history list"""
        current_item = self.history_list.currentItem()
        if not current_item:
            return

        menu = RoundMenu(parent=self)

        copy_action = Action(FIF.COPY, "Copy to Clipboard")
        copy_action.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_action)

        fav_action = Action(FIF.HEART, "Toggle Favorite")
        fav_action.triggered.connect(self._toggle_favorite)
        menu.addAction(fav_action)

        menu.addSeparator()

        delete_action = Action(FIF.DELETE, "Delete Entry")
        delete_action.triggered.connect(self._delete_selected_entry)
        menu.addAction(delete_action)

        menu.exec(self.history_list.mapToGlobal(position))

    def _delete_selected_entry(self):
        """Delete the currently selected entry"""
        current_item = self.history_list.currentItem()
        if not current_item:
            return

        entry = current_item.data(Qt.ItemDataRole.UserRole)
        if not entry:
            return

        # Confirm deletion
        w = MessageBox(
            title="Delete Entry",
            content=f"Delete this entry?\n\n{entry.content[:100]}{'...' if len(entry.content) > 100 else ''}",
            parent=self
        )
        w.yesButton.setText("Delete")
        w.cancelButton.setText("Cancel")

        if w.exec():
            try:
                # Delete from database
                if self.repository:
                    self.repository.delete_entry(entry.content_hash)

                # Delete from in-memory history
                if self.clipboard_history:
                    self.clipboard_history.remove_entry(entry.content_hash)

                # Remove from UI
                row = self.history_list.row(current_item)
                self.history_list.takeItem(row)
                self.current_entries = [
                    e for e in self.current_entries if e.content_hash != entry.content_hash
                ]
                self._favorite_hashes.discard(entry.content_hash)
                # Re-apply filter so counts/empty-state stay accurate
                self._apply_combined_filter()

                # Update last_entry_count to avoid triggering auto-refresh
                if self.repository:
                    self.last_entry_count = self.repository.get_entry_count()
                else:
                    self.last_entry_count = len(self.current_entries)

                InfoBar.success(
                    title="Deleted",
                    content="Entry deleted",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.BOTTOM,
                    duration=1500,
                    parent=self
                )

                logger.info(f"Deleted entry: {entry.content_hash[:8]}")

            except Exception as e:
                logger.error(f"Failed to delete entry: {e}")
                InfoBar.error(
                    title="Error",
                    content=f"Failed to delete entry: {str(e)}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

    def closeEvent(self, event):
        """Handle window close event"""
        # Stop the auto-refresh timer
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        logger.info("History viewer window closed")
        event.accept()


# For standalone testing
if __name__ == "__main__":
    app = QApplication(sys.argv)

    viewer = ModernHistoryViewer()
    viewer.show()

    sys.exit(app.exec())
