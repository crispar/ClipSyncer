"""System tray icon implementation"""

import sys
import threading
from typing import Optional, Callable, Dict, Any
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem, Menu
from loguru import logger


class TrayIcon:
    """System tray icon with context menu"""

    def __init__(self, app_name: str = "ClipboardHistory"):
        """
        Initialize tray icon

        Args:
            app_name: Application name
        """
        self.app_name = app_name
        self.icon: Optional[pystray.Icon] = None
        self._callbacks: Dict[str, Callable] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Create default icon
        self.icon_image = self._create_default_icon()

        logger.info(f"TrayIcon initialized for {app_name}")

    def _create_default_icon(self) -> Image.Image:
        """
        Create default application icon

        Returns:
            PIL Image object
        """
        # Create a simple clipboard icon
        size = 64
        image = Image.new('RGBA', (size, size), color=(255, 255, 255, 0))
        draw = ImageDraw.Draw(image)

        # Draw clipboard shape
        clipboard_color = (70, 130, 180)  # Steel blue
        draw.rectangle([10, 5, 54, 59], fill=clipboard_color)
        draw.rectangle([20, 0, 44, 10], fill=clipboard_color)

        # Draw clip
        clip_color = (192, 192, 192)  # Silver
        draw.rectangle([25, 0, 39, 15], fill=clip_color)
        draw.rectangle([28, 0, 36, 5], fill=(255, 255, 255, 0))

        # Draw lines to represent text
        line_color = (255, 255, 255)
        for i in range(3):
            y = 25 + i * 10
            draw.rectangle([18, y, 46, y + 3], fill=line_color)

        return image

    def set_icon(self, image_path: Optional[str] = None) -> None:
        """
        Set custom icon

        Args:
            image_path: Path to icon image file
        """
        try:
            if image_path:
                self.icon_image = Image.open(image_path)
                logger.info(f"Loaded custom icon: {image_path}")
            else:
                self.icon_image = self._create_default_icon()
                logger.info("Using default icon")

            # Update icon if running
            if self.icon:
                self.icon.icon = self.icon_image

        except Exception as e:
            logger.error(f"Failed to set icon: {e}")
            self.icon_image = self._create_default_icon()

    def add_menu_item(self, title: str, callback: Callable, enabled: bool = True) -> None:
        """
        Add menu item

        Args:
            title: Menu item title
            callback: Function to call when clicked
            enabled: Whether item is enabled
        """
        self._callbacks[title] = (callback, enabled)
        logger.debug(f"Added menu item: {title}")

    def add_separator(self) -> None:
        """Add menu separator"""
        self._callbacks[f"_separator_{len(self._callbacks)}"] = (None, True)

    def _create_menu(self) -> Menu:
        """
        Create context menu

        Returns:
            pystray Menu object
        """
        items = []

        for title, (callback, enabled) in self._callbacks.items():
            if title.startswith("_separator_"):
                items.append(Menu.SEPARATOR)
            else:
                if callback:
                    # Create a closure to capture the callback
                    def make_handler(cb):
                        def handler(icon, item):
                            self._handle_click(cb)
                        return handler

                    item = MenuItem(
                        title,
                        make_handler(callback),
                        enabled=enabled
                    )
                else:
                    item = MenuItem(title, None, enabled=False)

                items.append(item)

        return Menu(*items)

    def _handle_click(self, callback: Callable) -> None:
        """
        Handle menu item click

        Args:
            callback: Function to execute
        """
        try:
            # Execute callback directly (should emit Qt signals)
            callback()
        except Exception as e:
            logger.error(f"Error in menu callback: {e}")

    def start(self) -> None:
        """Start system tray icon"""
        if self._running:
            logger.warning("Tray icon already running")
            return

        self._running = True

        # Create menu
        menu = self._create_menu()

        # Create icon
        self.icon = pystray.Icon(
            name=self.app_name,
            icon=self.icon_image,
            title=self.app_name,
            menu=menu
        )

        # Start in separate thread
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

        logger.info("System tray icon started")

    def _run(self) -> None:
        """Run the icon (blocking)"""
        try:
            self.icon.run()
        except Exception as e:
            logger.error(f"Tray icon error: {e}")
        finally:
            self._running = False

    def stop(self) -> None:
        """Stop system tray icon"""
        if not self._running:
            logger.warning("Tray icon not running")
            return

        if self.icon:
            self.icon.stop()

        self._running = False
        logger.info("System tray icon stopped")

    def show_notification(self, title: str, message: str) -> None:
        """
        Show system notification

        Args:
            title: Notification title
            message: Notification message
        """
        try:
            if self.icon:
                self.icon.notify(title=title, message=message)
                logger.debug(f"Notification shown: {title}")
        except Exception as e:
            logger.error(f"Failed to show notification: {e}")

    def update_menu(self) -> None:
        """Update context menu"""
        if self.icon:
            self.icon.menu = self._create_menu()
            logger.debug("Menu updated")

    def update_tooltip(self, text: str) -> None:
        """
        Update icon tooltip

        Args:
            text: New tooltip text
        """
        if self.icon:
            self.icon.title = text

    @property
    def is_running(self) -> bool:
        """Check if tray icon is running"""
        return self._running