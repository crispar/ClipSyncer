"""Improved history viewer window with better styling"""

import sys
import pyperclip
from typing import Optional, List
from datetime import datetime
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QTextEdit, QPushButton,
    QLineEdit, QLabel, QMessageBox, QToolBar, QSplitter,
    QGroupBox, QCheckBox, QSpinBox, QComboBox, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QAction, QIcon, QFont, QKeySequence, QPalette, QColor
from loguru import logger


class HistoryViewer(QMainWindow):
    """Main history viewer window with improved styling"""

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

        # Set application style
        self.setStyleSheet("")  # Clear any problematic styles first

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Create toolbar
        self._create_toolbar()

        # Create search bar
        search_frame = QFrame()
        search_frame.setFrameStyle(QFrame.Shape.Box)
        search_layout = QHBoxLayout(search_frame)

        search_label = QLabel("Search:")
        search_label.setStyleSheet("QLabel { font-weight: bold; }")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search clipboard history...")
        self.search_input.textChanged.connect(self._on_search)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
                font-size: 14px;
            }
        """)

        category_label = QLabel("Category:")
        category_label.setStyleSheet("QLabel { font-weight: bold; }")

        self.search_category = QComboBox()
        self.search_category.addItems(["All", "Text", "URL", "File Path", "Email"])
        self.search_category.currentTextChanged.connect(self._on_filter_change)
        self.search_category.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)

        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(category_label)
        search_layout.addWidget(self.search_category)

        main_layout.addWidget(search_frame)

        # Create splitter for list and preview
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create history list
        list_frame = QFrame()
        list_frame.setFrameStyle(QFrame.Shape.Box)
        list_layout = QVBoxLayout(list_frame)

        list_label = QLabel("History")
        list_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        list_label.setStyleSheet("QLabel { padding: 5px; background-color: #f0f0f0; }")
        list_layout.addWidget(list_label)

        self.history_list = QListWidget()
        self.history_list.currentItemChanged.connect(self._on_selection_changed)
        self.history_list.itemDoubleClicked.connect(self._copy_to_clipboard)
        self.history_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ddd;
                background-color: white;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e1f5fe;
            }
        """)
        list_layout.addWidget(self.history_list)

        # Create preview panel
        preview_frame = QFrame()
        preview_frame.setFrameStyle(QFrame.Shape.Box)
        preview_layout = QVBoxLayout(preview_frame)

        # Preview header
        preview_header = QHBoxLayout()
        self.preview_label = QLabel("Preview")
        self.preview_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        self.preview_label.setStyleSheet("QLabel { padding: 5px; background-color: #f0f0f0; }")

        self.copy_button = QPushButton("📋 Copy to Clipboard")
        self.copy_button.clicked.connect(self._copy_to_clipboard)
        self.copy_button.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)

        self.favorite_button = QPushButton("⭐ Favorite")
        self.favorite_button.clicked.connect(self._toggle_favorite)
        self.favorite_button.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: black;
                border: none;
                padding: 8px 16px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)

        preview_header.addWidget(self.preview_label)
        preview_header.addStretch()
        preview_header.addWidget(self.favorite_button)
        preview_header.addWidget(self.copy_button)

        preview_layout.addLayout(preview_header)

        # Preview content
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ddd;
                background-color: white;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                padding: 10px;
            }
        """)
        preview_layout.addWidget(self.preview_text)

        # Metadata display
        self.metadata_label = QLabel()
        self.metadata_label.setWordWrap(True)
        self.metadata_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 3px;
            }
        """)
        preview_layout.addWidget(self.metadata_label)

        # Add frames to splitter
        splitter.addWidget(list_frame)
        splitter.addWidget(preview_frame)
        splitter.setSizes([400, 600])

        main_layout.addWidget(splitter)

        # Status bar
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("""
            QLabel {
                padding: 5px;
                background-color: #f0f0f0;
                border: 1px solid #ddd;
            }
        """)
        main_layout.addWidget(self.status_label)

    def _create_toolbar(self):
        """Create toolbar with actions"""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #f0f0f0;
                border: 1px solid #ddd;
                padding: 5px;
            }
        """)

        # Refresh action
        refresh_action = QAction("🔄 Refresh", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self._load_entries)
        toolbar.addAction(refresh_action)

        # Clear action
        clear_action = QAction("🗑️ Clear All", self)
        clear_action.triggered.connect(self._clear_history)
        toolbar.addAction(clear_action)

        # Export action
        export_action = QAction("💾 Export", self)
        export_action.triggered.connect(self._export_history)
        toolbar.addAction(export_action)

        # Import action
        import_action = QAction("📁 Import", self)
        import_action.triggered.connect(self._import_history)
        toolbar.addAction(import_action)

        toolbar.addSeparator()

        # Settings action
        settings_action = QAction("⚙️ Settings", self)
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
        preview = entry.content[:100].replace('\n', ' ')
        if len(entry.content) > 100:
            preview += "..."

        # Format timestamp
        time_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # Category emoji
        category_icons = {
            "text": "📝",
            "url": "🌐",
            "file_path": "📁",
            "email": "✉️"
        }
        icon = category_icons.get(entry.category, "📋")

        # Create list item
        item_text = f"{icon} [{time_str}]\n{preview}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, entry)

        self.history_list.addItem(item)

    def _on_selection_changed(self, current, previous):
        """Handle selection change"""
        if not current:
            return

        entry = current.data(Qt.ItemDataRole.UserRole)
        if entry:
            # Update preview
            self.preview_text.setPlainText(entry.content)

            # Update metadata
            metadata = f"📊 Metadata:\n"
            metadata += f"• Category: {entry.category}\n"
            metadata += f"• Timestamp: {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            metadata += f"• Length: {len(entry.content)} characters\n"
            metadata += f"• Hash: {entry.content_hash[:16]}..."

            self.metadata_label.setText(metadata)

    def _on_search(self, text):
        """Handle search input"""
        search_text = text.lower()

        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            entry = item.data(Qt.ItemDataRole.UserRole)

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

            if category == "All" or entry.category.lower() == category.lower().replace(" ", "_"):
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
                self.status_label.setText(f"✅ Copied to clipboard: {len(entry.content)} characters")
                logger.info(f"Copied entry to clipboard: {entry.content_hash[:8]}")

    def _toggle_favorite(self):
        """Toggle favorite status of selected entry"""
        current_item = self.history_list.currentItem()
        if current_item and self.repository:
            entry = current_item.data(Qt.ItemDataRole.UserRole)
            if entry:
                success = self.repository.toggle_favorite(entry.content_hash)
                if success:
                    self.status_label.setText("⭐ Favorite status toggled")
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
            # Clear database through repository if available
            self.history_list.clear()
            self.preview_text.clear()
            self.metadata_label.clear()
            self.status_label.setText("🗑️ History cleared")
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
                self.status_label.setText(f"💾 Exported to {filename}")
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
                self.status_label.setText(f"📁 Imported from {filename}")
                logger.info(f"History imported from {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", str(e))
                logger.error(f"Import failed: {e}")

    def _show_settings(self):
        """Show settings dialog"""
        QMessageBox.information(
            self,
            "Settings",
            "Settings dialog will be implemented soon!\n\nFor now, edit config/settings.yaml"
        )

    def closeEvent(self, event):
        """Handle window close event"""
        logger.info("History viewer window closed")
        event.accept()