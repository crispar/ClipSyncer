"""Tests for AutoSyncService"""

import time
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.services.auto_sync_service import AutoSyncService


class TestAutoSyncService:
    """Tests for AutoSyncService"""

    def test_init_defaults(self):
        service = AutoSyncService()
        assert service.pull_interval == 60
        assert service.enabled is False
        assert service.pending_changes == 0

    def test_set_push_callback(self):
        service = AutoSyncService()
        cb = MagicMock()
        service.set_push_callback(cb)
        assert service._push_callback == cb

    def test_set_pull_callback(self):
        service = AutoSyncService()
        cb = MagicMock()
        service.set_pull_callback(cb)
        assert service._pull_callback == cb

    def test_trigger_push_increments_pending(self):
        service = AutoSyncService()
        service.trigger_push()
        assert service.pending_changes == 1
        service.trigger_push()
        assert service.pending_changes == 2

    def test_trigger_push_without_enable_does_not_schedule(self):
        service = AutoSyncService()
        service.set_push_callback(MagicMock())
        service.trigger_push()
        # No timer should be started since service is not enabled
        assert service._debounce_timer is None

    def test_start_sets_enabled(self):
        service = AutoSyncService()
        service.set_push_callback(MagicMock())
        service.start()
        assert service.enabled is True
        service.stop()

    def test_stop_clears_timers(self):
        service = AutoSyncService()
        service.set_push_callback(MagicMock())
        service.set_pull_callback(MagicMock())
        service.start()
        service.stop()
        assert service.enabled is False
        assert service._debounce_timer is None
        assert service._pull_timer is None

    def test_force_push_calls_callback(self):
        service = AutoSyncService()
        cb = MagicMock()
        service.set_push_callback(cb)
        service.enabled = True
        service._pending_changes = 3
        service.force_push()
        cb.assert_called_once()
        assert service.pending_changes == 0

    def test_force_push_without_callback(self):
        service = AutoSyncService()
        service.enabled = True
        # Should not raise
        service.force_push()

    def test_force_pull_calls_callback(self):
        service = AutoSyncService()
        cb = MagicMock()
        service.set_pull_callback(cb)
        service.force_pull()
        cb.assert_called_once()

    def test_force_pull_without_callback(self):
        service = AutoSyncService()
        # Should not raise
        service.force_pull()

    def test_pull_interval_property(self):
        service = AutoSyncService(pull_interval_seconds=120)
        assert service.pull_interval_seconds == 120
        service.pull_interval_seconds = 30
        assert service.pull_interval_seconds == 30

    def test_last_push_time(self):
        service = AutoSyncService()
        cb = MagicMock()
        service.set_push_callback(cb)
        service.force_push()
        assert service.last_push_time > datetime.min

    def test_force_push_handles_callback_error(self):
        service = AutoSyncService()
        cb = MagicMock(side_effect=RuntimeError("network error"))
        service.set_push_callback(cb)
        # Should not raise
        service.force_push()
        cb.assert_called_once()

    def test_force_pull_handles_callback_error(self):
        service = AutoSyncService()
        cb = MagicMock(side_effect=RuntimeError("network error"))
        service.set_pull_callback(cb)
        # Should not raise
        service.force_pull()
        cb.assert_called_once()
