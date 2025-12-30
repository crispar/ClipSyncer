"""Cleanup service for duplicate removal and maintenance"""

import threading
from typing import Optional, Callable
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger


class CleanupService:
    """Handles periodic cleanup and maintenance tasks"""

    def __init__(self, interval_seconds: int = 3600):
        """
        Initialize cleanup service

        Args:
            interval_seconds: Cleanup interval in seconds (default 1 hour)
        """
        self.interval = interval_seconds
        self.scheduler = BackgroundScheduler()
        self._callbacks = []
        self._running = False
        self._lock = threading.RLock()

        logger.info(f"CleanupService initialized with {interval_seconds}s interval")

    def add_task(self, task: Callable, name: str = None) -> None:
        """
        Add cleanup task

        Args:
            task: Cleanup function to run
            name: Optional task name
        """
        with self._lock:
            self._callbacks.append((task, name or task.__name__))
            logger.debug(f"Added cleanup task: {name or task.__name__}")

    def start(self) -> None:
        """Start cleanup service"""
        with self._lock:
            if self._running:
                logger.warning("Cleanup service already running")
                return

            # Schedule cleanup job
            self.scheduler.add_job(
                func=self._run_cleanup,
                trigger=IntervalTrigger(seconds=self.interval),
                id='cleanup_job',
                replace_existing=True
            )

            # Start scheduler
            self.scheduler.start()
            self._running = True

            logger.info("Cleanup service started")

            # Run initial cleanup
            self._run_cleanup()

    def stop(self) -> None:
        """Stop cleanup service"""
        with self._lock:
            if not self._running:
                logger.warning("Cleanup service not running")
                return

            self.scheduler.shutdown(wait=True)
            self._running = False

            logger.info("Cleanup service stopped")

    def _run_cleanup(self) -> None:
        """Execute all cleanup tasks"""
        logger.info("Starting cleanup cycle")
        start_time = datetime.now()

        with self._lock:
            tasks = self._callbacks.copy()

        for task, name in tasks:
            try:
                logger.debug(f"Running cleanup task: {name}")
                task()
            except Exception as e:
                logger.error(f"Cleanup task '{name}' failed: {e}")

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Cleanup cycle completed in {elapsed:.2f}s")

    def run_now(self) -> None:
        """Run cleanup immediately"""
        if self._running:
            self._run_cleanup()
        else:
            logger.warning("Cleanup service not running")

    @property
    def is_running(self) -> bool:
        """Check if service is running"""
        return self._running

    def get_next_run(self) -> Optional[datetime]:
        """
        Get next scheduled cleanup time

        Returns:
            Next run datetime or None
        """
        if not self._running:
            return None

        job = self.scheduler.get_job('cleanup_job')
        if job:
            return job.next_run_time

        return None


class DuplicateRemover:
    """Removes duplicate entries from clipboard history"""

    def __init__(self, history_manager, repository):
        """
        Initialize duplicate remover

        Args:
            history_manager: ClipboardHistory instance
            repository: ClipboardRepository instance
        """
        self.history = history_manager
        self.repository = repository

    def remove_duplicates(self) -> int:
        """
        Remove duplicate entries

        Returns:
            Number of duplicates removed
        """
        try:
            # Remove from in-memory history
            memory_removed = self.history.remove_duplicates()

            # Remove from database
            # This would need to be implemented in repository
            # For now, we'll just return memory count

            logger.info(f"Removed {memory_removed} duplicate entries")
            return memory_removed

        except Exception as e:
            logger.error(f"Failed to remove duplicates: {e}")
            return 0


class OldDataCleaner:
    """Cleans up old data based on retention policy"""

    def __init__(self, repository, retention_days: int = 30):
        """
        Initialize old data cleaner

        Args:
            repository: ClipboardRepository instance
            retention_days: Days to retain data
        """
        self.repository = repository
        self.retention_days = retention_days

    def cleanup(self) -> int:
        """
        Clean up old data

        Returns:
            Number of entries cleaned up
        """
        try:
            removed = self.repository.cleanup_old_entries(self.retention_days)

            if removed > 0:
                logger.info(f"Cleaned up {removed} entries older than {self.retention_days} days")

            return removed

        except Exception as e:
            logger.error(f"Failed to clean up old data: {e}")
            return 0


class DatabaseOptimizer:
    """Optimizes database performance"""

    def __init__(self, database_manager):
        """
        Initialize database optimizer

        Args:
            database_manager: DatabaseManager instance
        """
        self.db_manager = database_manager

    def optimize(self) -> bool:
        """
        Optimize database

        Returns:
            True if successful
        """
        try:
            # Run VACUUM to optimize SQLite database
            self.db_manager.vacuum()

            # Get database size
            size_mb = self.db_manager.get_size() / (1024 * 1024)
            logger.info(f"Database optimized, current size: {size_mb:.2f} MB")

            return True

        except Exception as e:
            logger.error(f"Database optimization failed: {e}")
            return False