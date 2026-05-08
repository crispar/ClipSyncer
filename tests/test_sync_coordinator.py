"""Tests for SyncCoordinator behavior and compatibility guarantees."""

from datetime import datetime, timedelta

from src.core.clipboard.history import ClipboardEntry
from src.core.encryption.manager import EncryptionManager
from src.services.sync_coordinator import SyncCoordinator


class DummySyncBackend:
    """Simple in-memory sync backend for coordinator tests."""

    def __init__(self, backup_payload=None, enabled=True):
        self._backup_payload = backup_payload
        self._enabled = enabled
        self.uploaded_payloads = []

    @property
    def is_enabled(self):
        return self._enabled

    def download_backup(self, filename=None):
        return self._backup_payload

    def upload_backup(self, data, filename=None):
        self.uploaded_payloads.append((data, filename))
        return True


class TestSyncCoordinator:
    def test_initial_sync_preserves_category_and_metadata(
        self, repository, clipboard_history, encryption_manager
    ):
        timestamp = datetime(2026, 2, 14, 9, 0, 0)
        remote_data = {
            "entries": [
                {
                    "content": "https://example.com",
                    "timestamp": timestamp.isoformat(),
                    "content_hash": ClipboardEntry.calculate_hash("https://example.com"),
                    "category": "url",
                    "metadata": {"source": "browser"},
                }
            ]
        }
        encrypted_remote = encryption_manager.encrypt_json(remote_data)
        backend = DummySyncBackend(backup_payload=encrypted_remote)

        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
        )

        loaded_count = coordinator.initial_sync()
        assert loaded_count == 1

        db_entries = repository.get_entries()
        assert len(db_entries) == 1
        assert db_entries[0].category == "url"
        assert db_entries[0].metadata == {"source": "browser"}

        memory_entries = clipboard_history.get_entries()
        assert len(memory_entries) == 1
        assert memory_entries[0].category == "url"
        assert memory_entries[0].metadata == {"source": "browser"}

    def test_build_sync_payload_uses_configured_history_limit(
        self, repository, clipboard_history, encryption_manager
    ):
        now = datetime.now()
        for i in range(10):
            entry = ClipboardEntry(
                content=f"entry_{i}",
                timestamp=now - timedelta(minutes=i),
                content_hash=ClipboardEntry.calculate_hash(f"entry_{i}"),
            )
            repository.save_entry(entry)
            clipboard_history.import_entry(entry)

        backend = DummySyncBackend()
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {
                "clipboard": {"max_history_size": 3},
                "github": {"token": "must_not_be_synced"},
            },
        )

        payload = coordinator._build_sync_payload()
        assert len(payload["entries"]) == 3
        assert "token" not in payload["settings"]["github"]

    def test_pull_and_merge_uses_repository_as_local_source_of_truth(
        self, repository, clipboard_history, encryption_manager
    ):
        # Local DB has one entry, but in-memory history starts empty. The
        # dirty mark simulates the user actually having added that entry via
        # the clipboard, so pull_and_merge should push it (the assertion this
        # test is really about: pull reads from the DB, not from in-memory
        # history, when both diverge).
        local_entry = ClipboardEntry(
            content="local_only",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("local_only"),
        )
        repository.save_entry(local_entry)
        clipboard_history.clear()

        encrypted_remote = encryption_manager.encrypt_json({"entries": []})
        backend = DummySyncBackend(backup_payload=encrypted_remote)
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {"clipboard": {"max_history_size": 500}},
        )
        coordinator.mark_local_dirty()

        coordinator.pull_and_merge()
        assert len(backend.uploaded_payloads) == 1
        # And it pushed the DB entry, not the empty history.
        pushed_payload, _ = backend.uploaded_payloads[0]
        decrypted = encryption_manager.decrypt_json(pushed_payload)
        assert any(e["content"] == "local_only" for e in decrypted["entries"])


