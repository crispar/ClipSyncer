"""Automatic GitHub sync service with real-time push and periodic pull"""

import threading
from typing import Optional, Callable
from datetime import datetime
from loguru import logger


class AutoSyncService:
    """Service for automatic GitHub synchronization with real-time push and periodic pull"""

    # Constants for sync timing
    DEBOUNCE_SECONDS = 5        # Wait 5 seconds after last change before syncing
    MIN_PUSH_INTERVAL = 30      # Minimum 30 seconds between push syncs
    DEFAULT_PULL_INTERVAL = 60  # Check for remote changes every 60 seconds

    def __init__(self, pull_interval_seconds: int = DEFAULT_PULL_INTERVAL):
        """
        Initialize auto sync service

        Args:
            pull_interval_seconds: Seconds between pull checks (default 60)
        """
        self.pull_interval = pull_interval_seconds
        self.enabled = False

        # Callbacks
        self._push_callback: Optional[Callable] = None
        self._pull_callback: Optional[Callable] = None

        # Timers
        self._debounce_timer: Optional[threading.Timer] = None
        self._pull_timer: Optional[threading.Timer] = None

        # State tracking
        self._last_push = datetime.min  # Allow immediate first push
        self._last_pull = datetime.min
        self._pending_changes = 0
        self._lock = threading.RLock()

    def set_push_callback(self, callback: Callable):
        """Set the callback function for pushing (upload to GitHub)"""
        self._push_callback = callback

    def set_pull_callback(self, callback: Callable):
        """Set the callback function for pulling (download from GitHub)"""
        self._pull_callback = callback

    # Legacy support
    def set_sync_callback(self, callback: Callable):
        """Legacy: Set the callback function for syncing (same as push)"""
        self.set_push_callback(callback)

    def trigger_push(self):
        """
        Trigger a push sync with debouncing.
        Called when clipboard content changes.
        Waits DEBOUNCE_SECONDS after last change, respects MIN_PUSH_INTERVAL.
        """
        with self._lock:
            self._pending_changes += 1
            logger.debug(f"Push triggered, pending changes: {self._pending_changes}")

            if not self.enabled:
                return

            # Cancel existing debounce timer
            if self._debounce_timer:
                self._debounce_timer.cancel()

            # Schedule new debounce timer
            self._debounce_timer = threading.Timer(
                self.DEBOUNCE_SECONDS,
                self._execute_push
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    # Legacy support
    def increment_changes(self):
        """Legacy: Track that a change occurred (now triggers immediate push with debounce)"""
        self.trigger_push()

    def _execute_push(self):
        """Execute push sync if conditions are met"""
        with self._lock:
            if not self.enabled or not self._push_callback:
                return

            if self._pending_changes == 0:
                logger.debug("Skipping push - no pending changes")
                return

            # Check minimum interval
            time_since_last = (datetime.now() - self._last_push).total_seconds()
            if time_since_last < self.MIN_PUSH_INTERVAL:
                # Schedule retry after remaining time
                remaining = self.MIN_PUSH_INTERVAL - time_since_last
                logger.debug(f"Push delayed, retrying in {remaining:.1f}s")

                self._debounce_timer = threading.Timer(remaining, self._execute_push)
                self._debounce_timer.daemon = True
                self._debounce_timer.start()
                return

            # Execute push
            try:
                logger.info(f"Executing push sync ({self._pending_changes} changes)")
                self._push_callback()
                self._last_push = datetime.now()
                self._pending_changes = 0
                logger.info("Push sync completed")
            except Exception as e:
                logger.error(f"Push sync failed: {e}")

    def _execute_pull(self):
        """Execute pull sync and schedule next one"""
        if not self.enabled:
            return

        try:
            if self._pull_callback:
                logger.debug("Executing pull sync")
                self._pull_callback()
                self._last_pull = datetime.now()
        except Exception as e:
            logger.error(f"Pull sync failed: {e}")
        finally:
            # Schedule next pull
            self._schedule_next_pull()

    def _schedule_next_pull(self):
        """Schedule the next pull check"""
        if not self.enabled:
            return

        if self._pull_timer:
            self._pull_timer.cancel()

        self._pull_timer = threading.Timer(self.pull_interval, self._execute_pull)
        self._pull_timer.daemon = True
        self._pull_timer.start()

    def start(self):
        """Start automatic sync service"""
        if not self._push_callback:
            logger.warning("No push callback set")

        self.enabled = True

        # Start periodic pull if callback is set
        if self._pull_callback:
            # Execute initial pull after a short delay
            self._pull_timer = threading.Timer(5.0, self._execute_pull)
            self._pull_timer.daemon = True
            self._pull_timer.start()
            logger.info(f"Auto sync started (push: on-change with {self.DEBOUNCE_SECONDS}s debounce, pull: every {self.pull_interval}s)")
        else:
            logger.info(f"Auto sync started (push: on-change with {self.DEBOUNCE_SECONDS}s debounce, pull: disabled)")

    def stop(self):
        """Stop automatic sync service"""
        self.enabled = False

        with self._lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
                self._debounce_timer = None

            if self._pull_timer:
                self._pull_timer.cancel()
                self._pull_timer = None

        logger.info("Auto sync stopped")

    def force_push(self):
        """Force an immediate push sync, bypassing debounce and interval"""
        with self._lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
                self._debounce_timer = None

            if not self._push_callback:
                logger.warning("No push callback set")
                return

            try:
                logger.info("Executing forced push sync")
                self._push_callback()
                self._last_push = datetime.now()
                self._pending_changes = 0
            except Exception as e:
                logger.error(f"Forced push sync failed: {e}")

    def force_pull(self):
        """Force an immediate pull sync"""
        if not self._pull_callback:
            logger.warning("No pull callback set")
            return

        try:
            logger.info("Executing forced pull sync")
            self._pull_callback()
            self._last_pull = datetime.now()
        except Exception as e:
            logger.error(f"Forced pull sync failed: {e}")

    @property
    def pull_interval_seconds(self) -> int:
        """Get pull interval in seconds"""
        return self.pull_interval

    @pull_interval_seconds.setter
    def pull_interval_seconds(self, value: int):
        """Set pull interval in seconds"""
        self.pull_interval = value
        if self.enabled and self._pull_callback:
            # Restart pull timer with new interval
            if self._pull_timer:
                self._pull_timer.cancel()
            self._schedule_next_pull()

    # Legacy property support
    @property
    def sync_interval_minutes(self) -> int:
        """Legacy: Get sync interval in minutes"""
        return self.pull_interval // 60

    @sync_interval_minutes.setter
    def sync_interval_minutes(self, value: int):
        """Legacy: Set sync interval in minutes"""
        self.pull_interval = value * 60

    @property
    def pending_changes(self) -> int:
        """Get number of pending changes"""
        return self._pending_changes

    @property
    def last_push_time(self) -> datetime:
        """Get last push time"""
        return self._last_push

    @property
    def last_pull_time(self) -> datetime:
        """Get last pull time"""
        return self._last_pull
