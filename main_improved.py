"""Improved main application with better Qt thread handling"""

import sys
import os
import signal
import threading
import hashlib
from pathlib import Path

# Add src to path BEFORE any HTTPS-using imports - so truststore can inject
# into ssl before urllib3/requests/PyGithub cache their default SSLContext.
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.utils import tls as _tls_bootstrap  # noqa: E402
_tls_bootstrap.activate()

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtCore import QTimer, pyqtSignal, QObject  # noqa: E402
from loguru import logger  # noqa: E402

from src.services.component_factory import ComponentFactory  # noqa: E402
from src.services.sync_coordinator import SyncCoordinator
from src.services.auto_sync_service import AutoSyncService
from src.services.archive_manager import ArchiveManager
from src.ui.tray import TrayIcon
from src.ui.history import HistoryViewer
from src.utils import ConfigManager


class QtSignalBridge(QObject):
    """Bridge for communicating between threads and Qt main thread"""
    show_history_signal = pyqtSignal()
    toggle_monitoring_signal = pyqtSignal()
    sync_github_signal = pyqtSignal()
    cleanup_signal = pyqtSignal()
    quit_signal = pyqtSignal()
    show_notification_signal = pyqtSignal(str, str)
    refresh_history_signal = pyqtSignal()


class ClipboardHistoryApp:
    """Main application class - orchestrates UI and services"""

    def __init__(self):
        """Initialize application"""
        # Core components (set during initialize)
        self.config_manager = None
        self.clipboard_monitor = None
        self.clipboard_history = None
        self.encryption_manager = None
        self.database_manager = None
        self.repository = None
        self.github_sync = None
        self.cleanup_service = None
        self.archive_manager = None
        self.sync_coordinator = None
        self.auto_sync = None

        # UI components
        self.tray_icon = None
        self.history_viewer = None
        self.qt_app = None
        self.signal_bridge = None

        # State
        self._shutdown_event = threading.Event()
        self.is_github_primary = False

        # Setup logging
        self._setup_logging()

        logger.info("=" * 60)
        logger.info("ClipboardHistory Application Starting")
        logger.info("=" * 60)

    def _setup_logging(self):
        """Configure logging"""
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
            log_dir = exe_dir / 'logs'
        else:
            log_dir = Path(os.environ.get('APPDATA', '.')) / 'ClipboardHistory' / 'logs'

        log_dir.mkdir(parents=True, exist_ok=True)

        logger.remove()

        if sys.stderr is not None:
            logger.add(
                sys.stderr,
                level="INFO",
                format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
            )

        log_file = log_dir / "ClipSyncer_{time:YYYY-MM-DD}.log"
        logger.add(
            log_file,
            rotation="1 day",
            retention="7 days",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            encoding="utf-8"
        )

        latest_log = log_dir / "ClipSyncer_latest.log"
        logger.add(
            latest_log,
            rotation="10 MB",
            retention=1,
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            encoding="utf-8",
            mode="w"
        )

        logger.info(f"=== ClipSyncer Started ===")
        logger.info(f"Executable: {sys.executable}")
        logger.info(f"Log directory: {log_dir}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")

        # Surface truststore status. Critical to debug corporate TLS issues:
        # if active=True, OS trust store is in use (Windows cert mgr / macOS
        # keychain) which usually fixes CERTIFICATE_VERIFY_FAILED on corporate
        # MITM proxies. If active=False the user must rely on the certifi
        # bundle or a manually configured ca_bundle_path.
        if _tls_bootstrap.is_active():
            logger.info(
                "TLS: truststore active - using OS trust store "
                "(Windows cert mgr / macOS keychain / Linux system store)"
            )
        else:
            logger.warning(
                f"TLS: truststore NOT active ({_tls_bootstrap.last_error() or 'unknown'}); "
                "falling back to certifi - corporate MITM proxies may break HTTPS. "
                "Install truststore (Python 3.10+) for native Windows CA support."
            )

    def initialize(self):
        """Initialize all components using ComponentFactory"""
        try:
            # Load configuration
            logger.info("Loading configuration...")
            self.config_manager = ConfigManager()

            if not self.config_manager.validate():
                logger.error("Invalid configuration")
                return False

            # Create component factory
            factory = ComponentFactory(self.config_manager)

            # Create core components
            key_manager, self.encryption_manager = factory.create_encryption()
            self.database_manager, self.repository = factory.create_storage(self.encryption_manager)
            self.clipboard_monitor, self.clipboard_history = factory.create_clipboard()

            # Setup clipboard callback
            self.clipboard_monitor.add_callback(self._on_clipboard_change)

            # Initialize GitHub sync
            self.auto_sync = None
            github_settings = factory.load_github_settings()

            if github_settings and github_settings.get('enabled'):
                logger.info("Initializing GitHub sync from github_settings.yaml...")
                self.github_sync = factory.create_github_sync(github_settings)

                if self.github_sync:
                    self.is_github_primary = github_settings.get('is_primary_storage', True)
                    logger.info("GitHub is PRIMARY storage - local DB will be cache-only")

                    # Create sync coordinator
                    self.sync_coordinator = SyncCoordinator(
                        sync_backend=self.github_sync,
                        encryption=self.encryption_manager,
                        clipboard_history=self.clipboard_history,
                        repository=self.repository,
                        config_getter=self.config_manager.get_all
                    )

                    # Initial sync
                    logger.info("Performing initial sync from GitHub...")
                    self.sync_coordinator.initial_sync()

                    # Auto sync
                    self.auto_sync = factory.create_auto_sync(github_settings)
                    if self.auto_sync:
                        self.auto_sync.set_push_callback(self.sync_coordinator.push_to_remote)
                        self.auto_sync.set_pull_callback(self._pull_from_github)
                        logger.info("Auto sync configured with immediate push and periodic pull")

            elif self.config_manager.get('github.enabled'):
                # Fallback to main config
                logger.info("Initializing GitHub sync from main config...")
                fallback_settings = {
                    'token': self.config_manager.get('github.token'),
                    'repository': self.config_manager.get('github.repository'),
                    'enterprise_url': self.config_manager.get('github.enterprise_url'),
                    'auto_sync_enabled': self.config_manager.get('github.auto_sync_enabled', True),
                    'auto_sync_interval_minutes': self.config_manager.get('github.auto_sync_interval_minutes', 30),
                }
                self.github_sync = factory.create_github_sync(fallback_settings)

                if self.github_sync:
                    self.sync_coordinator = SyncCoordinator(
                        sync_backend=self.github_sync,
                        encryption=self.encryption_manager,
                        clipboard_history=self.clipboard_history,
                        repository=self.repository,
                        config_getter=self.config_manager.get_all
                    )
                    self.auto_sync = factory.create_auto_sync(fallback_settings)
                    if self.auto_sync:
                        self.auto_sync.set_push_callback(self.sync_coordinator.push_to_remote)
                        self.auto_sync.set_pull_callback(self._pull_from_github)
                        logger.info("Auto sync configured with real-time push and periodic pull")
            else:
                logger.info("GitHub sync not configured")

            # Initialize archive manager
            logger.info("Initializing archive manager...")
            self.archive_manager = ArchiveManager(self.github_sync)

            # Initialize cleanup service
            self.cleanup_service = factory.create_cleanup(
                self.clipboard_history, self.repository,
                self.database_manager, self.archive_manager
            )

            logger.info("Application initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            return False

    def _on_clipboard_change(self, content: str, timestamp):
        """Handle clipboard change event"""
        try:
            added, removed_entry = self.clipboard_history.add_entry(content, timestamp)

            # Archive the removed entry if any
            if removed_entry and self.archive_manager:
                try:
                    archive_entry = {
                        'content': removed_entry.content,
                        'timestamp': removed_entry.timestamp.isoformat(),
                        'content_hash': removed_entry.content_hash,
                        'category': removed_entry.category,
                        'metadata': removed_entry.metadata
                    }
                    self.archive_manager.archive_entries([archive_entry])
                    logger.debug(f"Archived overflow entry: {removed_entry.content_hash[:8]}")
                except Exception as e:
                    logger.error(f"Failed to archive overflow entry: {e}")

            latest_entry = None
            entries = self.clipboard_history.get_entries(limit=1)
            if entries:
                latest_entry = entries[0]

            if added and latest_entry:
                self.repository.save_entry(latest_entry)

                if self.auto_sync:
                    self.auto_sync.trigger_push()

                if self.config_manager.get('ui.show_notifications') and self.signal_bridge:
                    self.signal_bridge.show_notification_signal.emit(
                        "Clipboard Captured",
                        f"Saved {len(content)} characters"
                    )

                logger.debug(f"Clipboard content saved: {len(content)} characters")
            elif content and latest_entry:
                # Duplicate content updates timestamp in memory; persist timestamp refresh to DB.
                expected_hash = hashlib.sha256(content.encode()).hexdigest()
                if latest_entry.content_hash == expected_hash:
                    self.repository.save_entry(latest_entry)
                    if self.auto_sync:
                        self.auto_sync.trigger_push()
                    logger.debug(f"Clipboard duplicate timestamp refreshed: {expected_hash[:8]}")

        except Exception as e:
            logger.error(f"Error handling clipboard change: {e}")

    def _show_history(self):
        """Show history viewer window"""
        try:
            if not self.history_viewer:
                self.history_viewer = HistoryViewer(
                    self.clipboard_history,
                    self.repository,
                    self.config_manager,
                    github_sync=self.github_sync,
                    encryption_manager=self.encryption_manager,
                    on_github_settings_changed=self._on_github_settings_changed
                )

            self.history_viewer.show()
            self.history_viewer.raise_()
            self.history_viewer.activateWindow()

        except Exception as e:
            logger.error(f"Failed to show history viewer: {e}")

    def _on_github_settings_changed(self, settings):
        """Handle GitHub settings being updated from UI"""
        try:
            from src.core.encryption import KeyManager, EncryptionManager
            from src.services.sync.github_sync import GitHubSyncService

            # Reinitialize encryption manager with updated key
            key_manager = KeyManager()
            encryption_key = key_manager.get_or_create_key()
            self.encryption_manager = EncryptionManager(encryption_key)
            logger.info("Encryption manager reinitialized with updated key")

            # Update GitHub sync service with new settings
            self.github_sync = GitHubSyncService(
                token=settings.get('token'),
                repository=settings.get('repository'),
                enterprise_url=settings.get('enterprise_url'),
                ca_bundle_path=settings.get('ca_bundle_path') or None,
                verify_ssl=settings.get('verify_ssl', True),
            )
            logger.info("GitHub sync service reinitialized")

            # Reinitialize sync coordinator and auto sync
            if self.github_sync.enabled:
                self.sync_coordinator = SyncCoordinator(
                    sync_backend=self.github_sync,
                    encryption=self.encryption_manager,
                    clipboard_history=self.clipboard_history,
                    repository=self.repository,
                    config_getter=self.config_manager.get_all,
                    notifier=self._emit_sync_notification,
                )

                auto_sync_minutes = settings.get('auto_sync_interval_minutes', 1)
                pull_interval = max(auto_sync_minutes * 60, AutoSyncService.DEFAULT_PULL_INTERVAL)

                if self.auto_sync:
                    self.auto_sync.stop()

                self.auto_sync = AutoSyncService(pull_interval_seconds=pull_interval)
                self.auto_sync.set_push_callback(self.sync_coordinator.push_to_remote)
                self.auto_sync.set_pull_callback(self._pull_from_github)
                self.auto_sync.start()
                logger.info("Auto sync service reinitialized")

            # Update all references to new instances
            if self.archive_manager:
                self.archive_manager.github_sync = self.github_sync
            if self.repository:
                self.repository.encryption = self.encryption_manager
            if self.history_viewer:
                self.history_viewer.github_sync = self.github_sync
                self.history_viewer.encryption_manager = self.encryption_manager

        except Exception as e:
            logger.error(f"Failed to reinitialize GitHub sync: {e}")

    def _toggle_monitoring(self):
        """Toggle clipboard monitoring on/off"""
        if self.clipboard_monitor.is_running:
            self.clipboard_monitor.stop()
            logger.info("Clipboard monitoring stopped")
            if self.tray_icon:
                self.tray_icon.update_icon(active=False)
        else:
            self.clipboard_monitor.start()
            logger.info("Clipboard monitoring started")
            if self.tray_icon:
                self.tray_icon.update_icon(active=True)

    def _sync_to_github(self):
        """Manually sync to GitHub"""
        if self.sync_coordinator:
            self.sync_coordinator.manual_sync(self.signal_bridge)
        else:
            logger.warning("GitHub sync not configured")

    def _pull_from_github(self):
        """Pull from GitHub and merge (callback for auto sync, runs in background thread)"""
        if self.sync_coordinator:
            self.sync_coordinator.pull_and_merge()
            # Refresh UI via signal (thread-safe)
            if self.signal_bridge:
                self.signal_bridge.refresh_history_signal.emit()

    def _emit_sync_notification(self, title: str, body: str):
        """Thread-safe bridge between SyncCoordinator and tray notifications."""
        if self.signal_bridge:
            self.signal_bridge.show_notification_signal.emit(title, body)

    def _cleanup_now(self):
        """Run cleanup immediately"""
        def cleanup_task():
            if self.cleanup_service:
                self.cleanup_service.run_now()
                if self.signal_bridge:
                    self.signal_bridge.show_notification_signal.emit(
                        "Cleanup Complete",
                        "History cleaned and optimized"
                    )

        threading.Thread(target=cleanup_task, daemon=True).start()

    def _refresh_history_viewer(self):
        """Refresh history viewer (thread-safe, called via signal)"""
        if self.history_viewer and self.history_viewer.isVisible():
            if hasattr(self.history_viewer, "refresh_entries"):
                self.history_viewer.refresh_entries()
            else:
                self.history_viewer._load_entries()

    def _show_notification(self, title: str, message: str):
        """Show notification"""
        if self.tray_icon:
            self.tray_icon.show_notification(title, message)

    def _quit_application(self):
        """Quit the application"""
        logger.info("Quit requested")
        self.shutdown()

    def _check_and_show_first_run(self):
        """Check if this is first run and show welcome dialog if needed"""
        from src.ui.dialogs.welcome_dialog import check_first_run, WelcomeDialog, mark_first_run_complete

        if check_first_run():
            logger.info("First run detected - showing welcome dialog")

            welcome_dialog = WelcomeDialog()

            def on_setup_completed(settings):
                logger.info("GitHub setup completed via welcome dialog")
                mark_first_run_complete()

            def on_setup_skipped():
                logger.info("User skipped GitHub setup - using local storage only")
                mark_first_run_complete()

            welcome_dialog.setup_completed.connect(on_setup_completed)
            welcome_dialog.setup_skipped.connect(on_setup_skipped)

            welcome_dialog.exec()
            return True
        return False

    def start(self):
        """Start the application"""
        try:
            self.qt_app = QApplication(sys.argv)
            self.qt_app.setQuitOnLastWindowClosed(False)

            # Check for first run before initialization
            self._check_and_show_first_run()

            if not self.initialize():
                logger.error("Failed to initialize application")
                sys.exit(1)

            # Create signal bridge
            self.signal_bridge = QtSignalBridge()

            # Connect signals to slots
            self.signal_bridge.show_history_signal.connect(self._show_history)
            self.signal_bridge.toggle_monitoring_signal.connect(self._toggle_monitoring)
            self.signal_bridge.sync_github_signal.connect(self._sync_to_github)
            self.signal_bridge.cleanup_signal.connect(self._cleanup_now)
            self.signal_bridge.quit_signal.connect(self._quit_application)
            self.signal_bridge.show_notification_signal.connect(self._show_notification)
            self.signal_bridge.refresh_history_signal.connect(self._refresh_history_viewer)

            # Now that the bridge exists, route SyncCoordinator notifications
            # through it (must be a Qt signal emit so the toast happens on the
            # GUI thread).
            if self.sync_coordinator:
                self.sync_coordinator.set_notifier(self._emit_sync_notification)

            # Start services
            self.clipboard_monitor.start()
            self.cleanup_service.start()

            if self.auto_sync:
                self.auto_sync.start()

            # Create system tray
            self.tray_icon = TrayIcon("ClipboardHistory")

            self.tray_icon.add_menu_item(
                "Show History",
                lambda: self.signal_bridge.show_history_signal.emit()
            )
            self.tray_icon.add_separator()
            self.tray_icon.add_menu_item(
                "Toggle Monitoring",
                lambda: self.signal_bridge.toggle_monitoring_signal.emit()
            )
            self.tray_icon.add_menu_item(
                "Sync to GitHub",
                lambda: self.signal_bridge.sync_github_signal.emit()
            )
            self.tray_icon.add_menu_item(
                "Run Cleanup",
                lambda: self.signal_bridge.cleanup_signal.emit()
            )
            self.tray_icon.add_separator()
            self.tray_icon.add_menu_item(
                "Quit",
                lambda: self.signal_bridge.quit_signal.emit()
            )

            self.tray_icon.start()

            if self.config_manager.get('ui.show_notifications'):
                QTimer.singleShot(1000, lambda: self._show_notification(
                    "ClipboardHistory Started",
                    "Monitoring clipboard activity"
                ))

            logger.info("Application started successfully")

            sys.exit(self.qt_app.exec())

        except Exception as e:
            import traceback
            logger.error(f"Failed to start application: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            self.shutdown()

    def shutdown(self):
        """Shutdown the application"""
        logger.info("Shutting down application...")

        try:
            if self.clipboard_monitor:
                self.clipboard_monitor.stop()

            if self.cleanup_service:
                self.cleanup_service.stop()

            if self.auto_sync:
                self.auto_sync.stop()

            if self.tray_icon:
                self.tray_icon.stop()

            if self.database_manager:
                self.database_manager.close()

            if self.config_manager:
                self.config_manager.save()

            if self.qt_app:
                self.qt_app.quit()

            logger.info("Application shutdown complete")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        finally:
            self._shutdown_event.set()


def signal_handler(signum, frame):
    """Handle system signals"""
    logger.info(f"Received signal {signum}")
    if hasattr(signal_handler, 'app'):
        signal_handler.app.shutdown()
    sys.exit(0)


def main():
    """Main entry point"""
    app = ClipboardHistoryApp()

    signal_handler.app = app

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    app.start()


if __name__ == "__main__":
    main()
