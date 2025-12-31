"""Secure key management using Windows Credential Manager"""

import base64
import os
import hashlib
import hmac
from typing import Optional
import keyring
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from loguru import logger


# Fixed salt for password-based key derivation (same across all devices)
# This is public and doesn't need to be secret - the password provides security
SYNC_SALT = b"ClipSyncer_v1_salt_2024"


class KeyManager:
    """Manages encryption keys securely using system keyring"""

    SERVICE_NAME = "ClipboardHistory"
    KEY_NAME = "encryption_key"
    SYNC_PASSWORD_KEY = "sync_password_hash"  # Store hash to verify password
    GITHUB_TOKEN_KEY = "github_token"  # Store GitHub token securely

    def __init__(self):
        """Initialize key manager"""
        self.keyring = keyring.get_keyring()
        logger.info(f"KeyManager initialized with backend: {self.keyring.name}")

    def get_or_create_key(self) -> bytes:
        """
        Get existing key or create new one

        Returns:
            32-byte encryption key
        """
        # Try to get existing key
        key = self.get_key()

        if key is None:
            # Generate new key
            key = self.generate_key()
            self.store_key(key)
            logger.info("Created new encryption key")
        else:
            logger.info("Retrieved existing encryption key")

        return key

    def get_key(self) -> Optional[bytes]:
        """
        Retrieve stored encryption key

        Returns:
            Encryption key or None if not found
        """
        try:
            key_b64 = keyring.get_password(self.SERVICE_NAME, self.KEY_NAME)

            if key_b64:
                key = base64.b64decode(key_b64)
                if len(key) == 32:
                    return key
                else:
                    logger.warning(f"Invalid key length: {len(key)}")
                    return None

            return None

        except Exception as e:
            logger.error(f"Failed to retrieve key: {e}")
            return None

    def store_key(self, key: bytes) -> bool:
        """
        Store encryption key securely

        Args:
            key: 32-byte encryption key

        Returns:
            True if successful
        """
        try:
            if len(key) != 32:
                raise ValueError("Key must be 32 bytes")

            key_b64 = base64.b64encode(key).decode('ascii')
            keyring.set_password(self.SERVICE_NAME, self.KEY_NAME, key_b64)

            logger.info("Encryption key stored securely")
            return True

        except Exception as e:
            logger.error(f"Failed to store key: {e}")
            return False

    def delete_key(self) -> bool:
        """
        Delete stored encryption key

        Returns:
            True if successful
        """
        try:
            keyring.delete_password(self.SERVICE_NAME, self.KEY_NAME)
            logger.info("Encryption key deleted")
            return True

        except Exception as e:
            logger.error(f"Failed to delete key: {e}")
            return False

    def rotate_key(self) -> bytes:
        """
        Generate and store a new encryption key

        Returns:
            New 32-byte encryption key
        """
        new_key = self.generate_key()
        self.store_key(new_key)
        logger.info("Encryption key rotated")
        return new_key

    @staticmethod
    def generate_key() -> bytes:
        """
        Generate a new 256-bit encryption key

        Returns:
            32-byte random key
        """
        return os.urandom(32)

    @staticmethod
    def derive_key_from_password(password: str) -> bytes:
        """
        Derive a 256-bit encryption key from a password using PBKDF2.
        Uses a fixed salt so the same password produces the same key on all devices.

        Args:
            password: User-provided sync password

        Returns:
            32-byte derived key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=SYNC_SALT,
            iterations=600000,  # High iteration count for security
        )
        return kdf.derive(password.encode('utf-8'))

    def set_sync_password(self, password: str) -> bytes:
        """
        Set a sync password and derive encryption key from it.
        Stores the derived key and a password hash for verification.

        Args:
            password: User-provided sync password

        Returns:
            32-byte derived encryption key
        """
        # Derive key from password
        key = self.derive_key_from_password(password)

        # Store the key
        self.store_key(key)

        # Store password hash for verification (using different salt)
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            b"ClipSyncer_password_verify",
            100000
        )
        password_hash_b64 = base64.b64encode(password_hash).decode('ascii')
        keyring.set_password(self.SERVICE_NAME, self.SYNC_PASSWORD_KEY, password_hash_b64)

        logger.info("Sync password set and key derived successfully")
        return key

    def verify_sync_password(self, password: str) -> bool:
        """
        Verify if a password matches the stored sync password.

        Args:
            password: Password to verify

        Returns:
            True if password matches
        """
        try:
            stored_hash_b64 = keyring.get_password(self.SERVICE_NAME, self.SYNC_PASSWORD_KEY)
            if not stored_hash_b64:
                return False

            stored_hash = base64.b64decode(stored_hash_b64)

            # Calculate hash of provided password
            password_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                b"ClipSyncer_password_verify",
                100000
            )

            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(password_hash, stored_hash)

        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False

    def has_sync_password(self) -> bool:
        """
        Check if a sync password has been set.

        Returns:
            True if sync password exists
        """
        try:
            stored_hash = keyring.get_password(self.SERVICE_NAME, self.SYNC_PASSWORD_KEY)
            return stored_hash is not None
        except Exception:
            return False

    def clear_sync_password(self) -> bool:
        """
        Clear the stored sync password hash.

        Returns:
            True if successful
        """
        try:
            keyring.delete_password(self.SERVICE_NAME, self.SYNC_PASSWORD_KEY)
            logger.info("Sync password cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear sync password: {e}")
            return False

    def get_key_with_password(self, password: str) -> Optional[bytes]:
        """
        Get encryption key using sync password.
        If password matches stored hash, returns the stored key.
        If no password was set before, sets it and derives new key.

        Args:
            password: Sync password

        Returns:
            32-byte encryption key or None if password is wrong
        """
        if self.has_sync_password():
            # Verify password matches
            if self.verify_sync_password(password):
                key = self.get_key()
                if key:
                    logger.info("Retrieved key with verified password")
                    return key
                else:
                    # Key missing but password correct - regenerate
                    return self.set_sync_password(password)
            else:
                logger.warning("Sync password verification failed")
                return None
        else:
            # First time setting password
            return self.set_sync_password(password)

    # =====================================================
    # GitHub Token Secure Storage
    # =====================================================

    def store_github_token(self, token: str) -> bool:
        """
        Store GitHub token securely in system keyring.

        Args:
            token: GitHub personal access token

        Returns:
            True if successful
        """
        try:
            keyring.set_password(self.SERVICE_NAME, self.GITHUB_TOKEN_KEY, token)
            logger.info("GitHub token stored securely in keyring")
            return True
        except Exception as e:
            logger.error(f"Failed to store GitHub token: {e}")
            return False

    def get_github_token(self) -> Optional[str]:
        """
        Retrieve GitHub token from system keyring.

        Returns:
            GitHub token or None if not found
        """
        try:
            token = keyring.get_password(self.SERVICE_NAME, self.GITHUB_TOKEN_KEY)
            return token
        except Exception as e:
            logger.error(f"Failed to retrieve GitHub token: {e}")
            return None

    def delete_github_token(self) -> bool:
        """
        Delete GitHub token from system keyring.

        Returns:
            True if successful
        """
        try:
            keyring.delete_password(self.SERVICE_NAME, self.GITHUB_TOKEN_KEY)
            logger.info("GitHub token deleted from keyring")
            return True
        except Exception as e:
            logger.error(f"Failed to delete GitHub token: {e}")
            return False

    def has_github_token(self) -> bool:
        """
        Check if GitHub token is stored.

        Returns:
            True if token exists
        """
        try:
            token = keyring.get_password(self.SERVICE_NAME, self.GITHUB_TOKEN_KEY)
            return token is not None
        except Exception:
            return False

    def verify_access(self) -> bool:
        """
        Verify that keyring is accessible

        Returns:
            True if keyring is accessible
        """
        try:
            # Test write and read
            test_key = "test_access"
            test_value = "test_value"

            keyring.set_password(self.SERVICE_NAME, test_key, test_value)
            result = keyring.get_password(self.SERVICE_NAME, test_key)
            keyring.delete_password(self.SERVICE_NAME, test_key)

            return result == test_value

        except Exception as e:
            logger.error(f"Keyring access verification failed: {e}")
            return False

    def export_key(self, filepath: str, password: Optional[str] = None) -> bool:
        """
        Export key to file (optionally password-protected)

        Args:
            filepath: Path to export file
            password: Optional password for encryption

        Returns:
            True if successful
        """
        try:
            key = self.get_key()
            if not key:
                logger.error("No key to export")
                return False

            if password:
                # Use password-based encryption for export
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

                salt = os.urandom(16)
                kdf = PBKDF2(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=salt,
                    iterations=100000,
                    backend=None
                )
                derived_key = kdf.derive(password.encode())

                # Encrypt the key with derived key
                from ..encryption.manager import EncryptionManager
                em = EncryptionManager(derived_key)
                encrypted = em.encrypt(base64.b64encode(key).decode('ascii'))

                export_data = {
                    'encrypted': True,
                    'salt': base64.b64encode(salt).decode('ascii'),
                    'data': encrypted
                }
            else:
                # Plain export (base64 encoded)
                export_data = {
                    'encrypted': False,
                    'data': base64.b64encode(key).decode('ascii')
                }

            import json
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)

            logger.info(f"Key exported to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to export key: {e}")
            return False