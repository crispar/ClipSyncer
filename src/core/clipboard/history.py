"""Clipboard history management with duplicate detection"""

import hashlib
import threading
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import json
from loguru import logger


@dataclass
class ClipboardEntry:
    """Single clipboard history entry"""
    content: str
    timestamp: datetime
    content_hash: str
    category: str = "text"  # text, url, file_path, etc.
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = self.calculate_hash(self.content)
        if self.metadata is None:
            self.metadata = {}

    @staticmethod
    def calculate_hash(content: str) -> str:
        """Calculate SHA-256 hash of content"""
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ClipboardEntry':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

    def __eq__(self, other):
        if not isinstance(other, ClipboardEntry):
            return False
        return self.content_hash == other.content_hash


class ClipboardHistory:
    """Manages clipboard history with duplicate detection"""

    def __init__(self, max_size: int = 1000, dedupe_enabled: bool = True):
        """
        Initialize clipboard history

        Args:
            max_size: Maximum number of entries to store
            dedupe_enabled: Enable automatic duplicate removal
        """
        self.max_size = max_size
        self.dedupe_enabled = dedupe_enabled
        self._entries: List[ClipboardEntry] = []
        self._hash_index: Dict[str, ClipboardEntry] = {}
        self._lock = threading.RLock()

        logger.info(f"ClipboardHistory initialized (max_size={max_size}, dedupe={dedupe_enabled})")

    def add_entry(self, content: str, timestamp: Optional[datetime] = None) -> tuple[bool, Optional['ClipboardEntry']]:
        """
        Add new entry to history

        Args:
            content: Clipboard content
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Tuple of (entry_added, removed_entry):
                - entry_added: True if entry was added, False if duplicate
                - removed_entry: The entry that was removed due to max_size, if any
        """
        if not content:
            return False, None

        if timestamp is None:
            timestamp = datetime.now()

        # Detect content category
        category = self._detect_category(content)

        # Create entry
        entry = ClipboardEntry(
            content=content,
            timestamp=timestamp,
            content_hash=ClipboardEntry.calculate_hash(content),
            category=category
        )

        with self._lock:
            # Handle duplicates
            if self.dedupe_enabled and entry.content_hash in self._hash_index:
                # Update timestamp of existing entry (move to top)
                existing = self._hash_index[entry.content_hash]
                self._entries.remove(existing)
                existing.timestamp = timestamp
                self._entries.insert(0, existing)
                logger.debug(f"Updated duplicate entry timestamp: {entry.content_hash[:8]}")
                return False, None

            # Add new entry
            self._entries.insert(0, entry)
            self._hash_index[entry.content_hash] = entry

            # Enforce max size
            removed_entry = None
            if len(self._entries) > self.max_size:
                removed_entry = self._entries.pop()
                del self._hash_index[removed_entry.content_hash]
                logger.debug(f"Removed oldest entry: {removed_entry.content_hash[:8]}")

            logger.info(f"Added new entry: category={category}, hash={entry.content_hash[:8]}")
            return True, removed_entry

    def get_entries(self, limit: Optional[int] = None) -> List[ClipboardEntry]:
        """
        Get history entries

        Args:
            limit: Optional limit on number of entries

        Returns:
            List of clipboard entries (newest first)
        """
        with self._lock:
            if limit:
                return self._entries[:limit]
            return self._entries.copy()

    def search(self, query: str, case_sensitive: bool = False) -> List[ClipboardEntry]:
        """
        Search history for matching entries

        Args:
            query: Search query
            case_sensitive: Case sensitive search

        Returns:
            Matching entries
        """
        if not case_sensitive:
            query = query.lower()

        with self._lock:
            results = []
            for entry in self._entries:
                content = entry.content if case_sensitive else entry.content.lower()
                if query in content:
                    results.append(entry)

            return results

    def clear(self) -> None:
        """Clear all history"""
        with self._lock:
            self._entries.clear()
            self._hash_index.clear()
        logger.info("Clipboard history cleared")

    def remove_duplicates(self) -> int:
        """
        Remove duplicate entries (keep newest)

        Returns:
            Number of duplicates removed
        """
        if not self.dedupe_enabled:
            return 0

        with self._lock:
            seen = set()
            new_entries = []
            removed_count = 0

            for entry in self._entries:
                if entry.content_hash not in seen:
                    seen.add(entry.content_hash)
                    new_entries.append(entry)
                else:
                    removed_count += 1

            self._entries = new_entries
            self._rebuild_hash_index()

        if removed_count > 0:
            logger.info(f"Removed {removed_count} duplicate entries")

        return removed_count

    def cleanup_old_entries(self, days: int = 30) -> int:
        """
        Remove entries older than specified days

        Args:
            days: Number of days to keep

        Returns:
            Number of entries removed
        """
        cutoff = datetime.now() - timedelta(days=days)

        with self._lock:
            original_count = len(self._entries)
            self._entries = [e for e in self._entries if e.timestamp > cutoff]
            self._rebuild_hash_index()
            removed_count = original_count - len(self._entries)

        if removed_count > 0:
            logger.info(f"Removed {removed_count} entries older than {days} days")

        return removed_count

    def _rebuild_hash_index(self) -> None:
        """Rebuild hash index from entries"""
        self._hash_index.clear()
        for entry in self._entries:
            self._hash_index[entry.content_hash] = entry

    def import_entry(self, entry: ClipboardEntry) -> bool:
        """
        Import an external entry (e.g., from remote sync).
        Skips duplicates and maintains proper encapsulation.

        Args:
            entry: ClipboardEntry to import

        Returns:
            True if entry was imported, False if duplicate exists
        """
        if not entry or not entry.content_hash:
            return False

        with self._lock:
            # Check for duplicate
            if entry.content_hash in self._hash_index:
                logger.debug(f"Skipped duplicate import: {entry.content_hash[:8]}")
                return False

            # Add to history
            self._entries.append(entry)
            self._hash_index[entry.content_hash] = entry

            # Enforce max size
            while len(self._entries) > self.max_size:
                removed = self._entries.pop(0)  # Remove oldest (at start after append)
                del self._hash_index[removed.content_hash]

        logger.debug(f"Imported entry: {entry.content_hash[:8]}")
        return True

    def has_entry(self, content_hash: str) -> bool:
        """
        Check if an entry with the given hash exists.

        Args:
            content_hash: Hash to check

        Returns:
            True if entry exists
        """
        with self._lock:
            return content_hash in self._hash_index

    def _detect_category(self, content: str) -> str:
        """
        Detect content category

        Args:
            content: Content to analyze

        Returns:
            Category name
        """
        content = content.strip()

        # URL detection
        if content.startswith(('http://', 'https://', 'ftp://')):
            return 'url'

        # File path detection (Windows)
        if ':\\' in content or content.startswith('\\\\'):
            return 'file_path'

        # Email detection
        if '@' in content and '.' in content:
            parts = content.split('@')
            if len(parts) == 2 and '.' in parts[1]:
                return 'email'

        # Default to text
        return 'text'

    def to_json(self) -> str:
        """Export history to JSON"""
        with self._lock:
            data = {
                'entries': [e.to_dict() for e in self._entries],
                'max_size': self.max_size,
                'dedupe_enabled': self.dedupe_enabled
            }
        return json.dumps(data, indent=2)

    def from_json(self, json_str: str) -> None:
        """Import history from JSON"""
        data = json.loads(json_str)

        with self._lock:
            self.max_size = data.get('max_size', 1000)
            self.dedupe_enabled = data.get('dedupe_enabled', True)

            self._entries = []
            self._hash_index = {}

            for entry_data in data.get('entries', []):
                entry = ClipboardEntry.from_dict(entry_data)
                self._entries.append(entry)
                self._hash_index[entry.content_hash] = entry

        logger.info(f"Imported {len(self._entries)} entries from JSON")

    @property
    def size(self) -> int:
        """Get current number of entries"""
        with self._lock:
            return len(self._entries)