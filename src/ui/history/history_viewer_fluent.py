"""Modern history viewer with Windows 11 Fluent Design using PyQt6-Fluent-Widgets"""

import sys
import pyperclip
from typing import Optional, List
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout,
    QWidget, QListWidgetItem, QLabel
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QFont

# Import Fluent Design components
from qfluentwidgets import (
    FluentWindow, ListWidget, TextEdit, PushButton, LineEdit,
    ComboBox, ToolButton, InfoBar, InfoBarPosition, Theme,
    setTheme, isDarkTheme, FluentIcon as FIF, SearchLineEdit,
    CardWidget, BodyLabel, SubtitleLabel, TitleLabel, CaptionLabel,
    TransparentToolButton, PrimaryPushButton, ToggleButton,
    SplitFluentWindow, NavigationItemPosition, MessageBox,
    Dialog, StateToolTip
)
from qfluentwidgets import FluentStyleSheet
from loguru import logger


class ModernHistoryViewer(FluentWindow):
    """Modern history viewer window with Windows 11 Fluent Design"""

    def __init__(self, clipboard_history=None, repository=None):
        """
        Initialize history viewer

        Args:
            clipboard_history: ClipboardHistory instance
            repository: ClipboardRepository instance
        """
        super().__init__()
        self.clipboard_history = clipboard_history
        self.repository = repository
        self.current_entries = []

        # Set window properties
        self.setWindowTitle("Clipboard History")
        self.resize(1100, 750)

        # Auto-detect and apply system theme
        if isDarkTheme():
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.LIGHT)

        self._init_ui()
        self._load_entries()

    def _init_ui(self):
        """Initialize modern UI with Fluent Design"""
        # Create central widget - FluentWindow uses setWidget instead
        central_widget = QWidget()
        self.setWidget(central_widget)

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

        # Category filter
        self.category_combo = ComboBox()
        self.category_combo.addItems(["All", "Text", "URL", "File Path", "Email"])
        self.category_combo.currentTextChanged.connect(self._on_filter_change)
        self.category_combo.setFixedWidth(150)

        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(BodyLabel("Category:"))
        search_layout.addWidget(self.category_combo)

        main_layout.addWidget(search_card)

        # Content section with list and preview
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # History list card
        list_card = CardWidget()
        list_card.setFixedWidth(450)
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

        # History list with Fluent style
        self.history_list = ListWidget()
        self.history_list.currentItemChanged.connect(self._on_selection_changed)
        self.history_list.itemDoubleClicked.connect(self._copy_to_clipboard)
        list_layout.addWidget(self.history_list)

        content_layout.addWidget(list_card)

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
        metadata_widget.setFixedHeight(120)
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

        content_layout.addWidget(preview_card, 1)

        main_layout.addLayout(content_layout, 1)

    def _load_entries(self):
        """Load clipboard entries"""
        try:
            self.history_list.clear()

            if self.repository:
                # Load from database
                self.current_entries = self.repository.get_entries(limit=100)
            elif self.clipboard_history:
                # Load from memory
                self.current_entries = self.clipboard_history.get_entries(limit=100)
            else:
                self.current_entries = []

            # Add to list widget
            for entry in self.current_entries:
                self._add_entry_to_list(entry)

            # Update count
            self.count_label.setText(f"{len(self.current_entries)} items")

            # Show success notification
            InfoBar.success(
                title="Refreshed",
                content=f"Loaded {len(self.current_entries)} entries",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

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

    def _add_entry_to_list(self, entry):
        """Add entry to list widget with modern styling"""
        # Create display text
        preview = entry.content[:80].replace('\n', ' ')
        if len(entry.content) > 80:
            preview += "..."

        # Format timestamp
        time_str = entry.timestamp.strftime("%H:%M · %b %d")

        # Category icon mapping (using Fluent icons)
        category_names = {
            "text": "Text",
            "url": "Link",
            "file_path": "File",
            "email": "Email"
        }
        category_name = category_names.get(entry.category, "Other")

        # Create list item with rich formatting
        item_text = f"{time_str}\n{preview}\n{category_name} · {len(entry.content)} chars"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, entry)

        # Set item height
        item.setSizeHint(QSize(0, 75))

        self.history_list.addItem(item)

    def _on_selection_changed(self, current, previous):
        """Handle selection change"""
        if not current:
            self.preview_text.clear()
            self.metadata_label.clear()
            return

        entry = current.data(Qt.ItemDataRole.UserRole)
        if entry:
            # Update preview
            self.preview_text.setPlainText(entry.content)

            # Update metadata with modern formatting
            metadata_lines = [
                f"Type: {entry.category.replace('_', ' ').title()}",
                f"Time: {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Size: {len(entry.content)} characters",
                f"ID: {entry.content_hash[:16]}..."
            ]
            self.metadata_label.setText(" · ".join(metadata_lines))

    def _on_search(self, text):
        """Handle search input"""
        search_text = text.lower()
        visible_count = 0

        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)

            if entry:
                # Check if entry matches search
                if search_text in entry.content.lower():
                    item.setHidden(False)
                    visible_count += 1
                else:
                    item.setHidden(True)

        # Update count label
        self.count_label.setText(f"{visible_count} of {len(self.current_entries)} items")

    def _on_filter_change(self, category):
        """Handle category filter change"""
        visible_count = 0

        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)

            if entry:
                if category == "All":
                    item.setHidden(False)
                    visible_count += 1
                else:
                    # Convert display category to internal format
                    category_map = {
                        "Text": "text",
                        "URL": "url",
                        "File Path": "file_path",
                        "Email": "email"
                    }
                    internal_category = category_map.get(category, "text")

                    if entry.category == internal_category:
                        item.setHidden(False)
                        visible_count += 1
                    else:
                        item.setHidden(True)

        # Update count label
        self.count_label.setText(f"{visible_count} of {len(self.current_entries)} items")

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
                    # Update button state
                    self.favorite_button.setChecked(not self.favorite_button.isChecked())

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
        # Show modern confirmation dialog
        w = MessageBox(
            title="Clear History",
            content="Are you sure you want to clear all clipboard history?\nThis action cannot be undone.",
            parent=self
        )
        w.yesButton.setText("Clear")
        w.cancelButton.setText("Cancel")

        if w.exec():
            if self.clipboard_history:
                self.clipboard_history.clear()

            self.history_list.clear()
            self.preview_text.clear()
            self.metadata_label.clear()
            self.count_label.setText("0 items")

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

            logger.info("Clipboard history cleared")

    def _export_history(self):
        """Export history to file"""
        from PyQt6.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export History",
            "",
            "JSON Files (*.json)"
        )

        if filename and self.clipboard_history:
            # Show progress tooltip
            stateTooltip = StateToolTip("Exporting", "Please wait...", self)
            stateTooltip.move(self.geometry().center())
            stateTooltip.show()

            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.clipboard_history.to_json())

                stateTooltip.setContent("Export completed successfully")
                stateTooltip.setState(True)

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

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import History",
            "",
            "JSON Files (*.json)"
        )

        if filename and self.clipboard_history:
            # Show progress tooltip
            stateTooltip = StateToolTip("Importing", "Please wait...", self)
            stateTooltip.move(self.geometry().center())
            stateTooltip.show()

            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.clipboard_history.from_json(f.read())

                self._load_entries()

                stateTooltip.setContent("Import completed successfully")
                stateTooltip.setState(True)

                logger.info(f"History imported from {filename}")

            except Exception as e:
                stateTooltip.setContent(f"Import failed: {str(e)}")
                stateTooltip.setState(False)
                logger.error(f"Import failed: {e}")

            finally:
                stateTooltip.hide()

    def _show_settings(self):
        """Show settings dialog"""
        # Show modern info dialog
        w = Dialog(
            title="Settings",
            content="Settings can be edited in:\n%APPDATA%\\ClipboardHistory\\settings.yaml\n\nA settings UI will be added in a future update.",
            parent=self
        )
        w.yesButton.setText("OK")
        w.cancelButton.hide()
        w.exec()

    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("History viewer window closed")
        event.accept()


# For standalone testing
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Enable high DPI scaling
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)

    viewer = ModernHistoryViewer()
    viewer.show()

    sys.exit(app.exec())