"""Tests for AutoSyncService"""

import time
import threading
import pytest

from src.services.auto_sync_service import AutoSyncService


class TestAutoSyncServiceInit:
    """Tests for AutoSyncService initialization"""

    def test_default_pull_interval(self):
        service = AutoSyncService()
        assert service.pull_interval == AutoSyncService.DEFAULT_PULL_INTERVAL

    def test_custom_pull_interval(self):
        service = AutoSyncService(pull_interval_seconds=300)
        assert service.pull_interval == 300

    def test_initial_state(self):
        service = AutoSyncService()
        assert service.enabled is False
        assert service.pending_changes == 0


class TestAutoSyncPush:
    """Tests for push trigger and debounce logic"""

    def test_trigger_push_increments_pending(self):
        service = AutoSyncService()
        service.trigger_push()
        assert service.pending_changes == 1
        service.trigger_push()
        assert service.pending_changes == 2

    def test_trigger_push_not_enabled_no_timer(self):
        service = AutoSyncService()
        service.trigger_push()
        # Timer shouldn't be created when service not enabled
        assert service._debounce_timer is None

    def test_push_executes_callback(self):
        service = AutoSyncService()
        push_count = [0]

        def push_cb():
            push_count[0] += 1

        service.set_push_callback(push_cb)
        service.enabled = True
        service._pending_changes = 1
        service._execute_push()
        assert push_count[0] == 1
        assert service.pending_changes == 0

    def test_push_skips_when_no_pending_changes(self):
        service = AutoSyncService()
        push_count = [0]

        def push_cb():
            push_count[0] += 1

        service.set_push_callback(push_cb)
        service.enabled = True
        service._pending_changes = 0
        service._execute_push()
        assert push_count[0] == 0

    def test_push_skips_when_disabled(self):
        service = AutoSyncService()
        push_count = [0]

        def push_cb():
            push_count[0] += 1

        service.set_push_callback(push_cb)
        service.enabled = False
        service._pending_changes = 5
        service._execute_push()
        assert push_count[0] == 0

    def test_push_respects_min_interval(self):
        service = AutoSyncService()
        push_count = [0]

        def push_cb():
            push_count[0] += 1

        service.set_push_callback(push_cb)
        service.enabled = True
        service._pending_changes = 1

        # First push succeeds
        service._execute_push()
        assert push_count[0] == 1

        # Immediate second push should be delayed (within MIN_PUSH_INTERVAL)
        service._pending_changes = 1
        service._execute_push()
        # Should not have executed immediately
        assert push_count[0] == 1
        # But a timer should be scheduled
        assert service._debounce_timer is not None

        # Cleanup
        if service._debounce_timer:
            service._debounce_timer.cancel()

    def test_push_callback_error_handled(self):
        service = AutoSyncService()

        def bad_cb():
            raise RuntimeError("push failed")

        service.set_push_callback(bad_cb)
        service.enabled = True
        service._pending_changes = 1
        # Should not raise
        service._execute_push()

    def test_debounce_with_enabled_service(self):
        service = AutoSyncService()
        push_count = [0]

        def push_cb():
            push_count[0] += 1

        service.set_push_callback(push_cb)
        service.enabled = True

        # Trigger push - should start debounce timer
        service.trigger_push()
        assert service._debounce_timer is not None

        # Cleanup
        service.stop()


class TestAutoSyncPull:
    """Tests for pull scheduling"""

    def test_pull_executes_callback(self):
        service = AutoSyncService(pull_interval_seconds=3600)
        pull_count = [0]

        def pull_cb():
            pull_count[0] += 1

        service.set_pull_callback(pull_cb)
        service.enabled = True
        service._execute_pull()
        assert pull_count[0] == 1

    def test_pull_callback_error_handled(self):
        service = AutoSyncService(pull_interval_seconds=3600)

        def bad_cb():
            raise RuntimeError("pull failed")

        service.set_pull_callback(bad_cb)
        service.enabled = True
        # Should not raise, and should schedule next pull
        service._execute_pull()
        # Cleanup
        service.stop()

    def test_pull_not_executed_when_disabled(self):
        service = AutoSyncService(pull_interval_seconds=3600)
        pull_count = [0]

        def pull_cb():
            pull_count[0] += 1

        service.set_pull_callback(pull_cb)
        service.enabled = False
        service._execute_pull()
        assert pull_count[0] == 0


class TestAutoSyncLifecycle:
    """Tests for start/stop lifecycle"""

    def test_start_enables_service(self):
        service = AutoSyncService(pull_interval_seconds=3600)
        service.set_push_callback(lambda: None)
        service.set_pull_callback(lambda: None)
        service.start()
        assert service.enabled is True
        service.stop()

    def test_stop_disables_service(self):
        service = AutoSyncService(pull_interval_seconds=3600)
        service.set_push_callback(lambda: None)
        service.set_pull_callback(lambda: None)
        service.start()
        service.stop()
        assert service.enabled is False
        assert service._debounce_timer is None
        assert service._pull_timer is None

    def test_start_without_push_callback(self):
        service = AutoSyncService(pull_interval_seconds=3600)
        service.set_pull_callback(lambda: None)
        # Should start without error (just logs warning)
        service.start()
        service.stop()

    def test_start_schedules_pull_timer(self):
        service = AutoSyncService(pull_interval_seconds=3600)
        service.set_pull_callback(lambda: None)
        service.start()
        assert service._pull_timer is not None
        service.stop()


class TestAutoSyncForce:
    """Tests for force push/pull"""

    def test_force_push(self):
        service = AutoSyncService()
        push_count = [0]

        def push_cb():
            push_count[0] += 1

        service.set_push_callback(push_cb)
        service.force_push()
        assert push_count[0] == 1
        assert service.pending_changes == 0

    def test_force_push_no_callback(self):
        service = AutoSyncService()
        # Should not raise
        service.force_push()

    def test_force_pull(self):
        service = AutoSyncService()
        pull_count = [0]

        def pull_cb():
            pull_count[0] += 1

        service.set_pull_callback(pull_cb)
        service.force_pull()
        assert pull_count[0] == 1

    def test_force_pull_no_callback(self):
        service = AutoSyncService()
        # Should not raise
        service.force_pull()

    def test_force_push_error_handled(self):
        service = AutoSyncService()
        service.set_push_callback(lambda: (_ for _ in ()).throw(RuntimeError("err")))
        # Should not raise
        service.force_push()


class TestAutoSyncInterval:
    """Tests for pull interval property"""

    def test_get_pull_interval(self):
        service = AutoSyncService(pull_interval_seconds=120)
        assert service.pull_interval_seconds == 120

    def test_set_pull_interval(self):
        service = AutoSyncService(pull_interval_seconds=60)
        service.pull_interval_seconds = 300
        assert service.pull_interval == 300

    def test_set_pull_interval_restarts_timer(self):
        service = AutoSyncService(pull_interval_seconds=3600)
        service.set_pull_callback(lambda: None)
        service.start()
        old_timer = service._pull_timer
        service.pull_interval_seconds = 120
        # Timer should have been restarted
        assert service._pull_timer is not old_timer
        service.stop()
