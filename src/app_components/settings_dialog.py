"""
Settings Dialog
GUI for configuring application settings (Flet version)
"""

import flet as ft
# Compatibility fix for Flet 0.28+ (Icons vs icons, Colors vs colors)
ft.icons = ft.Icons
ft.colors = ft.Colors
from typing import Dict, Any, Optional, List, Tuple
import os
import asyncio
import sys
import subprocess


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

        # Dropdown refs
        self.detected_repos_dropdown_ref = ft.Ref[ft.Dropdown]()
        self.ollama_model_dropdown_ref = ft.Ref[ft.Dropdown]()

        # Package checker refs
        self.package_status_ref = ft.Ref[ft.Container]()

    def show(self, on_result=None):
        """Show the settings dialog"""
        try:
            print("SettingsDialog.show() called")
            self.on_result = on_result

            # Create the dialog
            print("Creating dialog...")
            dialog = self._create_dialog()
            print(f"Dialog created: {dialog}")

            # Always set the dialog ref to the current dialog instance
            print("Setting dialog_ref.current to new dialog instance")
            self.dialog_ref.current = dialog

            # Use Flet 0.28+ API: page.open() instead of page.dialog
            print("Opening dialog with page.open()...")
            self.page.open(dialog)
            # Ensure UI updates immediately (useful when console is not visible)
            try:
                self.page.update()
            except Exception:
                pass
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
        # Load cached Ollama models
        await self._load_cached_ollama_models()
        # Check packages for current AI provider
        await self._check_packages_for_current_provider()

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
        controls.append(self._create_section_header("🐙 GitHub Personal Access Token"))

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
                "   • Note: Target and Fork repositories are configured in the main GUI",
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
                "2. Configure GitHub repositories in the main GUI\n"
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

        # Package Status Section (at the top)
        controls.append(ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Package Status", size=16, weight=ft.FontWeight.BOLD),
                    ft.IconButton(
                        icon=ft.icons.REFRESH,
                        tooltip="Refresh package status",
                        on_click=lambda e: self.page.run_task(self._check_packages_for_current_provider),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(
                    ref=self.package_status_ref,
                    content=ft.Row([
                        ft.ProgressRing(width=20, height=20),
                        ft.Text("Checking packages...", color=ft.colors.BLUE),
                    ]),
                    padding=10,
                    bgcolor=ft.colors.BLUE_100,
                    border_radius=5,
                ),
            ], spacing=10),
            padding=ft.padding.only(bottom=10),
        ))

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
            on_change=lambda e: self.page.run_task(self._check_packages_for_current_provider),
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
        ollama_model = ft.Dropdown(
            ref=self.ollama_model_dropdown_ref,
            label="Ollama Model",
            value=self.config.get('OLLAMA_MODEL', ''),
            options=[],
            hint_text="Click scan to load models",
            expand=True,
        )
        self.entries['OLLAMA_MODEL'] = ollama_model

        ollama_model_row = ft.Row(
            [
                ollama_model,
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

    def _check_ai_packages(self, provider_name: str) -> Tuple[bool, List[str]]:
        """Check if required packages for AI provider are installed"""
        try:
            from .ai_manager import AIManager
            ai_manager = AIManager()
            available, missing = ai_manager.check_ai_module_availability(provider_name)
            return available, missing
        except Exception as e:
            print(f"Error checking AI packages: {e}")
            return False, []

    def _detect_environment(self) -> Tuple[bool, str]:
        """Detect if running in virtual environment"""
        in_venv = (hasattr(sys, 'real_prefix') or
                   (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
                   os.environ.get('VIRTUAL_ENV') is not None)

        if in_venv:
            venv_path = os.environ.get('VIRTUAL_ENV', sys.prefix)
            venv_name = os.path.basename(venv_path)
            return True, venv_name
        else:
            return False, "system-wide"

    async def _load_cached_ollama_models(self):
        """Load cached Ollama models on dialog open"""
        if not self.cache_manager:
            return

        try:
            # Get Ollama URL to use as cache identifier
            ollama_url = self.config.get('OLLAMA_URL', '').strip()
            if not ollama_url:
                return

            # Load cached models
            def load_cache():
                cached_data = self.cache_manager.load_from_cache('ollama_models', ollama_url)
                if cached_data:
                    # Extract model names from cache format
                    return [item['name'] for item in cached_data if 'name' in item]
                return []

            cached_models = await asyncio.to_thread(load_cache)

            if cached_models and self.ollama_model_dropdown_ref.current:
                # Update dropdown with cached models
                self.ollama_model_dropdown_ref.current.options = [
                    ft.dropdown.Option(model) for model in cached_models
                ]

                # Restore saved selection
                saved_model = self.config.get('OLLAMA_MODEL', '')
                if saved_model and saved_model in cached_models:
                    self.ollama_model_dropdown_ref.current.value = saved_model
                elif cached_models:
                    # If saved model not in list, select first one
                    self.ollama_model_dropdown_ref.current.value = cached_models[0]

                self.page.update()
                print(f"Loaded {len(cached_models)} cached Ollama models")

        except Exception as e:
            print(f"Error loading cached Ollama models: {e}")

    async def _check_packages_for_current_provider(self):
        """Check packages for the currently selected AI provider"""
        if not self.package_status_ref.current:
            return

        # Get current provider selection
        ai_provider_dropdown = self.entries.get('AI_PROVIDER')
        if not ai_provider_dropdown:
            return

        provider = ai_provider_dropdown.value
        if not provider or provider == 'none':
            self.package_status_ref.current.content = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.INFO, color=ft.colors.BLUE),
                    ft.Text("No AI provider selected", color=ft.colors.BLUE),
                ]),
                padding=10,
                bgcolor=ft.colors.BLUE_100,
                border_radius=5,
            )
            self.page.update()
            return

        # Check packages in background thread
        def check_packages():
            return self._check_ai_packages(provider)

        available, missing = await asyncio.to_thread(check_packages)

        # Update UI with results
        if available:
            self.package_status_ref.current.content = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.CHECK_CIRCLE, color=ft.colors.GREEN),
                    ft.Text(f"All required packages for {provider} are installed", color=ft.colors.GREEN),
                ]),
                padding=10,
                bgcolor=ft.colors.GREEN_100,
                border_radius=5,
            )
        else:
            in_venv, env_name = self._detect_environment()
            env_text = f"Virtual environment: {env_name}" if in_venv else "System-wide installation"

            self.package_status_ref.current.content = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.WARNING, color=ft.colors.ORANGE),
                        ft.Text(f"Missing packages for {provider}", color=ft.colors.ORANGE, weight=ft.FontWeight.BOLD),
                    ]),
                    ft.Text(f"Required: {', '.join(missing)}", size=12),
                    ft.Text(f"Environment: {env_text}", size=12, italic=True),
                    ft.ElevatedButton(
                        "Install Packages",
                        icon=ft.icons.DOWNLOAD,
                        on_click=lambda e: self._install_packages(missing, provider),
                    ),
                ], spacing=5),
                padding=10,
                bgcolor=ft.colors.ORANGE_100,
                border_radius=5,
            )

        self.page.update()

    def _install_packages(self, packages: List[str], provider: str):
        """Install missing packages"""
        in_venv, env_name = self._detect_environment()
        env_text = f"virtual environment '{env_name}'" if in_venv else "system-wide (may require administrator rights)"

        # Create confirmation dialog
        package_list = ', '.join(packages)
        message = (f"Install the following packages for {provider}?\n\n"
                  f"Packages: {package_list}\n\n"
                  f"Installation location: {env_text}\n\n"
                  f"Command: pip install {' '.join(packages)}")

        def handle_install(e):
            self.page.close(install_dialog)
            # Run installation in background
            self.page.run_task(lambda: self._do_install_packages(packages, provider))

        def handle_cancel(e):
            self.page.close(install_dialog)

        install_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Install AI Packages"),
            content=ft.Text(message),
            actions=[
                ft.TextButton("Cancel", on_click=handle_cancel),
                ft.FilledButton("Install", on_click=handle_install),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.open(install_dialog)

    async def _do_install_packages(self, packages: List[str], provider: str):
        """Actually install the packages"""
        in_venv, env_name = self._detect_environment()

        # Update status to show installation in progress
        if self.package_status_ref.current:
            self.package_status_ref.current.content = ft.Container(
                content=ft.Row([
                    ft.ProgressRing(width=20, height=20),
                    ft.Text(f"Installing packages for {provider}...", color=ft.colors.BLUE),
                ]),
                padding=10,
                bgcolor=ft.colors.BLUE_100,
                border_radius=5,
            )
            self.page.update()

        # Install packages in background thread
        def install():
            try:
                for package in packages:
                    print(f"Installing {package}...")
                    pip_cmd = [sys.executable, '-m', 'pip', 'install', package]
                    result = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=300)

                    # If direct install fails and we're not in venv, try with --user flag
                    if result.returncode != 0 and not in_venv:
                        print(f"  Direct installation failed, trying with --user flag...")
                        pip_cmd_user = [sys.executable, '-m', 'pip', 'install', '--user', package]
                        result = subprocess.run(pip_cmd_user, capture_output=True, text=True, timeout=300)

                    if result.returncode != 0:
                        return False, f"Failed to install {package}: {result.stderr}"

                return True, "All packages installed successfully"

            except subprocess.TimeoutExpired:
                return False, "Installation timed out"
            except Exception as e:
                return False, f"Error installing packages: {str(e)}"

        success, message = await asyncio.to_thread(install)

        # Show result and offer to restart
        if success:
            def handle_restart(e):
                self.page.close(result_dialog)
                self._restart_application()

            def handle_later(e):
                self.page.close(result_dialog)
                # Re-check packages after installation
                self.page.run_task(self._check_packages_for_current_provider)

            result_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Installation Complete"),
                content=ft.Text(f"{message}\n\nThe application needs to restart to use the newly installed packages."),
                actions=[
                    ft.TextButton("Restart Later", on_click=handle_later),
                    ft.FilledButton("Restart Now", on_click=handle_restart),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            self.page.open(result_dialog)
        else:
            self._show_alert("Installation Failed", message)
            # Re-check packages to update status
            await self._check_packages_for_current_provider()

    def _restart_application(self):
        """Restart the application"""
        try:
            # Close the dialog first
            if self.dialog_ref.current:
                self.page.close(self.dialog_ref.current)

            # Show restart message
            restart_msg = ft.SnackBar(
                content=ft.Text("Restarting application..."),
                bgcolor=ft.colors.BLUE,
            )
            self.page.open(restart_msg)
            self.page.update()

            # Restart the application
            python = sys.executable
            os.execl(python, python, *sys.argv)
        except Exception as e:
            self._show_alert("Restart Failed", f"Could not restart application: {str(e)}\n\nPlease restart manually.")

    async def _install_and_save(self, packages: List[str], provider: str, config_values: Dict[str, Any]):
        """Install packages and then save configuration"""
        # Install packages
        in_venv, _ = self._detect_environment()

        def install():
            try:
                for package in packages:
                    print(f"Installing {package}...")
                    pip_cmd = [sys.executable, '-m', 'pip', 'install', package]
                    result = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=300)

                    # If direct install fails and we're not in venv, try with --user flag
                    if result.returncode != 0 and not in_venv:
                        print(f"  Direct installation failed, trying with --user flag...")
                        pip_cmd_user = [sys.executable, '-m', 'pip', 'install', '--user', package]
                        result = subprocess.run(pip_cmd_user, capture_output=True, text=True, timeout=300)

                    if result.returncode != 0:
                        return False, f"Failed to install {package}: {result.stderr}"

                return True, "All packages installed successfully"

            except subprocess.TimeoutExpired:
                return False, "Installation timed out"
            except Exception as e:
                return False, f"Error installing packages: {str(e)}"

        success, message = await asyncio.to_thread(install)

        if success:
            # Save configuration after successful installation
            self._do_save(config_values)

            # Offer to restart
            def handle_restart(e):
                self.page.close(restart_dialog)
                self._restart_application()

            def handle_later(e):
                self.page.close(restart_dialog)

            restart_dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Installation Complete"),
                content=ft.Text(
                    f"Packages installed successfully!\n"
                    f"Settings have been saved.\n\n"
                    f"The application needs to restart to use the newly installed packages."
                ),
                actions=[
                    ft.TextButton("Restart Later", on_click=handle_later),
                    ft.FilledButton("Restart Now", on_click=handle_restart),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            self.page.open(restart_dialog)
        else:
            self._show_alert("Installation Failed", f"{message}\n\nSettings were not saved.")

    def _do_save(self, config_values: Dict[str, Any]):
        """Actually save the configuration"""
        try:
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

                # Cache the models
                if self.cache_manager and model_names:
                    # Convert to cache format (list of dicts)
                    cache_data = [{'name': name} for name in model_names]
                    self.cache_manager.save_to_cache('ollama_models', ollama_url, cache_data)
                    print(f"Cached {len(model_names)} Ollama models")

                # Update UI
                if self.ollama_model_dropdown_ref.current:
                    if model_names:
                        self.ollama_model_dropdown_ref.current.options = [
                            ft.dropdown.Option(name) for name in model_names
                        ]

                        # Restore saved selection if it exists in the list
                        saved_model = self.config.get('OLLAMA_MODEL', '')
                        if saved_model and saved_model in model_names:
                            self.ollama_model_dropdown_ref.current.value = saved_model
                        elif model_names:
                            # Otherwise select first model
                            self.ollama_model_dropdown_ref.current.value = model_names[0]

                        self.page.update()

                        models_text = "\n".join(f"• {name}" for name in model_names[:10])
                        if len(model_names) > 10:
                            models_text += f"\n\n...and {len(model_names) - 10} more"

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
                if ai_provider in ['chatgpt', 'claude', 'anthropic', 'github-copilot', 'copilot', 'github_copilot', 'ollama']:
                    available, missing = self._check_ai_packages(ai_provider)
                    if not available and missing:
                        # Offer to install missing packages
                        in_venv, env_name = self._detect_environment()
                        env_text = f"virtual environment '{env_name}'" if in_venv else "system-wide"

                        def handle_install_and_save(e):
                            self.page.close(package_warning_dialog)
                            # Install packages and then save
                            self.page.run_task(lambda: self._install_and_save(missing, ai_provider, config_values))

                        def handle_save_anyway(e):
                            self.page.close(package_warning_dialog)
                            # Continue with save
                            self._do_save(config_values)

                        def handle_cancel_save(e):
                            self.page.close(package_warning_dialog)

                        package_warning_dialog = ft.AlertDialog(
                            modal=True,
                            title=ft.Text("Missing AI Packages"),
                            content=ft.Text(
                                f"AI provider '{ai_provider}' requires additional packages:\n\n"
                                f"{', '.join(missing)}\n\n"
                                f"Installation location: {env_text}\n\n"
                                f"Would you like to install them now?"
                            ),
                            actions=[
                                ft.TextButton("Cancel", on_click=handle_cancel_save),
                                ft.TextButton("Save Without Installing", on_click=handle_save_anyway),
                                ft.FilledButton("Install & Save", on_click=handle_install_and_save),
                            ],
                            actions_alignment=ft.MainAxisAlignment.END,
                        )

                        self.page.open(package_warning_dialog)
                        return  # Don't save yet, wait for user choice

            # Save configuration (packages are already installed or not needed)
            self._do_save(config_values)

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
