"""
Utility functions and helpers
"""

import json
import os
import re
import subprocess
import threading
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from urllib.parse import urlparse


class Logger:
    """Simple logger for GUI applications"""
    
    def __init__(self, text_widget=None):
        self.text_widget = text_widget
        self._lock = threading.Lock()
    
    def log(self, message: str) -> None:
        """Log a message to the text widget and console"""
        timestamp = __import__('datetime').datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        try:
            print(formatted_message)
        except UnicodeEncodeError:
            # Fallback: replace Unicode emojis with ASCII equivalents
            safe_message = formatted_message.replace('✅', '[SUCCESS]').replace('❌', '[ERROR]').replace('⚠️', '[WARNING]').replace('📋', '[INFO]').replace('📄', '[FILE]').replace('📍', '[LOCATION]').replace('📝', '[EDIT]')
            print(safe_message)
        
        if self.text_widget:
            def update_widget():
                try:
                    with self._lock:
                        self.text_widget.config(state='normal')
                        self.text_widget.insert('end', formatted_message + '\n')
                        self.text_widget.see('end')
                        self.text_widget.config(state='disabled')
                        self.text_widget.update_idletasks()
                except:
                    pass  # Widget might be destroyed
            
            # Schedule update on main thread
            if hasattr(self.text_widget, 'after'):
                self.text_widget.after(0, update_widget)
            else:
                update_widget()


