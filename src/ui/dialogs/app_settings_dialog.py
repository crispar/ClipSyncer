"""App Settings Dialog for general application settings"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QDialog
from qfluentwidgets import (
    PushButton, PrimaryPushButton,
    BodyLabel, CaptionLabel, InfoBar, InfoBarPosition,
    SwitchButton, isDarkTheme
)
from loguru import logger
import yaml
import os


class AppSettingsDialog(QDialog):
    """Dialog for configuring general application settings"""

    settings_saved = pyqtSignal(dict)  # Signal emitted when settings are saved

    @property
    def _config_path(self) -> str:
        """Get config file path"""
        return os.path.join(
            os.environ.get('APPDATA', '.'),
            'ClipboardHistory',
            'settings.yaml'
        )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark_theme = isDarkTheme()

        # Set window properties
        self.setWindowTitle("App Settings")
        self.setModal(True)

        # Apply theme-aware styling
        self._apply_theme_style()

        # Load current settings
        self.current_settings = self._load_current_settings()

        # Setup UI
        self._setup_ui()

        # Set window size
        self.setFixedWidth(400)
        self.setFixedHeight(250)

    def _apply_theme_style(self):
        """Apply appropriate styling based on system theme"""
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

    def _load_current_settings(self) -> dict:
        """Load current settings from config"""
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    settings = yaml.safe_load(f) or {}
                    return settings

        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

        # Return defaults
        return {
            'ui': {
                'show_notifications': True
            }
        }

    def _setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title_label = BodyLabel("App Settings")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title_label)

        # Notifications section
        notifications_section = QWidget()
        notifications_layout = QHBoxLayout(notifications_section)
        notifications_layout.setContentsMargins(0, 8, 0, 8)

        notifications_label_container = QWidget()
        notifications_label_layout = QVBoxLayout(notifications_label_container)
        notifications_label_layout.setContentsMargins(0, 0, 0, 0)
        notifications_label_layout.setSpacing(2)

        notifications_label = BodyLabel("Show Notifications")
        notifications_desc = CaptionLabel("Show popup when clipboard content is captured")
        desc_color = "#aaaaaa" if self._is_dark_theme else "#888888"
        notifications_desc.setStyleSheet(f"color: {desc_color};")

        notifications_label_layout.addWidget(notifications_label)
        notifications_label_layout.addWidget(notifications_desc)

        self.notifications_switch = SwitchButton()
        self.notifications_switch.setChecked(
            self.current_settings.get('ui', {}).get('show_notifications', True)
        )

        notifications_layout.addWidget(notifications_label_container)
        notifications_layout.addStretch()
        notifications_layout.addWidget(self.notifications_switch)

        layout.addWidget(notifications_section)

        # Add stretch to push buttons to bottom
        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        cancel_btn = PushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        save_btn = PrimaryPushButton("Save")
        save_btn.clicked.connect(self._save_settings)

        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

    def _save_settings(self):
        """Save settings to config file"""
        try:
            # Load existing settings
            settings = {}
            if os.path.exists(self._config_path):
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    settings = yaml.safe_load(f) or {}

            # Update UI settings
            if 'ui' not in settings:
                settings['ui'] = {}

            settings['ui']['show_notifications'] = self.notifications_switch.isChecked()

            # Save to file
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, 'w', encoding='utf-8') as f:
                yaml.dump(settings, f, default_flow_style=False)

            logger.info(f"App settings saved: show_notifications={settings['ui']['show_notifications']}")

            # Show success message
            InfoBar.success(
                title="Saved",
                content="Settings saved successfully",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

            # Emit signal with updated settings
            self.settings_saved.emit(settings)

            # Close dialog after short delay
            QTimer.singleShot(500, self.accept)

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            InfoBar.error(
                title="Error",
                content=f"Failed to save settings: {str(e)}",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
