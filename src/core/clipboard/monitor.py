"""Clipboard monitoring service for real-time clipboard content detection"""

import threading
import time
import hashlib
from typing import Optional, Callable, Set
from datetime import datetime
import pyperclip
from loguru import logger


class ClipboardMonitor:
    """Real-time clipboard monitoring service"""

    def __init__(self, check_interval: int = 500):
        """
        Initialize clipboard monitor

        Args:
            check_interval: Check interval in milliseconds
        """
        self.check_interval = check_interval / 1000.0  # Convert to seconds
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_content: str = ""
        self._last_hash: str = ""
        self._callbacks: Set[Callable] = set()
        self._lock = threading.RLock()

        logger.info(f"ClipboardMonitor initialized with {check_interval}ms interval")

    def add_callback(self, callback: Callable[[str, datetime], None]) -> None:
        """
        Add a callback for clipboard changes

        Args:
            callback: Function to call when clipboard changes (content, timestamp)
        """
        with self._lock:
            self._callbacks.add(callback)
            logger.debug(f"Added callback: {callback.__name__}")

    def remove_callback(self, callback: Callable) -> None:
        """Remove a callback"""
        with self._lock:
            self._callbacks.discard(callback)
            logger.debug(f"Removed callback: {callback.__name__}")

    def start(self) -> None:
        """Start monitoring the clipboard"""
        with self._lock:
            if self._running:
                logger.warning("Monitor already running")
                return

            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
            logger.info("Clipboard monitoring started")

    def stop(self) -> None:
        """Stop monitoring the clipboard"""
        with self._lock:
            if not self._running:
                logger.warning("Monitor not running")
                return

            self._running = False

        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

        logger.info("Clipboard monitoring stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        logger.debug("Monitor loop started")

        while self._running:
            try:
                current_content = pyperclip.paste()

                if current_content and self._has_changed(current_content):
                    timestamp = datetime.now()
                    self._notify_callbacks(current_content, timestamp)

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")

            time.sleep(self.check_interval)

        logger.debug("Monitor loop ended")

    def _has_changed(self, content: str) -> bool:
        """
        Check if clipboard content has changed

        Args:
            content: Current clipboard content

        Returns:
            True if content has changed
        """
        # Calculate hash for efficient comparison
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        if content_hash != self._last_hash:
            self._last_content = content
            self._last_hash = content_hash
            return True

        return False

    def _notify_callbacks(self, content: str, timestamp: datetime) -> None:
        """
        Notify all callbacks of clipboard change

        Args:
            content: New clipboard content
            timestamp: Time of change
        """
        with self._lock:
            callbacks = self._callbacks.copy()

        for callback in callbacks:
            try:
                callback(content, timestamp)
            except Exception as e:
                logger.error(f"Error in callback {callback.__name__}: {e}")

    @property
    def is_running(self) -> bool:
        """Check if monitor is running"""
        return self._running

    def get_current_content(self) -> Optional[str]:
        """Get current clipboard content"""
        try:
            return pyperclip.paste()
        except Exception as e:
            logger.error(f"Failed to get clipboard content: {e}")
            return None