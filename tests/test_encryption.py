"""Tests for EncryptionManager and KeyManager"""

import os
import json
import tempfile
import pytest

from src.core.encryption.manager import EncryptionManager
from src.core.encryption.key_manager import KeyManager, SYNC_SALT
from src.core.exceptions import EncryptionError, DecryptionError


class TestEncryptionManager:
    """Tests for EncryptionManager"""

    def test_generate_key(self):
        key = EncryptionManager.generate_key()
        assert len(key) == 32
        # Should be random - two keys should differ
        key2 = EncryptionManager.generate_key()
        assert key != key2

    def test_init_with_key(self, encryption_key):
        em = EncryptionManager(encryption_key)
        assert em.key == encryption_key

    def test_init_generates_key(self):
        em = EncryptionManager()
        assert len(em.key) == 32

    def test_init_invalid_key_length(self):
        with pytest.raises(EncryptionError, match="Key must be 32 bytes"):
            EncryptionManager(b'\x00' * 16)

    def test_encrypt_decrypt_roundtrip(self, encryption_manager):
        plaintext = "Hello, World!"
        encrypted = encryption_manager.encrypt(plaintext)
        decrypted = encryption_manager.decrypt(encrypted)
        assert decrypted == plaintext

    def test_encrypt_returns_required_fields(self, encryption_manager):
        encrypted = encryption_manager.encrypt("test")
        assert 'ciphertext' in encrypted
        assert 'nonce' in encrypted
        assert 'tag' in encrypted

    def test_different_nonces_per_encryption(self, encryption_manager):
        enc1 = encryption_manager.encrypt("same")
        enc2 = encryption_manager.encrypt("same")
        # Nonces must be unique (critical for GCM security)
        assert enc1['nonce'] != enc2['nonce']

    def test_wrong_key_fails_decrypt(self, encryption_manager):
        encrypted = encryption_manager.encrypt("secret")
        wrong_key = os.urandom(32)
        wrong_em = EncryptionManager(wrong_key)
        with pytest.raises(DecryptionError, match="wrong encryption key"):
            wrong_em.decrypt(encrypted)

    def test_tampered_ciphertext_fails(self, encryption_manager):
        encrypted = encryption_manager.encrypt("integrity test")
        import base64
        ct = base64.b64decode(encrypted['ciphertext'])
        tampered = bytes([ct[0] ^ 0xFF]) + ct[1:]
        encrypted['ciphertext'] = base64.b64encode(tampered).decode('ascii')
        with pytest.raises(DecryptionError):
            encryption_manager.decrypt(encrypted)

    def test_tampered_tag_fails(self, encryption_manager):
        encrypted = encryption_manager.encrypt("tag test")
        import base64
        tag = base64.b64decode(encrypted['tag'])
        tampered = bytes([tag[0] ^ 0xFF]) + tag[1:]
        encrypted['tag'] = base64.b64encode(tampered).decode('ascii')
        with pytest.raises(DecryptionError):
            encryption_manager.decrypt(encrypted)

    def test_unicode_content(self, encryption_manager):
        plaintext = "한국어 테스트 🎉 日本語"
        encrypted = encryption_manager.encrypt(plaintext)
        decrypted = encryption_manager.decrypt(encrypted)
        assert decrypted == plaintext

    def test_large_content(self, encryption_manager):
        plaintext = "A" * 100_000
        encrypted = encryption_manager.encrypt(plaintext)
        decrypted = encryption_manager.decrypt(encrypted)
        assert decrypted == plaintext

    def test_empty_string(self, encryption_manager):
        encrypted = encryption_manager.encrypt("")
        decrypted = encryption_manager.decrypt(encrypted)
        assert decrypted == ""

    def test_encrypt_json(self, encryption_manager):
        obj = {"key": "value", "nested": {"list": [1, 2, 3]}}
        encrypted = encryption_manager.encrypt_json(obj)
        decrypted = encryption_manager.decrypt_json(encrypted)
        assert decrypted == obj

    def test_encrypt_json_unicode(self, encryption_manager):
        obj = {"message": "안녕하세요", "emoji": "🔑"}
        encrypted = encryption_manager.encrypt_json(obj)
        decrypted = encryption_manager.decrypt_json(encrypted)
        assert decrypted == obj

    def test_encrypt_file(self, encryption_manager, tmp_path):
        input_file = tmp_path / "input.txt"
        encrypted_file = tmp_path / "encrypted.json"
        output_file = tmp_path / "output.txt"

        input_file.write_text("file content to encrypt", encoding='utf-8')
        encryption_manager.encrypt_file(str(input_file), str(encrypted_file))
        encryption_manager.decrypt_file(str(encrypted_file), str(output_file))

        assert output_file.read_text(encoding='utf-8') == "file content to encrypt"

    def test_verify_key_self_test(self, encryption_manager):
        assert encryption_manager.verify_key() is True

    def test_verify_key_with_test_data(self, encryption_manager):
        encrypted = encryption_manager.encrypt("verify me")
        assert encryption_manager.verify_key(test_data=encrypted) is True

    def test_verify_key_wrong_data(self):
        em = EncryptionManager(os.urandom(32))
        other = EncryptionManager(os.urandom(32))
        encrypted = other.encrypt("wrong key")
        assert em.verify_key(test_data=encrypted) is False


class TestKeyManagerDerivation:
    """Tests for KeyManager key derivation (no keyring dependency)"""

    def test_derive_key_from_password(self):
        key = KeyManager.derive_key_from_password("test_password")
        assert len(key) == 32
        assert isinstance(key, bytes)

    def test_derive_key_deterministic(self):
        """Same password must produce same key (cross-device sync)"""
        key1 = KeyManager.derive_key_from_password("my_sync_password")
        key2 = KeyManager.derive_key_from_password("my_sync_password")
        assert key1 == key2

    def test_derive_key_different_passwords(self):
        key1 = KeyManager.derive_key_from_password("password1")
        key2 = KeyManager.derive_key_from_password("password2")
        assert key1 != key2

    def test_derive_key_unicode_password(self):
        key = KeyManager.derive_key_from_password("패스워드🔑")
        assert len(key) == 32

    def test_generate_key_random(self):
        key1 = KeyManager.generate_key()
        key2 = KeyManager.generate_key()
        assert len(key1) == 32
        assert key1 != key2

    def test_sync_salt_constant(self):
        """SYNC_SALT must not change (would break cross-device sync)"""
        assert SYNC_SALT == b"ClipSyncer_v1_salt_2024"

    def test_fingerprint_for_password_deterministic(self):
        """Same password must produce same fingerprint on every device."""
        fp1 = KeyManager.fingerprint_for_password("shared_secret")
        fp2 = KeyManager.fingerprint_for_password("shared_secret")
        assert fp1 == fp2
        assert len(fp1) == 8
        # Hex only
        int(fp1, 16)

    def test_fingerprint_for_password_distinguishes(self):
        """Different passwords must produce different fingerprints (with overwhelming probability)."""
        fp1 = KeyManager.fingerprint_for_password("password_one")
        fp2 = KeyManager.fingerprint_for_password("password_two")
        assert fp1 != fp2

    def test_fingerprint_does_not_expose_password_or_key(self):
        """Fingerprint must not equal or contain the password / raw key."""
        password = "supersecret"
        fp = KeyManager.fingerprint_for_password(password)
        assert password not in fp
        key = KeyManager.derive_key_from_password(password)
        # Hex of key vs fingerprint - fingerprint is sha256(key)[:8],
        # not key bytes themselves.
        assert fp != key.hex()[:8]
