"""
GitHub Pulse
Main application entry point

This application provides GitHub automation workflows with AI assistance.

Note: You may see a Flutter engine warning when closing the app:
  "embedder.cc (2519): 'FlutterEngineRemoveView' returned 'kInvalidArguments'"
This is a harmless known issue with Flet/Flutter and can be safely ignored.
"""

import sys
import os
import flet as ft

# Compatibility fix for Flet 0.28+ (Icons vs icons, Colors vs colors)
ft.icons = ft.Icons
ft.colors = ft.Colors

# Import our modular components
try:
    from app_components.config_manager import ConfigManager
    from app_components.ai_manager import AIManager
    from app_components.github_api import GitHubAPI
    from app_components.main_gui import MainGUI
except ImportError as e:
    print(f"Error importing application components: {e}")
    print("Make sure all files are present in the app_components folder")
    # In production builds, show a user-friendly error
    if getattr(sys, 'frozen', False):
        import traceback
        error_details = traceback.format_exc()
        print(error_details)
    sys.exit(1)


class GitHubAutomationApp:
    """Main application class that orchestrates all components"""

    def __init__(self, page: ft.Page):
        """Initialize the application"""
        self.page = page

        # Configure page
        self.page.title = "GitHub Pulse"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 0

        # Set window size with platform detection
        # Mobile devices will use full screen
        is_mobile = page.web or (hasattr(page, 'platform') and
                                 page.platform in ['android', 'ios'])

        if not is_mobile:
            self.page.window_width = 1400
            self.page.window_height = 1000
            self.page.window_min_width = 1200
            self.page.window_min_height = 800

        # Material Design 3 theme with optimized settings
        self.page.theme = ft.Theme(
            color_scheme_seed="blue",
            use_material3=True,
        )

        # Initialize core managers
        self.config_manager = ConfigManager()
        self.ai_manager = AIManager()

        # Load configuration
        self.config = self.config_manager.load_configuration()

        # Initialize dry run state
        dry_run_config = self.config.get('DRY_RUN', 'false')
        self.dry_run_enabled = str(dry_run_config).lower() in ('true', '1', 'yes', 'on')

        # Register listener for live settings updates
        self.config_manager.register_listener(self._on_setting_changed)

        # Initialize main GUI
        self.main_gui = MainGUI(
            page=self.page,
            config_manager=self.config_manager,
            ai_manager=self.ai_manager,
            app=self
        )

        # Build UI
        self.page.add(self.main_gui.build())

        # Check AI provider setup after a short delay
        self.page.run_task(self._check_ai_provider_setup_async)

    async def _check_ai_provider_setup_async(self):
        """Check and setup AI providers after GUI initialization"""
        try:
            # Wait a bit for GUI to fully load
            import asyncio
            await asyncio.sleep(0.5)

            ai_provider = self.config.get('AI_PROVIDER', '').strip().lower()

            if not ai_provider or ai_provider in ['none', '']:
                return  # No AI provider selected

            if ai_provider not in ['chatgpt', 'claude', 'anthropic', 'github-copilot', 'copilot', 'github_copilot']:
                return  # Unknown provider

            # Check if modules are available and offer installation if needed
            await self.ai_manager.check_and_install_ai_modules_async(ai_provider, self.page)

        except Exception as e:
            print(f"Error checking AI provider setup: {e}")

    def get_config(self):
        """Get current configuration"""
        return self.config.copy()

    def update_config(self, new_config):
        """Update configuration"""
        self.config.update(new_config)
        self.config_manager.config = self.config.copy()

    def save_config(self, config_values):
        """Save configuration"""
        success = self.config_manager.save_configuration(config_values)
        if success:
            self.config = self.config_manager.get_config()
            # Update dry run state
            dry_run_config = self.config.get('DRY_RUN', 'false')
            self.dry_run_enabled = str(dry_run_config).lower() in ('true', '1', 'yes', 'on')
        return success

    def create_github_api(self, token=None, dry_run=None):
        """Create a GitHub API instance"""
        if token is None:
            token = self.config.get('GITHUB_PAT', '')
        if dry_run is None:
            dry_run = self.dry_run_enabled

        logger = self.main_gui.logger if hasattr(self.main_gui, 'logger') else None
        return GitHubAPI(token, logger, dry_run)

    def _on_setting_changed(self, key: str, value: any):
        """
        Handle settings changes with live updates (no restart needed!)

        Args:
            key: Setting key that changed
            value: New value
        """
        print(f"⚡ Setting changed: {key} = {value}")

        # Theme changes - apply immediately
        if key == 'THEME_MODE':
            if value == 'dark':
                self.page.theme_mode = ft.ThemeMode.DARK
            elif value == 'light':
                self.page.theme_mode = ft.ThemeMode.LIGHT
            self.page.update()
            print(f"✓ Theme updated to {value}")

        # Dry run mode changes
        elif key == 'DRY_RUN':
            self.dry_run_enabled = str(value).lower() in ('true', '1', 'yes', 'on')
            print(f"✓ Dry run mode: {self.dry_run_enabled}")

        # GitHub token changes - reinitialize API
        elif key == 'GITHUB_PAT':
            if hasattr(self, 'main_gui') and self.main_gui:
                print("✓ GitHub token updated - API will be reinitialized on next use")

        # AI provider changes
        elif key == 'AI_PROVIDER':
            print(f"✓ AI provider changed to: {value}")
            # AI manager will use new provider on next request

        # Update internal config
        self.config[key] = value


async def main(page: ft.Page):
    """Main entry point for Flet application"""
    try:
        app = GitHubAutomationApp(page)
    except Exception as e:
        # Show error as a simple text on the page since dialog can't open before page init
        print(f"Failed to start application: {e}")
        import traceback
        traceback.print_exc()

        # Add error message to page
        error_text = ft.Text(
            f"Application Error:\n\n{str(e)}\n\nPlease check the console for details.",
            color="red",
            size=16,
        )
        page.add(error_text)


if __name__ == "__main__":
    # Run the Flet app with optimized settings
    # For production builds, use appropriate view settings
    is_production = getattr(sys, 'frozen', False)

    if is_production:
        # Production build settings
        ft.app(
            target=main,
            view=ft.AppView.FLET_APP,  # Native app view for builds
            assets_dir="assets"  # Ensure assets are loaded correctly
        )
    else:
        # Development settings
        ft.app(
            target=main,
            assets_dir="assets"
        )
