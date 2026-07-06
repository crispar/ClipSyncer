"""Event-driven clipboard monitor backed by ``QClipboard.dataChanged``.

This avoids the 2Hz polling wake of the cross-platform :class:`ClipboardMonitor`
when a Qt event loop is available. The public interface matches
``ClipboardMonitor`` (``add_callback`` / ``start`` / ``stop`` / ``is_running``)
so call sites stay unchanged and the polling implementation remains the
fallback when Qt is not running.
"""

import hashlib
import threading
from datetime import datetime
from typing import Callable, Optional, Set

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QApplication
from loguru import logger


class QtClipboardMonitor(QObject):
    """Notify listeners whenever the OS clipboard fires ``dataChanged``.

    Raises ``RuntimeError`` if no ``QApplication`` is currently running so the
    caller can fall back to the polling implementation.
    """

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        app = QApplication.instance()
        if not isinstance(app, QApplication):
            raise RuntimeError(
                "QtClipboardMonitor requires an active QApplication"
            )
        self._clipboard = app.clipboard()
        self._running = False
        self._callbacks: Set[Callable[[str, datetime], None]] = set()
        self._last_hash: str = ""
        self._lock = threading.RLock()
        logger.info("QtClipboardMonitor initialized (event-driven)")

    def add_callback(self, callback: Callable[[str, datetime], None]) -> None:
        with self._lock:
            self._callbacks.add(callback)

    def remove_callback(self, callback: Callable) -> None:
        with self._lock:
            self._callbacks.discard(callback)

    def start(self) -> None:
        with self._lock:
            if self._running:
                logger.warning("QtClipboardMonitor already running")
                return
            self._running = True
        self._clipboard.dataChanged.connect(self._on_data_changed)
        logger.info("QtClipboardMonitor started")

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
        try:
            self._clipboard.dataChanged.disconnect(self._on_data_changed)
        except (TypeError, RuntimeError):
            # Already disconnected or clipboard torn down during shutdown.
            pass
        logger.info("QtClipboardMonitor stopped")

    def _on_data_changed(self) -> None:
        try:
            content = self._clipboard.text()
        except Exception as e:
            logger.error(f"Failed to read clipboard text: {e}")
            return

        if not content:
            return

        content_hash = hashlib.sha256(content.encode()).hexdigest()

        with self._lock:
            if content_hash == self._last_hash:
                return
            self._last_hash = content_hash
            callbacks = self._callbacks.copy()

        timestamp = datetime.now()
        for callback in callbacks:
            try:
                callback(content, timestamp)
            except Exception as e:
                logger.error(
                    f"Error in callback "
                    f"{getattr(callback, '__name__', repr(callback))}: {e}"
                )

    @property
    def is_running(self) -> bool:
        return self._running

    def get_current_content(self) -> Optional[str]:
        try:
            return self._clipboard.text()
        except Exception as e:
            logger.error(f"Failed to read clipboard text: {e}")
            return None
