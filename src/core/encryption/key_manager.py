"""Secure key management using Windows Credential Manager"""

import base64
import os
from typing import Optional
import keyring
from loguru import logger


class KeyManager:
    """Manages encryption keys securely using system keyring"""

    SERVICE_NAME = "ClipboardHistory"
    KEY_NAME = "encryption_key"

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