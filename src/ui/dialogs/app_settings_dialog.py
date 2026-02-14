"""App Settings Dialog for general application settings"""

from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QDialog, QScrollArea
from qfluentwidgets import (
    PushButton, PrimaryPushButton,
    BodyLabel, CaptionLabel, InfoBar, InfoBarPosition,
    SwitchButton, isDarkTheme, ComboBox, SpinBox,
    SubtitleLabel
)
from loguru import logger
import os
from src.utils import ConfigManager


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
        self.setFixedWidth(480)
        self.setMinimumHeight(420)

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
            cm = ConfigManager(self._config_path)
            return cm.get_all()
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

        # Return defaults
        return {
            'ui': {
                'show_notifications': True,
                'theme': 'auto'
            },
            'clipboard': {
                'check_interval': 500,
                'max_history_size': 500
            },
            'storage': {
                'retention_days': 30
            }
        }

    def _create_setting_row(self, label_text, desc_text, widget):
        """Helper to create a consistent setting row"""
        section = QWidget()
        section_layout = QHBoxLayout(section)
        section_layout.setContentsMargins(0, 6, 0, 6)

        label_container = QWidget()
        label_layout = QVBoxLayout(label_container)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(2)

        label = BodyLabel(label_text)
        desc = CaptionLabel(desc_text)
        desc_color = "#aaaaaa" if self._is_dark_theme else "#888888"
        desc.setStyleSheet(f"color: {desc_color};")

        label_layout.addWidget(label)
        label_layout.addWidget(desc)

        section_layout.addWidget(label_container)
        section_layout.addStretch()
        section_layout.addWidget(widget)

        return section

    def _setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        title_label = SubtitleLabel("App Settings")
        layout.addWidget(title_label)

        # --- UI Section ---
        ui_header = BodyLabel("User Interface")
        ui_header.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(ui_header)

        # Notifications toggle
        self.notifications_switch = SwitchButton()
        self.notifications_switch.setChecked(
            self.current_settings.get('ui', {}).get('show_notifications', True)
        )
        layout.addWidget(self._create_setting_row(
            "Show Notifications",
            "Show popup when clipboard content is captured",
            self.notifications_switch
        ))

        # Theme selector
        self.theme_combo = ComboBox()
        self.theme_combo.addItems(["Auto", "Light", "Dark"])
        current_theme = self.current_settings.get('ui', {}).get('theme', 'auto')
        theme_map = {'auto': 0, 'light': 1, 'dark': 2}
        self.theme_combo.setCurrentIndex(theme_map.get(current_theme, 0))
        self.theme_combo.setFixedWidth(120)
        layout.addWidget(self._create_setting_row(
            "Theme",
            "Application color theme",
            self.theme_combo
        ))

        # --- Clipboard Section ---
        clip_header = BodyLabel("Clipboard")
        clip_header.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(clip_header)

        # Check interval
        self.interval_spin = SpinBox()
        self.interval_spin.setRange(200, 5000)
        self.interval_spin.setSingleStep(100)
        self.interval_spin.setSuffix(" ms")
        self.interval_spin.setValue(
            self.current_settings.get('clipboard', {}).get('check_interval', 500)
        )
        self.interval_spin.setFixedWidth(140)
        layout.addWidget(self._create_setting_row(
            "Check Interval",
            "How often to check clipboard for changes",
            self.interval_spin
        ))

        # Max history size
        self.history_size_spin = SpinBox()
        self.history_size_spin.setRange(50, 10000)
        self.history_size_spin.setSingleStep(100)
        self.history_size_spin.setValue(
            self.current_settings.get('clipboard', {}).get('max_history_size', 500)
        )
        self.history_size_spin.setFixedWidth(140)
        layout.addWidget(self._create_setting_row(
            "Max History Size",
            "Maximum number of entries to keep",
            self.history_size_spin
        ))

        # --- Storage Section ---
        storage_header = BodyLabel("Storage")
        storage_header.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(storage_header)

        # Retention days
        self.retention_spin = SpinBox()
        self.retention_spin.setRange(1, 365)
        self.retention_spin.setSuffix(" days")
        self.retention_spin.setValue(
            self.current_settings.get('storage', {}).get('retention_days', 30)
        )
        self.retention_spin.setFixedWidth(140)
        layout.addWidget(self._create_setting_row(
            "Retention Period",
            "Days to keep clipboard history before cleanup",
            self.retention_spin
        ))

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
            cm = ConfigManager(self._config_path)

            # Update UI settings
            cm.set('ui.show_notifications', self.notifications_switch.isChecked())
            theme_map = {0: 'auto', 1: 'light', 2: 'dark'}
            cm.set('ui.theme', theme_map.get(self.theme_combo.currentIndex(), 'auto'))

            # Update clipboard settings
            cm.set('clipboard.check_interval', self.interval_spin.value())
            cm.set('clipboard.max_history_size', self.history_size_spin.value())

            # Update storage settings
            cm.set('storage.retention_days', self.retention_spin.value())

            if not cm.save():
                raise RuntimeError("Config save returned False")

            logger.info(f"App settings saved")

            # Emit signal with updated settings
            self.settings_saved.emit(cm.get_all())

            # Close dialog
            self.accept()

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
