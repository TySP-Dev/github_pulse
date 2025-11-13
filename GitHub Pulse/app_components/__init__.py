"""
GitHub Pulse - Application Components
Modular components for the application
"""

# Version info
__version__ = "1.0.0"
__author__ = "GitHub Pulse"

# Export main classes for easier imports
from .config_manager import ConfigManager
from .ai_manager import AIManager
from .github_api import GitHubAPI
from .settings_dialog import SettingsDialog
from .main_gui import MainGUI
from .utils import Logger, PRNumberManager, ContentBuilders
from .workflow import WorkflowManager, WorkflowItem, GitHubRepoFetcher

__all__ = [
    'ConfigManager',
    'AIManager',
    'GitHubAPI',
    'SettingsDialog',
    'MainGUI',
    'Logger',
    'PRNumberManager',
    'ContentBuilders',
    'WorkflowManager',
    'WorkflowItem',
    'GitHubRepoFetcher'
]
