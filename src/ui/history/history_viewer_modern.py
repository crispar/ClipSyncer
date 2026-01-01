"""Modern history viewer with Windows 11 Fluent Design using PyQt6-Fluent-Widgets"""

import sys
import pyperclip
from typing import Optional, List
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QListWidgetItem, QLabel, QSplitter
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QFont

# Import Fluent Design components
from qfluentwidgets import (
    ListWidget, TextEdit, PushButton, LineEdit,
    ComboBox, ToolButton, InfoBar, InfoBarPosition, Theme,
    setTheme, isDarkTheme, FluentIcon as FIF, SearchLineEdit,
    CardWidget, BodyLabel, SubtitleLabel, TitleLabel, CaptionLabel,
    TransparentToolButton, PrimaryPushButton, ToggleButton,
    MessageBox, Dialog, StateToolTip, setThemeColor,
    FluentStyleSheet, qconfig, RoundMenu, Action
)
from loguru import logger


class ModernHistoryViewer(QMainWindow):
    """Modern history viewer window with Windows 11 Fluent Design"""

    def __init__(self, clipboard_history=None, repository=None, config_manager=None):
        """
        Initialize history viewer

        Args:
            clipboard_history: ClipboardHistory instance
            repository: ClipboardRepository instance
            config_manager: ConfigManager instance for settings reload
        """
        super().__init__()
        self.clipboard_history = clipboard_history
        self.repository = repository
        self.config_manager = config_manager
        self.current_entries = []
        self.last_entry_count = 0

        # Set window properties
        self.setWindowTitle("Clipboard History")
        self.resize(1100, 750)

        # Apply Fluent Design theme
        self._setup_theme()

        self._init_ui()
        self._load_entries()

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

        # Create splitter for content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

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

            # Update last entry count (use actual DB count to match _check_for_updates)
            if self.repository:
                self.last_entry_count = self.repository.get_entry_count()
            else:
                self.last_entry_count = len(self.current_entries)

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

    def _check_for_updates(self):
        """Check for new clipboard entries and refresh if needed"""
        try:
            # Get current entry count from the actual source
            if self.repository:
                current_count = self.repository.get_entry_count()
            elif self.clipboard_history:
                current_count = len(self.clipboard_history.get_entries())
            else:
                return

            # If count changed, refresh the list
            if current_count != self.last_entry_count:
                # Remember current selection
                current_row = self.history_list.currentRow()
                current_item_content = None

                if current_row >= 0 and current_row < len(self.current_entries):
                    current_item_content = self.current_entries[current_row].content

                # Reload entries - this will update self.last_entry_count
                self._load_entries()

                # Try to restore selection based on content
                if current_item_content:
                    for i, entry in enumerate(self.current_entries):
                        if entry.content == current_item_content:
                            self.history_list.setCurrentRow(i)
                            break
                    else:
                        # If not found, select the first item
                        if self.history_list.count() > 0:
                            self.history_list.setCurrentRow(0)
                elif self.history_list.count() > 0:
                    # Select the first (newest) item
                    self.history_list.setCurrentRow(0)

                # Show notification only for new entries (not deletions)
                if current_count > self.last_entry_count:
                    InfoBar.success(
                        title="New Entry",
                        content="Clipboard history updated",
                        orient=Qt.Orientation.Horizontal,
                        isClosable=True,
                        position=InfoBarPosition.BOTTOM_RIGHT,
                        duration=1500,
                        parent=self
                    )

        except Exception as e:
            logger.error(f"Error checking for updates: {e}")

    def _add_entry_to_list(self, entry):
        """Add entry to list widget with modern styling"""
        # Create display text
        preview = entry.content[:80].replace('\n', ' ')
        if len(entry.content) > 80:
            preview += "..."

        # Format timestamp
        time_str = entry.timestamp.strftime("%H:%M · %b %d")

        # Category icon mapping (using text icons for simplicity)
        category_icons = {
            "text": "📝",
            "url": "🌐",
            "file_path": "📁",
            "email": "✉️"
        }
        icon = category_icons.get(entry.category, "📋")

        # Category names
        category_names = {
            "text": "Text",
            "url": "Link",
            "file_path": "File",
            "email": "Email"
        }
        category_name = category_names.get(entry.category, "Other")

        # Create list item with rich formatting
        item_text = f"{icon} {time_str}\n{preview}\n{category_name} · {len(entry.content)} chars"
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
        """Handle GitHub settings being saved"""
        logger.info("GitHub settings saved, reinitializing sync service...")

        # Reinitialize GitHub sync service if main app reference exists
        if hasattr(self, 'main_app') and self.main_app:
            try:
                # Reinitialize encryption manager with updated key
                from src.core.encryption import KeyManager, EncryptionManager
                key_manager = KeyManager()
                encryption_key = key_manager.get_or_create_key()
                self.main_app.encryption_manager = EncryptionManager(encryption_key)
                logger.info("Encryption manager reinitialized with updated key")

                # Update GitHub sync service with new settings
                from src.services.sync.github_sync import GitHubSyncService

                self.main_app.github_sync = GitHubSyncService(
                    token=settings.get('token'),
                    repository=settings.get('repository')
                )
                logger.info("GitHub sync service reinitialized")

                # Reinitialize auto sync service if GitHub sync is enabled
                if self.main_app.github_sync.enabled:
                    from src.services.auto_sync_service import AutoSyncService
                    pull_interval = 60  # Default 60 seconds

                    # Stop existing auto sync service if any
                    if self.main_app.auto_sync_service:
                        self.main_app.auto_sync_service.stop()

                    self.main_app.auto_sync_service = AutoSyncService(pull_interval_seconds=pull_interval)
                    self.main_app.auto_sync_service.set_push_callback(self.main_app._push_to_github)
                    self.main_app.auto_sync_service.set_pull_callback(self.main_app._pull_from_github)
                    self.main_app.auto_sync_service.start()
                    logger.info("Auto sync service reinitialized")

                # Show success notification
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

    def _restore_from_github(self):
        """Show dialog to restore from GitHub backup"""
        try:
            from src.ui.dialogs.restore_dialog import RestoreDialog

            # Get current app instance for access to services
            app = QApplication.instance()
            if hasattr(app, 'main_window'):
                main = app.main_window

                if main.github_sync and main.github_sync.enabled:
                    dialog = RestoreDialog(
                        main.github_sync,
                        main.repository,
                        main.encryption_manager,
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
            else:
                InfoBar.error(
                    title="Error",
                    content="Cannot access main application services",
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