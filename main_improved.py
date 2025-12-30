"""Improved main application with better Qt thread handling"""

import sys
import os
import signal
import threading
import yaml
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, pyqtSignal, QObject
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.core.clipboard import ClipboardMonitor, ClipboardHistory
from src.core.encryption import EncryptionManager, KeyManager
from src.core.storage import DatabaseManager, ClipboardRepository
from src.services import GitHubSyncService, CleanupService
from src.services.cleanup.cleanup_service import (
    DuplicateRemover, OldDataCleaner, DatabaseOptimizer
)
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


class ClipboardHistoryApp:
    """Main application class with improved Qt handling"""

    def __init__(self):
        """Initialize application"""
        self.config_manager = None
        self.clipboard_monitor = None
        self.clipboard_history = None
        self.encryption_manager = None
        self.database_manager = None
        self.repository = None
        self.github_sync = None
        self.cleanup_service = None
        self.tray_icon = None
        self.history_viewer = None
        self.qt_app = None
        self.signal_bridge = None

        # Threading
        self._shutdown_event = threading.Event()

        # Setup logging
        self._setup_logging()

        logger.info("=" * 60)
        logger.info("ClipboardHistory Application Starting")
        logger.info("=" * 60)

    def _load_github_settings(self):
        """Load GitHub settings from dedicated file"""
        try:
            config_path = os.path.join(
                os.environ.get('APPDATA', '.'),
                'ClipboardHistory',
                'github_settings.yaml'
            )

            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    settings = yaml.safe_load(f) or {}
                    return settings.get('github', {})
        except Exception as e:
            logger.error(f"Failed to load GitHub settings: {e}")

        return {}

    def _setup_logging(self):
        """Configure logging"""
        # Determine log directory based on execution context
        if getattr(sys, 'frozen', False):
            # Running as compiled executable - use exe directory
            exe_dir = Path(sys.executable).parent
            log_dir = exe_dir / 'logs'
        else:
            # Running as script - use AppData directory
            log_dir = Path(os.environ.get('APPDATA', '.')) / 'ClipboardHistory' / 'logs'

        log_dir.mkdir(parents=True, exist_ok=True)

        # Configure loguru
        logger.remove()  # Remove default handler

        # Console logging - check if stderr is available (not None in exe)
        if sys.stderr is not None:
            logger.add(
                sys.stderr,
                level="INFO",
                format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
            )

        # File logging - always enabled
        log_file = log_dir / "ClipSyncer_{time:YYYY-MM-DD}.log"
        logger.add(
            log_file,
            rotation="1 day",
            retention="7 days",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            encoding="utf-8"
        )

        # Also create a latest.log that always contains the most recent session
        latest_log = log_dir / "ClipSyncer_latest.log"
        logger.add(
            latest_log,
            rotation="10 MB",  # Rotate when file reaches 10MB
            retention=1,  # Keep only 1 backup file (integer, not string)
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            encoding="utf-8",
            mode="w"  # Overwrite on each start
        )

        logger.info(f"=== ClipSyncer Started ===")
        logger.info(f"Executable: {sys.executable}")
        logger.info(f"Log directory: {log_dir}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")

    def initialize(self):
        """Initialize all components"""
        try:
            # Load configuration
            logger.info("Loading configuration...")
            self.config_manager = ConfigManager()

            if not self.config_manager.validate():
                logger.error("Invalid configuration")
                return False

            # Initialize encryption
            logger.info("Initializing encryption...")
            key_manager = KeyManager()
            encryption_key = key_manager.get_or_create_key()
            self.encryption_manager = EncryptionManager(encryption_key)

            # Initialize database
            logger.info("Initializing database...")
            db_path = self.config_manager.get('storage.database_path')
            self.database_manager = DatabaseManager(db_path)

            # Initialize repository with database manager
            self.repository = ClipboardRepository(self.database_manager, self.encryption_manager)

            # Initialize clipboard components
            logger.info("Initializing clipboard monitoring...")
            check_interval = self.config_manager.get('clipboard.check_interval', 500)
            max_history = self.config_manager.get('clipboard.max_history_size', 1000)

            self.clipboard_monitor = ClipboardMonitor(check_interval)
            self.clipboard_history = ClipboardHistory(max_history)

            # Setup clipboard callback
            self.clipboard_monitor.add_callback(self._on_clipboard_change)

            # Initialize GitHub sync (if enabled)
            # Try to load GitHub settings from dedicated file first
            github_settings = self._load_github_settings()

            if github_settings and github_settings.get('enabled'):
                logger.info("Initializing GitHub sync from github_settings.yaml...")
                token = github_settings.get('token')
                repository = github_settings.get('repository')

                if token and repository:
                    self.github_sync = GitHubSyncService(token, repository)
                    logger.info(f"GitHub sync initialized for repository: {repository}")
                else:
                    logger.warning("GitHub sync disabled: missing credentials")
            elif self.config_manager.get('github.enabled'):
                # Fallback to main config
                logger.info("Initializing GitHub sync from main config...")
                token = self.config_manager.get('github.token')
                repository = self.config_manager.get('github.repository')

                if token and repository:
                    self.github_sync = GitHubSyncService(token, repository)
                    logger.info(f"GitHub sync initialized for repository: {repository}")
                else:
                    logger.warning("GitHub sync disabled: missing credentials")
            else:
                logger.info("GitHub sync not configured")

            # Initialize cleanup service
            logger.info("Initializing cleanup service...")
            cleanup_interval = self.config_manager.get('cleanup.cleanup_interval', 3600)
            self.cleanup_service = CleanupService(cleanup_interval)

            # Add cleanup tasks
            if self.config_manager.get('cleanup.duplicate_removal'):
                remover = DuplicateRemover(self.clipboard_history, self.repository)
                self.cleanup_service.add_task(remover.remove_duplicates, "duplicate_removal")

            retention_days = self.config_manager.get('storage.retention_days', 30)
            cleaner = OldDataCleaner(self.repository, retention_days)
            self.cleanup_service.add_task(cleaner.cleanup, "old_data_cleanup")

            optimizer = DatabaseOptimizer(self.database_manager)
            self.cleanup_service.add_task(optimizer.optimize, "database_optimization")

            logger.info("Application initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            return False

    def _on_clipboard_change(self, content: str, timestamp):
        """Handle clipboard change event"""
        try:
            # Add to history
            added = self.clipboard_history.add_entry(content, timestamp)

            if added:
                # Save to database
                entries = self.clipboard_history.get_entries(limit=1)
                if entries:
                    self.repository.save_entry(entries[0])

                # Show notification if enabled
                if self.config_manager.get('ui.show_notifications') and self.signal_bridge:
                    self.signal_bridge.show_notification_signal.emit(
                        "Clipboard Captured",
                        f"Saved {len(content)} characters"
                    )

                logger.debug(f"Clipboard content saved: {len(content)} characters")

        except Exception as e:
            logger.error(f"Error handling clipboard change: {e}")

    def _show_history(self):
        """Show history viewer window (runs in main thread)"""
        try:
            if not self.history_viewer:
                self.history_viewer = HistoryViewer(
                    self.clipboard_history,
                    self.repository
                )

            self.history_viewer.show()
            self.history_viewer.raise_()
            self.history_viewer.activateWindow()

        except Exception as e:
            logger.error(f"Failed to show history viewer: {e}")

    def _toggle_monitoring(self):
        """Toggle clipboard monitoring on/off (runs in main thread)"""
        if self.clipboard_monitor.is_running:
            self.clipboard_monitor.stop()
            logger.info("Clipboard monitoring stopped")
            if self.tray_icon:
                self.tray_icon.update_icon(active=False)  # Update icon to inactive state
                # tooltip update is now handled in update_icon
        else:
            self.clipboard_monitor.start()
            logger.info("Clipboard monitoring started")
            if self.tray_icon:
                self.tray_icon.update_icon(active=True)  # Update icon to active state
                # tooltip update is now handled in update_icon

    def _sync_to_github(self):
        """Manually sync to GitHub (runs in main thread)"""
        # Run in separate thread to avoid blocking UI
        def sync_task():
            if self.github_sync and self.github_sync.enabled:
                try:
                    # Export current history
                    history_data = {
                        'entries': [e.to_dict() for e in self.clipboard_history.get_entries()],
                        'settings': self.config_manager.get_all()
                    }

                    # Encrypt before upload
                    encrypted = self.encryption_manager.encrypt_json(history_data)

                    # Upload to GitHub
                    success = self.github_sync.upload_backup(encrypted)

                    if success:
                        logger.info("Successfully synced to GitHub")
                        if self.signal_bridge:
                            self.signal_bridge.show_notification_signal.emit(
                                "GitHub Sync",
                                "Backup uploaded successfully"
                            )
                    else:
                        logger.error("GitHub sync failed")

                except Exception as e:
                    logger.error(f"GitHub sync error: {e}")
            else:
                logger.warning("GitHub sync not configured")

        threading.Thread(target=sync_task, daemon=True).start()

    def _cleanup_now(self):
        """Run cleanup immediately (runs in main thread)"""
        # Run in separate thread to avoid blocking UI
        def cleanup_task():
            if self.cleanup_service:
                self.cleanup_service.run_now()
                if self.signal_bridge:
                    self.signal_bridge.show_notification_signal.emit(
                        "Cleanup Complete",
                        "History cleaned and optimized"
                    )

        threading.Thread(target=cleanup_task, daemon=True).start()

    def _show_notification(self, title: str, message: str):
        """Show notification (runs in main thread)"""
        if self.tray_icon:
            self.tray_icon.show_notification(title, message)

    def _quit_application(self):
        """Quit the application (runs in main thread)"""
        logger.info("Quit requested")
        self.shutdown()

    def start(self):
        """Start the application"""
        try:
            # Create Qt application
            self.qt_app = QApplication(sys.argv)
            self.qt_app.setQuitOnLastWindowClosed(False)

            # Create signal bridge
            self.signal_bridge = QtSignalBridge()

            # Connect signals to slots (these will run in main thread)
            self.signal_bridge.show_history_signal.connect(self._show_history)
            self.signal_bridge.toggle_monitoring_signal.connect(self._toggle_monitoring)
            self.signal_bridge.sync_github_signal.connect(self._sync_to_github)
            self.signal_bridge.cleanup_signal.connect(self._cleanup_now)
            self.signal_bridge.quit_signal.connect(self._quit_application)
            self.signal_bridge.show_notification_signal.connect(self._show_notification)

            # Start services
            self.clipboard_monitor.start()
            self.cleanup_service.start()

            # Create system tray with improved callbacks
            self.tray_icon = TrayIcon("ClipboardHistory")

            # Add menu items with signal emission
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

            # Start tray icon
            self.tray_icon.start()

            # Show notification
            if self.config_manager.get('ui.show_notifications'):
                QTimer.singleShot(1000, lambda: self._show_notification(
                    "ClipboardHistory Started",
                    "Monitoring clipboard activity"
                ))

            logger.info("Application started successfully")

            # Start Qt event loop
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
            # Stop monitoring
            if self.clipboard_monitor:
                self.clipboard_monitor.stop()

            # Stop cleanup service
            if self.cleanup_service:
                self.cleanup_service.stop()

            # Stop tray icon
            if self.tray_icon:
                self.tray_icon.stop()

            # Close database
            if self.database_manager:
                self.database_manager.close()

            # Save configuration
            if self.config_manager:
                self.config_manager.save()

            # Quit Qt application
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
    # Create application
    app = ClipboardHistoryApp()

    # Store app reference for signal handler
    signal_handler.app = app

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize application
    if not app.initialize():
        logger.error("Failed to initialize application")
        sys.exit(1)

    # Start application
    app.start()


if __name__ == "__main__":
    main()