"""Tests for custom exceptions and ABC interfaces"""

import pytest
from unittest.mock import MagicMock

from src.core.exceptions import (
    ClipSyncerError,
    EncryptionError,
    DecryptionError,
    SyncError,
    SyncConnectionError,
    SyncAuthenticationError,
    StorageError,
    ConfigurationError,
)
from src.core.interfaces import EncryptionStrategy, SyncBackend, StorageBackend
from src.core.encryption.manager import EncryptionManager
from src.services.sync.github_sync import GitHubSyncService
from src.core.storage.repository_improved import ClipboardRepository


class TestExceptionHierarchy:
    """Tests for the custom exception hierarchy"""

    def test_base_exception(self):
        with pytest.raises(ClipSyncerError):
            raise ClipSyncerError("base error")

    def test_encryption_error_is_clipsyncer_error(self):
        with pytest.raises(ClipSyncerError):
            raise EncryptionError("encryption failed")

    def test_decryption_error_is_clipsyncer_error(self):
        with pytest.raises(ClipSyncerError):
            raise DecryptionError("decryption failed")

    def test_sync_error_is_clipsyncer_error(self):
        with pytest.raises(ClipSyncerError):
            raise SyncError("sync failed")

    def test_sync_connection_error_is_sync_error(self):
        with pytest.raises(SyncError):
            raise SyncConnectionError("connection failed")

    def test_sync_auth_error_is_sync_error(self):
        with pytest.raises(SyncError):
            raise SyncAuthenticationError("auth failed")

    def test_storage_error_is_clipsyncer_error(self):
        with pytest.raises(ClipSyncerError):
            raise StorageError("storage failed")

    def test_configuration_error_is_clipsyncer_error(self):
        with pytest.raises(ClipSyncerError):
            raise ConfigurationError("config invalid")

    def test_exception_message(self):
        err = EncryptionError("test message")
        assert str(err) == "test message"

    def test_exception_chain(self):
        """Test exception chaining with 'from'"""
        try:
            try:
                raise ValueError("original")
            except ValueError as e:
                raise EncryptionError("wrapped") from e
        except EncryptionError as e:
            assert str(e) == "wrapped"
            assert isinstance(e.__cause__, ValueError)


class TestInterfaceImplementation:
    """Tests that concrete classes implement the ABC interfaces"""

    def test_encryption_manager_implements_strategy(self):
        em = EncryptionManager()
        assert isinstance(em, EncryptionStrategy)

    def test_github_sync_implements_backend(self):
        gs = GitHubSyncService()
        assert isinstance(gs, SyncBackend)

    def test_repository_implements_storage(self, db_manager, encryption_manager):
        repo = ClipboardRepository(db_manager, encryption_manager)
        assert isinstance(repo, StorageBackend)


class TestEncryptionValidation:
    """Tests for input validation in EncryptionManager"""

    def test_encrypt_non_string_raises(self, encryption_manager):
        with pytest.raises(EncryptionError, match="Expected str"):
            encryption_manager.encrypt(12345)

    def test_decrypt_non_dict_raises(self, encryption_manager):
        with pytest.raises(DecryptionError, match="Expected dict"):
            encryption_manager.decrypt("not a dict")

    def test_decrypt_missing_fields_raises(self, encryption_manager):
        with pytest.raises(DecryptionError, match="Missing required fields"):
            encryption_manager.decrypt({"ciphertext": "abc"})

    def test_decrypt_wrong_key_gives_clear_message(self):
        import os
        em1 = EncryptionManager(os.urandom(32))
        em2 = EncryptionManager(os.urandom(32))
        encrypted = em1.encrypt("test")
        with pytest.raises(DecryptionError, match="wrong encryption key"):
            em2.decrypt(encrypted)

    def test_init_non_bytes_key_raises(self):
        with pytest.raises(EncryptionError, match="Key must be 32 bytes"):
            EncryptionManager("not bytes")


class TestGitHubSyncEncapsulation:
    """Tests for GitHubSyncService encapsulation"""

    def test_private_fields(self):
        gs = GitHubSyncService(token="test", repository="user/repo")
        # Private fields should not be directly accessible via public name
        assert not hasattr(gs, 'token')  # was public, now private
        assert hasattr(gs, '_token')

    def test_enabled_property(self):
        gs = GitHubSyncService()
        assert gs.enabled is False
        assert gs.is_enabled is False

    def test_repository_name_still_public(self):
        gs = GitHubSyncService(repository="user/repo")
        assert gs.repository_name == "user/repo"
