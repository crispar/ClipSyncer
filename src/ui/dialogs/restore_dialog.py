"""GitHub Backup Restore Dialog"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QDialog, QListWidget, QListWidgetItem
from qfluentwidgets import (
    PushButton, PrimaryPushButton, BodyLabel, CaptionLabel,
    InfoBar, InfoBarPosition, StateToolTip, FluentIcon as FIF,
    ListWidget, isDarkTheme, ProgressBar
)
from loguru import logger
import yaml
import os


class RestoreWorker(QThread):
    """Worker thread for restore operation"""

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, github_sync, filename, repository, encryption_manager):
        super().__init__()
        self.github_sync = github_sync
        self.filename = filename
        self.repository = repository
        self.encryption_manager = encryption_manager

    def run(self):
        """Run restore operation in background"""
        try:
            # Download backup from GitHub
            self.progress.emit("Downloading backup from GitHub...")
            backup_data = self.github_sync.download_backup(self.filename)

            if not backup_data:
                self.finished.emit(False, "Failed to download backup")
                return

            # Decrypt the backup
            self.progress.emit("Decrypting backup data...")
            decrypted_data = self.encryption_manager.decrypt_json(backup_data)

            if not decrypted_data:
                self.finished.emit(False, "Failed to decrypt backup")
                return

            # Clear existing data
            self.progress.emit("Clearing existing data...")
            self.repository.clear_all()

            # Restore entries
            entries = decrypted_data.get('entries', [])
            total = len(entries)

            for i, entry_data in enumerate(entries):
                self.progress.emit(f"Restoring entry {i+1}/{total}...")

                # Create ClipboardEntry from data
                from src.core.clipboard.history import ClipboardEntry
                entry = ClipboardEntry(
                    content=entry_data['content'],
                    timestamp=datetime.fromisoformat(entry_data['timestamp']),
                    content_hash=entry_data.get('content_hash'),
                    category=entry_data.get('category'),
                    metadata=entry_data.get('metadata', {})
                )

                # Save to database
                self.repository.save_entry(entry)

            self.finished.emit(True, f"Successfully restored {total} entries")

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            self.finished.emit(False, str(e))


class RestoreDialog(QDialog):
    """Dialog for restoring from GitHub backup"""

    restore_completed = pyqtSignal()

    def __init__(self, github_sync, repository, encryption_manager, parent=None):
        super().__init__(parent)
        self.github_sync = github_sync
        self.repository = repository
        self.encryption_manager = encryption_manager
        self.backups = []

        self.setWindowTitle("Restore from GitHub Backup")
        self.setModal(True)
        self._setup_ui()
        self._apply_theme_style()
        self.setFixedSize(600, 500)

        # Load available backups
        self._load_backups()

    def _apply_theme_style(self):
        """Apply theme-aware styling"""
        if isDarkTheme():
            self.setStyleSheet("""
                QDialog {
                    background-color: #202020;
                    color: #ffffff;
                }
                QListWidget {
                    background-color: #2d2d2d;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    color: #ffffff;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                }
                QListWidget::item:hover {
                    background-color: #404040;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f3f3f3;
                    color: #000000;
                }
                QListWidget {
                    background-color: #ffffff;
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    color: #000000;
                }
                QListWidget::item:selected {
                    background-color: #0078d4;
                    color: #ffffff;
                }
                QListWidget::item:hover {
                    background-color: #e0e0e0;
                }
            """)

    def _setup_ui(self):
        """Setup the dialog UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = BodyLabel("Select a backup to restore:")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        main_layout.addWidget(title)

        # Warning
        warning = CaptionLabel(
            "⚠️ Warning: Restoring will replace ALL current clipboard history!\n"
            "This action cannot be undone."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #ff9800;")
        main_layout.addWidget(warning)

        # Backup list
        self.backup_list = QListWidget()
        self.backup_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        main_layout.addWidget(self.backup_list, 1)

        # Info label
        self.info_label = CaptionLabel("Loading backups...")
        main_layout.addWidget(self.info_label)

        # Progress bar
        self.progress_bar = ProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.refresh_button = PushButton("Refresh", self, FIF.SYNC)
        self.refresh_button.clicked.connect(self._load_backups)
        button_layout.addWidget(self.refresh_button)

        self.restore_button = PrimaryPushButton("Restore", self, FIF.DOWNLOAD)
        self.restore_button.clicked.connect(self._restore_backup)
        self.restore_button.setEnabled(False)
        button_layout.addWidget(self.restore_button)

        self.cancel_button = PushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)

    def _load_backups(self):
        """Load available backups from GitHub"""
        try:
            self.backup_list.clear()
            self.backups = []
            self.info_label.setText("Loading backups...")
            self.restore_button.setEnabled(False)

            if not self.github_sync or not self.github_sync.enabled:
                self.info_label.setText("GitHub sync not configured")
                return

            # Get list of backups
            self.backups = self.github_sync.list_backups()

            if not self.backups:
                self.info_label.setText("No backups found")
                return

            # Add to list widget
            for backup in self.backups:
                item = QListWidgetItem()
                filename = backup['filename']
                size_kb = backup['size'] / 1024

                # Parse timestamp from filename
                if filename.startswith('auto_backup_') or filename.startswith('clipboard_backup_'):
                    try:
                        date_str = filename.split('_')[-1].replace('.json', '')
                        timestamp = datetime.strptime(date_str, "%Y%m%d_%H%M%S" if '_' in date_str else "%Y%m%d%H%M%S")
                        date_display = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        date_display = filename
                else:
                    date_display = filename

                item.setText(f"{date_display} ({size_kb:.1f} KB)")
                item.setData(Qt.ItemDataRole.UserRole, backup)
                self.backup_list.addItem(item)

            self.info_label.setText(f"Found {len(self.backups)} backup(s)")

        except Exception as e:
            logger.error(f"Failed to load backups: {e}")
            self.info_label.setText(f"Error: {str(e)}")

    def _on_item_double_clicked(self, item):
        """Handle double-click on backup item"""
        self._restore_backup()

    def _restore_backup(self):
        """Restore selected backup"""
        current_item = self.backup_list.currentItem()
        if not current_item:
            InfoBar.warning(
                title="No Selection",
                content="Please select a backup to restore",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        backup = current_item.data(Qt.ItemDataRole.UserRole)
        filename = backup['filename']

        # Confirm action
        from qfluentwidgets import MessageBox
        w = MessageBox(
            "Confirm Restore",
            f"Are you sure you want to restore from:\n{filename}\n\n"
            "This will REPLACE all current clipboard history!",
            self
        )
        w.yesButton.setText("Restore")
        w.cancelButton.setText("Cancel")

        if not w.exec():
            return

        # Disable UI during restore
        self.backup_list.setEnabled(False)
        self.refresh_button.setEnabled(False)
        self.restore_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setVisible(True)

        # Create worker thread
        self.worker = RestoreWorker(
            self.github_sync,
            filename,
            self.repository,
            self.encryption_manager
        )

        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_restore_finished)
        self.worker.start()

    def _on_progress(self, message: str):
        """Update progress message"""
        self.info_label.setText(message)

    def _on_restore_finished(self, success: bool, message: str):
        """Handle restore completion"""
        self.progress_bar.setVisible(False)
        self.backup_list.setEnabled(True)
        self.refresh_button.setEnabled(True)
        self.restore_button.setEnabled(True)
        self.cancel_button.setEnabled(True)

        if success:
            InfoBar.success(
                title="Restore Complete",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            self.restore_completed.emit()
            self.accept()
        else:
            InfoBar.error(
                title="Restore Failed",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
            self.info_label.setText("Restore failed")