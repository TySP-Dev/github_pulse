"""
GitHub Pulse - Application Components
Modular components for the application
"""

import sys
import os

# Version info
__version__ = "0.0.1"
__author__ = "TySP-Dev"
__app_name__ = "GitHub Pulse"

# Determine if running in production build
IS_PRODUCTION = getattr(sys, 'frozen', False)

# Get the application directory
if IS_PRODUCTION:
    # In production build, get the executable directory
    APP_DIR = os.path.dirname(sys.executable)
else:
    # In development, get the source directory
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Export main classes for easier imports
from .config_manager import ConfigManager
from .ai_manager import AIManager
from .github_api import GitHubAPI
from .settings_dialog import SettingsDialog
from .main_gui import MainGUI
from .utils import Logger, PRNumberManager, ContentBuilders
from .workflow import WorkflowManager, WorkflowItem, GitHubRepoFetcher
from .ai_action_planner import AIActionPlanner, ActionPlan

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
    'GitHubRepoFetcher',
    'AIActionPlanner',
    'ActionPlan',
    '__version__',
    '__author__',
    '__app_name__',
    'IS_PRODUCTION',
    'APP_DIR'
]
