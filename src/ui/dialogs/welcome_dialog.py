"""Welcome/First Run Setup Dialog"""

from typing import Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QDialog, QWidget
from qfluentwidgets import (
    PrimaryPushButton, PushButton, TitleLabel, BodyLabel,
    CaptionLabel, InfoBar, InfoBarPosition, FluentIcon as FIF,
    isDarkTheme
)
from loguru import logger
import os
import yaml


class WelcomeDialog(QDialog):
    """Welcome dialog for first-time setup"""

    setup_completed = pyqtSignal(dict)  # Signal emitted when setup is complete
    setup_skipped = pyqtSignal()  # Signal emitted when user skips setup

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set window properties
        self.setWindowTitle("Welcome to ClipSyncer")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Apply theme styling
        self._apply_theme_style()

        # Setup UI
        self._setup_ui()

        # Set window size
        self.setFixedSize(600, 450)

    def _apply_theme_style(self):
        """Apply theme-aware styling"""
        if isDarkTheme():
            self.setStyleSheet("""
                QDialog {
                    background-color: #202020;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #f3f3f3;
                    color: #000000;
                }
                QLabel {
                    color: #000000;
                }
            """)

    def _setup_ui(self):
        """Setup the dialog UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # Welcome title
        title = TitleLabel("Welcome to ClipSyncer!")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)

        # Subtitle
        subtitle = BodyLabel("Secure Clipboard History with GitHub Sync")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 16px; color: #666666;")
        main_layout.addWidget(subtitle)

        # Add spacing
        main_layout.addSpacing(20)

        # Feature highlights
        features_layout = QVBoxLayout()
        features_layout.setSpacing(15)

        features = [
            ("🔒", "End-to-end encryption for your clipboard data"),
            ("☁️", "GitHub as primary storage - access from anywhere"),
            ("🔄", "Automatic sync across all your devices"),
            ("📝", "Full clipboard history with search and categories"),
            ("🏢", "Support for GitHub Enterprise (Samsung, etc.)")
        ]

        for icon, text in features:
            feature_layout = QHBoxLayout()
            feature_layout.setSpacing(10)

            icon_label = BodyLabel(icon)
            icon_label.setFixedWidth(30)
            icon_label.setStyleSheet("font-size: 20px;")
            feature_layout.addWidget(icon_label)

            text_label = BodyLabel(text)
            text_label.setWordWrap(True)
            feature_layout.addWidget(text_label, 1)

            features_layout.addLayout(feature_layout)

        main_layout.addLayout(features_layout)

        # Add spacing before buttons
        main_layout.addStretch()

        # Info message
        info_label = CaptionLabel(
            "To get started, you'll need to configure GitHub as your storage backend.\n"
            "This ensures your clipboard data is safely stored and synced."
        )
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("color: #888888; margin: 10px 0;")
        main_layout.addWidget(info_label)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        # Skip button (for users who want to use local-only)
        self.skip_button = PushButton("Use Local Storage Only", self)
        self.skip_button.clicked.connect(self._on_skip)
        button_layout.addWidget(self.skip_button)

        button_layout.addStretch()

        # Setup GitHub button (primary action)
        self.setup_button = PrimaryPushButton("Setup GitHub Storage", self, FIF.GITHUB)
        self.setup_button.clicked.connect(self._on_setup)
        button_layout.addWidget(self.setup_button)

        main_layout.addLayout(button_layout)

    def _on_setup(self):
        """Handle setup button click"""
        # Close this dialog
        self.accept()

        # Import and show GitHub settings dialog
        from src.ui.dialogs.github_settings_dialog import GitHubSettingsDialog

        settings_dialog = GitHubSettingsDialog(self.parent())
        settings_dialog.settings_saved.connect(self._on_settings_saved)
        settings_dialog.exec()

    def _on_settings_saved(self, settings):
        """Handle settings saved from GitHub dialog"""
        # Emit setup completed signal with settings
        self.setup_completed.emit(settings)

    def _on_skip(self):
        """Handle skip button click"""
        # Create minimal configuration for local-only mode
        config_dir = os.path.join(
            os.environ.get('APPDATA', '.'),
            'ClipboardHistory'
        )
        os.makedirs(config_dir, exist_ok=True)

        # Mark first run as complete
        first_run_file = os.path.join(config_dir, '.first_run_complete')
        with open(first_run_file, 'w') as f:
            f.write('local_only')

        logger.info("User chose local storage only mode")

        # Emit skipped signal
        self.setup_skipped.emit()

        # Close dialog
        self.accept()


def check_first_run() -> bool:
    """
    Check if this is the first run of the application

    Returns:
        True if first run, False otherwise
    """
    config_dir = os.path.join(
        os.environ.get('APPDATA', '.'),
        'ClipboardHistory'
    )

    # Check for first run marker file
    first_run_file = os.path.join(config_dir, '.first_run_complete')

    # Also check if GitHub settings exist
    github_settings_file = os.path.join(config_dir, 'github_settings.yaml')

    # It's first run if neither file exists
    is_first_run = not os.path.exists(first_run_file) and not os.path.exists(github_settings_file)

    return is_first_run


def mark_first_run_complete():
    """Mark that first run setup has been completed"""
    config_dir = os.path.join(
        os.environ.get('APPDATA', '.'),
        'ClipboardHistory'
    )
    os.makedirs(config_dir, exist_ok=True)

    first_run_file = os.path.join(config_dir, '.first_run_complete')
    with open(first_run_file, 'w') as f:
        f.write('completed')