"""Sync coordinator for managing all GitHub sync operations (SRP extraction)"""

import threading
from typing import Callable, Optional
from loguru import logger

from src.core.clipboard.history import ClipboardHistory, ClipboardEntry
from src.core.exceptions import DecryptionError
from src.core.interfaces import EncryptionStrategy, SyncBackend
from src.core.storage.repository_improved import ClipboardRepository


# User-facing notification copy for decryption failure. Reused by initial_sync,
# pull_and_merge, and push_to_remote so the user sees a single consistent message.
_DECRYPTION_LOCK_TITLE = "Sync paused: wrong sync password"
_DECRYPTION_LOCK_BODY = (
    "Couldn't decrypt the GitHub backup with the current sync password. "
    "Auto-push is disabled to protect remote data. "
    "Open GitHub Settings and re-enter the same password used on your other PC."
)


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
                 config_getter=None,
                 notifier: Optional[Callable[[str, str], None]] = None):
        """
        Args:
            sync_backend: The sync backend (e.g., GitHubSyncService)
            encryption: Encryption strategy for data
            clipboard_history: In-memory clipboard history
            repository: Persistent storage repository
            config_getter: Callable that returns config dict (for settings sync)
            notifier: Optional callable(title, body) used to surface user-visible
                events (e.g., decryption failure). Must be safe to invoke from a
                background thread; typically wired to a Qt signal emit.
        """
        self._sync_backend = sync_backend
        self._encryption = encryption
        self._history = clipboard_history
        self._repository = repository
        self._config_getter = config_getter
        self._notifier = notifier

        # Push lockout: once decryption fails we refuse to upload, otherwise a
        # device with the wrong key would overwrite the remote backup with
        # data nobody else can decrypt.
        self._push_locked = False
        self._notified_lock = False
        self._state_lock = threading.Lock()

    @property
    def sync_backend(self) -> SyncBackend:
        """Access the sync backend"""
        return self._sync_backend

    @property
    def is_push_locked(self) -> bool:
        """Whether push is currently locked due to a decryption failure."""
        return self._push_locked

    def set_notifier(self, notifier: Optional[Callable[[str, str], None]]):
        """Wire a notifier after construction (e.g., once signal_bridge exists)."""
        self._notifier = notifier

    def reset_push_lock(self):
        """Clear the push-lock flag. Call after the user updates the sync password."""
        with self._state_lock:
            was_locked = self._push_locked
            self._push_locked = False
            self._notified_lock = False
        if was_locked:
            logger.info("Push lock cleared - sync resumed")

    def _engage_push_lock(self, reason: str):
        """Engage the push lock and notify the user (once per lock cycle)."""
        with self._state_lock:
            already_locked = self._push_locked
            self._push_locked = True
            should_notify = not self._notified_lock
            self._notified_lock = True

        if not already_locked:
            logger.error(f"Push locked: {reason}")
        if should_notify and self._notifier:
            try:
                self._notifier(_DECRYPTION_LOCK_TITLE, _DECRYPTION_LOCK_BODY)
            except Exception as notify_err:  # pragma: no cover - defensive
                logger.error(f"Notifier failed: {notify_err}")

    def initial_sync(self) -> int:
        """
        Perform initial sync from remote: clear local cache and load remote data.

        Returns:
            Number of entries loaded
        """
        if not self._sync_backend.is_enabled:
            return 0

        try:
            # Download and decrypt BEFORE clearing local data to prevent data loss
            logger.info("Downloading remote data for initial sync...")
            backup_data = self._sync_backend.download_backup()
            if not backup_data:
                logger.warning("No remote backup found - keeping local data")
                return 0

            try:
                decrypted = self._encryption.decrypt_json(backup_data)
            except DecryptionError as e:
                self._engage_push_lock(f"initial_sync decryption failed: {e}")
                return 0

            # Successful decrypt means the current key is correct - lift any
            # prior lock that was engaged with a stale key.
            self.reset_push_lock()

            remote_entries = decrypted.get('entries', []) if decrypted else []
            logger.info(f"Initial sync decrypted backup: {len(remote_entries)} entries")
            if not remote_entries:
                logger.info("Remote backup is empty - keeping local data")
                return 0

            # Only clear local data after successful download and decrypt
            logger.info("Remote data verified, clearing local cache...")
            self._repository.clear_all()
            self._history.clear()

            loaded_count = 0
            from datetime import datetime
            for entry_data in remote_entries:
                try:
                    entry = ClipboardEntry(
                        content=entry_data['content'],
                        timestamp=datetime.fromisoformat(entry_data['timestamp']),
                        content_hash=entry_data.get('content_hash'),
                        category=entry_data.get('category') or 'text',
                        metadata=entry_data.get('metadata', {})
                    )
                    saved = self._repository.save_entry(entry)
                    if saved:
                        self._history.import_entry(entry)
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

        if self._push_locked:
            logger.warning(
                "Skipping push - decryption lock engaged "
                "(re-enter sync password in GitHub Settings to resume)"
            )
            return

        try:
            history_data = self._build_sync_payload()
            encrypted = self._encryption.encrypt_json(history_data)
            success = self._sync_backend.upload_backup(encrypted)

            if success:
                logger.info(
                    f"Push to remote completed ({len(history_data.get('entries', []))} entries)"
                )
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
                # Bumped to INFO so users can tell pull *ran* but came back
                # empty (vs. pull never running at all). The most common cause
                # is the remote file genuinely missing (404) or the two PCs
                # being pointed at different repositories / Enterprise URLs.
                logger.info(
                    "Pull skipped: download_backup returned no data "
                    "(remote file missing or unreachable - check repository config and logs above)"
                )
                return

            try:
                decrypted = self._encryption.decrypt_json(backup_data)
            except DecryptionError as e:
                self._engage_push_lock(f"pull_and_merge decryption failed: {e}")
                return

            # Successful decrypt means the current key is correct - lift any
            # prior lock that was engaged with a stale key.
            self.reset_push_lock()

            # Build hash maps for merge
            remote_entries = decrypted.get('entries', []) if decrypted else []
            logger.info(f"Pull decrypted backup: {len(remote_entries)} entries")
            remote_by_hash = {
                e.get('content_hash'): e
                for e in remote_entries if e.get('content_hash')
            }

            local_entries = self._repository.get_entries(limit=self._get_sync_limit())
            if not local_entries:
                local_entries = self._history.get_entries(limit=self._get_sync_limit())
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
                        category=entry_data.get('category') or 'text',
                        metadata=entry_data.get('metadata', {})
                    )
                    if self._history.import_entry(entry):
                        self._repository.save_entry(entry)
                        added_to_local += 1
                except Exception as e:
                    logger.error(f"Failed to import remote entry {content_hash[:8]}: {e}")

            if added_to_local > 0:
                logger.info(f"Added {added_to_local} entries from remote to local")

            # Push merged data if there are local-only entries
            if local_only_hashes:
                logger.info(f"Found {len(local_only_hashes)} local-only entries, pushing to remote...")
                self.push_to_remote()

            # Refresh UI if viewer is open
            if history_viewer:
                if hasattr(history_viewer, "refresh_entries"):
                    history_viewer.refresh_entries()
                elif hasattr(history_viewer, "_load_entries"):
                    # Backward compatibility with older viewers
                    history_viewer._load_entries()

        except Exception as e:
            logger.error(f"Pull and merge failed: {e}")

    def manual_sync(self, signal_bridge=None):
        """Run manual sync in a background thread"""
        def sync_task():
            if not self._sync_backend.is_enabled:
                logger.warning("Sync not configured")
                return

            if self._push_locked:
                logger.warning("Manual sync blocked - decryption lock engaged")
                if signal_bridge:
                    signal_bridge.show_notification_signal.emit(
                        _DECRYPTION_LOCK_TITLE, _DECRYPTION_LOCK_BODY
                    )
                return

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

        threading.Thread(target=sync_task, daemon=True).start()

    def _get_sync_limit(self) -> int:
        """Resolve sync entry limit from config with sane fallback."""
        default_limit = 500
        if not self._config_getter:
            return default_limit
        try:
            settings = self._config_getter() or {}
            clipboard_settings = settings.get('clipboard', {})
            value = int(clipboard_settings.get('max_history_size', default_limit))
            return max(1, value)
        except Exception:
            return default_limit

    def _build_sync_payload(self) -> dict:
        """Build the data payload for sync using configured history size limit."""
        sync_limit = self._get_sync_limit()
        # Prefer DB entries (persistent) over in-memory history
        entries = self._repository.get_entries(limit=sync_limit)
        if not entries:
            entries = self._history.get_entries(limit=sync_limit)

        payload = {
            'entries': [e.to_dict() for e in entries],
        }
        if self._config_getter:
            import copy
            settings = copy.deepcopy(self._config_getter())
            # Strip sensitive data - token must never be included in sync payload
            if 'github' in settings:
                settings['github'].pop('token', None)
            payload['settings'] = settings
        return payload
