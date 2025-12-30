"""Automatic GitHub sync service"""

import threading
from typing import Optional, Callable
from datetime import datetime, timedelta
from loguru import logger


class AutoSyncService:
    """Service for automatic periodic GitHub synchronization"""

    def __init__(self, sync_interval_minutes: int = 30):
        """
        Initialize auto sync service

        Args:
            sync_interval_minutes: Minutes between auto syncs (default 30)
        """
        self.sync_interval = sync_interval_minutes * 60  # Convert to seconds
        self.enabled = False
        self._timer: Optional[threading.Timer] = None
        self._sync_callback: Optional[Callable] = None
        self._last_sync = datetime.now()
        self._pending_changes = 0

    def set_sync_callback(self, callback: Callable):
        """Set the callback function for syncing"""
        self._sync_callback = callback

    def increment_changes(self):
        """Track that a change occurred"""
        self._pending_changes += 1
        logger.debug(f"Pending changes: {self._pending_changes}")

        # If we have accumulated enough changes, trigger sync early
        if self._pending_changes >= 10 and self.enabled:
            time_since_last = (datetime.now() - self._last_sync).total_seconds()
            # Only sync if at least 5 minutes have passed
            if time_since_last >= 300:
                logger.info("Triggering early sync due to 10+ pending changes")
                self._run_sync()

    def start(self):
        """Start automatic sync service"""
        if not self._sync_callback:
            logger.warning("No sync callback set, auto sync disabled")
            return

        self.enabled = True
        self._schedule_next_sync()
        logger.info(f"Auto sync started (interval: {self.sync_interval_minutes} minutes)")

    def stop(self):
        """Stop automatic sync service"""
        self.enabled = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        logger.info("Auto sync stopped")

    def _schedule_next_sync(self):
        """Schedule the next sync"""
        if not self.enabled:
            return

        if self._timer:
            self._timer.cancel()

        self._timer = threading.Timer(self.sync_interval, self._run_sync)
        self._timer.daemon = True
        self._timer.start()

    def _run_sync(self):
        """Run the sync operation"""
        if not self.enabled or not self._sync_callback:
            return

        try:
            if self._pending_changes > 0:
                logger.info(f"Running auto sync ({self._pending_changes} pending changes)")
                self._sync_callback()
                self._last_sync = datetime.now()
                self._pending_changes = 0
            else:
                logger.debug("Skipping auto sync - no pending changes")

        except Exception as e:
            logger.error(f"Auto sync failed: {e}")
        finally:
            # Schedule next sync
            self._schedule_next_sync()

    @property
    def sync_interval_minutes(self) -> int:
        """Get sync interval in minutes"""
        return self.sync_interval // 60

    @sync_interval_minutes.setter
    def sync_interval_minutes(self, value: int):
        """Set sync interval in minutes"""
        self.sync_interval = value * 60
        if self.enabled:
            # Restart with new interval
            self.stop()
            self.start()