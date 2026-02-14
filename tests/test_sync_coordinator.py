"""Tests for SyncCoordinator behavior and compatibility guarantees."""

from datetime import datetime, timedelta

from src.core.clipboard.history import ClipboardEntry
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
        # Local DB has one entry, but in-memory history starts empty.
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

        coordinator.pull_and_merge()
        assert len(backend.uploaded_payloads) == 1
