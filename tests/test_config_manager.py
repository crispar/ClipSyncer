"""Tests for ConfigManager"""

import os
import yaml
import pytest

from src.utils.config_manager import ConfigManager


@pytest.fixture
def config_with_defaults(tmp_path):
    """ConfigManager with a temp config path (defaults loaded from project)"""
    config_path = str(tmp_path / "settings.yaml")
    return ConfigManager(config_path=config_path)


@pytest.fixture
def config_with_user_settings(tmp_path):
    """ConfigManager with pre-existing user settings"""
    config_path = tmp_path / "settings.yaml"
    user_config = {
        'clipboard': {
            'check_interval': 1000,
            'max_history_size': 500
        },
        'ui': {
            'theme': 'dark'
        }
    }
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(user_config, f)
    return ConfigManager(config_path=str(config_path))


class TestConfigManagerDefaults:
    """Tests for default configuration loading"""

    def test_has_clipboard_defaults(self, config_with_defaults):
        assert config_with_defaults.get('clipboard.check_interval') is not None
        assert config_with_defaults.get('clipboard.max_history_size') is not None

    def test_has_encryption_defaults(self, config_with_defaults):
        assert config_with_defaults.get('encryption.enabled') is True
        assert config_with_defaults.get('encryption.algorithm') == 'AES-256-GCM'

    def test_has_storage_defaults(self, config_with_defaults):
        assert config_with_defaults.get('storage.retention_days') == 30

    def test_has_github_defaults(self, config_with_defaults):
        assert config_with_defaults.get('github.enabled') is False

    def test_has_cleanup_defaults(self, config_with_defaults):
        assert config_with_defaults.get('cleanup.enabled') is True
        assert config_with_defaults.get('cleanup.duplicate_removal') is True

    def test_has_ui_defaults(self, config_with_defaults):
        assert config_with_defaults.get('ui.show_notifications') is True


class TestConfigManagerGet:
    """Tests for get method with dot notation"""

    def test_get_top_level(self, config_with_defaults):
        result = config_with_defaults.get('clipboard')
        assert isinstance(result, dict)
        assert 'check_interval' in result

    def test_get_nested(self, config_with_defaults):
        result = config_with_defaults.get('clipboard.check_interval')
        assert isinstance(result, int)

    def test_get_nonexistent_returns_default(self, config_with_defaults):
        result = config_with_defaults.get('nonexistent.key', 'fallback')
        assert result == 'fallback'

    def test_get_nonexistent_returns_none(self, config_with_defaults):
        result = config_with_defaults.get('nonexistent.key')
        assert result is None

    def test_get_deeply_nested(self, config_with_defaults):
        config_with_defaults.set('a.b.c.d', 42)
        assert config_with_defaults.get('a.b.c.d') == 42


class TestConfigManagerSet:
    """Tests for set method"""

    def test_set_existing_key(self, config_with_defaults):
        config_with_defaults.set('clipboard.check_interval', 2000)
        assert config_with_defaults.get('clipboard.check_interval') == 2000

    def test_set_new_key(self, config_with_defaults):
        config_with_defaults.set('custom.setting', 'value')
        assert config_with_defaults.get('custom.setting') == 'value'

    def test_set_creates_intermediate_dicts(self, config_with_defaults):
        config_with_defaults.set('new.nested.key', True)
        assert config_with_defaults.get('new.nested.key') is True


class TestConfigManagerMerge:
    """Tests for config merging"""

    def test_user_config_overrides_defaults(self, config_with_user_settings):
        assert config_with_user_settings.get('clipboard.check_interval') == 1000
        assert config_with_user_settings.get('clipboard.max_history_size') == 500

    def test_user_config_preserves_unset_defaults(self, config_with_user_settings):
        # User didn't set encryption, so default should remain
        assert config_with_user_settings.get('encryption.enabled') is True

    def test_user_theme_override(self, config_with_user_settings):
        assert config_with_user_settings.get('ui.theme') == 'dark'


class TestConfigManagerSaveReload:
    """Tests for save and reload"""

    def test_save_creates_file(self, config_with_defaults):
        config_with_defaults.set('test.key', 'save_test')
        result = config_with_defaults.save()
        assert result is True
        assert os.path.exists(config_with_defaults.config_path)

    def test_save_and_reload_preserves_values(self, config_with_defaults):
        config_with_defaults.set('custom.value', 42)
        config_with_defaults.save()

        # Create new instance with same path
        reloaded = ConfigManager(config_path=config_with_defaults.config_path)
        assert reloaded.get('custom.value') == 42

    def test_reload_method(self, config_with_defaults):
        config_with_defaults.set('temporary', 'value')
        config_with_defaults.reload()
        # After reload, unsaved changes are lost
        assert config_with_defaults.get('temporary') is None

    def test_save_strips_github_token(self, config_with_defaults):
        config_with_defaults.set('github.token', 'secret_token_value')
        config_with_defaults.save()

        # Read file directly to verify token is stripped
        with open(config_with_defaults.config_path, 'r') as f:
            saved = yaml.safe_load(f)
        assert saved.get('github', {}).get('token') is None

    def test_reset_restores_defaults(self, config_with_defaults):
        config_with_defaults.set('clipboard.check_interval', 9999)
        config_with_defaults.reset()
        # Should be back to default
        interval = config_with_defaults.get('clipboard.check_interval')
        assert interval != 9999


class TestConfigManagerValidate:
    """Tests for configuration validation"""

    def test_valid_config(self, config_with_defaults):
        assert config_with_defaults.validate() is True

    def test_invalid_check_interval(self, config_with_defaults):
        config_with_defaults.set('clipboard.check_interval', 50)
        assert config_with_defaults.validate() is False

    def test_invalid_history_size(self, config_with_defaults):
        config_with_defaults.set('clipboard.max_history_size', 5)
        assert config_with_defaults.validate() is False

    def test_missing_required_field(self, config_with_defaults):
        # Remove a required field
        if 'encryption' in config_with_defaults.config:
            del config_with_defaults.config['encryption']
        assert config_with_defaults.validate() is False


class TestConfigManagerGetAll:
    """Tests for get_all"""

    def test_get_all_returns_dict(self, config_with_defaults):
        all_config = config_with_defaults.get_all()
        assert isinstance(all_config, dict)
        assert 'clipboard' in all_config
        assert 'encryption' in all_config

    def test_get_all_contains_expected_keys(self, config_with_defaults):
        all_config = config_with_defaults.get_all()
        # Should contain all top-level sections
        expected_keys = {'clipboard', 'encryption', 'storage', 'github', 'cleanup', 'ui', 'logging'}
        assert expected_keys.issubset(set(all_config.keys()))
