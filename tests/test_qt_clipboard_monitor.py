"""Tests for the event-driven QtClipboardMonitor."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

try:
    from PyQt6.QtWidgets import QApplication  # noqa: F401

    HAS_QT = True
except Exception:  # pragma: no cover
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PyQt6 not available")


@pytest.fixture
def monitor(qtbot):
    """Build a QtClipboardMonitor using the qapp provided by pytest-qt."""
    from src.core.clipboard.qt_monitor import QtClipboardMonitor

    m = QtClipboardMonitor()
    yield m
    m.stop()


class TestQtClipboardMonitorLifecycle:
    def test_requires_running_qapplication(self, monkeypatch):
        # Simulate "no QApplication" by patching QApplication.instance().
        from src.core.clipboard import qt_monitor as qm

        monkeypatch.setattr(qm.QApplication, "instance", staticmethod(lambda: None))
        with pytest.raises(RuntimeError):
            qm.QtClipboardMonitor()

    def test_start_and_stop_toggle_is_running(self, monitor):
        assert monitor.is_running is False
        monitor.start()
        assert monitor.is_running is True
        monitor.stop()
        assert monitor.is_running is False

    def test_double_start_is_noop(self, monitor):
        monitor.start()
        monitor.start()  # should log a warning, not raise
        assert monitor.is_running is True

    def test_double_stop_is_safe(self, monitor):
        monitor.stop()
        monitor.stop()
        assert monitor.is_running is False


class TestCallbacks:
    def test_callback_fires_on_data_changed(self, monitor):
        received = []
        monitor.add_callback(lambda content, ts: received.append((content, ts)))
        monitor.start()

        # Drive the internal handler directly to avoid depending on the OS
        # clipboard (headless Linux may expose a stub provider).
        monitor._clipboard = MagicMock()
        monitor._clipboard.text.return_value = "hello"
        monitor._on_data_changed()

        assert len(received) == 1
        assert received[0][0] == "hello"
        assert isinstance(received[0][1], datetime)

    def test_duplicate_content_does_not_re_fire(self, monitor):
        received = []
        monitor.add_callback(lambda c, t: received.append(c))
        monitor.start()

        monitor._clipboard = MagicMock()
        monitor._clipboard.text.return_value = "same"

        monitor._on_data_changed()
        monitor._on_data_changed()
        monitor._on_data_changed()

        assert received == ["same"]

    def test_different_content_fires_again(self, monitor):
        received = []
        monitor.add_callback(lambda c, t: received.append(c))
        monitor.start()

        monitor._clipboard = MagicMock()

        monitor._clipboard.text.return_value = "first"
        monitor._on_data_changed()

        monitor._clipboard.text.return_value = "second"
        monitor._on_data_changed()

        assert received == ["first", "second"]

    def test_empty_content_is_ignored(self, monitor):
        received = []
        monitor.add_callback(lambda c, t: received.append(c))
        monitor.start()

        monitor._clipboard = MagicMock()
        monitor._clipboard.text.return_value = ""
        monitor._on_data_changed()

        assert received == []

    def test_remove_callback_prevents_invocation(self, monitor):
        received = []
        cb = lambda c, t: received.append(c)
        monitor.add_callback(cb)
        monitor.remove_callback(cb)
        monitor.start()

        monitor._clipboard = MagicMock()
        monitor._clipboard.text.return_value = "gone"
        monitor._on_data_changed()

        assert received == []

    def test_callback_exception_does_not_break_other_callbacks(self, monitor):
        received = []

        def bad(_c, _t):
            raise RuntimeError("boom")

        def good(c, _t):
            received.append(c)

        monitor.add_callback(bad)
        monitor.add_callback(good)
        monitor.start()

        monitor._clipboard = MagicMock()
        monitor._clipboard.text.return_value = "ok"
        monitor._on_data_changed()

        assert received == ["ok"]


class TestComponentFactoryFallback:
    def test_factory_picks_qt_monitor_when_qapp_present(self, qtbot, tmp_path):
        from src.services.component_factory import ComponentFactory
        from src.utils.config_manager import ConfigManager
        from src.core.clipboard.qt_monitor import QtClipboardMonitor

        cm = ConfigManager(str(tmp_path / "settings.yaml"))
        factory = ComponentFactory(cm)
        monitor, _history = factory.create_clipboard()
        assert isinstance(monitor, QtClipboardMonitor)

    def test_factory_falls_back_when_no_qapp(self, monkeypatch, tmp_path):
        from src.services import component_factory as cf
        from src.core.clipboard import ClipboardMonitor
        from src.utils.config_manager import ConfigManager

        # Force the Qt check to fail as if no QApplication were running.
        monkeypatch.setattr(cf.ComponentFactory, "_try_create_qt_monitor",
                            staticmethod(lambda: None))

        cm = ConfigManager(str(tmp_path / "settings.yaml"))
        factory = cf.ComponentFactory(cm)
        monitor, _history = factory.create_clipboard()
        assert isinstance(monitor, ClipboardMonitor)
