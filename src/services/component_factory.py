"""Component factory for creating and wiring application components (SRP extraction)"""

import os
import yaml
from typing import Optional
from loguru import logger

from src.core.clipboard import ClipboardMonitor, ClipboardHistory
from src.core.encryption import EncryptionManager, KeyManager
from src.core.storage import DatabaseManager, ClipboardRepository
from src.core.exceptions import ConfigurationError
from src.services import GitHubSyncService, CleanupService
from src.services.cleanup.cleanup_service import (
    DuplicateRemover, OldDataCleaner, DatabaseOptimizer
)
from src.services.auto_sync_service import AutoSyncService
from src.services.archive_manager import ArchiveManager
from src.utils import ConfigManager


class ComponentFactory:
    """Creates and wires all application components.

    Extracted from ClipboardHistoryApp to follow Single Responsibility Principle.
    This class handles only component initialization and dependency injection.
    """

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def create_encryption(self) -> tuple[KeyManager, EncryptionManager]:
        """Create encryption components"""
        logger.info("Initializing encryption...")
        key_manager = KeyManager()
        encryption_key = key_manager.get_or_create_key()
        encryption_manager = EncryptionManager(encryption_key)
        return key_manager, encryption_manager

    def create_storage(self, encryption_manager: EncryptionManager) -> tuple[DatabaseManager, ClipboardRepository]:
        """Create storage components"""
        logger.info("Initializing database...")
        db_path = self.config.get('storage.database_path')
        database_manager = DatabaseManager(db_path)
        repository = ClipboardRepository(database_manager, encryption_manager)
        return database_manager, repository

    def create_clipboard(self) -> tuple[ClipboardMonitor, ClipboardHistory]:
        """Create clipboard monitoring components"""
        logger.info("Initializing clipboard monitoring...")
        check_interval = self.config.get('clipboard.check_interval', 500)
        max_history = self.config.get('clipboard.max_history_size', 500)
        monitor = ClipboardMonitor(check_interval)
        history = ClipboardHistory(max_history)
        return monitor, history

    def create_github_sync(self, github_settings: dict) -> Optional[GitHubSyncService]:
        """Create GitHub sync service from settings"""
        token = github_settings.get('token')
        repository = github_settings.get('repository')
        enterprise_url = github_settings.get('enterprise_url')

        if not token or not repository:
            logger.warning("GitHub sync disabled: missing credentials")
            return None

        sync_service = GitHubSyncService(token, repository, enterprise_url)
        logger.info(f"GitHub sync initialized for repository: {repository}")
        return sync_service

    def create_auto_sync(self, github_settings: dict) -> Optional[AutoSyncService]:
        """Create auto sync service based on settings"""
        auto_sync_enabled = github_settings.get('auto_sync_enabled', True)
        if not auto_sync_enabled:
            return None

        auto_sync_interval = github_settings.get('auto_sync_interval_minutes', 30)
        pull_interval_sec = max(auto_sync_interval * 60, AutoSyncService.DEFAULT_PULL_INTERVAL)
        auto_sync = AutoSyncService(pull_interval_seconds=pull_interval_sec)
        logger.info(f"Auto sync service created (pull interval: {pull_interval_sec}s)")
        return auto_sync

    def create_cleanup(self, clipboard_history: ClipboardHistory,
                       repository: ClipboardRepository,
                       database_manager: DatabaseManager,
                       archive_manager: Optional[ArchiveManager] = None) -> CleanupService:
        """Create and configure cleanup service"""
        logger.info("Initializing cleanup service...")
        cleanup_interval = self.config.get('cleanup.cleanup_interval', 3600)
        cleanup_service = CleanupService(cleanup_interval)

        if self.config.get('cleanup.duplicate_removal'):
            remover = DuplicateRemover(clipboard_history, repository)
            cleanup_service.add_task(remover.remove_duplicates, "duplicate_removal")

        retention_days = self.config.get('storage.retention_days', 30)
        cleaner = OldDataCleaner(repository, retention_days)
        cleanup_service.add_task(cleaner.cleanup, "old_data_cleanup")

        optimizer = DatabaseOptimizer(database_manager)
        cleanup_service.add_task(optimizer.optimize, "database_optimization")

        if archive_manager:
            cleanup_service.add_task(
                archive_manager.cleanup_old_archives, "archive_cleanup"
            )

        return cleanup_service

    @staticmethod
    def load_github_settings() -> dict:
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
