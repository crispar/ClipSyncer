"""Integration tests for application initialization."""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add project root to sys.path to import main_improved
sys.path.insert(0, str(Path(__file__).parent.parent))

from main_improved import ClipboardHistoryApp  # noqa: E402


@pytest.fixture
def mock_env(tmp_path):
    """Set up environment variables for testing."""
    # Set APPDATA to a temporary directory
    app_data = tmp_path / "AppData" / "Roaming"
    app_data.mkdir(parents=True)

    with patch.dict(os.environ, {"APPDATA": str(app_data)}):
        yield app_data


@pytest.fixture
def mock_dependencies():
    """Mock external dependencies that require GUI or system integration."""
    with patch('main_improved.QApplication') as mock_app, \
         patch('main_improved.TrayIcon') as mock_tray, \
         patch('src.core.encryption.key_manager.keyring') as mock_keyring:

        # Mock QApplication instance
        mock_app_instance = MagicMock()
        mock_app.return_value = mock_app_instance

        # Mock keyring get_password to return None (simulating first run)
        mock_keyring.get_password.return_value = None
        mock_keyring.set_password.return_value = None

        yield mock_app, mock_tray, mock_keyring


def test_app_initialization(mock_env, mock_dependencies):
    """Test that the application initializes correctly."""
    app = ClipboardHistoryApp()

    # Initialize the application
    result = app.initialize()

    assert result is True, "Application failed to initialize"

    # Check that critical components are initialized
    assert app.config_manager is not None
    assert app.clipboard_monitor is not None
    assert app.clipboard_history is not None
    assert app.encryption_manager is not None
    assert app.database_manager is not None
    assert app.cleanup_service is not None
    assert app.archive_manager is not None

    # Check that logs directory was created
    log_dir = mock_env / "ClipboardHistory" / "logs"
    assert log_dir.exists()

    # Shutdown
    app.shutdown()
