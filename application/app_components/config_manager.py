"""
Configuration Manager
Handles loading/saving configuration from .env files and launch.json
"""

import os
import json
from typing import Dict, Any, Optional


class ConfigManager:
    """Manages application configuration from multiple sources"""
    
    def __init__(self):
        self.config = self.load_configuration()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            'AZURE_DEVOPS_QUERY': None,
            'AZURE_DEVOPS_PAT': None,
            'GITHUB_PAT': None,
            'GITHUB_REPO': None,
            'FORKED_REPO': None,  # User's fork repository
            'AI_PROVIDER': None,
            'CLAUDE_API_KEY': None,
            'OPENAI_API_KEY': None,
            'GITHUB_TOKEN': None,  # For GitHub Copilot AI Provider
            'LOCAL_REPO_PATH': None,
            'DRY_RUN': 'false',
            'DATAVERSE_ENVIRONMENT_URL': None,
            'DATAVERSE_TABLE_NAME': None,
            'AZURE_AD_CLIENT_ID': None,
            'AZURE_AD_CLIENT_SECRET': None,
            'AZURE_AD_TENANT_ID': None,
            'CUSTOM_INSTRUCTIONS': None  # Custom AI instructions
        }
    
    def load_configuration(self) -> Dict[str, Any]:
        """Load configuration from launch.json first, then .env as fallback"""
        config = self._get_default_config()
        launch_json_keys = set()
        
        # First, try to load from launch.json
        launch_json_path = os.path.join('.vscode', 'launch.json')
        if os.path.exists(launch_json_path):
            try:
                with open(launch_json_path, 'r', encoding='utf-8') as f:
                    launch_data = json.load(f)
                    
                # Look for configurations with env variables
                for configuration in launch_data.get('configurations', []):
                    env_vars = configuration.get('env', {})
                    for key in config.keys():
                        if key in env_vars and env_vars[key] and not env_vars[key].startswith('<'):
                            config[key] = env_vars[key]
                            launch_json_keys.add(key)
                            
                if launch_json_keys:
                    print(f"Loaded configuration from launch.json: {launch_json_path}")
                
            except (json.JSONDecodeError, FileNotFoundError, KeyError) as e:
                print(f"Could not load launch.json: {e}")
        
        # Check if .env file exists, create default if not
        if not os.path.exists('.env'):
            print("No .env file found. Creating default .env file...")
            self._create_default_env_file(config)
        
        # Load values from .env file (but don't override launch.json values)
        if os.path.exists('.env'):
            try:
                env_loaded = False
                with open('.env', 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            
                            # Load from .env if key exists in config and wasn't loaded from launch.json
                            if key in config and key not in launch_json_keys:
                                config[key] = value if value else ''
                                env_loaded = True
                                
                if env_loaded:
                    print("Loaded configuration from .env file")
                elif not launch_json_keys:
                    print("Configuration files found but no valid values loaded")
                    
            except FileNotFoundError:
                print("No .env file found")
            except Exception as e:
                print(f"Could not load .env file: {e}")
        
        # Ensure all config values are strings, not None
        for key in config:
            if config[key] is None:
                config[key] = ''
        
        # Special handling for AI_PROVIDER - default to 'none' if empty
        if not config.get('AI_PROVIDER'):
            config['AI_PROVIDER'] = 'none'
        
        # Debug output
        loaded_from = []
        for key, value in config.items():
            if value:
                loaded_from.append(f"{key}: {'loaded' if value else 'not found'}")
        
        if loaded_from:
            print(f"Configuration status: {', '.join(loaded_from)}")
        else:
            print("No configuration values loaded - all fields will be blank")
        
        self.config = config
        return config
    
    def _create_default_env_file(self, config: Dict[str, Any]) -> None:
        """Create a default .env file with empty values"""
        try:
            env_template = """# Azure DevOps to GitHub Tool Configuration
# Generated automatically - fill in your values
# IMPORTANT: Do NOT commit this file to source control. Add it to .gitignore.

# Azure DevOps Configuration
AZURE_DEVOPS_QUERY=
AZURE_DEVOPS_PAT=

# GitHub Configuration
GITHUB_PAT=
GITHUB_REPO=
FORKED_REPO=

# Application Settings
DRY_RUN=false

# AI Provider Configuration (for local PR creation with AI assistance)
AI_PROVIDER=
CLAUDE_API_KEY=
OPENAI_API_KEY=
GITHUB_TOKEN=
LOCAL_REPO_PATH=

# PowerApp/Dataverse Configuration (for UUF items - optional)
DATAVERSE_ENVIRONMENT_URL=
DATAVERSE_TABLE_NAME=
AZURE_AD_CLIENT_ID=
AZURE_AD_CLIENT_SECRET=
AZURE_AD_TENANT_ID=

# Custom AI Instructions (optional)
CUSTOM_INSTRUCTIONS=
"""
            
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(env_template)
            
            print("Created default .env file with blank values")
            
        except Exception as e:
            print(f"Error creating default .env file: {e}")
    
    def save_configuration(self, config_values: Dict[str, Any]) -> bool:
        """Save configuration to .env file"""
        try:
            print(f"DEBUG: Saving config values: {config_values}")
            print(f"DEBUG: AI_PROVIDER value being saved: '{config_values.get('AI_PROVIDER', 'NOT_FOUND')}'")
            
            # Update internal config
            for key, value in config_values.items():
                if key in self.config:
                    old_value = self.config[key]
                    new_value = value or ''
                    self.config[key] = new_value
                    if key == 'AI_PROVIDER':
                        print(f"DEBUG: Updated AI_PROVIDER from '{old_value}' to '{new_value}'")
            
            # Build .env file content
            env_content = []
            env_content.append("# Azure DevOps to GitHub Tool Configuration")
            env_content.append("# Generated by Settings Dialog")
            env_content.append("# IMPORTANT: Do NOT commit this file to source control. Add it to .gitignore.")
            env_content.append("")
            
            env_content.append("# Azure DevOps Configuration")
            env_content.append(f"AZURE_DEVOPS_QUERY={self.config.get('AZURE_DEVOPS_QUERY', '')}")
            env_content.append(f"AZURE_DEVOPS_PAT={self.config.get('AZURE_DEVOPS_PAT', '')}")
            env_content.append("")
            
            env_content.append("# GitHub Configuration")
            env_content.append(f"GITHUB_PAT={self.config.get('GITHUB_PAT', '')}")
            env_content.append(f"GITHUB_REPO={self.config.get('GITHUB_REPO', '')}")
            env_content.append(f"FORKED_REPO={self.config.get('FORKED_REPO', '')}")
            env_content.append("")
            
            env_content.append("# Application Settings")
            dry_run_value = str(self.config.get('DRY_RUN', 'false')).lower()
            env_content.append(f"DRY_RUN={dry_run_value}")
            env_content.append("")
            
            env_content.append("# AI Provider Configuration (for local PR creation with AI assistance)")
            ai_provider_value = self.config.get('AI_PROVIDER', '')
            print(f"DEBUG: Writing AI_PROVIDER to file: '{ai_provider_value}'")
            env_content.append(f"AI_PROVIDER={ai_provider_value}")
            env_content.append(f"CLAUDE_API_KEY={self.config.get('CLAUDE_API_KEY', '')}")
            env_content.append(f"OPENAI_API_KEY={self.config.get('OPENAI_API_KEY', '')}")
            env_content.append(f"GITHUB_TOKEN={self.config.get('GITHUB_TOKEN', '')}")
            env_content.append(f"LOCAL_REPO_PATH={self.config.get('LOCAL_REPO_PATH', '')}")
            env_content.append("")
            
            env_content.append("# PowerApp/Dataverse Configuration (for UUF items - optional)")
            env_content.append(f"DATAVERSE_ENVIRONMENT_URL={self.config.get('DATAVERSE_ENVIRONMENT_URL', '')}")
            env_content.append(f"DATAVERSE_TABLE_NAME={self.config.get('DATAVERSE_TABLE_NAME', '')}")
            env_content.append(f"AZURE_AD_CLIENT_ID={self.config.get('AZURE_AD_CLIENT_ID', '')}")
            env_content.append(f"AZURE_AD_CLIENT_SECRET={self.config.get('AZURE_AD_CLIENT_SECRET', '')}")
            env_content.append(f"AZURE_AD_TENANT_ID={self.config.get('AZURE_AD_TENANT_ID', '')}")
            env_content.append("")
            
            env_content.append("# Custom AI Instructions (optional)")
            env_content.append(f"CUSTOM_INSTRUCTIONS={self.config.get('CUSTOM_INSTRUCTIONS', '')}")
            env_content.append("")
            
            # Write to file
            with open('.env', 'w', encoding='utf-8') as f:
                f.write('\n'.join(env_content))
            
            print("Configuration saved to .env file")
            return True
            
        except Exception as e:
            print(f"Error saving configuration: {e}")
            return False
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration with automatic GITHUB_TOKEN defaulting"""
        config = self.config.copy()
        
        # Auto-default GITHUB_TOKEN to GITHUB_PAT if GITHUB_TOKEN is empty or None
        github_token = config.get('GITHUB_TOKEN', '').strip() if config.get('GITHUB_TOKEN') else ''
        github_pat = config.get('GITHUB_PAT', '').strip() if config.get('GITHUB_PAT') else ''
        
        if not github_token and github_pat:
            config['GITHUB_TOKEN'] = github_pat
            
        return config
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value"""
        return self.config.get(key, default)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a specific configuration value (dictionary-like interface)"""
        return self.config.get(key, default)
    
    def set_value(self, key: str, value: Any) -> None:
        """Set a specific configuration value"""
        if key in self.config:
            self.config[key] = value
    
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
        return {}
    
    def save_pr_counter(self, counter: Dict[str, int]) -> None:
        """Save the PR counter to file"""
        counter_file = self.get_pr_counter_file()
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(counter_file), exist_ok=True)
            with open(counter_file, 'w', encoding='utf-8') as f:
                json.dump(counter, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save PR counter: {e}")
    
    def get_next_pr_number(self, provider_key: str) -> int:
        """
        Get the next PR number for a given provider.

        Args:
            provider_key: Either the AI provider name ('chatgpt', 'claude') or 'gh_copilot'

        Returns:
            The next PR number for this provider
        """
        counter = self.load_pr_counter()
        current_number = counter.get(provider_key, 0)
        next_number = current_number + 1
        counter[provider_key] = next_number
        self.save_pr_counter(counter)
        return next_number