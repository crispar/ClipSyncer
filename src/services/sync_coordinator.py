"""Sync coordinator for managing all GitHub sync operations (SRP extraction)"""

import threading
from typing import Optional
from loguru import logger

from src.core.clipboard.history import ClipboardHistory, ClipboardEntry
from src.core.interfaces import EncryptionStrategy, SyncBackend
from src.core.storage.repository_improved import ClipboardRepository
from src.services.auto_sync_service import AutoSyncService


class SyncCoordinator:
    """Coordinates all sync operations between local and remote storage.

    Extracted from ClipboardHistoryApp to follow Single Responsibility Principle.
    This class handles only sync logic (push, pull, merge, initial sync).
    """

    def __init__(self,
                 sync_backend: SyncBackend,
                 encryption: EncryptionStrategy,
                 clipboard_history: ClipboardHistory,
                 repository: ClipboardRepository,
                 config_getter=None):
        """
        Args:
            sync_backend: The sync backend (e.g., GitHubSyncService)
            encryption: Encryption strategy for data
            clipboard_history: In-memory clipboard history
            repository: Persistent storage repository
            config_getter: Callable that returns config dict (for settings sync)
        """
        self._sync_backend = sync_backend
        self._encryption = encryption
        self._history = clipboard_history
        self._repository = repository
        self._config_getter = config_getter

    @property
    def sync_backend(self) -> SyncBackend:
        """Access the sync backend"""
        return self._sync_backend

    def initial_sync(self) -> int:
        """
        Perform initial sync from remote: clear local cache and load remote data.

        Returns:
            Number of entries loaded
        """
        if not self._sync_backend.is_enabled:
            return 0

        try:
            logger.info("Clearing local cache before initial sync...")
            self._repository.clear_all()
            self._history.clear()

            logger.info("Loading initial data from remote...")
            backup_data = self._sync_backend.download_backup()
            if not backup_data:
                logger.error("Failed to download initial backup")
                return 0

            decrypted = self._encryption.decrypt_json(backup_data)
            if not decrypted:
                logger.warning("Failed to decrypt backup - may need sync password")
                return 0

            remote_entries = decrypted.get('entries', [])
            loaded_count = 0

            for entry_data in remote_entries:
                try:
                    from datetime import datetime
                    entry = ClipboardEntry(
                        content=entry_data['content'],
                        timestamp=datetime.fromisoformat(entry_data['timestamp']),
                        content_hash=entry_data.get('content_hash'),
                        category=entry_data.get('category'),
                        metadata=entry_data.get('metadata', {})
                    )
                    self._repository.save_entry(entry)
                    self._history.add_entry(entry.content, entry.timestamp)
                    loaded_count += 1
                except Exception as e:
                    logger.error(f"Failed to load entry: {e}")

            logger.info(f"Initial sync complete - loaded {loaded_count} entries")
            return loaded_count

        except Exception as e:
            logger.error(f"Initial sync failed: {e}")
            return 0

    def push_to_remote(self):
        """Push current local state to remote (immediate, for primary storage mode)"""
        if not self._sync_backend.is_enabled:
            return

        try:
            history_data = self._build_sync_payload()
            encrypted = self._encryption.encrypt_json(history_data)
            success = self._sync_backend.upload_backup(encrypted)

            if success:
                logger.info("Push to remote completed")
            else:
                logger.error("Push to remote failed")

        except Exception as e:
            logger.error(f"Push to remote error: {e}")

    def pull_and_merge(self, history_viewer=None):
        """
        Pull from remote and merge with local data (bidirectional sync).

        Args:
            history_viewer: Optional UI viewer to refresh after merge
        """
        if not self._sync_backend.is_enabled:
            return

        try:
            logger.debug("Pulling clipboard sync from remote")
            backup_data = self._sync_backend.download_backup()
            if not backup_data:
                logger.debug("No backup found or download failed")
                return

            decrypted = self._encryption.decrypt_json(backup_data)
            if not decrypted:
                logger.warning("Failed to decrypt backup - may need sync password")
                return

            # Build hash maps for merge
            remote_entries = decrypted.get('entries', [])
            remote_by_hash = {
                e.get('content_hash'): e
                for e in remote_entries if e.get('content_hash')
            }

            local_entries = self._history.get_entries()
            local_by_hash = {e.content_hash: e for e in local_entries}

            local_only_hashes = set(local_by_hash.keys()) - set(remote_by_hash.keys())
            remote_only_hashes = set(remote_by_hash.keys()) - set(local_by_hash.keys())

            # Merge: add remote-only entries to local
            from datetime import datetime
            added_to_local = 0
            for content_hash in remote_only_hashes:
                entry_data = remote_by_hash[content_hash]
                try:
                    entry = ClipboardEntry(
                        content=entry_data['content'],
                        timestamp=datetime.fromisoformat(entry_data['timestamp']),
                        content_hash=content_hash,
                        category=entry_data.get('category'),
                        metadata=entry_data.get('metadata', {})
                    )
                    if self._history.import_entry(entry):
                        self._repository.save_entry(entry)
                        added_to_local += 1
                except Exception as e:
                    logger.error(f"Failed to import remote entry {content_hash[:8]}: {e}")

            if added_to_local > 0:
                logger.info(f"Added {added_to_local} entries from remote to local")

            # Push merged data if needed
            if added_to_local > 0 and local_only_hashes:
                logger.info(f"Found {len(local_only_hashes)} local entries not on remote, syncing...")
                self.push_to_remote()
            elif local_only_hashes:
                logger.debug(f"{len(local_only_hashes)} local-only entries, no new remote entries - skipping push")

            # Refresh UI if viewer is open
            if history_viewer:
                history_viewer.load_history()

        except Exception as e:
            logger.error(f"Pull and merge failed: {e}")

    def manual_sync(self, signal_bridge=None):
        """Run manual sync in a background thread"""
        def sync_task():
            if self._sync_backend.is_enabled:
                try:
                    history_data = self._build_sync_payload()
                    encrypted = self._encryption.encrypt_json(history_data)
                    success = self._sync_backend.upload_backup(encrypted)

                    if success:
                        logger.info("Successfully synced to remote")
                        if signal_bridge:
                            signal_bridge.show_notification_signal.emit(
                                "GitHub Sync", "Backup uploaded successfully"
                            )
                    else:
                        logger.error("Manual sync failed")
                except Exception as e:
                    logger.error(f"Manual sync error: {e}")
            else:
                logger.warning("Sync not configured")

        threading.Thread(target=sync_task, daemon=True).start()

    def _build_sync_payload(self) -> dict:
        """Build the data payload for sync"""
        payload = {
            'entries': [e.to_dict() for e in self._history.get_entries()],
        }
        if self._config_getter:
            payload['settings'] = self._config_getter()
        return payload
