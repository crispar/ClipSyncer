"""Custom exception hierarchy for ClipSyncer application"""


class ClipSyncerError(Exception):
    """Base exception for all ClipSyncer errors"""
    pass


class EncryptionError(ClipSyncerError):
    """Raised when encryption operations fail"""
    pass


class DecryptionError(ClipSyncerError):
    """Raised when decryption operations fail (wrong key, corrupted data, etc.)"""
    pass


class SyncError(ClipSyncerError):
    """Raised when sync operations fail"""
    pass


class SyncConnectionError(SyncError):
    """Raised when sync backend connection fails"""
    pass


class SyncAuthenticationError(SyncError):
    """Raised when sync authentication fails (bad token, expired, etc.)"""
    pass


class StorageError(ClipSyncerError):
    """Raised when storage operations fail"""
    pass


class ConfigurationError(ClipSyncerError):
    """Raised when configuration is invalid or missing"""
    pass
