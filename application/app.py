"""
GitHub Automation Tool
Main application entry point

This application provides GitHub automation workflows with AI assistance.
"""

import sys
import tkinter as tk
from tkinter import messagebox

# Import our modular components
try:
    from app_components.config_manager import ConfigManager
    from app_components.ai_manager import AIManager
    from app_components.github_api import GitHubAPI
    from app_components.main_gui import MainGUI
except ImportError as e:
    print(f"Error importing application components: {e}")
    print("Make sure all files are present in the app_components folder")
    sys.exit(1)


class GitHubAutomationApp:
    """Main application class that orchestrates all components"""

    def __init__(self):
        """Initialize the application"""
        self.root = tk.Tk()
        self.root.title("GitHub Automation Tool")
        self.root.geometry("1400x1000")

        # Initialize core managers
        self.config_manager = ConfigManager()
        self.ai_manager = AIManager()

        # Load configuration
        self.config = self.config_manager.load_configuration()

        # Initialize dry run state
        dry_run_config = self.config.get('DRY_RUN', 'false')
        self.dry_run_enabled = str(dry_run_config).lower() in ('true', '1', 'yes', 'on')

        # Initialize main GUI
        self.main_gui = MainGUI(
            root=self.root,
            config_manager=self.config_manager,
            ai_manager=self.ai_manager,
            app=self
        )

        # Set up AI provider check after GUI is ready
        self.root.after(100, self._check_ai_provider_setup)

    def _check_ai_provider_setup(self):
        """Check and setup AI providers after GUI initialization"""
        try:
            ai_provider = self.config.get('AI_PROVIDER', '').strip().lower()

            if not ai_provider or ai_provider in ['none', '']:
                return  # No AI provider selected

            if ai_provider not in ['chatgpt', 'claude', 'anthropic', 'github-copilot', 'copilot', 'github_copilot']:
                return  # Unknown provider

            # Check if modules are available and offer installation if needed
            self.ai_manager.check_and_install_ai_modules(ai_provider, self.root)

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

    def run(self):
        """Start the application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("Application interrupted by user")
        except Exception as e:
            messagebox.showerror("Application Error", f"An unexpected error occurred:\n{str(e)}")
            print(f"Application error: {e}")


def main():
    """Main entry point"""
    try:
        app = GitHubAutomationApp()
        app.run()
    except Exception as e:
        print(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
