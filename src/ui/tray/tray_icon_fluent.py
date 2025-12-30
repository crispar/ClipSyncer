"""Modern system tray icon with Windows 11 styling"""

import sys
from typing import Optional, Callable, List, Tuple
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PyQt6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PyQt6.QtCore import QTimer, QObject, pyqtSignal
from qfluentwidgets import Theme, isDarkTheme
from loguru import logger


class ModernTrayIcon(QObject):
    """Modern system tray icon with Windows 11 styling"""

    # Signals for thread-safe GUI operations
    show_history_signal = pyqtSignal()
    quit_signal = pyqtSignal()

    def __init__(self, tooltip: str = "ClipboardHistory"):
        super().__init__()
        self._tooltip = tooltip
        self._tray_icon: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None
        self._menu_items: List[Tuple[str, Callable]] = []
        self._timer: Optional[QTimer] = None
        self._running = False
        self._monitoring_active = True  # Track monitoring state

        # Create modern icon based on theme
        self._icon = self._create_modern_icon(self._monitoring_active)

    def _create_modern_icon(self, active: bool = True) -> QIcon:
        """Create a modern icon that matches Windows 11 style

        Args:
            active: Whether monitoring is currently active
        """
        # Create a pixmap for the icon
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Determine colors based on system theme and active state
        if isDarkTheme():
            # Dark theme colors
            if active:
                bg_color = QColor(32, 32, 32, 200)
                fg_color = QColor(255, 255, 255, 240)
                accent_color = QColor(0, 200, 83)  # Green for active
            else:
                bg_color = QColor(32, 32, 32, 150)
                fg_color = QColor(180, 180, 180, 200)  # Dimmed for inactive
                accent_color = QColor(255, 95, 95)  # Red for inactive
        else:
            # Light theme colors
            if active:
                bg_color = QColor(255, 255, 255, 200)
                fg_color = QColor(32, 32, 32, 240)
                accent_color = QColor(0, 170, 0)  # Green for active
            else:
                bg_color = QColor(240, 240, 240, 180)
                fg_color = QColor(120, 120, 120, 200)  # Dimmed for inactive
                accent_color = QColor(220, 50, 50)  # Red for inactive

        # Draw rounded rectangle background
        painter.setBrush(bg_color)
        painter.setPen(QColor(0, 0, 0, 0))
        painter.drawRoundedRect(4, 4, 56, 56, 12, 12)

        # Draw clipboard icon using text (simple approach)
        font = QFont("Segoe Fluent Icons", 28)
        painter.setFont(font)
        painter.setPen(fg_color)

        # Use clipboard icon from Segoe Fluent Icons font
        # Fallback to text if font not available
        clipboard_icon = "📋"  # Fallback emoji
        painter.drawText(pixmap.rect(), 0x1000 | 0x0004, clipboard_icon)

        # Draw status indicator dot
        painter.setBrush(accent_color)
        painter.setPen(QColor(0, 0, 0, 0))
        painter.drawEllipse(44, 44, 12, 12)

        # If inactive, draw a pause symbol overlay
        if not active:
            painter.setPen(QColor(255, 255, 255, 200))
            painter.setBrush(QColor(0, 0, 0, 0))
            pause_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
            painter.setFont(pause_font)
            painter.drawText(42, 42, 16, 16, 0x1000 | 0x0004, "⏸")

        painter.end()

        return QIcon(pixmap)

    def add_menu_item(self, label: str, callback: Callable) -> None:
        """Add a menu item with modern styling"""
        self._menu_items.append((label, callback))
        logger.debug(f"Added menu item: {label}")

    def add_separator(self) -> None:
        """Add a separator to the menu"""
        self._menu_items.append((None, None))
        logger.debug("Added menu separator")

    def start(self) -> None:
        """Start the system tray icon"""
        if self._running:
            logger.warning("Tray icon already running")
            return

        try:
            # Check if system tray is available
            if not QSystemTrayIcon.isSystemTrayAvailable():
                logger.error("System tray is not available")
                return

            # Create tray icon
            self._tray_icon = QSystemTrayIcon()
            self._tray_icon.setIcon(self._icon)
            self._tray_icon.setToolTip(self._tooltip)

            # Create context menu with modern styling
            self._menu = QMenu()

            # Apply modern menu styling
            self._apply_modern_menu_style()

            # Add menu items
            for label, callback in self._menu_items:
                if label is None:
                    self._menu.addSeparator()
                else:
                    action = QAction(label, self._menu)
                    if callback:
                        action.triggered.connect(callback)

                    # Add icons to common actions
                    if "History" in label:
                        action.setText("📜 " + label)
                    elif "Toggle" in label or "Monitor" in label:
                        # Show play/pause icon based on monitoring state
                        icon = "▶️" if not self._monitoring_active else "⏸️"
                        action.setText(f"{icon} " + label)
                    elif "Sync" in label or "GitHub" in label:
                        action.setText("☁️ " + label)
                    elif "Cleanup" in label or "Clean" in label:
                        action.setText("🧹 " + label)
                    elif "Settings" in label:
                        action.setText("⚙️ " + label)
                    elif "Quit" in label or "Exit" in label:
                        action.setText("❌ " + label)

                    self._menu.addAction(action)

            # Set the context menu
            self._tray_icon.setContextMenu(self._menu)

            # Connect double-click to show history
            self._tray_icon.activated.connect(self._on_tray_activated)

            # Show the tray icon
            self._tray_icon.show()

            self._running = True
            logger.info("System tray icon started with modern styling")

        except Exception as e:
            logger.error(f"Failed to start tray icon: {e}")

    def _apply_modern_menu_style(self):
        """Apply Windows 11 Fluent Design style to the menu"""
        if not self._menu:
            return

        # Modern menu stylesheet for Windows 11 look
        if isDarkTheme():
            # Dark theme menu style
            menu_style = """
                QMenu {
                    background-color: #2b2b2b;
                    border: 1px solid #3c3c3c;
                    border-radius: 8px;
                    padding: 4px;
                }
                QMenu::item {
                    padding: 8px 32px 8px 32px;
                    border-radius: 4px;
                    color: #ffffff;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 14px;
                }
                QMenu::item:selected {
                    background-color: rgba(255, 255, 255, 0.1);
                }
                QMenu::item:pressed {
                    background-color: rgba(255, 255, 255, 0.2);
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #3c3c3c;
                    margin: 4px 16px;
                }
            """
        else:
            # Light theme menu style
            menu_style = """
                QMenu {
                    background-color: #ffffff;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 4px;
                    box-shadow: 0px 8px 16px rgba(0, 0, 0, 0.14);
                }
                QMenu::item {
                    padding: 8px 32px 8px 32px;
                    border-radius: 4px;
                    color: #202020;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 14px;
                }
                QMenu::item:selected {
                    background-color: rgba(0, 0, 0, 0.05);
                }
                QMenu::item:pressed {
                    background-color: rgba(0, 0, 0, 0.1);
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #e0e0e0;
                    margin: 4px 16px;
                }
            """

        self._menu.setStyleSheet(menu_style)

    def _on_tray_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # Emit signal to show history (first menu item callback)
            if self._menu_items and self._menu_items[0][1]:
                self._menu_items[0][1]()

    def update_tooltip(self, tooltip: str) -> None:
        """Update the tooltip text"""
        self._tooltip = tooltip
        if self._tray_icon:
            self._tray_icon.setToolTip(tooltip)
            logger.debug(f"Updated tooltip: {tooltip}")

    def show_notification(self, title: str, message: str, duration: int = 3000) -> None:
        """Show a system notification with modern styling"""
        if self._tray_icon and QSystemTrayIcon.supportsMessages():
            self._tray_icon.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Information,
                duration
            )
            logger.debug(f"Showed notification: {title}")

    def update_icon(self, active: bool = True):
        """Update icon to show active/inactive state"""
        self._monitoring_active = active
        if self._tray_icon:
            # Recreate icon with updated state
            self._icon = self._create_modern_icon(active)
            self._tray_icon.setIcon(self._icon)

            # Update tooltip to reflect state
            state_text = " (Active)" if active else " (Paused)"
            base_tooltip = self._tooltip.replace(" (Active)", "").replace(" (Paused)", "")
            self._tray_icon.setToolTip(base_tooltip + state_text)

            logger.info(f"Updated tray icon - Monitoring: {'Active' if active else 'Paused'}")

    def stop(self) -> None:
        """Stop the system tray icon"""
        if self._tray_icon:
            self._tray_icon.hide()
            self._tray_icon = None

        if self._timer:
            self._timer.stop()
            self._timer = None

        self._running = False
        logger.info("System tray icon stopped")

    def is_running(self) -> bool:
        """Check if tray icon is running"""
        return self._running