class TestSyncCoordinatorPushLock:
    """Decryption-failure safeguards: notify + refuse to push."""

    def _wrong_key_encrypted_payload(self):
        """Build a backup encrypted with a key SyncCoordinator does NOT have."""
        wrong_em = EncryptionManager(b"\x11" * 32)
        return wrong_em.encrypt_json({"entries": [{"content_hash": "deadbeef"}]})

    def test_pull_decryption_failure_engages_push_lock_and_notifies(
        self, repository, clipboard_history, encryption_manager
    ):
        notifications = []
        backend = DummySyncBackend(backup_payload=self._wrong_key_encrypted_payload())
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
            notifier=lambda title, body: notifications.append((title, body)),
        )

        coordinator.pull_and_merge()

        assert coordinator.is_push_locked is True
        assert len(notifications) == 1
        assert "sync password" in notifications[0][1].lower()

    def test_locked_push_refuses_to_upload(
        self, repository, clipboard_history, encryption_manager
    ):
        backend = DummySyncBackend(backup_payload=self._wrong_key_encrypted_payload())
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
            notifier=lambda *_: None,
        )

        # Trigger lock
        coordinator.pull_and_merge()
        assert coordinator.is_push_locked is True

        # Add a local entry then attempt push - it must NOT touch the backend
        repository.save_entry(ClipboardEntry(
            content="local",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("local"),
        ))
        coordinator.push_to_remote()
        assert backend.uploaded_payloads == []

    def test_notifier_fires_only_once_per_lock_cycle(
        self, repository, clipboard_history, encryption_manager
    ):
        notifications = []
        backend = DummySyncBackend(backup_payload=self._wrong_key_encrypted_payload())
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
            notifier=lambda title, body: notifications.append((title, body)),
        )

        coordinator.pull_and_merge()
        coordinator.pull_and_merge()
        coordinator.pull_and_merge()

        assert len(notifications) == 1

    def test_successful_pull_clears_lock(
        self, repository, clipboard_history, encryption_manager
    ):
        # First, fail with wrong-key payload to engage the lock.
        backend = DummySyncBackend(backup_payload=self._wrong_key_encrypted_payload())
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
            notifier=lambda *_: None,
        )
        coordinator.pull_and_merge()
        assert coordinator.is_push_locked is True

        # Now swap in a valid (correctly-encrypted) backup and pull again.
        backend._backup_payload = encryption_manager.encrypt_json({"entries": []})
        coordinator.pull_and_merge()
        assert coordinator.is_push_locked is False

    def test_initial_sync_decryption_failure_engages_lock(
        self, repository, clipboard_history, encryption_manager
    ):
        notifications = []
        backend = DummySyncBackend(backup_payload=self._wrong_key_encrypted_payload())
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
            notifier=lambda title, body: notifications.append((title, body)),
        )

        loaded = coordinator.initial_sync()
        assert loaded == 0
        assert coordinator.is_push_locked is True
        assert len(notifications) == 1

    def test_reset_push_lock_unblocks_uploads(
        self, repository, clipboard_history, encryption_manager
    ):
        backend = DummySyncBackend(backup_payload=self._wrong_key_encrypted_payload())
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
            notifier=lambda *_: None,
        )
        coordinator.pull_and_merge()
        assert coordinator.is_push_locked is True

        coordinator.reset_push_lock()
        assert coordinator.is_push_locked is False

        repository.save_entry(ClipboardEntry(
            content="post-reset",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("post-reset"),
        ))
        coordinator.push_to_remote()
        assert len(backend.uploaded_payloads) == 1


class TestSyncCoordinatorPullDrivenPush:
    """pull_and_merge must NOT push every cycle when nothing changed locally."""

    def test_pull_does_not_push_when_clean_even_with_local_only_drift(
        self, repository, clipboard_history, encryption_manager
    ):
        # Local has one entry; remote is empty (simulates the drift scenario
        # where the entry is "local-only" relative to the remote payload).
        local_entry = ClipboardEntry(
            content="drift_entry",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("drift_entry"),
        )
        repository.save_entry(local_entry)

        encrypted_remote = encryption_manager.encrypt_json({"entries": []})
        backend = DummySyncBackend(backup_payload=encrypted_remote)
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
        )

        # Coordinator was just constructed - nothing was marked dirty - so
        # pull_and_merge must NOT trigger a push despite local-only hashes.
        assert coordinator.is_local_dirty() is False
        coordinator.pull_and_merge()
        assert backend.uploaded_payloads == [], (
            "pull-driven push fired despite no local changes - this is the "
            "every-minute-push regression"
        )

    def test_pull_does_push_when_dirty_and_local_only_present(
        self, repository, clipboard_history, encryption_manager
    ):
        local_entry = ClipboardEntry(
            content="actually_new",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("actually_new"),
        )
        repository.save_entry(local_entry)

        encrypted_remote = encryption_manager.encrypt_json({"entries": []})
        backend = DummySyncBackend(backup_payload=encrypted_remote)
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
        )

        # Simulate a real clipboard add having marked the coordinator dirty.
        coordinator.mark_local_dirty()
        assert coordinator.is_local_dirty() is True

        coordinator.pull_and_merge()
        assert len(backend.uploaded_payloads) == 1

    def test_successful_push_clears_dirty(
        self, repository, clipboard_history, encryption_manager
    ):
        repository.save_entry(ClipboardEntry(
            content="x",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("x"),
        ))
        backend = DummySyncBackend()
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
        )

        coordinator.mark_local_dirty()
        assert coordinator.is_local_dirty() is True

        coordinator.push_to_remote()
        assert coordinator.is_local_dirty() is False

    def test_dirty_during_push_remains_dirty(
        self, repository, clipboard_history, encryption_manager
    ):
        """A clipboard add that races with an in-flight push must NOT be
        silently swallowed - the dirty flag must stay set so a follow-up push
        actually runs."""
        repository.save_entry(ClipboardEntry(
            content="x",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("x"),
        ))

        race_token_check = {}

        class RacingBackend(DummySyncBackend):
            def upload_backup(self, data, filename=None):
                # Simulate a clipboard add happening while we're uploading.
                race_token_check["coordinator"].mark_local_dirty()
                return super().upload_backup(data, filename)

        backend = RacingBackend()
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
        )
        race_token_check["coordinator"] = coordinator

        coordinator.mark_local_dirty()
        coordinator.push_to_remote()
        assert coordinator.is_local_dirty() is True, (
            "Race-during-push lost the new dirty mark - second push will be skipped"
        )

    def test_failed_push_keeps_dirty(
        self, repository, clipboard_history, encryption_manager
    ):
        repository.save_entry(ClipboardEntry(
            content="x",
            timestamp=datetime.now(),
            content_hash=ClipboardEntry.calculate_hash("x"),
        ))

        class FailingBackend(DummySyncBackend):
            def upload_backup(self, data, filename=None):
                self.uploaded_payloads.append((data, filename))
                return False

        backend = FailingBackend()
        coordinator = SyncCoordinator(
            sync_backend=backend,
            encryption=encryption_manager,
            clipboard_history=clipboard_history,
            repository=repository,
            config_getter=lambda: {},
        )

        coordinator.mark_local_dirty()
        coordinator.push_to_remote()
        assert coordinator.is_local_dirty() is True
