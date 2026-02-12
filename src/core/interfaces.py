"""Abstract interfaces for Dependency Inversion Principle (DIP)"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class EncryptionStrategy(ABC):
    """Abstract interface for encryption operations"""

    @abstractmethod
    def encrypt(self, data: str) -> Dict[str, str]:
        """
        Encrypt string data.

        Args:
            data: String to encrypt

        Returns:
            Dictionary with encrypted data components

        Raises:
            EncryptionError: If encryption fails
        """
        ...

    @abstractmethod
    def decrypt(self, encrypted_data: Dict[str, str]) -> str:
        """
        Decrypt encrypted data.

        Args:
            encrypted_data: Dictionary with encrypted data components

        Returns:
            Decrypted string

        Raises:
            DecryptionError: If decryption fails
        """
        ...

    @abstractmethod
    def encrypt_json(self, obj: Any) -> Dict[str, str]:
        """Encrypt a JSON-serializable object"""
        ...

    @abstractmethod
    def decrypt_json(self, encrypted_data: Dict[str, str]) -> Any:
        """Decrypt and parse JSON data"""
        ...


class SyncBackend(ABC):
    """Abstract interface for sync backends (GitHub, future: S3, local, etc.)"""

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to the sync backend.

        Returns:
            True if connection successful

        Raises:
            SyncConnectionError: If connection fails
        """
        ...

    @abstractmethod
    def upload_backup(self, data: Dict[str, Any], filename: Optional[str] = None) -> bool:
        """
        Upload backup data.

        Args:
            data: Data to upload
            filename: Optional filename

        Returns:
            True if successful

        Raises:
            SyncError: If upload fails
        """
        ...

    @abstractmethod
    def download_backup(self, filename: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Download backup data.

        Args:
            filename: Optional filename

        Returns:
            Backup data or None

        Raises:
            SyncError: If download fails
        """
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the backend connection is working.

        Returns:
            True if connection is healthy
        """
        ...

    @property
    @abstractmethod
    def is_enabled(self) -> bool:
        """Whether this sync backend is connected and enabled"""
        ...


class StorageBackend(ABC):
    """Abstract interface for persistent storage"""

    @abstractmethod
    def save_entry(self, entry) -> bool:
        """
        Save a clipboard entry.

        Args:
            entry: ClipboardEntry to save

        Returns:
            True if successful

        Raises:
            StorageError: If save fails
        """
        ...

    @abstractmethod
    def get_entries(self, limit: Optional[int] = None) -> List:
        """
        Get clipboard entries.

        Args:
            limit: Optional limit on entries

        Returns:
            List of ClipboardEntry objects

        Raises:
            StorageError: If retrieval fails
        """
        ...

    @abstractmethod
    def delete_entry(self, content_hash: str) -> bool:
        """
        Delete an entry by content hash.

        Args:
            content_hash: Hash of entry to delete

        Returns:
            True if successful

        Raises:
            StorageError: If deletion fails
        """
        ...

    @abstractmethod
    def clear_all(self) -> bool:
        """
        Clear all entries.

        Returns:
            True if successful

        Raises:
            StorageError: If clearing fails
        """
        ...

    @abstractmethod
    def get_entry_count(self) -> int:
        """
        Get total number of entries.

        Returns:
            Number of entries
        """
        ...
