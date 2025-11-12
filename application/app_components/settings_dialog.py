"""
Settings Dialog
GUI for configuring application settings (Flet version)
"""

import flet as ft
# Compatibility fix for Flet 0.28+ (Icons vs icons, Colors vs colors)
ft.icons = ft.Icons
ft.colors = ft.Colors
import threading
import subprocess
from typing import Dict, Any, Optional
import sys
import os
import asyncio


class SettingsDialog:
    """Settings configuration dialog"""

    def __init__(self, page: ft.Page, config: Dict[str, Any], config_manager=None, cache_manager=None):
        self.page = page
        self.config = config.copy()
        self.config_manager = config_manager
        self.cache_manager = cache_manager
        self.result = None
        self.entries = {}
        self.dialog_ref = ft.Ref[ft.AlertDialog]()

        # Repository data
        self.target_repos = []
        self.forked_repos = []

        # Dropdown refs
        self.target_repo_dropdown_ref = ft.Ref[ft.Dropdown]()
        self.forked_repo_dropdown_ref = ft.Ref[ft.Dropdown]()
        self.detected_repos_dropdown_ref = ft.Ref[ft.Dropdown]()
        self.ollama_model_dropdown_ref = ft.Ref[ft.Dropdown]()

    def show(self, on_result=None):
        """Show the settings dialog"""
        try:
            print("SettingsDialog.show() called")
            self.on_result = on_result

            # Create the dialog
            print("Creating dialog...")
            dialog = self._create_dialog()
            print(f"Dialog created: {dialog}")

            # IMPORTANT: Set the reference before opening
            if self.dialog_ref.current is None:
                print("dialog_ref.current is None, setting it now")
                self.dialog_ref.current = dialog

            # Use Flet 0.28+ API: page.open() instead of page.dialog
            print("Opening dialog with page.open()...")
            self.page.open(dialog)
            print("page.open() completed")

            # Start async initialization
            print("Starting async initialization...")
            self.page.run_task(self._init_async)
            print("SettingsDialog.show() completed")
        except Exception as ex:
            print(f"Error in SettingsDialog.show(): {ex}")
            import traceback
            traceback.print_exc()

    async def _init_async(self):
        """Initialize async operations"""
        await asyncio.sleep(0.1)
        await self._scan_repos_async()
        await self._load_target_repos_async()
        await self._load_user_forks_async()

    def _create_dialog(self) -> ft.AlertDialog:
        """Create the settings dialog"""
        # Create tabs
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="General",
                    icon=ft.icons.SETTINGS,
                    content=self._create_general_tab()
                ),
                ft.Tab(
                    text="AI Providers",
                    icon=ft.icons.PSYCHOLOGY,
                    content=self._create_ai_tab()
                ),
            ],
            expand=True,
        )

        # Action buttons
        actions = ft.Row(
            [
                ft.TextButton(
                    "Test Connection",
                    icon=ft.icons.CABLE,
                    on_click=self._test_connection
                ),
                ft.TextButton(
                    "Clear Cache",
                    icon=ft.icons.DELETE_SWEEP,
                    on_click=self._clear_cache
                ),
                ft.Container(expand=True),
                ft.TextButton("Cancel", on_click=self._cancel_clicked),
                ft.FilledButton("Save Settings", icon=ft.icons.SAVE, on_click=self._save_clicked),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        dialog = ft.AlertDialog(
            ref=self.dialog_ref,
            modal=True,
            title=ft.Text("⚙️ Settings", size=24, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=tabs,
                width=900,
                height=700,
                padding=10,
            ),
            actions=[actions],
            actions_padding=ft.padding.all(20),
        )

        return dialog

    def _create_general_tab(self) -> ft.Container:
        """Create general settings tab"""
        controls = []

        # GitHub Configuration Section
        controls.append(self._create_section_header("🐙 GitHub Configuration"))

        # GitHub PAT
        github_pat = ft.TextField(
            label="Personal Access Token",
            password=True,
            can_reveal_password=True,
            value=self.config.get('GITHUB_PAT', ''),
            hint_text="Enter your GitHub Personal Access Token",
            expand=True,
        )
        self.entries['GITHUB_PAT'] = github_pat
        controls.append(github_pat)

        # Target Repository
        controls.append(ft.Text("Target Repository", weight=ft.FontWeight.BOLD, size=14))
        target_repo_row = ft.Row(
            [
                ft.Dropdown(
                    ref=self.target_repo_dropdown_ref,
                    label="Target Repository",
                    value=self.config.get('GITHUB_REPO', ''),
                    options=[],
                    hint_text="Select or type repository",
                    expand=True,
                    on_change=lambda e: self._on_target_repo_search(e),
                ),
                ft.IconButton(
                    icon=ft.icons.REFRESH,
                    tooltip="Refresh",
                    on_click=lambda e: self.page.run_task(self._refresh_target_repos_async),
                ),
                ft.IconButton(
                    icon=ft.icons.SEARCH,
                    tooltip="Search",
                    on_click=lambda e: self.page.run_task(self._search_target_repos_async),
                ),
            ],
            spacing=5,
        )
        controls.append(target_repo_row)
        controls.append(ft.Text(
            "ℹ️ Upstream repo where PRs will be created. Type to search all GitHub repos.",
            size=12,
            color="grey400",
        ))

        # Forked Repository
        controls.append(ft.Text("Forked Repository", weight=ft.FontWeight.BOLD, size=14))
        forked_repo_row = ft.Row(
            [
                ft.Dropdown(
                    ref=self.forked_repo_dropdown_ref,
                    label="Forked Repository",
                    value=self.config.get('FORKED_REPO', ''),
                    options=[],
                    hint_text="Select your fork",
                    expand=True,
                ),
                ft.IconButton(
                    icon=ft.icons.REFRESH,
                    tooltip="Refresh",
                    on_click=lambda e: self.page.run_task(self._refresh_forked_repos_async),
                ),
                ft.IconButton(
                    icon=ft.icons.DOWNLOAD,
                    tooltip="Clone",
                    on_click=self._clone_forked_repo,
                ),
            ],
            spacing=5,
        )
        controls.append(forked_repo_row)
        controls.append(ft.Text(
            "ℹ️ Your fork where changes will be made. Leave empty to auto-detect from document URL.",
            size=12,
            color="grey400",
        ))

        # General Options Section
        controls.append(self._create_section_header("⚙️ General Options"))

        # Dry Run Mode
        dry_run_checkbox = ft.Checkbox(
            label="🧪 Dry Run Mode (Test without making changes)",
            value=str(self.config.get('DRY_RUN', 'false')).lower() in ('true', '1', 'yes', 'on'),
        )
        self.entries['DRY_RUN'] = dry_run_checkbox
        controls.append(dry_run_checkbox)
        controls.append(ft.Text(
            "ℹ️ Simulates operations without creating actual GitHub issues/PRs",
            size=12,
            color="grey400",
        ))

        # Local Repo Path
        local_repo_path = ft.TextField(
            label="Local Repo Path",
            value=self.config.get('LOCAL_REPO_PATH', ''),
            hint_text="Path where repositories are cloned",
            expand=True,
        )
        self.entries['LOCAL_REPO_PATH'] = local_repo_path
        controls.append(local_repo_path)

        # Detected Repos
        controls.append(ft.Text("Detected Repos", weight=ft.FontWeight.BOLD, size=14))
        detected_repos_row = ft.Row(
            [
                ft.Dropdown(
                    ref=self.detected_repos_dropdown_ref,
                    label="Detected Repositories",
                    value="Scanning...",
                    options=[],
                    hint_text="Scanned local repositories",
                    expand=True,
                ),
                ft.ElevatedButton(
                    "🔄 Scan",
                    on_click=lambda e: self.page.run_task(self._scan_repos_async),
                ),
            ],
            spacing=5,
        )
        controls.append(detected_repos_row)

        # Help text
        controls.append(ft.Container(
            content=ft.Text(
                "💡 Repository Setup Guide:\n"
                "   • Local Repo Path: Where your fork repos are cloned (e.g., C:\\git\\repos)\n"
                "   • Detected Repos: Shows your local fork (e.g., yourname/repo)\n"
                "   • Target Repository: Upstream repo for PRs (e.g., microsoft/repo)\n"
                "   • Fork Workflow: Work on your fork locally, create PRs to upstream",
                size=12,
                color="grey400",
            ),
            padding=ft.padding.all(10),
            bgcolor="surfacevariant",
            border_radius=5,
            margin=ft.margin.only(top=10),
        ))

        controls.append(ft.Container(
            content=ft.Text(
                "💡 Getting Started:\n"
                "1. Create a GitHub Personal Access Token\n"
                "2. Configure GitHub repositories:\n"
                "   • Target Repository: Where PRs will be created\n"
                "   • Forked Repository: Your fork where changes are made\n"
                "3. Set Local Repo Path for automatic repository detection\n"
                "4. Configure AI provider in the AI tab (optional)\n"
                "5. Test your connection before processing items",
                size=12,
                color="blue400",
            ),
            padding=ft.padding.all(10),
            bgcolor="blue900",
            border_radius=5,
            margin=ft.margin.only(top=10),
        ))

        return ft.Container(
            content=ft.ListView(
                controls=controls,
                spacing=15,
                padding=20,
            ),
            expand=True,
        )

    def _create_ai_tab(self) -> ft.Container:
        """Create AI settings tab"""
        controls = []

        # AI Provider Section
        controls.append(self._create_section_header("🤖 AI Provider Configuration"))

        # Provider dropdown
        ai_provider = ft.Dropdown(
            label="AI Provider",
            value=self.config.get('AI_PROVIDER', 'none'),
            options=[
                ft.dropdown.Option("none", "None"),
                ft.dropdown.Option("claude", "Claude"),
                ft.dropdown.Option("chatgpt", "ChatGPT"),
                ft.dropdown.Option("github-copilot", "GitHub Copilot"),
                ft.dropdown.Option("ollama", "Ollama"),
            ],
            expand=True,
        )
        self.entries['AI_PROVIDER'] = ai_provider
        controls.append(ai_provider)

        # API Keys
        claude_key = ft.TextField(
            label="Claude API Key",
            password=True,
            can_reveal_password=True,
            value=self.config.get('CLAUDE_API_KEY', ''),
            hint_text="Get key at console.anthropic.com",
            expand=True,
        )
        self.entries['CLAUDE_API_KEY'] = claude_key
        controls.append(claude_key)

        chatgpt_key = ft.TextField(
            label="ChatGPT API Key",
            password=True,
            can_reveal_password=True,
            value=self.config.get('OPENAI_API_KEY', ''),
            hint_text="Get key at platform.openai.com/api-keys",
            expand=True,
        )
        self.entries['OPENAI_API_KEY'] = chatgpt_key
        controls.append(chatgpt_key)

        github_token = ft.TextField(
            label="GitHub Token (for Copilot) [defaults to GitHub PAT]",
            password=True,
            can_reveal_password=True,
            value=self.config.get('GITHUB_TOKEN', ''),
            hint_text="Defaults to GitHub PAT if empty",
            expand=True,
        )
        self.entries['GITHUB_TOKEN'] = github_token
        controls.append(github_token)

        # Ollama Configuration
        controls.append(self._create_section_header("🦙 Ollama Configuration"))

        ollama_url = ft.TextField(
            label="Ollama Server URL",
            value=self.config.get('OLLAMA_URL', ''),
            hint_text="http://localhost:11434",
            expand=True,
        )
        self.entries['OLLAMA_URL'] = ollama_url
        controls.append(ollama_url)

        ollama_api_key = ft.TextField(
            label="Ollama API Key (optional)",
            password=True,
            can_reveal_password=True,
            value=self.config.get('OLLAMA_API_KEY', ''),
            expand=True,
        )
        self.entries['OLLAMA_API_KEY'] = ollama_api_key
        controls.append(ollama_api_key)

        # Ollama Model
        ollama_model_row = ft.Row(
            [
                ft.Dropdown(
                    ref=self.ollama_model_dropdown_ref,
                    label="Ollama Model",
                    value=self.config.get('OLLAMA_MODEL', ''),
                    options=[],
                    hint_text="Click scan to load models",
                    expand=True,
                ),
                ft.ElevatedButton(
                    "🔍 Scan",
                    on_click=lambda e: self.page.run_task(self._scan_ollama_models_async),
                ),
            ],
            spacing=5,
        )
        controls.append(ollama_model_row)
        controls.append(ft.Text(
            "ℹ️ Click 🔍 to scan available models from your Ollama server.",
            size=12,
            color="grey400",
        ))

        # Help text
        controls.append(ft.Container(
            content=ft.Text(
                "💡 Tips:\n"
                "• Provider: Choose 'none' to disable AI (uses Copilot workflow)\n"
                "• Claude: Get key at console.anthropic.com\n"
                "• ChatGPT: Get key at platform.openai.com/api-keys\n"
                "• GitHub Copilot: Uses GitHub Models API (requires GitHub token)\n"
                "• GitHub Token: Auto-defaults to GitHub PAT if left empty\n"
                "• Ollama: Self-hosted AI (requires Ollama server running)\n"
                "• Cost: ~$0.01-0.05 per PR with AI, free with 'none' and Ollama\n"
                "• AI providers clone repos locally to make changes before pushing",
                size=12,
                color="blue400",
            ),
            padding=ft.padding.all(10),
            bgcolor="blue900",
            border_radius=5,
            margin=ft.margin.only(top=10),
        ))

        return ft.Container(
            content=ft.ListView(
                controls=controls,
                spacing=15,
                padding=20,
            ),
            expand=True,
        )

    def _create_section_header(self, text: str) -> ft.Container:
        """Create a section header"""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(text, size=18, weight=ft.FontWeight.BOLD),
                    ft.Divider(thickness=2, color="primary"),
                ],
                spacing=5,
            ),
            padding=ft.padding.only(top=20, bottom=10),
        )

    async def _scan_repos_async(self):
        """Scan for git repositories in the local repo path"""
        try:
            from pathlib import Path

            # Get the local repo path
            local_path_field = self.entries.get('LOCAL_REPO_PATH')
            if local_path_field:
                path_str = local_path_field.value.strip()
            else:
                path_str = self.config.get('LOCAL_REPO_PATH', '').strip()

            if not path_str:
                path_str = str(Path.home() / "Downloads" / "github_repos")

            base_path = Path(path_str)

            if not base_path.exists():
                if self.detected_repos_dropdown_ref.current:
                    self.detected_repos_dropdown_ref.current.value = 'No repos found (directory does not exist)'
                    self.detected_repos_dropdown_ref.current.options = []
                    self.page.update()
                return

            # Scan for git repositories
            repos = []
            try:
                for owner_dir in base_path.iterdir():
                    if not owner_dir.is_dir():
                        continue

                    for repo_dir in owner_dir.iterdir():
                        if not repo_dir.is_dir():
                            continue

                        git_dir = repo_dir / ".git"
                        if git_dir.exists():
                            repo_name = f"{owner_dir.name}/{repo_dir.name}"
                            repos.append(repo_name)

            except Exception as e:
                print(f"Error scanning repos: {e}")

            # Update dropdown
            if self.detected_repos_dropdown_ref.current:
                if repos:
                    repos.sort()
                    self.detected_repos_dropdown_ref.current.options = [
                        ft.dropdown.Option(repo) for repo in repos
                    ]
                    if len(repos) == 1:
                        self.detected_repos_dropdown_ref.current.value = repos[0]
                    else:
                        self.detected_repos_dropdown_ref.current.value = f'{len(repos)} repo(s) found - select one'
                else:
                    self.detected_repos_dropdown_ref.current.value = 'No git repositories found'
                    self.detected_repos_dropdown_ref.current.options = []

                self.page.update()

        except Exception as e:
            print(f"Error in _scan_repos_async: {e}")

    async def _load_target_repos_async(self):
        """Load target repos (with push/admin access) asynchronously"""
        def load_repos():
            try:
                github_token = self.config.get('GITHUB_PAT', '')
                if not github_token:
                    return

                from .workflow import GitHubRepoFetcher
                repo_fetcher = GitHubRepoFetcher(github_token)
                repos = repo_fetcher.fetch_repos_with_permissions(min_permission='push')
                self.target_repos = repo_fetcher.get_repo_names(repos)

                # Update UI on main thread
                if self.target_repo_dropdown_ref.current:
                    self.page.run_task(self._update_target_dropdown_async)

            except Exception as e:
                print(f"Error loading target repos: {e}")

        await asyncio.to_thread(load_repos)

    async def _update_target_dropdown_async(self):
        """Update the target repository dropdown"""
        try:
            if not self.target_repo_dropdown_ref.current:
                return

            options = []
            if self.target_repos:
                options.append(ft.dropdown.Option("--- Your Repos (with edit access) ---", disabled=True))
                options.extend([ft.dropdown.Option(repo) for repo in self.target_repos])

            self.target_repo_dropdown_ref.current.options = options
            self.page.update()

        except Exception as e:
            print(f"Error updating target dropdown: {e}")

    async def _refresh_target_repos_async(self):
        """Refresh target repositories"""
        await self._load_target_repos_async()

    async def _search_target_repos_async(self):
        """Search for repositories on GitHub"""
        if not self.target_repo_dropdown_ref.current:
            return

        query = self.target_repo_dropdown_ref.current.value.strip()
        if not query:
            return

        def search_repos():
            try:
                github_token = self.config.get('GITHUB_PAT', '')
                if not github_token:
                    return

                from .workflow import GitHubRepoFetcher
                repo_fetcher = GitHubRepoFetcher(github_token)
                repos = repo_fetcher.search_repositories(query, per_page=50)
                search_results = repo_fetcher.get_repo_names(repos)

                # Update UI
                if self.target_repo_dropdown_ref.current:
                    options = []
                    if self.target_repos:
                        options.append(ft.dropdown.Option("--- Your Repos (with edit access) ---", disabled=True))
                        options.extend([ft.dropdown.Option(repo) for repo in self.target_repos])

                    if search_results:
                        options.append(ft.dropdown.Option(f"--- Search Results for \"{query}\" ---", disabled=True))
                        options.extend([ft.dropdown.Option(repo) for repo in search_results])

                    self.target_repo_dropdown_ref.current.options = options
                    self.page.update()

            except Exception as e:
                print(f"Error searching repos: {e}")

        await asyncio.to_thread(search_repos)

    def _on_target_repo_search(self, e):
        """Handle typing in target repo field for auto-search"""
        # Debounce search - could be implemented with a timer
        pass

    async def _load_user_forks_async(self):
        """Load user's GitHub forks asynchronously"""
        def load_forks():
            try:
                github_token = self.config.get('GITHUB_PAT', '')
                if not github_token:
                    return

                from .workflow import GitHubRepoFetcher
                repo_fetcher = GitHubRepoFetcher(github_token)
                repos = repo_fetcher.fetch_user_repos(repo_type='owner')
                self.forked_repos = repo_fetcher.get_repo_names(repos)

                # Update UI
                if self.forked_repo_dropdown_ref.current:
                    self.page.run_task(self._update_forked_dropdown_async)

            except Exception as e:
                print(f"Error loading user forks: {e}")

        await asyncio.to_thread(load_forks)

    async def _update_forked_dropdown_async(self):
        """Update the forked repository dropdown with GitHub forks"""
        try:
            if not self.forked_repo_dropdown_ref.current:
                return

            options = []

            # Add local repos
            local_repo_path = self.config.get('LOCAL_REPO_PATH', '')
            if local_repo_path:
                try:
                    from .utils import LocalRepositoryScanner
                    local_repos = LocalRepositoryScanner.scan_local_repos(local_repo_path)
                    if local_repos:
                        options.append(ft.dropdown.Option("--- Local Repositories ---", disabled=True))
                        options.extend([ft.dropdown.Option(repo) for repo in local_repos])
                except Exception as e:
                    print(f"Error scanning local repos: {e}")

            # Add GitHub repos
            if self.forked_repos:
                options.append(ft.dropdown.Option("--- Your GitHub Repos ---", disabled=True))
                options.extend([ft.dropdown.Option(repo) for repo in self.forked_repos])

            self.forked_repo_dropdown_ref.current.options = options
            self.page.update()

        except Exception as e:
            print(f"Error updating forked dropdown: {e}")

    async def _refresh_forked_repos_async(self):
        """Refresh the forked repositories dropdown"""
        await self._load_user_forks_async()
        await self._update_forked_dropdown_async()

    def _clone_forked_repo(self, e):
        """Clone the selected forked repository to the local repo path"""
        if not self.forked_repo_dropdown_ref.current:
            return

        selected_repo = self.forked_repo_dropdown_ref.current.value.strip()

        if not selected_repo or selected_repo.startswith('---'):
            self._show_alert("Invalid Selection", "Please select a repository, not a section header.")
            return

        local_repo_path = self.config.get('LOCAL_REPO_PATH', '').strip()
        if not local_repo_path:
            self._show_alert("Local Path Not Configured", "Please configure the Local Repository Path in settings first.")
            return

        # Start clone in background
        self.page.run_task(lambda: self._clone_repo_async(selected_repo, local_repo_path))

    async def _clone_repo_async(self, repo_name: str, local_repo_path: str):
        """Clone repository asynchronously"""
        try:
            os.makedirs(local_repo_path, exist_ok=True)

            if '/' not in repo_name:
                self._show_alert("Invalid Repository", "Repository must be in 'owner/repo' format.")
                return

            folder_name = repo_name.split('/')[-1]
            target_path = os.path.join(local_repo_path, folder_name)

            if os.path.exists(target_path):
                # Show confirmation dialog
                self._show_alert(
                    "Directory Exists",
                    f"The directory '{folder_name}' already exists. Clone may fail if it's already a git repository."
                )
                return

            clone_url = f"https://github.com/{repo_name}.git"

            # Show progress
            self._show_alert("Cloning Repository", f"Cloning {repo_name}...\nThis may take a few moments.")

            # Run git clone
            result = await asyncio.to_thread(
                subprocess.run,
                ['git', 'clone', clone_url, target_path],
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode == 0:
                self._show_alert("Clone Successful", f"Successfully cloned {repo_name}!\n\nLocation: {folder_name}/")
                await self._refresh_forked_repos_async()
            else:
                error_msg = result.stderr if result.stderr else result.stdout
                self._show_alert("Clone Failed", f"Failed to clone {repo_name}.\n\nError:\n{error_msg}")

        except Exception as e:
            self._show_alert("Clone Error", f"An error occurred while cloning:\n{str(e)}")

    async def _scan_ollama_models_async(self):
        """Scan Ollama server for available models"""
        ollama_url = self.entries.get('OLLAMA_URL').value.strip() if 'OLLAMA_URL' in self.entries else ''

        if not ollama_url:
            self._show_alert("Ollama URL Required", "Please enter the Ollama Server URL first.")
            return

        if not ollama_url.startswith('http'):
            ollama_url = f"http://{ollama_url}"

        def scan_models():
            try:
                import requests

                ollama_api_key = self.entries.get('OLLAMA_API_KEY').value.strip() if 'OLLAMA_API_KEY' in self.entries else ''

                headers = {}
                if ollama_api_key:
                    headers['Authorization'] = f'Bearer {ollama_api_key}'

                response = requests.get(f"{ollama_url}/api/tags", headers=headers, timeout=10)
                response.raise_for_status()

                data = response.json()
                models = data.get('models', [])
                model_names = [model.get('name', '') for model in models if model.get('name')]

                # Update UI
                if self.ollama_model_dropdown_ref.current:
                    if model_names:
                        self.ollama_model_dropdown_ref.current.options = [
                            ft.dropdown.Option(name) for name in model_names
                        ]
                        if model_names:
                            self.ollama_model_dropdown_ref.current.value = model_names[0]
                        self.page.update()

                        models_text = "\n".join(f"• {name}" for name in model_names[:10])
                        if len(model_names) > 10:
                            models_text += f"\n\n...and {len(model_names) - 10} more"

                        self._show_alert("Models Found", f"Found {len(model_names)} model(s):\n\n{models_text}")
                    else:
                        self._show_alert("No Models Found", "No models found on the Ollama server.\n\nUse 'ollama pull <model>' to download models.")

            except requests.exceptions.ConnectionError:
                self._show_alert("Connection Error", f"Could not connect to Ollama server at:\n{ollama_url}\n\nMake sure Ollama is running and the URL is correct.")
            except Exception as e:
                self._show_alert("Scan Error", f"An error occurred while scanning for models:\n{str(e)}")

        await asyncio.to_thread(scan_models)

    def _test_connection(self, e):
        """Test connection to configured services"""
        config_values = self._get_config_values()

        results = []

        # Test GitHub
        if config_values.get('GITHUB_PAT'):
            try:
                from .github_api import GitHubAPI
                api = GitHubAPI(config_values.get('GITHUB_PAT'))
                results.append("GitHub: ✅ Token configured")

                if config_values.get('GITHUB_REPO'):
                    results.append(f"GitHub Repository: ✅ {config_values.get('GITHUB_REPO')}")
                else:
                    results.append("GitHub Repository: ⚠️ Not configured")
            except Exception as e:
                results.append(f"GitHub: ❌ Error - {str(e)}")
        else:
            results.append("GitHub: ❌ No token configured")

        # Test AI Provider
        ai_provider = config_values.get('AI_PROVIDER', 'none').lower()
        if ai_provider and ai_provider != 'none':
            try:
                from .ai_manager import AIManager
                ai_manager = AIManager()
                available, missing = ai_manager.check_ai_module_availability(ai_provider)

                if available:
                    results.append(f"AI Provider ({ai_provider}): ✅ Available")
                else:
                    results.append(f"AI Provider ({ai_provider}): ⚠️ Missing packages: {', '.join(missing)}")
            except Exception as e:
                results.append(f"AI Provider ({ai_provider}): ⚠️ Error - {str(e)}")
        else:
            results.append("AI Provider: ℹ️ Disabled (using standard method)")

        # Show results
        if results:
            self._show_alert(
                "Connection Test Results",
                "\n".join(results) + "\n\n💡 Full validation requires running the application."
            )

    def _clear_cache(self, e):
        """Clear all cached items"""
        def do_clear():
            if self.cache_manager:
                self.cache_manager.invalidate_cache()
                self._show_alert(
                    "Cache Cleared",
                    "All cached items have been cleared.\nFresh data will be loaded on next app start."
                )
            else:
                self._show_alert("Error", "Cache manager not available")

        # Show confirmation dialog
        self._show_confirmation(
            "Clear Cache",
            "Are you sure you want to clear all cached items?\n\nAll cached data will be removed.\nThe next time you open the app, it will auto-load fresh data.",
            on_confirm=do_clear
        )

    def _get_config_values(self) -> Dict[str, Any]:
        """Get configuration values from entries"""
        config_values = {}

        for key, widget in self.entries.items():
            if isinstance(widget, ft.Checkbox):
                config_values[key] = 'true' if widget.value else 'false'
            elif isinstance(widget, (ft.TextField, ft.Dropdown)):
                value = widget.value or ''
                if isinstance(value, str):
                    value = value.strip()
                config_values[key] = value

        # Handle dropdown values specially
        if self.target_repo_dropdown_ref.current:
            config_values['GITHUB_REPO'] = self.target_repo_dropdown_ref.current.value or ''
        if self.forked_repo_dropdown_ref.current:
            config_values['FORKED_REPO'] = self.forked_repo_dropdown_ref.current.value or ''
        if self.ollama_model_dropdown_ref.current:
            config_values['OLLAMA_MODEL'] = self.ollama_model_dropdown_ref.current.value or ''

        return config_values

    def _save_clicked(self, e):
        """Handle save button click"""
        try:
            config_values = self._get_config_values()

            # Validate required fields
            if not config_values.get('GITHUB_PAT'):
                self._show_alert(
                    "Missing Configuration",
                    "GitHub Personal Access Token is required for basic functionality."
                )
                return

            # Check AI provider setup
            ai_provider = config_values.get('AI_PROVIDER', '').strip().lower()
            if ai_provider and ai_provider not in ['none', '']:
                if ai_provider in ['chatgpt', 'claude', 'anthropic', 'github-copilot', 'copilot', 'github_copilot']:
                    try:
                        from .ai_manager import AIManager
                        ai_manager = AIManager()
                        available, missing = ai_manager.check_ai_module_availability(ai_provider)
                        if not available:
                            # Show warning but continue
                            self._show_alert(
                                "AI Modules Not Installed",
                                f"Settings saved, but AI provider '{ai_provider}' requires additional packages: {', '.join(missing)}\n\n"
                                f"You can install them later with:\npip install {' '.join(missing)}"
                            )
                    except ImportError:
                        pass

            # Save configuration
            if self.config_manager:
                success = self.config_manager.save_configuration(config_values)
            else:
                success = self._save_to_env_file(config_values)

            if success:
                self.result = config_values
                self._show_alert(
                    "Settings Saved",
                    "Settings saved successfully!\n\nChanges applied immediately - no restart needed! ✨"
                )
                self._close_dialog()
            else:
                self._show_alert("Save Error", "Failed to save settings to .env file.")

        except Exception as e:
            self._show_alert("Save Error", f"Error saving settings:\n{str(e)}")

    def _save_to_env_file(self, config_values: Dict[str, Any]) -> bool:
        """Fallback method to save configuration to .env file"""
        try:
            env_content = "# GitHub Pulse Configuration\n"
            env_content += "# Generated by Settings Dialog\n\n"

            for key, value in config_values.items():
                if value:
                    env_content += f"{key}={value}\n"
                else:
                    env_content += f"{key}=\n"

            env_path = os.path.join(os.getcwd(), '.env')
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(env_content)

            return True

        except Exception as e:
            print(f"Error saving to .env file: {e}")
            return False

    def _cancel_clicked(self, e):
        """Handle cancel button click"""
        self.result = None
        self._close_dialog()

    def _close_dialog(self):
        """Close the dialog"""
        # Use Flet 0.28+ API: page.close() instead of page.dialog
        if self.dialog_ref.current:
            self.page.close(self.dialog_ref.current)

        if self.on_result:
            self.on_result(self.result)

    def _show_alert(self, title: str, message: str):
        """Show an alert dialog"""
        def close_dlg(e):
            self.page.close(alert_dialog)

        alert_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.open(alert_dialog)

    def _show_confirmation(self, title: str, message: str, on_confirm=None, on_cancel=None):
        """Show a confirmation dialog"""
        def handle_yes(e):
            self.page.close(confirm_dialog)
            if on_confirm:
                on_confirm()

        def handle_no(e):
            self.page.close(confirm_dialog)
            if on_cancel:
                on_cancel()

        confirm_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("No", on_click=handle_no),
                ft.FilledButton("Yes", on_click=handle_yes),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.open(confirm_dialog)
