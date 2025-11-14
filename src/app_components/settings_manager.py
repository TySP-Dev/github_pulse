"""
Settings Manager
Handles application settings with live updates and secure storage.

Non-secret settings are stored in config.json.
Secrets (API keys, tokens) are stored in the system keyring.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable
import keyring


class SettingsManager:
    """
    Manages application settings with live updates.

    Features:
    - Non-secret settings stored in JSON
    - API keys stored securely in system keyring
    - Live update notifications to registered listeners
    - No app restart required for changes
    """

    # Keyring service name for this app
    SERVICE_NAME = "GitHubPulse"

    # Keys that should be stored in keyring (secrets)
    SECRET_KEYS = {
        'GITHUB_PAT',
        'ANTHROPIC_API_KEY',
        'OPENAI_API_KEY',
        'GITHUB_COPILOT_TOKEN',
        'CLAUDE_API_KEY',  # Alternative name for Anthropic
        'GITHUB_TOKEN',   # For GitHub Copilot
        'OLLAMA_API_KEY',  # Optional Ollama API key
    }

    # Default settings (non-secrets)
    DEFAULT_SETTINGS = {
        # GitHub Configuration
        'GITHUB_REPO': '',
        'FORKED_REPO': '',
        'LOCAL_REPO_PATH': '',

        # Application Settings
        'AI_PROVIDER': 'none',
        'DRY_RUN': 'false',
        'DEFAULT_BRANCH': 'main',
        'THEME_MODE': 'dark',
        'AUTO_REFRESH': 'true',
        'REFRESH_INTERVAL': '300',

        # Ollama Configuration
        'OLLAMA_URL': '',
        'OLLAMA_MODEL': '',

        # Custom AI Instructions
        'CUSTOM_INSTRUCTIONS': '',
    }

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the settings manager.

        Args:
            config_dir: Directory to store config.json. Defaults to app directory.
        """
        # Determine config directory
        if config_dir is None:
            # Use app directory
            config_dir = Path(__file__).parent.parent
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.json"

        # Settings storage
        self._settings: Dict[str, Any] = {}

        # Registered change listeners
        self._listeners: list[Callable[[str, Any], None]] = []

        # Load settings
        self.load()

    def load(self) -> Dict[str, Any]:
        """
        Load settings from config.json and keyring.

        Returns:
            Dictionary of all settings (secrets and non-secrets combined)
        """
        # Start with defaults
        self._settings = self.DEFAULT_SETTINGS.copy()

        # Load from JSON file
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    saved_settings = json.load(f)
                    # Only load non-secret settings from JSON
                    for key, value in saved_settings.items():
                        if key not in self.SECRET_KEYS:
                            self._settings[key] = value
            except Exception as e:
                print(f"Error loading config.json: {e}")

        # Load secrets from keyring
        for secret_key in self.SECRET_KEYS:
            try:
                value = keyring.get_password(self.SERVICE_NAME, secret_key)
                if value:
                    self._settings[secret_key] = value
            except Exception as e:
                print(f"Error loading {secret_key} from keyring: {e}")

        return self._settings.copy()

    def save(self, settings: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save settings to config.json and keyring.

        Args:
            settings: Settings to save. If None, saves current settings.

        Returns:
            True if successful, False otherwise
        """
        if settings is not None:
            # Update internal settings
            for key, value in settings.items():
                old_value = self._settings.get(key)
                self._settings[key] = value

                # Notify listeners of changes
                if old_value != value:
                    self._notify_change(key, value)

        try:
            # Save non-secrets to JSON
            json_settings = {
                key: value for key, value in self._settings.items()
                if key not in self.SECRET_KEYS
            }

            with open(self.config_file, 'w') as f:
                json.dump(json_settings, f, indent=2)

            # Save secrets to keyring
            for secret_key in self.SECRET_KEYS:
                if secret_key in self._settings:
                    value = self._settings[secret_key]
                    if value:  # Only save non-empty values
                        try:
                            keyring.set_password(self.SERVICE_NAME, secret_key, str(value))
                        except Exception as e:
                            print(f"Error saving {secret_key} to keyring: {e}")

            return True

        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            key: Setting key
            default: Default value if key doesn't exist

        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> bool:
        """
        Set a setting value with live update.

        Args:
            key: Setting key
            value: New value
            save: Whether to persist immediately

        Returns:
            True if successful
        """
        old_value = self._settings.get(key)
        self._settings[key] = value

        # Notify listeners
        if old_value != value:
            self._notify_change(key, value)

        # Save if requested
        if save:
            return self.save()

        return True

    def get_all(self) -> Dict[str, Any]:
        """
        Get all settings.

        Returns:
            Dictionary of all settings
        """
        return self._settings.copy()

    def register_listener(self, callback: Callable[[str, Any], None]):
        """
        Register a callback to be notified of setting changes.

        The callback will be called with (key, new_value) when a setting changes.

        Args:
            callback: Function to call on settings change
        """
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[str, Any], None]):
        """
        Unregister a settings change callback.

        Args:
            callback: Function to remove from listeners
        """
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_change(self, key: str, value: Any):
        """
        Notify all registered listeners of a setting change.

        Args:
            key: Setting key that changed
            value: New value
        """
        for listener in self._listeners:
            try:
                listener(key, value)
            except Exception as e:
                print(f"Error notifying listener of {key} change: {e}")

    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret from the keyring.

        Args:
            key: Secret key to delete

        Returns:
            True if successful
        """
        if key not in self.SECRET_KEYS:
            return False

        try:
            keyring.delete_password(self.SERVICE_NAME, key)
            if key in self._settings:
                del self._settings[key]
            self._notify_change(key, None)
            return True
        except Exception as e:
            print(f"Error deleting {key} from keyring: {e}")
            return False

    def migrate_from_env(self, env_file: Path) -> bool:
        """
        Migrate settings from a .env file to the new system.

        Args:
            env_file: Path to .env file

        Returns:
            True if migration successful
        """
        if not env_file.exists():
            print(f"Env file not found: {env_file}")
            return False

        try:
            # Read .env file
            env_settings = {}
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            env_settings[key] = value

            # Save to new system
            self.save(env_settings)

            print(f"Successfully migrated {len(env_settings)} settings from .env")
            return True

        except Exception as e:
            print(f"Error migrating from .env: {e}")
            return False
