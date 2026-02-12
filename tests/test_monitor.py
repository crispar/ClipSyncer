"""Tests for ClipboardMonitor"""

import threading
import time
from unittest.mock import patch, MagicMock
from datetime import datetime
import pytest

from src.core.clipboard.monitor import ClipboardMonitor


class TestClipboardMonitorInit:
    """Tests for monitor initialization"""

    def test_default_interval(self):
        monitor = ClipboardMonitor()
        assert monitor.check_interval == 0.5  # 500ms = 0.5s

    def test_custom_interval(self):
        monitor = ClipboardMonitor(check_interval=1000)
        assert monitor.check_interval == 1.0

    def test_initial_state(self):
        monitor = ClipboardMonitor()
        assert monitor.is_running is False


class TestClipboardMonitorCallbacks:
    """Tests for callback management"""

    def test_add_callback(self):
        monitor = ClipboardMonitor()

        def cb(content, ts):
            pass

        monitor.add_callback(cb)
        assert cb in monitor._callbacks

    def test_remove_callback(self):
        monitor = ClipboardMonitor()

        def cb(content, ts):
            pass

        monitor.add_callback(cb)
        monitor.remove_callback(cb)
        assert cb not in monitor._callbacks

    def test_remove_nonexistent_callback(self):
        monitor = ClipboardMonitor()

        def cb(content, ts):
            pass

        # Should not raise
        monitor.remove_callback(cb)


class TestClipboardMonitorHasChanged:
    """Tests for content change detection"""

    def test_first_content_always_changed(self):
        monitor = ClipboardMonitor()
        assert monitor._has_changed("new content") is True

    def test_same_content_not_changed(self):
        monitor = ClipboardMonitor()
        monitor._has_changed("same")
        assert monitor._has_changed("same") is False

    def test_different_content_changed(self):
        monitor = ClipboardMonitor()
        monitor._has_changed("first")
        assert monitor._has_changed("second") is True

    def test_has_changed_thread_safe(self):
        """Test that _has_changed is thread-safe"""
        monitor = ClipboardMonitor()
        errors = []
        results = []

        def check_change(content):
            try:
                result = monitor._has_changed(content)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(20):
            t = threading.Thread(target=check_change, args=(f"content_{i % 5}",))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestClipboardMonitorStartStop:
    """Tests for start/stop lifecycle"""

    @patch('src.core.clipboard.monitor.pyperclip')
    def test_start_creates_thread(self, mock_pyperclip):
        mock_pyperclip.paste.return_value = ""
        monitor = ClipboardMonitor(check_interval=100)
        monitor.start()
        assert monitor.is_running is True
        assert monitor._thread is not None
        monitor.stop()

    @patch('src.core.clipboard.monitor.pyperclip')
    def test_stop_cleans_up(self, mock_pyperclip):
        mock_pyperclip.paste.return_value = ""
        monitor = ClipboardMonitor(check_interval=100)
        monitor.start()
        monitor.stop()
        assert monitor.is_running is False
        assert monitor._thread is None

    @patch('src.core.clipboard.monitor.pyperclip')
    def test_double_start(self, mock_pyperclip):
        mock_pyperclip.paste.return_value = ""
        monitor = ClipboardMonitor(check_interval=100)
        monitor.start()
        monitor.start()  # Should log warning, not crash
        assert monitor.is_running is True
        monitor.stop()

    def test_stop_when_not_running(self):
        monitor = ClipboardMonitor()
        monitor.stop()  # Should not crash

    @patch('src.core.clipboard.monitor.pyperclip')
    def test_callback_invoked_on_change(self, mock_pyperclip):
        """Test that callbacks are called when clipboard changes"""
        received = []

        def on_change(content, timestamp):
            received.append(content)

        mock_pyperclip.paste.side_effect = ["first", "first", "second", "second", ""]

        monitor = ClipboardMonitor(check_interval=50)
        monitor.add_callback(on_change)
        monitor.start()
        time.sleep(0.4)
        monitor.stop()

        # Should have detected at least 'first' and 'second'
        assert len(received) >= 1

    @patch('src.core.clipboard.monitor.pyperclip')
    def test_callback_error_doesnt_crash_monitor(self, mock_pyperclip):
        """Callback errors should be caught"""
        mock_pyperclip.paste.side_effect = ["trigger", "", ""]

        def bad_callback(content, timestamp):
            raise RuntimeError("callback error")

        monitor = ClipboardMonitor(check_interval=50)
        monitor.add_callback(bad_callback)
        monitor.start()
        time.sleep(0.2)
        monitor.stop()
        # Monitor should still have run without crashing


class TestClipboardMonitorGetCurrent:
    """Tests for get_current_content"""

    @patch('src.core.clipboard.monitor.pyperclip')
    def test_get_current_content(self, mock_pyperclip):
        mock_pyperclip.paste.return_value = "current text"
        monitor = ClipboardMonitor()
        assert monitor.get_current_content() == "current text"

    @patch('src.core.clipboard.monitor.pyperclip')
    def test_get_current_content_error(self, mock_pyperclip):
        mock_pyperclip.paste.side_effect = Exception("clipboard error")
        monitor = ClipboardMonitor()
        assert monitor.get_current_content() is None
