"""Fixed history viewer with better compatibility"""

import sys
import pyperclip
from typing import Optional, List
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QTextEdit, QPushButton,
    QLineEdit, QLabel, QMessageBox, QToolBar, QSplitter,
    QFrame, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont, QKeySequence
from loguru import logger


class HistoryViewer(QMainWindow):
    """Main history viewer window with fixed UI"""

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

        self._init_ui()
        self._load_entries()

    def _init_ui(self):
        """Initialize user interface"""
        self.setWindowTitle("ClipboardHistory Viewer")
        self.setGeometry(100, 100, 1000, 700)

        # Create central widget
        central_widget = QWidget()
        central_widget.setStyleSheet("background-color: #f0f0f0;")
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Create toolbar
        self._create_toolbar()

        # Create search bar
        search_widget = QWidget()
        search_widget.setStyleSheet("background-color: white; border: 1px solid #ccc; padding: 5px;")
        search_layout = QHBoxLayout(search_widget)
        search_layout.setContentsMargins(5, 5, 5, 5)

        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-weight: bold; border: none;")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search clipboard history...")
        self.search_input.textChanged.connect(self._on_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
        """)

        category_label = QLabel("Category:")
        category_label.setStyleSheet("font-weight: bold; border: none;")

        self.search_category = QComboBox()
        self.search_category.addItems(["All", "Text", "URL", "File Path", "Email"])
        self.search_category.currentTextChanged.connect(self._on_filter_change)
        self.search_category.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(category_label)
        search_layout.addWidget(self.search_category)

        main_layout.addWidget(search_widget)

        # Create splitter for list and preview
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #ccc; }")

        # Left panel - History list
        left_panel = QWidget()
        left_panel.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        list_header = QLabel("History")
        list_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        list_header.setStyleSheet("""
            QLabel {
                padding: 10px;
                background-color: #e0e0e0;
                font-weight: bold;
                font-size: 14px;
                border: none;
                border-bottom: 1px solid #ccc;
            }
        """)
        left_layout.addWidget(list_header)

        self.history_list = QListWidget()
        self.history_list.currentItemChanged.connect(self._on_selection_changed)
        self.history_list.itemDoubleClicked.connect(self._copy_to_clipboard)
        self.history_list.setStyleSheet("""
            QListWidget {
                border: none;
                background-color: white;
                outline: none;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #eee;
                color: #333;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #f0f8ff;
            }
        """)
        left_layout.addWidget(self.history_list)

        # Right panel - Preview
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Preview header with buttons
        preview_header_widget = QWidget()
        preview_header_widget.setStyleSheet("background-color: #e0e0e0; border: none; border-bottom: 1px solid #ccc;")
        preview_header_layout = QHBoxLayout(preview_header_widget)
        preview_header_layout.setContentsMargins(10, 5, 10, 5)

        preview_label = QLabel("Preview")
        preview_label.setStyleSheet("font-weight: bold; font-size: 14px; border: none;")

        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.copy_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)

        self.favorite_button = QPushButton("Toggle Favorite")
        self.favorite_button.clicked.connect(self._toggle_favorite)
        self.favorite_button.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #333;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
            QPushButton:pressed {
                background-color: #c69500;
            }
        """)

        preview_header_layout.addWidget(preview_label)
        preview_header_layout.addStretch()
        preview_header_layout.addWidget(self.favorite_button)
        preview_header_layout.addWidget(self.copy_button)

        right_layout.addWidget(preview_header_widget)

        # Preview text area
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                border: none;
                padding: 10px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                background-color: white;
            }
        """)
        right_layout.addWidget(self.preview_text, 3)

        # Metadata section
        metadata_widget = QWidget()
        metadata_widget.setStyleSheet("background-color: #f8f8f8; border: none; border-top: 1px solid #ccc;")
        metadata_layout = QVBoxLayout(metadata_widget)
        metadata_layout.setContentsMargins(10, 10, 10, 10)

        metadata_header = QLabel("Metadata")
        metadata_header.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        metadata_layout.addWidget(metadata_header)

        self.metadata_label = QLabel()
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setStyleSheet("color: #666;")
        metadata_layout.addWidget(self.metadata_label)

        right_layout.addWidget(metadata_widget, 1)

        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])

        main_layout.addWidget(splitter)

        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: white;
                border: 1px solid #ccc;
                color: #333;
            }
        """)
        main_layout.addWidget(self.status_label)

    def _create_toolbar(self):
        """Create toolbar with actions"""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #e0e0e0;
                border: none;
                border-bottom: 1px solid #ccc;
                padding: 5px;
                spacing: 5px;
            }
            QToolBar QToolButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 3px;
                padding: 5px;
                margin: 2px;
            }
            QToolBar QToolButton:hover {
                background-color: #d0d0d0;
                border: 1px solid #aaa;
            }
        """)

        # Refresh action
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self._load_entries)
        toolbar.addAction(refresh_action)

        # Clear action
        clear_action = QAction("Clear All", self)
        clear_action.triggered.connect(self._clear_history)
        toolbar.addAction(clear_action)

        # Export action
        export_action = QAction("Export", self)
        export_action.triggered.connect(self._export_history)
        toolbar.addAction(export_action)

        # Import action
        import_action = QAction("Import", self)
        import_action.triggered.connect(self._import_history)
        toolbar.addAction(import_action)

        toolbar.addSeparator()

        # Settings action
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._show_settings)
        toolbar.addAction(settings_action)

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

            self.status_label.setText(f"Loaded {len(self.current_entries)} entries")
            logger.info(f"Loaded {len(self.current_entries)} entries")

        except Exception as e:
            logger.error(f"Failed to load entries: {e}")
            self.status_label.setText(f"Error loading entries: {e}")

    def _add_entry_to_list(self, entry):
        """Add entry to list widget"""
        # Create display text
        preview = entry.content[:80].replace('\n', ' ')
        if len(entry.content) > 80:
            preview += "..."

        # Format timestamp
        time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Category prefix
        category_prefix = {
            "text": "[TXT]",
            "url": "[URL]",
            "file_path": "[FILE]",
            "email": "[EMAIL]"
        }
        prefix = category_prefix.get(entry.category, "[OTHER]")

        # Create list item text
        item_text = f"{prefix} {time_str}\n{preview}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, entry)

        # Set font
        font = QFont("Segoe UI", 9)
        item.setFont(font)

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

            # Update metadata
            metadata_lines = [
                f"Category: {entry.category}",
                f"Timestamp: {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Length: {len(entry.content)} characters",
                f"Hash: {entry.content_hash[:16]}..."
            ]
            self.metadata_label.setText("\n".join(metadata_lines))

    def _on_search(self, text):
        """Handle search input"""
        search_text = text.lower()

        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)

            if entry:
                # Check if entry matches search
                if search_text in entry.content.lower():
                    item.setHidden(False)
                else:
                    item.setHidden(True)

    def _on_filter_change(self, category):
        """Handle category filter change"""
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)

            if entry:
                if category == "All":
                    item.setHidden(False)
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
                    else:
                        item.setHidden(True)

    def _copy_to_clipboard(self):
        """Copy selected entry to clipboard"""
        current_item = self.history_list.currentItem()
        if current_item:
            entry = current_item.data(Qt.ItemDataRole.UserRole)
            if entry:
                pyperclip.copy(entry.content)
                self.status_label.setText(f"Copied to clipboard: {len(entry.content)} characters")
                logger.info(f"Copied entry to clipboard: {entry.content_hash[:8]}")

    def _toggle_favorite(self):
        """Toggle favorite status of selected entry"""
        current_item = self.history_list.currentItem()
        if current_item and self.repository:
            entry = current_item.data(Qt.ItemDataRole.UserRole)
            if entry:
                success = self.repository.toggle_favorite(entry.content_hash)
                if success:
                    self.status_label.setText("Favorite status toggled")
                    logger.info(f"Toggled favorite: {entry.content_hash[:8]}")

    def _clear_history(self):
        """Clear all history"""
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to clear all clipboard history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if self.clipboard_history:
                self.clipboard_history.clear()
            self.history_list.clear()
            self.preview_text.clear()
            self.metadata_label.clear()
            self.status_label.setText("History cleared")
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
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.clipboard_history.to_json())
                self.status_label.setText(f"Exported to {filename}")
                logger.info(f"History exported to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))
                logger.error(f"Export failed: {e}")

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
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.clipboard_history.from_json(f.read())
                self._load_entries()
                self.status_label.setText(f"Imported from {filename}")
                logger.info(f"History imported from {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))
                logger.error(f"Import failed: {e}")

    def _show_settings(self):
        """Show settings dialog"""
        QMessageBox.information(
            self,
            "Settings",
            "Settings can be edited in:\n%APPDATA%\\ClipboardHistory\\settings.yaml"
        )

    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("History viewer window closed")
        event.accept()