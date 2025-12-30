"""Configuration management module"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


class ConfigManager:
    """Manages application configuration"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager

        Args:
            config_path: Path to configuration file
        """
        if config_path is None:
            # Use default app data directory
            app_data = Path(os.environ.get('APPDATA', '.')) / 'ClipboardHistory'
            app_data.mkdir(exist_ok=True)
            config_path = str(app_data / 'settings.yaml')

        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self._load_defaults()
        self._load_config()

    def _load_defaults(self):
        """Load default configuration"""
        default_path = Path(__file__).parent.parent.parent / 'config' / 'default_settings.yaml'

        try:
            if default_path.exists():
                with open(default_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f) or {}
                logger.info("Loaded default configuration")
            else:
                logger.warning(f"Default config not found: {default_path}")
                self._create_default_config()

        except Exception as e:
            logger.error(f"Failed to load defaults: {e}")
            self._create_default_config()

    def _create_default_config(self):
        """Create default configuration in memory"""
        self.config = {
            'clipboard': {
                'check_interval': 500,
                'max_history_size': 1000,
                'auto_start': True
            },
            'encryption': {
                'enabled': True,
                'algorithm': 'AES-256-GCM'
            },
            'storage': {
                'retention_days': 30,
                'backup_interval': 86400,
                'database_path': None
            },
            'github': {
                'enabled': False,
                'repository': '',
                'token': '',
                'sync_interval': 3600,
                'auto_sync': False
            },
            'cleanup': {
                'enabled': True,
                'duplicate_removal': True,
                'cleanup_interval': 3600
            },
            'ui': {
                'show_notifications': True,
                'minimize_to_tray': True,
                'start_minimized': False,
                'theme': 'light'
            },
            'logging': {
                'level': 'INFO',
                'file_logging': True,
                'max_log_size': 10485760,
                'max_log_files': 5
            }
        }

    def _load_config(self):
        """Load user configuration"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = yaml.safe_load(f) or {}

                # Merge with defaults
                self._merge_config(self.config, user_config)
                logger.info(f"Loaded user configuration from {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to load user config: {e}")

    def _merge_config(self, base: Dict, updates: Dict):
        """
        Recursively merge configuration dictionaries

        Args:
            base: Base configuration
            updates: Updates to apply
        """
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def save(self):
        """Save current configuration to file"""
        try:
            # Create directory if needed
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False)

            logger.info(f"Configuration saved to {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value

        Args:
            key: Configuration key (dot notation supported)
            default: Default value if not found

        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any):
        """
        Set configuration value

        Args:
            key: Configuration key (dot notation supported)
            value: Value to set
        """
        keys = key.split('.')
        config = self.config

        # Navigate to the parent
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set the value
        config[keys[-1]] = value
        logger.debug(f"Set config: {key} = {value}")

    def get_all(self) -> Dict[str, Any]:
        """Get entire configuration"""
        return self.config.copy()

    def reset(self):
        """Reset to default configuration"""
        self._load_defaults()
        logger.info("Configuration reset to defaults")

    def validate(self) -> bool:
        """
        Validate configuration

        Returns:
            True if valid
        """
        try:
            # Check required fields
            required = [
                'clipboard.check_interval',
                'clipboard.max_history_size',
                'encryption.enabled',
                'storage.retention_days'
            ]

            for key in required:
                if self.get(key) is None:
                    logger.error(f"Missing required config: {key}")
                    return False

            # Validate types and ranges
            if self.get('clipboard.check_interval', 0) < 100:
                logger.error("Check interval too small (min 100ms)")
                return False

            if self.get('clipboard.max_history_size', 0) < 10:
                logger.error("History size too small (min 10)")
                return False

            return True

        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False