class PRNumberManager:
    """Manages PR numbers for branch naming"""
    
    PR_COUNTER_FILE = '.pr_counter.json'
    
    @classmethod
    def get_pr_counter_file(cls) -> str:
        """Get the path to the PR counter file"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(script_dir, cls.PR_COUNTER_FILE)
    
    @classmethod
    def load_pr_counter(cls) -> Dict[str, int]:
        """Load the PR counter from file"""
        counter_file = cls.get_pr_counter_file()
        if os.path.exists(counter_file):
            try:
                with open(counter_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}
    
    @classmethod
    def save_pr_counter(cls, counter: Dict[str, int]) -> None:
        """Save the PR counter to file"""
        counter_file = cls.get_pr_counter_file()
        try:
            with open(counter_file, 'w', encoding='utf-8') as f:
                json.dump(counter, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save PR counter: {e}")
    
    @classmethod
    def get_next_pr_number(cls, provider_key: str) -> int:
        """
        Get the next PR number for a given provider
        
        Args:
            provider_key: Either the AI provider name ('chatgpt', 'claude') or 'gh_copilot'
        
        Returns:
            Next available PR number for this provider
        """
        try:
            counter = cls.load_pr_counter()
            current_number = counter.get(provider_key, 0)
            next_number = current_number + 1
            counter[provider_key] = next_number
            cls.save_pr_counter(counter)
            return next_number
            
        except Exception as e:
            print(f"Error managing PR counter: {e}")
            # Fallback to a timestamp-based number
            import time
            return int(time.time()) % 10000


class GitHubInfoExtractor:
    """Extracts GitHub repository information from URLs"""
    
    @staticmethod
    def extract_github_info(doc_url: str) -> Dict[str, Any]:
        """Extract GitHub repository information from a document URL"""
        try:
            if not doc_url or 'github.com' not in doc_url:
                return {'error': 'Not a GitHub URL'}
            
            parsed = urlparse(doc_url)
            path_parts = parsed.path.strip('/').split('/')
            
            if len(path_parts) < 2:
                return {'error': 'Invalid GitHub URL format'}
            
            owner = path_parts[0]
            repo = path_parts[1]
            
            # Try to extract file path if it's a blob URL
            file_path = None
            if len(path_parts) > 3 and path_parts[2] == 'blob':
                # Skip branch name and get file path
                if len(path_parts) > 4:
                    file_path = '/'.join(path_parts[4:])
            
            result = {
                'owner': owner,
                'repo': repo,
                'original_content_git_url': doc_url
            }
            
            if file_path:
                result['file_path'] = file_path
            
            # Try to find ms.author from the URL or repo name
            ms_author = GitHubInfoExtractor._extract_ms_author(owner, repo, doc_url)
            if ms_author:
                result['ms_author'] = ms_author
            
            return result
            
        except Exception as e:
            return {'error': f'Error parsing GitHub URL: {str(e)}'}
    
    @staticmethod
    def _extract_ms_author(owner: str, repo: str, url: str) -> Optional[str]:
        """Try to extract ms.author from various sources"""
        try:
            # Method 1: Check if owner looks like a Microsoft username
            if owner.startswith('Microsoft') or 'microsoft' in owner.lower():
                # Try to extract from repo name or URL patterns
                if '-' in repo:
                    parts = repo.split('-')
                    for part in parts:
                        if len(part) > 2 and part.islower():
                            return part
            
            # Method 2: Look for patterns in the URL
            url_lower = url.lower()
            
            # Common patterns for ms.author
            patterns = [
                r'/([a-z][a-z0-9-]+[a-z0-9])/',  # username-like patterns
                r'author[=:]([a-z][a-z0-9-]+)',   # author= or author: patterns
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url_lower)
                if match:
                    candidate = match.group(1)
                    # Validate it looks like a reasonable username
                    if 3 <= len(candidate) <= 20 and candidate.replace('-', '').isalnum():
                        return candidate
            
            return None
            
        except Exception:
            return None


class WorkItemFieldExtractor:
    """Extracts and processes work item fields"""
    
    @staticmethod
    def extract_work_item_fields(work_item: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and process fields from Azure DevOps work item"""
        fields = work_item.get('fields', {})
        
        # Extract basic fields
        item_id = work_item.get('id', 'Unknown')
        title = fields.get('System.Title', 'No Title')
        
        # Extract custom fields with fallbacks
        nature_of_request = (
            fields.get('Custom.Natureofrequest') or 
            fields.get('Custom.NatureOfRequest') or 
            fields.get('Microsoft.VSTS.Common.DescriptionHtml', '')
        )
        
        # Clean HTML if present
        if nature_of_request and '<' in nature_of_request:
            nature_of_request = WorkItemFieldExtractor._clean_html(nature_of_request)
        
        mydoc_url = (
            fields.get('Custom.MyDocURL') or 
            fields.get('Custom.DocumentURL') or 
            fields.get('Custom.URL', '')
        )
        
        text_to_change = (
            fields.get('Custom.TextToChange') or 
            fields.get('Custom.CurrentText', '')
        )
        
        new_text = (
            fields.get('Custom.NewText') or 
            fields.get('Custom.ProposedText') or 
            fields.get('Custom.ReplacementText', '')
        )
        
        # Extract GitHub info from the document URL
        github_info = GitHubInfoExtractor.extract_github_info(mydoc_url)
        
        return {
            'id': item_id,
            'title': title,
            'nature_of_request': nature_of_request,
            'mydoc_url': mydoc_url,
            'text_to_change': text_to_change,
            'new_text': new_text,
            'github_info': github_info,
            'status': 'Ready',
            'source': 'Azure DevOps'
        }
    
    @staticmethod
    def extract_uuf_item_fields(uuf_item: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and process fields from UUF item"""
        # UUF items have different field structure
        item_id = uuf_item.get('cr_uufitemid', 'Unknown')
        title = uuf_item.get('cr_title', 'No Title')
        
        nature_of_request = uuf_item.get('cr_description', '')
        mydoc_url = uuf_item.get('cr_documenturl', '')
        text_to_change = uuf_item.get('cr_currenttext', '')
        new_text = uuf_item.get('cr_newtext', '')
        
        # Extract GitHub info
        github_info = GitHubInfoExtractor.extract_github_info(mydoc_url)
        
        return {
            'id': item_id,
            'title': title,
            'nature_of_request': nature_of_request,
            'mydoc_url': mydoc_url,
            'text_to_change': text_to_change,
            'new_text': new_text,
            'github_info': github_info,
            'status': 'Ready',
            'source': 'UUF'
        }
    
    @staticmethod
    def _clean_html(html_text: str) -> str:
        """Remove HTML tags and decode entities"""
        import html
        
        # Remove HTML tags
        clean_text = re.sub(r'<[^>]+>', '', html_text)
        
        # Decode HTML entities
        clean_text = html.unescape(clean_text)
        
        # Clean up whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text


class ContentBuilders:
    """Builds content for GitHub issues and PRs"""
    
    @staticmethod
    def build_issue_title(item: Dict[str, Any]) -> str:
        """Build GitHub issue title"""
        source_prefix = "UUF" if item.get('source') == 'UUF' else "AB"
        return f"[{source_prefix}#{item['id']}] {item['title']}"
    
    @staticmethod
    def build_issue_body(item: Dict[str, Any], github_info: Dict[str, Any]) -> str:
        """Build GitHub issue body"""
        body_parts = []
        
        # Header
        source_name = "UUF Item" if item.get('source') == 'UUF' else "Azure DevOps Work Item"
        body_parts.append(f"## {source_name} Details")
        body_parts.append("")

        # Make ID a hyperlink if source URL is available
        if item.get('source_url'):
            body_parts.append(f"**ID:** [{item['id']}]({item['source_url']})")
        else:
            body_parts.append(f"**ID:** {item['id']}")

        body_parts.append(f"**Title:** {item['title']}")
        body_parts.append("")
        
        # Nature of request
        if item['nature_of_request']:
            body_parts.append("**Nature of Request:**")
            body_parts.append(item['nature_of_request'])
            body_parts.append("")
        
        # Document information
        if item['mydoc_url']:
            body_parts.append("**Document URL:**")
            body_parts.append(item['mydoc_url'])
            body_parts.append("")
        
        # Change details
        body_parts.append("## Change Details")
        body_parts.append("")
        
        if item['text_to_change']:
            body_parts.append("**Text to Change:**")
            body_parts.append("```")
            body_parts.append(item['text_to_change'])
            body_parts.append("```")
            body_parts.append("")
        
        if item['new_text']:
            body_parts.append("**Proposed New Text:**")
            body_parts.append("```")
            body_parts.append(item['new_text'])
            body_parts.append("```")
            body_parts.append("")
        
        # Repository info
        if github_info.get('owner') and github_info.get('repo'):
            body_parts.append("## Repository Information")
            body_parts.append("")
            body_parts.append(f"**Repository:** {github_info['owner']}/{github_info['repo']}")
            
            if github_info.get('ms_author'):
                body_parts.append(f"**Author:** @{github_info['ms_author']}")
            
            body_parts.append("")
        
        # Instructions for manual review
        body_parts.append("## Instructions")
        body_parts.append("")
        body_parts.append("This issue requires manual review of the proposed documentation change.")
        body_parts.append("")
        body_parts.append("**Next Steps:**")
        body_parts.append("1. Review the proposed change above")
        body_parts.append("2. Navigate to the document URL")
        body_parts.append("3. Locate the text that needs to be changed")
        body_parts.append("4. Make the appropriate updates")
        body_parts.append("5. Close this issue when complete")
        body_parts.append("")
        body_parts.append("---")
        body_parts.append("*Created automatically by Azure DevOps → GitHub Processor*")
        
        return "\n".join(body_parts)
    
    @staticmethod
    def build_pr_title(item: Dict[str, Any]) -> str:
        """Build GitHub PR title"""
        source_prefix = "UUF" if item.get('source') == 'UUF' else "AB"
        return f"[{source_prefix}#{item['id']}] {item['title']}"
    
    @staticmethod
    def build_pr_body(item: Dict[str, Any], github_info: Dict[str, Any]) -> str:
        """Build GitHub PR body"""
        body_parts = []
        
        # Header
        source_name = "UUF Item" if item.get('source') == 'UUF' else "Azure DevOps Work Item"
        body_parts.append(f"## {source_name} Documentation Update")
        body_parts.append("")

        # Make ID a hyperlink if source URL is available
        if item.get('source_url'):
            body_parts.append(f"**ID:** [{item['id']}]({item['source_url']})")
        else:
            body_parts.append(f"**ID:** {item['id']}")

        body_parts.append(f"**Title:** {item['title']}")
        body_parts.append("")
        
        # Nature of request
        if item['nature_of_request']:
            body_parts.append("**Description:**")
            body_parts.append(item['nature_of_request'])
            body_parts.append("")
        
        # Change summary
        body_parts.append("## Changes Made")
        body_parts.append("")
        body_parts.append("This PR updates documentation as requested.")
        body_parts.append("")
        
        if item['text_to_change'] and item['new_text']:
            body_parts.append("**Change Summary:**")
            body_parts.append("- Updated specific text content as requested")
            body_parts.append("")
            
            body_parts.append("<details>")
            body_parts.append("<summary>View Change Details</summary>")
            body_parts.append("")
            body_parts.append("**Original Text:**")
            body_parts.append("```")
            body_parts.append(item['text_to_change'])
            body_parts.append("```")
            body_parts.append("")
            body_parts.append("**New Text:**")
            body_parts.append("```")
            body_parts.append(item['new_text'])
            body_parts.append("```")
            body_parts.append("</details>")
            body_parts.append("")
        
        # Repository info
        if github_info.get('ms_author'):
            body_parts.append(f"**Author:** @{github_info['ms_author']}")
            body_parts.append("")
        
        # Review instructions
        body_parts.append("## Review Checklist")
        body_parts.append("")
        body_parts.append("- [ ] Changes match the requested update")
        body_parts.append("- [ ] No unintended changes were made")
        body_parts.append("- [ ] Grammar and formatting are correct")
        body_parts.append("- [ ] Links and references are working")
        body_parts.append("")
        
        body_parts.append("---")
        body_parts.append("*Created automatically by Azure DevOps → GitHub Processor*")
        
        return "\n".join(body_parts)


class LocalRepositoryScanner:
    """Scans local repository path for Git repositories"""
    
    @staticmethod
    def scan_local_repos(local_repo_path: str) -> List[str]:
        """Scan local path for Git repositories"""
        if not local_repo_path or not os.path.exists(local_repo_path):
            return []
        
        repos = []
        try:
            for item in os.listdir(local_repo_path):
                item_path = os.path.join(local_repo_path, item)
                if os.path.isdir(item_path):
                    git_path = os.path.join(item_path, '.git')
                    if os.path.exists(git_path):
                        # Get remote origin URL to determine repo name
                        repo_info = LocalRepositoryScanner.get_repo_info(item_path)
                        if repo_info:
                            repos.append(repo_info)
                        else:
                            # Fallback to folder name
                            repos.append(f"local/{item}")
        except PermissionError:
            pass  # Skip directories we can't access
        except Exception as e:
            print(f"Error scanning local repos: {e}")
        
        return sorted(repos)
    
    @staticmethod
    def get_repo_info(repo_path: str) -> Optional[str]:
        """Get repository information from local Git repo"""
        try:
            # Get remote origin URL
            result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                url = result.stdout.strip()
                return LocalRepositoryScanner.parse_git_url(url)
        except Exception:
            pass
        
        return None
    
    @staticmethod
    def parse_git_url(url: str) -> Optional[str]:
        """Parse Git URL to extract owner/repo format"""
        try:
            # Handle GitHub URLs
            if 'github.com' in url:
                # Handle both HTTPS and SSH URLs
                if url.startswith('git@'):
                    # SSH: git@github.com:owner/repo.git
                    parts = url.split(':')[-1].replace('.git', '')
                    return parts
                else:
                    # HTTPS: https://github.com/owner/repo.git
                    parsed = urlparse(url)
                    path = parsed.path.strip('/').replace('.git', '')
                    return path
        except:
            pass
        
        return None
    
    @staticmethod
    def clone_repository(repo_url: str, local_path: str, repo_name: str) -> bool:
        """Clone a repository to local path"""
        try:
            target_path = os.path.join(local_path, repo_name.split('/')[-1])
            
            if os.path.exists(target_path):
                print(f"Repository already exists at {target_path}")
                return True
            
            os.makedirs(local_path, exist_ok=True)
            
            result = subprocess.run(
                ['git', 'clone', repo_url, target_path],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                print(f"Successfully cloned {repo_url} to {target_path}")
                return True
            else:
                print(f"Failed to clone repository: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error cloning repository: {e}")
            return False


class ConfigurationHelpers:
    """Configuration and validation utilities"""
    
    @staticmethod
    def validate_ai_provider_setup(config: Dict[str, Any], parent_window=None) -> bool:
        """Validate AI provider setup and offer to install missing modules
        
        Args:
            config: Configuration dictionary
            parent_window: Parent tkinter window for dialogs
            
        Returns:
            bool: True if setup is valid or user handled the issue
        """
        ai_provider = config.get('AI_PROVIDER', '').lower()
        
        if not ai_provider or ai_provider == 'none':
            return True  # No AI provider selected, nothing to validate
        
        try:
            # Try to import AI manager for validation
            from .ai_manager import AIManager
            ai_manager = AIManager()
            
            # Check if modules are available
            available, missing = ai_manager.check_ai_module_availability(ai_provider)
            
            if available:
                return True  # All modules available
            
            print(f"⚠️ AI Provider '{ai_provider}' selected but missing required packages: {', '.join(missing)}")
            
            # Offer to install missing packages
            success = ai_manager.install_ai_packages(missing, parent_window)
            
            if success:
                # Re-check availability after installation
                available, still_missing = ai_manager.check_ai_module_availability(ai_provider)
                if available:
                    print(f"✅ AI Provider '{ai_provider}' is now ready to use")
                    return True
                else:
                    print(f"⚠️ Some packages may still be missing: {', '.join(still_missing)}")
                    print("Please restart the application after installation completes")
                    return False
            
            return False
            
        except ImportError:
            # AI manager not available, skip validation
            return True
    
    @staticmethod
    def create_default_env_file() -> bool:
        """Create a default .env file with all settings blank"""
        try:
            default_config = """# Azure DevOps to GitHub Tool Configuration
# Generated automatically - fill in your values
# IMPORTANT: Do NOT commit this file to source control. Add it to .gitignore.

# Azure DevOps Configuration
AZURE_DEVOPS_QUERY=
AZURE_DEVOPS_PAT=

# GitHub Configuration
GITHUB_PAT=
GITHUB_REPO=

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
"""
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(default_config)
            
            print("Created default .env file with blank values")
            return True
            
        except Exception as e:
            print(f"Error creating default .env file: {e}")
            return False


class EnhancedContentBuilders(ContentBuilders):
    """Enhanced content builders with Azure DevOps specific methods"""
    
    @staticmethod
    def build_pr_title_for_azure_devops(item: Dict[str, Any]) -> str:
        """Build GitHub PR title for Azure DevOps items"""
        return f"Docs update: {item['title'][:80]} (AB#{item['id']})"

    @staticmethod
    def build_pr_body_for_azure_devops(item: Dict[str, Any], github_info: Dict[str, Any]) -> str:
        """Build GitHub PR body for Azure DevOps items with enhanced Copilot instructions"""
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            f"**Automated documentation update from Azure DevOps (created on {now})**",
            "",
            f"**Work Item ID:** AB#{item['id']}",
            f"**Document URL:** {item['mydoc_url']}",
        ]

        # Add file path information if available
        if github_info.get('original_content_git_url'):
            lines.append(f"**File Path:** {github_info['original_content_git_url']}")

        # Add ms.author metadata if available
        if github_info.get('ms_author'):
            lines.append(f"**ms.author:** `{github_info['ms_author']}`")

        # Add nature of request for context
        lines.extend([
            "",
            "## Change Type",
            f"{item['nature_of_request']}",
            "",
        ])

        lines.extend([
            "## Changes Requested",
            "",
            "### Current Text to Replace",
            "```",
            item['text_to_change'],
            "```",
            "",
            "### Proposed New Text",
            "```",
            item['new_text'],
            "```",
            "",
            "---",
            "",
            "## Instructions for GitHub Copilot",
            "",
            "**Task:** Update the documentation file with the changes requested above.",
            "",
            "**Steps to complete:**",
            "1. Locate the file containing the 'Current Text to Replace' shown above",
            "2. Find the exact text that needs to be updated",
            "3. Replace it with the 'Proposed New Text'",
            "4. Ensure no other changes are made to the file",
            "5. Commit the changes with a descriptive message",
            "",
            "**Important Notes:**",
            "- Only change the specific text shown above",
            "- Do not modify formatting, links, or other content",
            "- Verify the replacement text fits naturally in context",
            "",
            "---",
            "*This PR was created automatically from Azure DevOps work item AB#" + str(item['id']) + "*"
        ])

        return "\n".join(lines)


# Compatibility functions for direct function access
def get_next_pr_number(provider_key: str) -> int:
    """Compatibility function for direct access to PR number generation"""
    return PRNumberManager.get_next_pr_number(provider_key)


def validate_ai_provider_setup(config: Dict[str, Any], parent_window=None) -> bool:
    """Compatibility function for direct access to AI provider validation"""
    return ConfigurationHelpers.validate_ai_provider_setup(config, parent_window)


def create_default_env_file() -> bool:
    """Compatibility function for direct access to .env file creation"""
    return ConfigurationHelpers.create_default_env_file()