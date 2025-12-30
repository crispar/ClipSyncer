"""Encryption manager for secure data handling using AES-256-GCM"""

import os
import base64
import json
from typing import Any, Dict, Optional
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from loguru import logger


class EncryptionManager:
    """Handles encryption and decryption of clipboard data"""

    def __init__(self, key: Optional[bytes] = None):
        """
        Initialize encryption manager

        Args:
            key: 32-byte encryption key (generates new if None)
        """
        if key is None:
            self.key = self.generate_key()
            logger.info("Generated new encryption key")
        else:
            if len(key) != 32:
                raise ValueError("Key must be 32 bytes for AES-256")
            self.key = key
            logger.info("Initialized with provided key")

        self.backend = default_backend()

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
        """
        try:
            # Generate a random 96-bit nonce
            nonce = os.urandom(12)

            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(nonce),
                backend=self.backend
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

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise

    def decrypt(self, encrypted_data: Dict[str, str]) -> str:
        """
        Decrypt data encrypted with AES-256-GCM

        Args:
            encrypted_data: Dictionary with ciphertext, nonce, and tag

        Returns:
            Decrypted string
        """
        try:
            # Decode from base64
            ciphertext = base64.b64decode(encrypted_data['ciphertext'])
            nonce = base64.b64decode(encrypted_data['nonce'])
            tag = base64.b64decode(encrypted_data['tag'])

            # Create cipher
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(nonce, tag),
                backend=self.backend
            )
            decryptor = cipher.decryptor()

            # Decrypt data
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            result = plaintext.decode('utf-8')
            logger.debug(f"Decrypted {len(result)} characters")
            return result

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise

    def encrypt_json(self, obj: Any) -> Dict[str, str]:
        """
        Encrypt a JSON-serializable object

        Args:
            obj: Object to encrypt

        Returns:
            Encrypted data dictionary
        """
        json_str = json.dumps(obj, ensure_ascii=False, indent=2)
        return self.encrypt(json_str)

    def decrypt_json(self, encrypted_data: Dict[str, str]) -> Any:
        """
        Decrypt and parse JSON data

        Args:
            encrypted_data: Encrypted data dictionary

        Returns:
            Decrypted and parsed object
        """
        json_str = self.decrypt(encrypted_data)
        return json.loads(json_str)

    def encrypt_file(self, input_path: str, output_path: str) -> None:
        """
        Encrypt a file

        Args:
            input_path: Path to input file
            output_path: Path to output encrypted file
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                data = f.read()

            encrypted = self.encrypt(data)

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(encrypted, f, indent=2)

            logger.info(f"Encrypted file: {input_path} -> {output_path}")

        except Exception as e:
            logger.error(f"File encryption failed: {e}")
            raise

    def decrypt_file(self, input_path: str, output_path: str) -> None:
        """
        Decrypt a file

        Args:
            input_path: Path to encrypted file
            output_path: Path to output decrypted file
        """
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                encrypted = json.load(f)

            data = self.decrypt(encrypted)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(data)

            logger.info(f"Decrypted file: {input_path} -> {output_path}")

        except Exception as e:
            logger.error(f"File decryption failed: {e}")
            raise

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
                # Try to decrypt provided data
                self.decrypt(test_data)
            else:
                # Test with sample data
                test_str = "test_verification"
                encrypted = self.encrypt(test_str)
                decrypted = self.decrypt(encrypted)
                return decrypted == test_str

            return True

        except Exception as e:
            logger.error(f"Key verification failed: {e}")
            return False