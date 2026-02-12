"""Encryption manager for secure data handling using AES-256-GCM"""

import os
import base64
import json
from typing import Any, Dict, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag
from loguru import logger

from ..exceptions import EncryptionError, DecryptionError
from ..interfaces import EncryptionStrategy


class EncryptionManager(EncryptionStrategy):
    """Handles encryption and decryption of clipboard data using AES-256-GCM"""

    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize encryption manager

        Args:
            key: 32-byte encryption key (generates new if None)

        Raises:
            EncryptionError: If key is invalid
        """
        if key is None:
            self._key = self.generate_key()
            logger.info("Generated new encryption key")
        else:
            if not isinstance(key, bytes) or len(key) != 32:
                raise EncryptionError("Key must be 32 bytes for AES-256")
            self._key = key
            logger.info("Initialized with provided key")

        self._backend = default_backend()

    @property
    def key(self) -> bytes:
        """Access encryption key (read-only property for backward compatibility)"""
        return self._key

    @staticmethod
    def generate_key() -> bytes:
        """Generate a new 256-bit encryption key"""
        return os.urandom(32)

    def encrypt(self, data: str) -> Dict[str, str]:
        """
        Encrypt string data using AES-256-GCM

        Args:
            data: String to encrypt

        Returns:
            Dictionary with encrypted data, nonce, and tag

        Raises:
            EncryptionError: If data is invalid or encryption fails
        """
        if not isinstance(data, str):
            raise EncryptionError(f"Expected str, got {type(data).__name__}")

        try:
            # Generate a random 96-bit nonce
            nonce = os.urandom(12)

            # Create cipher
            cipher = Cipher(
                algorithms.AES(self._key),
                modes.GCM(nonce),
                backend=self._backend
            )
            encryptor = cipher.encryptor()

            # Encrypt data
            plaintext = data.encode('utf-8')
            ciphertext = encryptor.update(plaintext) + encryptor.finalize()

            # Get authentication tag
            tag = encryptor.tag

            # Encode to base64 for storage
            result = {
                'ciphertext': base64.b64encode(ciphertext).decode('ascii'),
                'nonce': base64.b64encode(nonce).decode('ascii'),
                'tag': base64.b64encode(tag).decode('ascii')
            }

            logger.debug(f"Encrypted {len(data)} characters")
            return result

        except EncryptionError:
            raise
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, encrypted_data: Dict[str, str]) -> str:
        """
        Decrypt data encrypted with AES-256-GCM

        Args:
            encrypted_data: Dictionary with ciphertext, nonce, and tag

        Returns:
            Decrypted string

        Raises:
            DecryptionError: If data is invalid, key is wrong, or decryption fails
        """
        if not isinstance(encrypted_data, dict):
            raise DecryptionError(f"Expected dict, got {type(encrypted_data).__name__}")

        required_keys = {'ciphertext', 'nonce', 'tag'}
        missing = required_keys - set(encrypted_data.keys())
        if missing:
            raise DecryptionError(f"Missing required fields: {missing}")

        try:
            # Decode from base64
            ciphertext = base64.b64decode(encrypted_data['ciphertext'])
            nonce = base64.b64decode(encrypted_data['nonce'])
            tag = base64.b64decode(encrypted_data['tag'])

            # Create cipher
            cipher = Cipher(
                algorithms.AES(self._key),
                modes.GCM(nonce, tag),
                backend=self._backend
            )
            decryptor = cipher.decryptor()

            # Decrypt data
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            result = plaintext.decode('utf-8')
            logger.debug(f"Decrypted {len(result)} characters")
            return result

        except InvalidTag:
            raise DecryptionError(
                "Decryption failed: wrong encryption key or corrupted data"
            )
        except DecryptionError:
            raise
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise DecryptionError(f"Decryption failed: {e}") from e

    def encrypt_json(self, obj: Any) -> Dict[str, str]:
        """
        Encrypt a JSON-serializable object

        Args:
            obj: Object to encrypt

        Returns:
            Encrypted data dictionary

        Raises:
            EncryptionError: If serialization or encryption fails
        """
        try:
            json_str = json.dumps(obj, ensure_ascii=False, indent=2)
        except (TypeError, ValueError) as e:
            raise EncryptionError(f"JSON serialization failed: {e}") from e
        return self.encrypt(json_str)

    def decrypt_json(self, encrypted_data: Dict[str, str]) -> Any:
        """
        Decrypt and parse JSON data

        Args:
            encrypted_data: Encrypted data dictionary

        Returns:
            Decrypted and parsed object

        Raises:
            DecryptionError: If decryption or JSON parsing fails
        """
        json_str = self.decrypt(encrypted_data)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise DecryptionError(f"JSON parsing failed after decryption: {e}") from e

    def encrypt_file(self, input_path: str, output_path: str) -> None:
        """
        Encrypt a file

        Args:
            input_path: Path to input file
            output_path: Path to output encrypted file

        Raises:
            EncryptionError: If file operation or encryption fails
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = f.read()
        except OSError as e:
            raise EncryptionError(f"Failed to read input file: {e}") from e

        encrypted = self.encrypt(data)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(encrypted, f, indent=2)
        except OSError as e:
            raise EncryptionError(f"Failed to write output file: {e}") from e

        logger.info(f"Encrypted file: {input_path} -> {output_path}")

    def decrypt_file(self, input_path: str, output_path: str) -> None:
        """
        Decrypt a file

        Args:
            input_path: Path to encrypted file
            output_path: Path to output decrypted file

        Raises:
            DecryptionError: If file operation or decryption fails
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                encrypted = json.load(f)
        except OSError as e:
            raise DecryptionError(f"Failed to read encrypted file: {e}") from e
        except json.JSONDecodeError as e:
            raise DecryptionError(f"Invalid encrypted file format: {e}") from e

        data = self.decrypt(encrypted)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(data)
        except OSError as e:
            raise DecryptionError(f"Failed to write output file: {e}") from e

        logger.info(f"Decrypted file: {input_path} -> {output_path}")

    def verify_key(self, test_data: Optional[Dict[str, str]] = None) -> bool:
        """
        Verify that the key works correctly

        Args:
            test_data: Optional encrypted data to test with

        Returns:
            True if key is valid
        """
        try:
            if test_data:
                self.decrypt(test_data)
            else:
                test_str = "test_verification"
                encrypted = self.encrypt(test_str)
                decrypted = self.decrypt(encrypted)
                return decrypted == test_str

            return True

        except (EncryptionError, DecryptionError):
            return False
        except Exception as e:
            logger.error(f"Key verification failed: {e}")
            return False