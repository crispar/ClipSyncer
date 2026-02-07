"""Shared fixtures for ClipSyncer tests"""

import os
import sys
import tempfile
import pytest
from pathlib import Path
from datetime import datetime

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for test files"""
    return tmp_path


@pytest.fixture
def encryption_key():
    """Provide a fixed 32-byte encryption key for testing"""
    return b'\x00' * 32


@pytest.fixture
def encryption_manager(encryption_key):
    """Provide an EncryptionManager instance"""
    from src.core.encryption.manager import EncryptionManager
    return EncryptionManager(encryption_key)


@pytest.fixture
def db_manager(temp_dir):
    """Provide a DatabaseManager with a temp SQLite database"""
    from src.core.storage.database import DatabaseManager
    db_path = str(temp_dir / "test_clipboard.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


@pytest.fixture
def repository(db_manager, encryption_manager):
    """Provide a ClipboardRepository instance"""
    from src.core.storage.repository_improved import ClipboardRepository
    return ClipboardRepository(db_manager, encryption_manager)


@pytest.fixture
def clipboard_history():
    """Provide a ClipboardHistory instance"""
    from src.core.clipboard.history import ClipboardHistory
    return ClipboardHistory(max_size=100, dedupe_enabled=True)


@pytest.fixture
def sample_entry():
    """Provide a sample ClipboardEntry"""
    from src.core.clipboard.history import ClipboardEntry
    return ClipboardEntry(
        content="Hello, World!",
        timestamp=datetime(2024, 1, 1, 12, 0, 0),
        content_hash=ClipboardEntry.calculate_hash("Hello, World!"),
        category="text"
    )


@pytest.fixture
def config_manager(temp_dir):
    """Provide a ConfigManager with temp config path"""
    from src.utils.config_manager import ConfigManager
    config_path = str(temp_dir / "test_settings.yaml")
    return ConfigManager(config_path)
