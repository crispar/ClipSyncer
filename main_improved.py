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
        self.archive_manager = None
        self.tray_icon = None
        self.history_viewer = None
        self.qt_app = None
        self.signal_bridge = None

        # Threading
        self._shutdown_event = threading.Event()

        # GitHub sync state
        self.is_github_primary = False

        # Setup logging
        self._setup_logging()

        logger.info("=" * 60)
        logger.info("ClipboardHistory Application Starting")
        logger.info("=" * 60)

    def _load_github_settings(self):
        """Load GitHub settings from dedicated file and keyring"""
        try:
            config_path = os.path.join(
                os.environ.get('APPDATA', '.'),
                'ClipboardHistory',
                'github_settings.yaml'
            )

            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    settings = yaml.safe_load(f) or {}
                    github_settings = settings.get('github', {})

                    # Load token from keyring (secure storage)
                    try:
                        from src.core.encryption import KeyManager
                        key_manager = KeyManager()
                        token = key_manager.get_github_token()
                        if token:
                            github_settings['token'] = token
                            logger.debug("Loaded GitHub token from secure keyring")
                    except Exception as e:
                        logger.warning(f"Could not load GitHub token from keyring: {e}")

                    return github_settings
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
            self.auto_sync = None

            if github_settings and github_settings.get('enabled'):
                logger.info("Initializing GitHub sync from github_settings.yaml...")
                token = github_settings.get('token')
                repository = github_settings.get('repository')
                enterprise_url = github_settings.get('enterprise_url')

                if token and repository:
                    # Initialize GitHubSyncService (always primary storage)
                    self.github_sync = GitHubSyncService(token, repository, enterprise_url)
                    logger.info(f"GitHub sync initialized for repository: {repository} (Primary Storage)")

                    # GitHub is always primary storage - local DB is cache-only
                    self.is_github_primary = github_settings.get('is_primary_storage', True)
                    logger.info("GitHub is PRIMARY storage - local DB will be cache-only")
                    # Pull from GitHub immediately to populate local cache
                    logger.info("Performing initial sync from GitHub...")
                    self._initial_github_sync()

                    # Initialize auto sync if configured
                    auto_sync_enabled = github_settings.get('auto_sync_enabled', True)
                    auto_sync_interval = github_settings.get('auto_sync_interval_minutes', 30)

                    if auto_sync_enabled:
                        self.auto_sync = AutoSyncService()
                        # Always use immediate push for primary storage
                        self.auto_sync.set_push_callback(self._immediate_sync_to_github)
                        # Enable pull to retrieve GitHub data periodically
                        self.auto_sync.set_pull_callback(self._pull_from_github)
                        logger.info("Auto sync configured with immediate push and periodic pull")
                else:
                    logger.warning("GitHub sync disabled: missing credentials")
            elif self.config_manager.get('github.enabled'):
                # Fallback to main config
                logger.info("Initializing GitHub sync from main config...")
                token = self.config_manager.get('github.token')
                repository = self.config_manager.get('github.repository')
                enterprise_url = self.config_manager.get('github.enterprise_url')

                if token and repository:
                    self.github_sync = GitHubSyncService(token, repository, enterprise_url)
                    logger.info(f"GitHub sync initialized for repository: {repository}")

                    # Initialize auto sync with default settings
                    auto_sync_enabled = self.config_manager.get('github.auto_sync_enabled', True)
                    auto_sync_interval = self.config_manager.get('github.auto_sync_interval_minutes', 30)

                    if auto_sync_enabled:
                        self.auto_sync = AutoSyncService()
                        self.auto_sync.set_push_callback(self._auto_sync_to_github)
                        # Enable pull to retrieve GitHub data periodically
                        self.auto_sync.set_pull_callback(self._pull_from_github)
                        logger.info(f"Auto sync configured with real-time push and periodic pull")
                else:
                    logger.warning("GitHub sync disabled: missing credentials")
            else:
                logger.info("GitHub sync not configured")

            # Initialize archive manager
            logger.info("Initializing archive manager...")
            self.archive_manager = ArchiveManager(self.github_sync)

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

            # Add archive cleanup task (runs daily)
            if self.archive_manager:
                self.cleanup_service.add_task(
                    self.archive_manager.cleanup_old_archives,
                    "archive_cleanup"
                )

            logger.info("Application initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            return False

    def _on_clipboard_change(self, content: str, timestamp):
        """Handle clipboard change event"""
        try:
            # Add to history
            added, removed_entry = self.clipboard_history.add_entry(content, timestamp)

            # Archive the removed entry if any
            if removed_entry and self.archive_manager:
                try:
                    # Convert entry to dict format for archiving
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

            if added:
                # Save to database
                entries = self.clipboard_history.get_entries(limit=1)
                if entries:
                    self.repository.save_entry(entries[0])

                # Track change for auto sync
                if self.auto_sync:
                    self.auto_sync.trigger_push()

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

    def _auto_sync_to_github(self):
        """Auto sync callback - runs in background thread"""
        if self.github_sync and self.github_sync.enabled:
            try:
                # Export current history
                history_data = {
                    'entries': [e.to_dict() for e in self.clipboard_history.get_entries()],
                    'settings': self.config_manager.get_all()
                }

                # Encrypt before upload
                encrypted = self.encryption_manager.encrypt_json(history_data)

                # Upload to GitHub with auto-generated filename
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"auto_backup_{timestamp}.json"
                success = self.github_sync.upload_backup(encrypted, filename)

                if success:
                    logger.info(f"Auto sync completed: {filename}")
                    if self.signal_bridge:
                        self.signal_bridge.show_notification_signal.emit(
                            "Auto Sync",
                            "Clipboard history backed up to GitHub"
                        )
                else:
                    logger.error("Auto sync failed")

            except Exception as e:
                logger.error(f"Auto sync error: {e}")

    def _initial_github_sync(self):
        """Perform initial sync from GitHub when starting with GitHub as primary storage"""
        if not self.github_sync or not self.github_sync.enabled:
            return

        try:
            # Clear local cache first (GitHub is always primary)
            logger.info("Clearing local cache before initial GitHub sync...")
            self.repository.clear_all()
            self.clipboard_history.clear()

            # Download single sync file
            logger.info("Loading initial data from GitHub...")
            backup_data = self.github_sync.download_backup()
            if not backup_data:
                logger.error("Failed to download initial backup from GitHub")
                return

            decrypted = self.encryption_manager.decrypt_json(backup_data)
            if not decrypted:
                logger.warning("Failed to decrypt GitHub backup - may need sync password")
                return

            # Load all entries from GitHub
            remote_entries = decrypted.get('entries', [])
            loaded_count = 0

            for entry_data in remote_entries:
                try:
                    from src.core.clipboard.history import ClipboardEntry
                    from datetime import datetime
                    entry = ClipboardEntry(
                        content=entry_data['content'],
                        timestamp=datetime.fromisoformat(entry_data['timestamp']),
                        content_hash=entry_data.get('content_hash'),
                        category=entry_data.get('category'),
                        metadata=entry_data.get('metadata', {})
                    )
                    # Save to local cache
                    self.repository.save_entry(entry)
                    # Also add to in-memory history
                    self.clipboard_history.add_entry(entry.content, entry.timestamp)
                    loaded_count += 1
                except Exception as e:
                    logger.error(f"Failed to load entry: {e}")

            logger.info(f"Initial sync complete - loaded {loaded_count} entries from GitHub")

        except Exception as e:
            logger.error(f"Initial GitHub sync failed: {e}")

    def _immediate_sync_to_github(self):
        """Immediate sync to GitHub (no debounce) for primary storage mode"""
        if not self.github_sync or not self.github_sync.enabled:
            return

        try:
            # Export current history
            history_data = {
                'entries': [e.to_dict() for e in self.clipboard_history.get_entries()],
                'settings': self.config_manager.get_all()
            }

            # Encrypt before upload
            encrypted = self.encryption_manager.encrypt_json(history_data)

            # Upload to GitHub (always uses single file)
            success = self.github_sync.upload_backup(encrypted)

            if success:
                logger.info("Immediate sync to GitHub completed")
            else:
                logger.error("Immediate sync to GitHub failed")

        except Exception as e:
            logger.error(f"Immediate sync error: {e}")

    def _pull_from_github(self):
        """Pull latest backup from GitHub and merge with local data (bidirectional sync)"""
        if not self.github_sync or not self.github_sync.enabled:
            return

        try:
            # Download sync file from GitHub
            logger.debug("Pulling clipboard sync from GitHub")
            backup_data = self.github_sync.download_backup()
            if not backup_data:
                logger.debug("No backup found on GitHub or download failed")
                return

            decrypted = self.encryption_manager.decrypt_json(backup_data)
            if not decrypted:
                logger.warning("Failed to decrypt GitHub backup - may need sync password")
                return

            # Get remote entries as dict keyed by content_hash
            remote_entries = decrypted.get('entries', [])
            remote_by_hash = {e.get('content_hash'): e for e in remote_entries if e.get('content_hash')}

            # Get local entries
            local_entries = self.clipboard_history.get_entries()
            local_by_hash = {e.content_hash: e for e in local_entries}

            # Find entries only in local (need to push to remote)
            local_only_hashes = set(local_by_hash.keys()) - set(remote_by_hash.keys())
            # Find entries only in remote (need to add to local)
            remote_only_hashes = set(remote_by_hash.keys()) - set(local_by_hash.keys())

            # Merge: Add remote-only entries to local
            from src.core.clipboard.history import ClipboardEntry
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
                    # Add to local (import_entry avoids duplicates)
                    if self.clipboard_history.import_entry(entry):
                        self.repository.save_entry(entry)
                        added_to_local += 1
                except Exception as e:
                    logger.error(f"Failed to import remote entry {content_hash[:8]}: {e}")

            if added_to_local > 0:
                logger.info(f"Added {added_to_local} entries from GitHub to local")

            # If there are local-only entries, push merged data back to GitHub
            if local_only_hashes:
                logger.info(f"Found {len(local_only_hashes)} local entries not on GitHub, syncing...")
                self._push_merged_to_github()

            # Refresh UI if viewer is open
            if self.history_viewer:
                self.history_viewer.load_history()

        except Exception as e:
            logger.error(f"Pull from GitHub failed: {e}")

    def _push_merged_to_github(self):
        """Push current local state to GitHub (used after merge)"""
        if not self.github_sync or not self.github_sync.enabled:
            return

        try:
            # Export current history (which now includes merged remote entries)
            history_data = {
                'entries': [e.to_dict() for e in self.clipboard_history.get_entries()],
                'settings': self.config_manager.get_all()
            }

            # Encrypt before upload
            encrypted = self.encryption_manager.encrypt_json(history_data)

            # Upload to GitHub
            success = self.github_sync.upload_backup(encrypted)

            if success:
                logger.info("Pushed merged data to GitHub")
            else:
                logger.error("Failed to push merged data to GitHub")

        except Exception as e:
            logger.error(f"Push merged data failed: {e}")

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

    def _check_and_show_first_run(self):
        """Check if this is first run and show welcome dialog if needed"""
        from src.ui.dialogs.welcome_dialog import check_first_run, WelcomeDialog, mark_first_run_complete

        if check_first_run():
            logger.info("First run detected - showing welcome dialog")

            # Show welcome dialog
            welcome_dialog = WelcomeDialog()

            def on_setup_completed(settings):
                """Handle setup completion - settings are already saved by the dialog"""
                logger.info("GitHub setup completed via welcome dialog")
                # Settings (github_settings.yaml, sync password in keyring) are already saved
                # by GitHubSettingsDialog. The initialize() method will read these settings
                # and set up encryption with the correct key derived from sync password.
                mark_first_run_complete()

            def on_setup_skipped():
                """Handle setup skip"""
                logger.info("User skipped GitHub setup - using local storage only")
                mark_first_run_complete()

            welcome_dialog.setup_completed.connect(on_setup_completed)
            welcome_dialog.setup_skipped.connect(on_setup_skipped)

            # Show dialog (blocking)
            welcome_dialog.exec()

            return True
        return False

    def start(self):
        """Start the application"""
        try:
            # Create Qt application
            self.qt_app = QApplication(sys.argv)
            self.qt_app.setQuitOnLastWindowClosed(False)

            # Check for first run and show welcome dialog BEFORE initialization
            # This ensures sync password is set before encryption key is created
            self._check_and_show_first_run()

            # Now initialize application with proper settings
            if not self.initialize():
                logger.error("Failed to initialize application")
                sys.exit(1)

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

            # Start auto sync if configured
            if self.auto_sync:
                self.auto_sync.start()

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

            # Stop auto sync
            if hasattr(self, 'auto_sync') and self.auto_sync:
                self.auto_sync.stop()

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

    # Start application (initialization happens inside start() after first-run check)
    app.start()


if __name__ == "__main__":
    main()