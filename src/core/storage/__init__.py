"""Data persistence and storage management"""

from .database import DatabaseManager
from .repository import ClipboardRepository

__all__ = ['DatabaseManager', 'ClipboardRepository']