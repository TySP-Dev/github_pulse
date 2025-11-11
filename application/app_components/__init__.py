"""
Azure DevOps & UUF → GitHub Processor - Application Components
Modular components for the application
"""

# Version info
__version__ = "3.0.0"
__author__ = "Azure DevOps to GitHub Processor"

# Export main classes for easier imports
from .config_manager import ConfigManager
from .ai_manager import AIManager
from .github_api import GitHubAPI
from .azure_devops_api import AzureDevOpsAPI
from .dataverse_api import DataverseAPI
from .work_item_processor import WorkItemProcessor
from .settings_dialog import SettingsDialog
from .main_gui import MainGUI
from .utils import Logger, PRNumberManager, ContentBuilders

__all__ = [
    'ConfigManager',
    'AIManager', 
    'GitHubAPI',
    'AzureDevOpsAPI',
    'DataverseAPI',
    'WorkItemProcessor',
    'SettingsDialog',
    'MainGUI',
    'Logger',
    'PRNumberManager',
    'ContentBuilders'
]