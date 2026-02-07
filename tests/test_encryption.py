"""Tests for EncryptionManager"""

import os
import json
import pytest
from src.core.encryption.manager import EncryptionManager


class TestEncryptionManager:
    """Tests for AES-256-GCM encryption"""

    def test_init_with_key(self, encryption_key):
        em = EncryptionManager(encryption_key)
        assert em.key == encryption_key

    def test_init_generates_key_if_none(self):
        em = EncryptionManager()
        assert len(em.key) == 32

    def test_init_rejects_wrong_key_length(self):
        with pytest.raises(ValueError, match="32 bytes"):
            EncryptionManager(b'\x00' * 16)

    def test_generate_key(self):
        key = EncryptionManager.generate_key()
        assert len(key) == 32
        # Two generated keys should be different
        key2 = EncryptionManager.generate_key()
        assert key != key2

    def test_encrypt_returns_required_fields(self, encryption_manager):
        result = encryption_manager.encrypt("test data")
        assert 'ciphertext' in result
        assert 'nonce' in result
        assert 'tag' in result

    def test_encrypt_decrypt_roundtrip(self, encryption_manager):
        original = "Hello, World! Special chars: 한국어 日本語 🎉"
        encrypted = encryption_manager.encrypt(original)
        decrypted = encryption_manager.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_produces_different_ciphertext(self, encryption_manager):
        """Each encryption should use a different nonce"""
        e1 = encryption_manager.encrypt("same data")
        e2 = encryption_manager.encrypt("same data")
        assert e1['nonce'] != e2['nonce']

    def test_decrypt_with_wrong_key_fails(self, encryption_manager):
        encrypted = encryption_manager.encrypt("secret")
        wrong_key_manager = EncryptionManager(os.urandom(32))
        with pytest.raises(Exception):
            wrong_key_manager.decrypt(encrypted)

    def test_decrypt_tampered_ciphertext_fails(self, encryption_manager):
        encrypted = encryption_manager.encrypt("test")
        # Tamper with ciphertext
        import base64
        ct = base64.b64decode(encrypted['ciphertext'])
        tampered = bytes([ct[0] ^ 0xFF]) + ct[1:]
        encrypted['ciphertext'] = base64.b64encode(tampered).decode('ascii')
        with pytest.raises(Exception):
            encryption_manager.decrypt(encrypted)

    def test_encrypt_json(self, encryption_manager):
        obj = {"entries": [{"content": "test"}], "count": 1}
        encrypted = encryption_manager.encrypt_json(obj)
        assert 'ciphertext' in encrypted

    def test_decrypt_json(self, encryption_manager):
        obj = {"key": "value", "list": [1, 2, 3]}
        encrypted = encryption_manager.encrypt_json(obj)
        decrypted = encryption_manager.decrypt_json(encrypted)
        assert decrypted == obj

    def test_encrypt_empty_string(self, encryption_manager):
        encrypted = encryption_manager.encrypt("")
        decrypted = encryption_manager.decrypt(encrypted)
        assert decrypted == ""

    def test_encrypt_large_data(self, encryption_manager):
        large_data = "x" * 100_000
        encrypted = encryption_manager.encrypt(large_data)
        decrypted = encryption_manager.decrypt(encrypted)
        assert decrypted == large_data

    def test_verify_key_valid(self, encryption_manager):
        assert encryption_manager.verify_key() is True

    def test_verify_key_with_test_data(self, encryption_manager):
        encrypted = encryption_manager.encrypt("test_verification")
        assert encryption_manager.verify_key(encrypted) is True

    def test_verify_key_wrong_data(self):
        em1 = EncryptionManager(os.urandom(32))
        em2 = EncryptionManager(os.urandom(32))
        encrypted = em1.encrypt("test")
        assert em2.verify_key(encrypted) is False

    def test_encrypt_file_decrypt_file(self, encryption_manager, temp_dir):
        input_path = str(temp_dir / "input.txt")
        encrypted_path = str(temp_dir / "encrypted.json")
        output_path = str(temp_dir / "output.txt")

        with open(input_path, 'w', encoding='utf-8') as f:
            f.write("File encryption test content")

        encryption_manager.encrypt_file(input_path, encrypted_path)
        encryption_manager.decrypt_file(encrypted_path, output_path)

        with open(output_path, 'r', encoding='utf-8') as f:
            assert f.read() == "File encryption test content"
