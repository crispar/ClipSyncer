"""GitHub Settings Dialog for configuring sync"""

from typing import Optional, Callable, Tuple
from urllib.parse import urlparse
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QDialog
from qfluentwidgets import (
    LineEdit, PasswordLineEdit, PushButton, PrimaryPushButton,
    BodyLabel, CaptionLabel, InfoBar, InfoBarPosition,
    MessageBox, StateToolTip, FluentIcon as FIF, isDarkTheme, setTheme, Theme
)
from loguru import logger
import yaml
import os


class GitHubSettingsDialog(QDialog):
    """Dialog for configuring GitHub sync settings"""

    settings_saved = pyqtSignal(dict)  # Signal emitted when settings are saved
    restore_requested = pyqtSignal()  # Signal emitted when restore is requested

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set window properties
        self.setWindowTitle("GitHub Sync Settings")
        self.setModal(True)

        # Apply theme-aware styling
        self._apply_theme_style()

        # Load current settings
        self.current_settings = self._load_current_settings()

        # Setup UI
        self._setup_ui()

        # Set window properties
        self.setFixedWidth(500)
        self.setFixedHeight(550)

    def _apply_theme_style(self):
        """Apply appropriate styling based on system theme"""
        if isDarkTheme():
            # Dark theme styling
            self.setStyleSheet("""
                QDialog {
                    background-color: #202020;
                    color: #ffffff;
                }
                QLabel {
                    color: #ffffff;
                }
                LineEdit, PasswordLineEdit {
                    background-color: #2d2d2d;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 8px;
                    color: #ffffff;
                    font-size: 13px;
                }
                LineEdit:focus, PasswordLineEdit:focus {
                    border: 1px solid #0078d4;
                    background-color: #333333;
                }
                LineEdit::placeholder, PasswordLineEdit::placeholder {
                    color: #888888;
                }
            """)
        else:
            # Light theme styling
            self.setStyleSheet("""
                QDialog {
                    background-color: #f3f3f3;
                    color: #000000;
                }
                QLabel {
                    color: #000000;
                }
                LineEdit, PasswordLineEdit {
                    background-color: #ffffff;
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    padding: 8px;
                    color: #000000;
                    font-size: 13px;
                }
                LineEdit:focus, PasswordLineEdit:focus {
                    border: 1px solid #0078d4;
                }
                LineEdit::placeholder, PasswordLineEdit::placeholder {
                    color: #999999;
                }
            """)

    def _load_current_settings(self) -> dict:
        """Load current GitHub settings from config"""
        try:
            config_path = os.path.join(
                os.environ.get('APPDATA', '.'),
                'ClipboardHistory',
                'github_settings.yaml'
            )

            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    settings = yaml.safe_load(f) or {}
                    return settings.get('github', {})

        except Exception as e:
            logger.error(f"Failed to load GitHub settings: {e}")

        return {}

    def _setup_ui(self):
        """Setup the dialog UI"""
        # Create main layout for the dialog
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Instructions
        instructions = CaptionLabel(
            "Configure GitHub as your primary clipboard storage.\n"
            "Local storage will be used as cache only.\n"
            "You'll need a GitHub Personal Access Token with 'repo' permissions."
        )
        instructions.setWordWrap(True)
        main_layout.addWidget(instructions)

        # Repository URL field (full URL)
        repo_label = BodyLabel("Repository Full URL:")
        main_layout.addWidget(repo_label)

        self.repo_input = LineEdit()
        self.repo_input.setPlaceholderText("e.g., https://github.com/username/repo or https://github.sec.samsung.net/username/repo")

        # Try to reconstruct full URL from existing settings
        existing_repo = self.current_settings.get('repository', '')
        existing_enterprise = self.current_settings.get('enterprise_url', '')
        if existing_repo:
            if existing_enterprise:
                full_url = f"{existing_enterprise}/{existing_repo}"
            else:
                full_url = f"https://github.com/{existing_repo}"
            self.repo_input.setText(full_url)

        main_layout.addWidget(self.repo_input)

        # Token field
        token_label = BodyLabel("Personal Access Token:")
        main_layout.addWidget(token_label)

        self.token_input = PasswordLineEdit()
        self.token_input.setPlaceholderText("ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

        # Show token if it exists (masked)
        if self.current_settings.get('token'):
            self.token_input.setText(self.current_settings['token'])

        main_layout.addWidget(self.token_input)

        # Sync Password field (for multi-device encryption)
        sync_password_label = BodyLabel("Sync Password (for multi-device encryption):")
        main_layout.addWidget(sync_password_label)

        self.sync_password_input = PasswordLineEdit()
        self.sync_password_input.setPlaceholderText("Enter same password on all devices")

        # Check if sync password exists
        from src.core.encryption import KeyManager
        self._key_manager = KeyManager()
        if self._key_manager.has_sync_password():
            self.sync_password_input.setPlaceholderText("Password already set (leave empty to keep)")

        main_layout.addWidget(self.sync_password_input)

        sync_password_hint = CaptionLabel(
            "Use the same password on all PCs to share encrypted clipboard data."
        )
        sync_password_hint.setWordWrap(True)
        main_layout.addWidget(sync_password_hint)

        # Auto-sync option
        self.auto_sync_label = BodyLabel("Auto-sync interval (minutes, 0 to disable):")
        main_layout.addWidget(self.auto_sync_label)

        self.auto_sync_input = LineEdit()
        self.auto_sync_input.setPlaceholderText("e.g., 30")
        # Try both old and new key names for backwards compatibility
        auto_sync_value = self.current_settings.get('auto_sync_interval_minutes',
                                                    self.current_settings.get('auto_sync_interval', 0))
        self.auto_sync_input.setText(str(auto_sync_value))
        main_layout.addWidget(self.auto_sync_input)

        # Help link
        help_label = CaptionLabel(
            '<a href="https://github.com/settings/tokens">Create GitHub Token</a> | '
            '<a href="https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token">Documentation</a>'
        )
        help_label.setOpenExternalLinks(True)
        main_layout.addWidget(help_label)

        # Add spacing
        main_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.restore_button = PushButton("Restore Backup", self, FIF.DOWNLOAD)
        self.restore_button.clicked.connect(self._request_restore)
        button_layout.addWidget(self.restore_button)

        self.test_button = PushButton("Test Connection", self, FIF.SYNC)
        self.test_button.clicked.connect(self._test_connection)
        button_layout.addWidget(self.test_button)

        self.save_button = PrimaryPushButton("Save", self, FIF.SAVE)
        self.save_button.clicked.connect(self._save_settings)
        button_layout.addWidget(self.save_button)

        self.cancel_button = PushButton("Cancel", self)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)

    def _parse_github_url(self, url: str) -> Tuple[str, str, Optional[str]]:
        """
        Parse GitHub URL to extract repository and enterprise URL

        Args:
            url: Full GitHub URL (e.g., https://github.com/user/repo or https://github.sec.samsung.net/user/repo)

        Returns:
            Tuple of (repository, base_url, enterprise_url)
            - repository: "username/repo"
            - base_url: The base URL (e.g., "https://github.com" or "https://github.sec.samsung.net")
            - enterprise_url: None for github.com, base URL for enterprise
        """
        if not url:
            return "", "", None

        # Clean up URL
        url = url.strip().rstrip('/')

        # Parse URL
        parsed = urlparse(url)

        # Extract base URL
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Extract repository path (remove leading /)
        path = parsed.path.lstrip('/')

        # Remove .git suffix if present
        if path.endswith('.git'):
            path = path[:-4]

        # For GitHub.com
        if parsed.netloc == 'github.com':
            return path, base_url, None
        else:
            # For GitHub Enterprise
            return path, base_url, base_url

    def _test_connection(self):
        """Test GitHub connection with provided settings"""
        repo_url = self.repo_input.text().strip()
        token = self.token_input.text().strip()

        if not repo_url or not token:
            InfoBar.warning(
                title="Missing Information",
                content="Please enter both repository and token",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Show progress
        state_tooltip = StateToolTip("Testing", "Connecting to GitHub...", self)
        state_tooltip.move(self.geometry().center())
        state_tooltip.show()

        # Parse the repository URL
        repository, base_url, enterprise_url = self._parse_github_url(repo_url)

        if not repository:
            InfoBar.warning(
                title="Invalid URL",
                content="Please enter a valid GitHub repository URL",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            state_tooltip.hide()
            return

        try:
            # Import GitHub sync service
            from src.services.sync.github_sync import GitHubSyncService

            # Test connection with parsed enterprise URL
            sync_service = GitHubSyncService(token, repository, enterprise_url)

            if sync_service.test_connection():
                state_tooltip.setContent("Connection successful!")
                state_tooltip.setState(True)

                InfoBar.success(
                    title="Success",
                    content="GitHub connection successful!",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )
            else:
                state_tooltip.setContent("Connection failed")
                state_tooltip.setState(False)

                InfoBar.error(
                    title="Connection Failed",
                    content="Could not connect to GitHub. Check your token and repository.",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=3000,
                    parent=self
                )

        except Exception as e:
            state_tooltip.setContent(f"Error: {str(e)}")
            state_tooltip.setState(False)

            InfoBar.error(
                title="Error",
                content=f"Connection test failed: {str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

        finally:
            state_tooltip.hide()

    def _save_settings(self):
        """Save GitHub settings"""
        repo_url = self.repo_input.text().strip()
        token = self.token_input.text().strip()
        sync_password = self.sync_password_input.text()

        try:
            auto_sync = int(self.auto_sync_input.text().strip() or "0")
        except ValueError:
            auto_sync = 0

        if not repo_url or not token:
            InfoBar.warning(
                title="Missing Information",
                content="Please enter both repository and token",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Parse the repository URL
        repository, base_url, enterprise_url = self._parse_github_url(repo_url)

        if not repository:
            InfoBar.warning(
                title="Invalid URL",
                content="Please enter a valid GitHub repository URL",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Check sync password requirement
        if not self._key_manager.has_sync_password() and not sync_password:
            InfoBar.warning(
                title="Sync Password Required",
                content="Please enter a sync password for multi-device encryption",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Set sync password if provided
        if sync_password:
            try:
                self._key_manager.set_sync_password(sync_password)
                logger.info("Sync password updated")
            except Exception as e:
                logger.error(f"Failed to set sync password: {e}")
                InfoBar.error(
                    title="Password Error",
                    content=f"Failed to set sync password: {str(e)}",
                    orient=Qt.Orientation.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=5000,
                    parent=self
                )
                return

        # Save settings with parsed URL values
        settings = {
            'github': {
                'repository': repository,
                'token': token,
                'enterprise_url': enterprise_url,
                'auto_sync_interval_minutes': auto_sync,
                'auto_sync_enabled': auto_sync > 0,
                'enabled': True,
                'is_primary_storage': True  # New flag to indicate GitHub is primary
            }
        }

        try:
            # Create config directory if it doesn't exist
            config_dir = os.path.join(
                os.environ.get('APPDATA', '.'),
                'ClipboardHistory'
            )
            os.makedirs(config_dir, exist_ok=True)

            # Save to file
            config_path = os.path.join(config_dir, 'github_settings.yaml')

            with open(config_path, 'w') as f:
                yaml.safe_dump(settings, f)

            # Emit signal with new settings
            self.settings_saved.emit(settings['github'])

            InfoBar.success(
                title="Settings Saved",
                content="GitHub sync settings have been saved successfully",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )

            logger.info("GitHub settings saved successfully")

            # Close dialog
            self.accept()

        except Exception as e:
            logger.error(f"Failed to save GitHub settings: {e}")

            InfoBar.error(
                title="Save Failed",
                content=f"Failed to save settings: {str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def _request_restore(self):
        """Emit signal to request restore from backup"""
        # Check if GitHub is configured
        repo = self.repo_input.text().strip()
        token = self.token_input.text().strip()

        if not repo or not token:
            InfoBar.warning(
                title="GitHub Not Configured",
                content="Please configure GitHub settings before restoring",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # Emit signal to trigger restore dialog
        self.restore_requested.emit()
        # Close this dialog
        self.accept()