"""Tests for ConfigManager"""

import os
import yaml
import pytest
from src.utils.config_manager import ConfigManager


class TestConfigManager:
    """Tests for ConfigManager"""

    def test_init_creates_default_config(self, config_manager):
        assert config_manager.config is not None
        assert 'clipboard' in config_manager.config

    def test_get_dot_notation(self, config_manager):
        value = config_manager.get('clipboard.check_interval')
        assert value == 500

    def test_get_nested(self, config_manager):
        value = config_manager.get('encryption.algorithm')
        assert value == 'AES-256-GCM'

    def test_get_default(self, config_manager):
        value = config_manager.get('nonexistent.key', 'default')
        assert value == 'default'

    def test_set_dot_notation(self, config_manager):
        config_manager.set('ui.theme', 'dark')
        assert config_manager.get('ui.theme') == 'dark'

    def test_set_creates_nested_keys(self, config_manager):
        config_manager.set('new.nested.key', 'value')
        assert config_manager.get('new.nested.key') == 'value'

    def test_save_and_reload(self, config_manager):
        config_manager.set('ui.theme', 'dark')
        config_manager.save()

        # Reload and verify
        reloaded = ConfigManager(config_manager.config_path)
        assert reloaded.get('ui.theme') == 'dark'

    def test_save_strips_github_token(self, config_manager):
        config_manager.set('github.token', 'secret_token_value')
        config_manager.save()

        # Read file directly to verify token is stripped
        with open(config_manager.config_path, 'r') as f:
            saved = yaml.safe_load(f)
        assert saved.get('github', {}).get('token') is None

    def test_get_all(self, config_manager):
        all_config = config_manager.get_all()
        assert isinstance(all_config, dict)
        assert 'clipboard' in all_config

    def test_validate_valid_config(self, config_manager):
        assert config_manager.validate() is True

    def test_validate_invalid_interval(self, config_manager):
        config_manager.set('clipboard.check_interval', 10)
        assert config_manager.validate() is False

    def test_validate_invalid_history_size(self, config_manager):
        config_manager.set('clipboard.max_history_size', 1)
        assert config_manager.validate() is False

    def test_reset(self, config_manager):
        config_manager.set('ui.theme', 'dark')
        config_manager.reset()
        # After reset, should be back to default
        assert config_manager.get('ui.theme') == 'light'

    def test_merge_config(self, config_manager):
        """Test that user config merges with defaults"""
        # Create a user config that only overrides some values
        os.makedirs(os.path.dirname(config_manager.config_path), exist_ok=True)
        user_config = {'ui': {'theme': 'dark'}}
        with open(config_manager.config_path, 'w') as f:
            yaml.dump(user_config, f)

        config_manager.reload()
        # Overridden value
        assert config_manager.get('ui.theme') == 'dark'
        # Default value should still be present
        assert config_manager.get('clipboard.check_interval') == 500
