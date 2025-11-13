"""
Configuration Manager
Wrapper around SettingsManager for backward compatibility.
Now uses config.json + keyring instead of .env files.
"""

import os
import json
from typing import Dict, Any, Optional
from pathlib import Path
from .settings_manager import SettingsManager


class ConfigManager:
    """
    Manages application configuration using the new SettingsManager.

    Provides backward compatibility with old .env-based code while
    using the modern config.json + keyring system underneath.
    """

    def __init__(self):
        """Initialize with SettingsManager backend"""
        # Initialize the modern settings system
        self._settings = SettingsManager()

        # Check if .env exists and offer migration
        env_path = Path('.env')
        if env_path.exists() and not Path('application/config.json').exists():
            print("\n" + "="*60)
            print("NOTICE: Legacy .env file detected!")
            print("="*60)
            print("Your app now uses a modern settings system with:")
            print("  ✓ Secure API key storage (Windows Credential Manager)")
            print("  ✓ Live settings updates (no restart needed)")
            print("  ✓ Better configuration management")
            print()
            print("Migrating settings from .env to new system...")
            print()

            if self._settings.migrate_from_env(env_path):
                print("✓ Migration successful!")
                print(f"  - Secrets → System keyring")
                print(f"  - Settings → {self._settings.config_file}")
                print()
                print("Your .env file is kept as backup.")
                print("You can delete it once you verify everything works.")
            else:
                print("✗ Migration failed. Using .env as fallback.")
            print("="*60 + "\n")

        # Load configuration
        self.config = self._settings.get_all()

        # Auto-default GITHUB_TOKEN to GITHUB_PAT if needed
        self._apply_token_defaults()

        # Show configuration status
        self._print_config_status()

    def _apply_token_defaults(self):
        """Auto-default GITHUB_TOKEN to GITHUB_PAT if GITHUB_TOKEN is empty"""
        github_token = self.config.get('GITHUB_TOKEN', '').strip() if self.config.get('GITHUB_TOKEN') else ''
        github_pat = self.config.get('GITHUB_PAT', '').strip() if self.config.get('GITHUB_PAT') else ''

        if not github_token and github_pat:
            self.config['GITHUB_TOKEN'] = github_pat
            self._settings.set('GITHUB_TOKEN', github_pat, save=False)

    def _print_config_status(self):
        """Print configuration load status"""
        loaded_keys = []
        for key, value in self.config.items():
            if value and str(value).strip():
                # Don't show actual secret values
                if key in SettingsManager.SECRET_KEYS:
                    loaded_keys.append(f"{key}: loaded")
                else:
                    loaded_keys.append(f"{key}: loaded")

        if loaded_keys:
            print(f"Configuration status: {', '.join(loaded_keys)}")
        else:
            print("No configuration values loaded - using defaults")

    def load_configuration(self) -> Dict[str, Any]:
        """
        Load configuration from new system (config.json + keyring).

        Returns:
            Dictionary of all settings
        """
        self.config = self._settings.load()
        self._apply_token_defaults()
        return self.config

    def save_configuration(self, config_values: Dict[str, Any]) -> bool:
        """
        Save configuration using new system.

        No restart required - changes apply immediately!

        Args:
            config_values: Settings to save

        Returns:
            True if successful
        """
        # Save using new system
        success = self._settings.save(config_values)

        if success:
            # Reload to get updated values
            self.config = self._settings.get_all()
            self._apply_token_defaults()
            print(f"Configuration saved to {self._settings.config_file}")
            print("Settings updated (no restart needed!)")
        else:
            print("Failed to save configuration")

        return success

    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration with automatic GITHUB_TOKEN defaulting.

        Returns:
            Dictionary of all settings
        """
        config = self.config.copy()

        # Auto-default GITHUB_TOKEN to GITHUB_PAT if needed
        github_token = config.get('GITHUB_TOKEN', '').strip() if config.get('GITHUB_TOKEN') else ''
        github_pat = config.get('GITHUB_PAT', '').strip() if config.get('GITHUB_PAT') else ''

        if not github_token and github_pat:
            config['GITHUB_TOKEN'] = github_pat

        return config

    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Get a specific configuration value.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a specific configuration value (dictionary-like interface).

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)

    def set_value(self, key: str, value: Any) -> None:
        """
        Set a specific configuration value.

        Args:
            key: Setting key
            value: New value
        """
        self._settings.set(key, value)
        self.config[key] = value

    def register_listener(self, callback):
        """
        Register a callback for settings changes (live updates).

        The callback will be called with (key, new_value) when a setting changes.

        Args:
            callback: Function to call on settings change

        Example:
            def on_settings_changed(key, value):
                if key == 'THEME_MODE':
                    # Update theme immediately
                    page.theme_mode = ft.ThemeMode.DARK if value == 'dark' else ft.ThemeMode.LIGHT
                    page.update()

            config_manager.register_listener(on_settings_changed)
        """
        self._settings.register_listener(callback)

    def unregister_listener(self, callback):
        """
        Unregister a settings change callback.

        Args:
            callback: Function to remove from listeners
        """
        self._settings.unregister_listener(callback)

    # Legacy methods for PR counter (unchanged)

    def get_pr_counter_file(self) -> str:
        """Get the path to the PR counter file"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(script_dir, '..', '.pr_counter.json')

    def load_pr_counter(self) -> Dict[str, int]:
        """Load the PR counter from file"""
        counter_file = self.get_pr_counter_file()
        if os.path.exists(counter_file):
            try:
                with open(counter_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {'count': 0}

    def save_pr_counter(self, counter: Dict[str, int]) -> bool:
        """Save the PR counter to file"""
        counter_file = self.get_pr_counter_file()
        try:
            with open(counter_file, 'w', encoding='utf-8') as f:
                json.dump(counter, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving PR counter: {e}")
            return False

    def increment_pr_counter(self) -> int:
        """Increment and return the PR counter"""
        counter = self.load_pr_counter()
        counter['count'] = counter.get('count', 0) + 1
        self.save_pr_counter(counter)
        return counter['count']

    def get_pr_counter(self) -> int:
        """Get the current PR counter value"""
        counter = self.load_pr_counter()
        return counter.get('count', 0)
