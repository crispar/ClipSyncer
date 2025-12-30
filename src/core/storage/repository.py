"""Repository pattern for clipboard data access"""

import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from loguru import logger

from .database import ClipboardEntryDB, SettingsDB
from ..clipboard.history import ClipboardEntry
from ..encryption.manager import EncryptionManager


class ClipboardRepository:
    """Repository for clipboard data operations"""

    def __init__(self, session: Session, encryption_manager: EncryptionManager):
        """
        Initialize repository

        Args:
            session: Database session
            encryption_manager: Encryption manager instance
        """
        self.session = session
        self.encryption = encryption_manager

    def save_entry(self, entry: ClipboardEntry) -> bool:
        """
        Save clipboard entry to database

        Args:
            entry: Clipboard entry to save

        Returns:
            True if successful
        """
        try:
            # Encrypt content
            encrypted_data = self.encryption.encrypt(entry.content)

            # Check if entry exists
            existing = self.session.query(ClipboardEntryDB).filter_by(
                content_hash=entry.content_hash
            ).first()

            if existing:
                # Update timestamp
                existing.timestamp = entry.timestamp
                logger.debug(f"Updated existing entry: {entry.content_hash[:8]}")
            else:
                # Create new entry
                db_entry = ClipboardEntryDB(
                    content_hash=entry.content_hash,
                    encrypted_content=encrypted_data['ciphertext'],
                    encrypted_nonce=encrypted_data['nonce'],
                    encrypted_tag=encrypted_data['tag'],
                    timestamp=entry.timestamp,
                    category=entry.category,
                    entry_metadata=json.dumps(entry.metadata) if entry.metadata else None
                )
                self.session.add(db_entry)
                logger.debug(f"Saved new entry: {entry.content_hash[:8]}")

            self.session.commit()
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to save entry: {e}")
            return False

    def get_entries(self, limit: Optional[int] = None) -> List[ClipboardEntry]:
        """
        Get clipboard entries from database

        Args:
            limit: Optional limit on number of entries

        Returns:
            List of clipboard entries
        """
        try:
            query = self.session.query(ClipboardEntryDB).order_by(
                ClipboardEntryDB.timestamp.desc()
            )

            if limit:
                query = query.limit(limit)

            db_entries = query.all()
            entries = []

            for db_entry in db_entries:
                try:
                    # Decrypt content
                    encrypted_data = {
                        'ciphertext': db_entry.encrypted_content,
                        'nonce': db_entry.encrypted_nonce,
                        'tag': db_entry.encrypted_tag
                    }
                    content = self.encryption.decrypt(encrypted_data)

                    # Create clipboard entry
                    entry = ClipboardEntry(
                        content=content,
                        timestamp=db_entry.timestamp,
                        content_hash=db_entry.content_hash,
                        category=db_entry.category,
                        metadata=json.loads(db_entry.entry_metadata) if db_entry.entry_metadata else {}
                    )
                    entries.append(entry)

                except Exception as e:
                    logger.error(f"Failed to decrypt entry {db_entry.id}: {e}")

            return entries

        except Exception as e:
            logger.error(f"Failed to get entries: {e}")
            return []

    def get_entry_count(self) -> int:
        """
        Get total number of entries in the database

        Returns:
            Number of entries
        """
        try:
            with self._session() as session:
                return session.query(DatabaseEntry).count()
        except Exception as e:
            logger.error(f"Failed to get entry count: {e}")
            return 0

    def delete_entry(self, content_hash: str) -> bool:
        """
        Delete entry by content hash

        Args:
            content_hash: Hash of content to delete

        Returns:
            True if successful
        """
        try:
            entry = self.session.query(ClipboardEntryDB).filter_by(
                content_hash=content_hash
            ).first()

            if entry:
                self.session.delete(entry)
                self.session.commit()
                logger.debug(f"Deleted entry: {content_hash[:8]}")
                return True

            return False

        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to delete entry: {e}")
            return False

    def cleanup_old_entries(self, days: int) -> int:
        """
        Delete entries older than specified days

        Args:
            days: Number of days to keep

        Returns:
            Number of entries deleted
        """
        try:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=days)

            deleted = self.session.query(ClipboardEntryDB).filter(
                ClipboardEntryDB.timestamp < cutoff
            ).delete()

            self.session.commit()
            logger.info(f"Deleted {deleted} old entries")
            return deleted

        except Exception as e:
            try:
                self.session.rollback()
            except:
                pass  # Rollback may fail if already committed
            logger.error(f"Failed to cleanup old entries: {e}")
            return 0

    def get_favorites(self) -> List[ClipboardEntry]:
        """
        Get favorite entries

        Returns:
            List of favorite entries
        """
        try:
            db_entries = self.session.query(ClipboardEntryDB).filter_by(
                is_favorite=True
            ).order_by(ClipboardEntryDB.timestamp.desc()).all()

            entries = []
            for db_entry in db_entries:
                try:
                    encrypted_data = {
                        'ciphertext': db_entry.encrypted_content,
                        'nonce': db_entry.encrypted_nonce,
                        'tag': db_entry.encrypted_tag
                    }
                    content = self.encryption.decrypt(encrypted_data)

                    entry = ClipboardEntry(
                        content=content,
                        timestamp=db_entry.timestamp,
                        content_hash=db_entry.content_hash,
                        category=db_entry.category,
                        metadata=json.loads(db_entry.entry_metadata) if db_entry.entry_metadata else {}
                    )
                    entries.append(entry)

                except Exception as e:
                    logger.error(f"Failed to decrypt favorite entry {db_entry.id}: {e}")

            return entries

        except Exception as e:
            logger.error(f"Failed to get favorites: {e}")
            return []

    def toggle_favorite(self, content_hash: str) -> bool:
        """
        Toggle favorite status of an entry

        Args:
            content_hash: Hash of entry to toggle

        Returns:
            True if successful
        """
        try:
            entry = self.session.query(ClipboardEntryDB).filter_by(
                content_hash=content_hash
            ).first()

            if entry:
                entry.is_favorite = not entry.is_favorite
                self.session.commit()
                logger.debug(f"Toggled favorite: {content_hash[:8]} -> {entry.is_favorite}")
                return True

            return False

        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to toggle favorite: {e}")
            return False

    def save_setting(self, key: str, value: Any) -> bool:
        """
        Save application setting

        Args:
            key: Setting key
            value: Setting value

        Returns:
            True if successful
        """
        try:
            setting = self.session.query(SettingsDB).filter_by(key=key).first()

            if setting:
                setting.value = json.dumps(value)
                setting.updated_at = datetime.now()
            else:
                setting = SettingsDB(
                    key=key,
                    value=json.dumps(value),
                    updated_at=datetime.now()
                )
                self.session.add(setting)

            self.session.commit()
            logger.debug(f"Saved setting: {key}")
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to save setting: {e}")
            return False

    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Get application setting

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        try:
            setting = self.session.query(SettingsDB).filter_by(key=key).first()

            if setting:
                return json.loads(setting.value)

            return default

        except Exception as e:
            logger.error(f"Failed to get setting: {e}")
            return default

    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all settings

        Returns:
            Dictionary of settings
        """
        try:
            settings = self.session.query(SettingsDB).all()
            return {s.key: json.loads(s.value) for s in settings}

        except Exception as e:
            logger.error(f"Failed to get all settings: {e}")
            return {}