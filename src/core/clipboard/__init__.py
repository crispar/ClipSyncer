"""Clipboard monitoring and management"""

from .monitor import ClipboardMonitor
from .history import ClipboardHistory

__all__ = ['ClipboardMonitor', 'ClipboardHistory']

# QtClipboardMonitor is intentionally imported lazily from qt_monitor to
# keep this package importable in environments where PyQt6 is absent.