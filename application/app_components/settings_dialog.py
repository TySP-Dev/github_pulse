"""
Settings Dialog
GUI for configuring application settings
"""

import tkinter as tk
import threading
import subprocess
from tkinter import ttk, messagebox, scrolledtext
from typing import Dict, Any, Optional
import sys
import os


class SettingsDialog:
    """Settings configuration dialog"""
    
    def __init__(self, parent, config: Dict[str, Any], config_manager=None, cache_manager=None):
        self.parent = parent
        self.config = config.copy()
        self.config_manager = config_manager
        self.cache_manager = cache_manager
        self.result = None
        self.entries = {}
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("⚙️ Settings")
        self.dialog.geometry("900x1000")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        self._create_widgets()
        self._bind_events()
    
    def _create_widgets(self):
        """Create dialog widgets"""
        # Main frame with scrollbar
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabbed settings
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Create tabs
        self._create_general_tab(notebook)
        self._create_ai_tab(notebook)
        # Removed: self._create_dataverse_tab(notebook) - Azure DevOps/Dataverse specific
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(10, 0))

        # Buttons
        ttk.Button(buttons_frame, text="💾 Save Settings", command=self._save_clicked).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(buttons_frame, text="❌ Cancel", command=self._cancel_clicked).pack(side=tk.RIGHT)
        ttk.Button(buttons_frame, text="🗑️ Clear Cache", command=self._clear_cache).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(buttons_frame, text="Test Connection", command=self._test_connection).pack(side=tk.LEFT)
        
        # Center dialog after everything is created
        self._center_dialog()
    
    def _create_general_tab(self, notebook):
        """Create general settings tab"""
        general_frame = ttk.Frame(notebook)
        notebook.add(general_frame, text="General")
        
        # Scrollable frame
        canvas = tk.Canvas(general_frame)
        scrollbar = ttk.Scrollbar(general_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Configure column weights for proper expansion
        scrollable_frame.columnconfigure(1, weight=1)
        
        current_row = 0

        # REMOVED: Azure DevOps Configuration section
        # This was specific to Azure DevOps integration

        # GitHub section
        self._create_section_header(scrollable_frame, current_row, "🐙 GitHub Configuration")
        current_row += 1
        
        self._create_label_entry(scrollable_frame, current_row, "Personal Access Token:", 'GITHUB_PAT', password=True, width=60)
        current_row += 1
        
        self._create_target_repo_dropdown(scrollable_frame, current_row)
        current_row += 1

        self._create_forked_repo_dropdown(scrollable_frame, current_row)
        current_row += 1
        
        # General options section
        self._create_section_header(scrollable_frame, current_row, "⚙️ General Options")
        current_row += 1
        
        self._create_dry_run_checkbox(scrollable_frame, current_row)
        current_row += 1
        
        self._create_label_entry(scrollable_frame, current_row, "Local Repo Path:", 'LOCAL_REPO_PATH', width=60)
        current_row += 1

        # Detected repos dropdown
        ttk.Label(scrollable_frame, text="Detected Repos:", font=('Arial', 10, 'bold')).grid(
            row=current_row, column=0, sticky=tk.W, pady=5, padx=10)

        # Frame for dropdown and refresh button
        detected_frame = ttk.Frame(scrollable_frame)
        detected_frame.grid(row=current_row, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)

        self.detected_repos_var = tk.StringVar(value='Scanning...')
        self.detected_repos_dropdown = ttk.Combobox(detected_frame, textvariable=self.detected_repos_var,
                                                   state='readonly', width=45)
        self.detected_repos_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.detected_repos_dropdown.bind('<<ComboboxSelected>>', self._on_repo_selected)

        refresh_button = ttk.Button(detected_frame, text="🔄 Scan", command=self._scan_repos, width=8)
        refresh_button.pack(side=tk.LEFT, padx=(5, 0))
        current_row += 1

        # Help text for local repo path
        repo_help = ttk.Label(scrollable_frame,
                             text="💡 Repository Setup Guide:\n"
                             "   • Local Repo Path: Where your fork repos are cloned (e.g., C:\\git\\repos)\n"
                             "   • Detected Repos: Shows your local fork (e.g., yourname/repo)\n"
                             "   • Target Repository: Upstream repo for PRs (e.g., microsoft/repo)\n"
                             "   • Fork Workflow: Work on your fork locally, create PRs to upstream",
                             font=('Arial', 9), foreground='gray', justify=tk.LEFT, wraplength=850)
        repo_help.grid(row=current_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 20), padx=10)
        current_row += 1

        # Help text
        help_text = ttk.Label(scrollable_frame, text="💡 Getting Started:\n"
                             "1. Create a GitHub Personal Access Token\n"
                             "2. Configure GitHub repositories:\n"
                             "   • Target Repository: Where PRs will be created\n"
                             "   • Forked Repository: Your fork where changes are made\n"
                             "3. Set Local Repo Path for automatic repository detection\n"
                             "4. Configure AI provider in the AI tab (optional)\n"
                             "5. Test your connection before processing items",
                             font=('Arial', 9), foreground='blue', justify=tk.LEFT, wraplength=850)
        help_text.grid(row=current_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(20, 30), padx=10)

        # Scan for repos after creating the UI
        self.dialog.after(100, self._scan_repos)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    def _create_ai_tab(self, notebook):
        """Create AI settings tab"""
        ai_frame = ttk.Frame(notebook)
        notebook.add(ai_frame, text="AI Providers")
        
        # Scrollable frame
        canvas = tk.Canvas(ai_frame)
        scrollbar = ttk.Scrollbar(ai_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # AI Provider section
        self._create_section_header(scrollable_frame, 0, "🤖 AI Provider Configuration")
        
        # Provider dropdown
        ttk.Label(scrollable_frame, text="AI Provider:", font=('Arial', 10, 'bold')).grid(
            row=1, column=0, sticky=tk.W, pady=5, padx=10)
        
        self.ai_provider_var = tk.StringVar(value=self.config.get('AI_PROVIDER', 'none'))
        provider_dropdown = ttk.Combobox(scrollable_frame, textvariable=self.ai_provider_var,
                                       values=['none', 'claude', 'chatgpt', 'github-copilot', 'ollama'], state='readonly', width=47)
        provider_dropdown.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)
        self.entries['AI_PROVIDER'] = self.ai_provider_var
        
        # API Keys
        self._create_label_entry(scrollable_frame, 2, "Claude API Key:", 'CLAUDE_API_KEY', password=True)
        self._create_label_entry(scrollable_frame, 3, "ChatGPT API Key:", 'OPENAI_API_KEY', password=True)
        self._create_label_entry(scrollable_frame, 4, "GitHub Token (for Copilot) [defaults to GitHub PAT]:", 'GITHUB_TOKEN', password=True)

        # Ollama Configuration
        self._create_label_entry(scrollable_frame, 5, "Ollama Server URL:", 'OLLAMA_URL')
        self._create_label_entry(scrollable_frame, 6, "Ollama API Key (optional):", 'OLLAMA_API_KEY', password=True)

        # Ollama Model Dropdown
        self._create_ollama_model_dropdown(scrollable_frame, 7)

        # Help text
        help_text = ttk.Label(scrollable_frame, text="\n💡 Tips:\n"
                             "• Provider: Choose 'none' to disable AI (uses Copilot workflow)\n"
                             "• Claude: Get key at console.anthropic.com\n"
                             "• ChatGPT: Get key at platform.openai.com/api-keys\n"
                             "• GitHub Copilot: Uses GitHub Models API (requires GitHub token)\n"
                             "• GitHub Token: Auto-defaults to GitHub PAT if left empty\n"
                             "• Ollama: Self-hosted AI (requires Ollama server running)\n"
                             "• Cost: ~$0.01-0.05 per PR with AI, free with 'none' and Ollama\n"
                             "• AI providers clone repos locally to make changes before pushing",
                             font=('Arial', 9), foreground='blue', justify=tk.LEFT, wraplength=800)
        help_text.grid(row=8, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=20, padx=10)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
    
    # REMOVED: _create_dataverse_tab method
    # This was specific to Azure DevOps/Dataverse integration
    # def _create_dataverse_tab(self, notebook):
    #     """Create Dataverse/PowerApp settings tab"""
    #     ...
    
    def _create_section_header(self, parent, row: int, text: str):
        """Create a section header"""
        header_frame = ttk.Frame(parent)
        header_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(20, 10), padx=10)
        header_frame.columnconfigure(1, weight=1)
        
        ttk.Label(header_frame, text=text, font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky=tk.W)
        ttk.Separator(header_frame, orient='horizontal').grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0))
    
    def _create_label_entry(self, parent, row: int, label_text: str, config_key: str, 
                           password: bool = False, width: int = 50, multiline: bool = False):
        """Create a label and entry pair"""
        ttk.Label(parent, text=label_text, font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=5, padx=10)
        
        if multiline:
            entry = scrolledtext.ScrolledText(parent, height=3, width=width)
            entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)
            entry.insert('1.0', self.config.get(config_key, '') or '')
        elif password:
            entry = ttk.Entry(parent, show="*", width=width)
            entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)
            
            # Special handling for GITHUB_TOKEN - show placeholder if using default
            if config_key == 'GITHUB_TOKEN':
                github_token = self.config.get('GITHUB_TOKEN', '').strip()
                github_pat = self.config.get('GITHUB_PAT', '').strip()
                if not github_token and github_pat:
                    # Show placeholder for defaulted value, but don't actually set it
                    entry.config(foreground='gray')
                    entry.insert(0, '(using GitHub PAT)')
                    
                    # Add event handlers to clear placeholder on focus
                    def on_focus_in(event):
                        if entry.get() == '(using GitHub PAT)':
                            entry.delete(0, tk.END)
                            entry.config(foreground='black')
                    
                    def on_focus_out(event):
                        if not entry.get():
                            entry.config(foreground='gray')
                            entry.insert(0, '(using GitHub PAT)')
                    
                    entry.bind('<FocusIn>', on_focus_in)
                    entry.bind('<FocusOut>', on_focus_out)
                else:
                    entry.insert(0, github_token)
            else:
                entry.insert(0, self.config.get(config_key, '') or '')
        else:
            entry = ttk.Entry(parent, width=width)
            entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)
            entry.insert(0, self.config.get(config_key, '') or '')
        
        self.entries[config_key] = entry
        parent.columnconfigure(1, weight=1)

    def _create_target_repo_dropdown(self, parent, row: int):
        """Create target repository dropdown with search functionality"""
        ttk.Label(parent, text="Target Repository:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=5, padx=10)

        # Frame for dropdown, search entry, and buttons
        dropdown_frame = ttk.Frame(parent)
        dropdown_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)
        dropdown_frame.columnconfigure(0, weight=1)

        # Placeholder for target repos
        self.target_repos = []

        # Combobox for target repo (searchable)
        self.target_repo_var = tk.StringVar(value=self.config.get('GITHUB_REPO', ''))
        self.target_repo_dropdown = ttk.Combobox(dropdown_frame, textvariable=self.target_repo_var,
                                                 values=[''], width=50)
        self.target_repo_dropdown.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.entries['GITHUB_REPO'] = self.target_repo_var

        # Bind typing event for search
        self.target_repo_dropdown.bind('<KeyRelease>', self._on_target_repo_search)

        # Refresh button
        refresh_btn = ttk.Button(dropdown_frame, text="🔄", width=3,
                               command=self._refresh_target_repos)
        refresh_btn.grid(row=0, column=1, padx=(0, 2))

        # Search button
        search_btn = ttk.Button(dropdown_frame, text="🔍", width=3,
                              command=self._search_target_repos)
        search_btn.grid(row=0, column=2)

        # Help text for target repo
        help_label = ttk.Label(parent,
                             text="  ℹ️ Upstream repo where PRs will be created. Type to search all GitHub repos.",
                             font=('Arial', 9), foreground='gray')
        help_label.grid(row=row+1, column=0, columnspan=3, sticky=tk.W, padx=10)

        # Start async loading of user's repos with edit access
        self.dialog.after(100, self._load_target_repos_async)

    def _create_forked_repo_dropdown(self, parent, row: int):
        """Create forked repository dropdown with local repo detection"""
        ttk.Label(parent, text="Forked Repository:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=5, padx=10)
        
        # Frame for dropdown and refresh button
        dropdown_frame = ttk.Frame(parent)
        dropdown_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)
        dropdown_frame.columnconfigure(0, weight=1)
        
        # Initial options
        repo_options = ['']  # Empty option
        
        # Add local repositories
        local_repo_path = self.config.get('LOCAL_REPO_PATH', '')
        if local_repo_path:
            try:
                from .utils import LocalRepositoryScanner
                local_repos = LocalRepositoryScanner.scan_local_repos(local_repo_path)
                if local_repos:
                    repo_options.append('--- Local Repositories ---')
                    repo_options.extend(local_repos)
            except Exception as e:
                print(f"Error scanning local repos: {e}")
        
        # Placeholder for user's forks (will be populated asynchronously)
        self.forked_repos = []
        
        self.forked_repo_var = tk.StringVar(value=self.config.get('FORKED_REPO', ''))
        self.forked_repo_dropdown = ttk.Combobox(dropdown_frame, textvariable=self.forked_repo_var,
                                               values=repo_options, width=50)
        self.forked_repo_dropdown.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.entries['FORKED_REPO'] = self.forked_repo_var
        
        # Refresh button
        refresh_btn = ttk.Button(dropdown_frame, text="🔄", width=3,
                               command=self._refresh_forked_repos)
        refresh_btn.grid(row=0, column=1, padx=(0, 2))

        # Clone button
        clone_btn = ttk.Button(dropdown_frame, text="📥", width=3,
                              command=self._clone_forked_repo)
        clone_btn.grid(row=0, column=2)

        # Help text for forked repo
        help_label = ttk.Label(parent, 
                             text="  ℹ️ Your fork where changes will be made. Leave empty to auto-detect from document URL.",
                             font=('Arial', 9), foreground='gray')
        help_label.grid(row=row+1, column=0, columnspan=3, sticky=tk.W, padx=10)
        
        # Start async loading of user's forks
        self.dialog.after(100, self._load_user_forks_async)
    
    def _refresh_forked_repos(self):
        """Refresh the forked repositories dropdown"""
        self._load_user_forks_async()
        
        # Also refresh local repos
        local_repo_path = self.config.get('LOCAL_REPO_PATH', '')
        if local_repo_path:
            try:
                from .utils import LocalRepositoryScanner
                local_repos = LocalRepositoryScanner.scan_local_repos(local_repo_path)
                
                # Update dropdown with current values plus refreshed local repos
                current_values = list(self.forked_repo_dropdown['values'])
                
                # Remove old local repos section
                if '--- Local Repositories ---' in current_values:
                    start_idx = current_values.index('--- Local Repositories ---')
                    # Find where GitHub repos start or end of list
                    end_idx = len(current_values)
                    for i in range(start_idx + 1, len(current_values)):
                        if current_values[i].startswith('--- ') and 'GitHub' in current_values[i]:
                            end_idx = i
                            break
                    
                    # Remove local repos section
                    current_values = current_values[:start_idx] + current_values[end_idx:]
                
                # Add refreshed local repos
                if local_repos:
                    current_values.insert(1, '--- Local Repositories ---')
                    for i, repo in enumerate(local_repos):
                        current_values.insert(2 + i, repo)
                
                self.forked_repo_dropdown['values'] = current_values
                
            except Exception as e:
                print(f"Error refreshing local repos: {e}")

    def _clone_forked_repo(self):
        """Clone the selected forked repository to the local repo path"""
        # Get selected repository
        selected_repo = self.forked_repo_var.get().strip()

        # Validate selection
        if not selected_repo:
            messagebox.showwarning("No Repository Selected",
                                 "Please select a repository to clone.")
            return

        # Check if it's a section header
        if selected_repo.startswith('---'):
            messagebox.showwarning("Invalid Selection",
                                 "Please select a repository, not a section header.")
            return

        # Get local repo path
        local_repo_path = self.config.get('LOCAL_REPO_PATH', '').strip()
        if not local_repo_path:
            messagebox.showwarning("Local Path Not Configured",
                                 "Please configure the Local Repository Path in settings first.")
            return

        # Create directory if it doesn't exist
        try:
            os.makedirs(local_repo_path, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Directory Error",
                               f"Could not create local repository directory:\n{str(e)}")
            return

        # Extract repo name (handle both "owner/repo" and URLs)
        repo_name = selected_repo
        if repo_name.startswith('http'):
            # Extract from URL
            parts = repo_name.rstrip('/').split('/')
            if len(parts) >= 2:
                repo_name = f"{parts[-2]}/{parts[-1]}"
            else:
                messagebox.showerror("Invalid Repository",
                                   "Could not parse repository name from URL.")
                return

        # Validate format "owner/repo"
        if '/' not in repo_name:
            messagebox.showerror("Invalid Repository",
                               "Repository must be in 'owner/repo' format.")
            return

        # Extract just the repo name for the folder
        folder_name = repo_name.split('/')[-1]
        target_path = os.path.join(local_repo_path, folder_name)

        # Check if directory already exists
        if os.path.exists(target_path):
            response = messagebox.askyesno("Directory Exists",
                                          f"The directory '{folder_name}' already exists.\n\n"
                                          f"Do you want to continue anyway?\n"
                                          f"(This may fail if it's already a git repository)")
            if not response:
                return

        # Construct clone URL
        clone_url = f"https://github.com/{repo_name}.git"

        # Clone in background thread
        def clone_repo():
            try:
                # Run git clone
                result = subprocess.run(
                    ['git', 'clone', clone_url, target_path],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )

                # Update UI on main thread
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: self._handle_clone_result(result, repo_name, folder_name))

            except subprocess.TimeoutExpired:
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: messagebox.showerror(
                        "Clone Timeout",
                        f"Cloning {repo_name} timed out after 5 minutes."))
            except FileNotFoundError:
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: messagebox.showerror(
                        "Git Not Found",
                        "Git is not installed or not found in PATH.\n\n"
                        "Please install Git from: https://git-scm.com/downloads"))
            except Exception as e:
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: messagebox.showerror(
                        "Clone Error",
                        f"An error occurred while cloning:\n{str(e)}"))

        # Show progress message
        messagebox.showinfo("Cloning Repository",
                          f"Cloning {repo_name} to:\n{target_path}\n\n"
                          f"This may take a few moments...")

        # Start clone in background
        thread = threading.Thread(target=clone_repo, daemon=True)
        thread.start()

    def _handle_clone_result(self, result, repo_name: str, folder_name: str):
        """Handle the result of a git clone operation"""
        if result.returncode == 0:
            messagebox.showinfo("Clone Successful",
                              f"Successfully cloned {repo_name}!\n\n"
                              f"Location: {folder_name}/")
            # Refresh the dropdown to show the newly cloned repo
            self._refresh_forked_repos()
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            messagebox.showerror("Clone Failed",
                               f"Failed to clone {repo_name}.\n\n"
                               f"Error:\n{error_msg}")

    def _load_user_forks_async(self):
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

                # Update dropdown on main thread
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, self._update_forked_dropdown)

            except Exception as e:
                print(f"Error loading user forks: {e}")

        threading.Thread(target=load_forks, daemon=True).start()
    
    def _update_forked_dropdown(self):
        """Update the forked repository dropdown with GitHub forks"""
        try:
            # Check if dialog and dropdown still exist
            if not hasattr(self, 'dialog') or not self.dialog.winfo_exists():
                return
            if not hasattr(self, 'forked_repo_dropdown') or not self.forked_repo_dropdown.winfo_exists():
                return
                
            current_values = list(self.forked_repo_dropdown['values'])

            # Remove old GitHub repos section if exists
            if '--- Your GitHub Repos ---' in current_values:
                start_idx = current_values.index('--- Your GitHub Repos ---')
                current_values = current_values[:start_idx]

            # Add GitHub repos section
            if self.forked_repos:
                current_values.append('--- Your GitHub Repos ---')
                current_values.extend(self.forked_repos)
            
            self.forked_repo_dropdown['values'] = current_values
            
        except Exception as e:
            print(f"Error updating forked dropdown: {e}")

    def _load_target_repos_async(self):
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

                # Update dropdown on main thread
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, self._update_target_dropdown)

            except Exception as e:
                print(f"Error loading target repos: {e}")

        threading.Thread(target=load_repos, daemon=True).start()

    def _update_target_dropdown(self):
        """Update the target repository dropdown"""
        try:
            if not hasattr(self, 'dialog') or not self.dialog.winfo_exists():
                return
            if not hasattr(self, 'target_repo_dropdown') or not self.target_repo_dropdown.winfo_exists():
                return

            current_values = ['']  # Start with empty option

            # Add user's repos with edit access
            if self.target_repos:
                current_values.append('--- Your Repos (with edit access) ---')
                current_values.extend(self.target_repos)

            self.target_repo_dropdown['values'] = current_values

        except Exception as e:
            print(f"Error updating target dropdown: {e}")

    def _refresh_target_repos(self):
        """Refresh target repositories"""
        self._load_target_repos_async()

    def _search_target_repos(self):
        """Search for repositories on GitHub"""
        query = self.target_repo_var.get().strip()
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

                # Update dropdown on main thread
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: self._update_target_dropdown_with_search(search_results, query))

            except Exception as e:
                print(f"Error searching repos: {e}")

        threading.Thread(target=search_repos, daemon=True).start()

    def _update_target_dropdown_with_search(self, search_results, query):
        """Update target dropdown with search results"""
        try:
            if not hasattr(self, 'target_repo_dropdown') or not self.target_repo_dropdown.winfo_exists():
                return

            current_values = ['']

            # Add user's repos
            if self.target_repos:
                current_values.append('--- Your Repos (with edit access) ---')
                current_values.extend(self.target_repos)

            # Add search results
            if search_results:
                current_values.append(f'--- Search Results for "{query}" ---')
                current_values.extend(search_results)

            self.target_repo_dropdown['values'] = current_values

        except Exception as e:
            print(f"Error updating target dropdown with search: {e}")

    def _on_target_repo_search(self, _event):
        """Handle typing in target repo field for auto-search"""
        # Debounce: only search after user stops typing for 500ms
        if hasattr(self, '_search_timer'):
            self.dialog.after_cancel(self._search_timer)

        query = self.target_repo_var.get().strip()
        if len(query) >= 3:  # Only search if at least 3 characters
            self._search_timer = self.dialog.after(500, self._search_target_repos)

    def _create_ollama_model_dropdown(self, parent, row: int):
        """Create Ollama model dropdown with scan button"""
        ttk.Label(parent, text="Ollama Model:", font=('Arial', 10, 'bold')).grid(
            row=row, column=0, sticky=tk.W, pady=5, padx=10)

        # Frame for dropdown and scan button
        dropdown_frame = ttk.Frame(parent)
        dropdown_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=10)
        dropdown_frame.columnconfigure(0, weight=1)

        # Model dropdown
        self.ollama_model_var = tk.StringVar(value=self.config.get('OLLAMA_MODEL', ''))
        self.ollama_model_dropdown = ttk.Combobox(dropdown_frame, textvariable=self.ollama_model_var,
                                                  values=[''], width=47)
        self.ollama_model_dropdown.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.entries['OLLAMA_MODEL'] = self.ollama_model_var

        # Scan button
        scan_btn = ttk.Button(dropdown_frame, text="🔍", width=3,
                             command=self._scan_ollama_models)
        scan_btn.grid(row=0, column=1)

        # Help text for Ollama model
        help_label = ttk.Label(parent,
                             text="  ℹ️ Click 🔍 to scan available models from your Ollama server.",
                             font=('Arial', 9), foreground='gray')
        help_label.grid(row=row+1, column=0, columnspan=3, sticky=tk.W, padx=10)

    def _scan_ollama_models(self):
        """Scan Ollama server for available models"""
        ollama_url = self.entries.get('OLLAMA_URL').get().strip() if 'OLLAMA_URL' in self.entries else ''

        if not ollama_url:
            messagebox.showwarning("Ollama URL Required",
                                 "Please enter the Ollama Server URL first.")
            return

        # Normalize URL
        if not ollama_url.startswith('http'):
            ollama_url = f"http://{ollama_url}"

        # Scan in background thread
        def scan_models():
            try:
                import requests

                # Get API key if provided
                ollama_api_key = self.entries.get('OLLAMA_API_KEY').get().strip() if 'OLLAMA_API_KEY' in self.entries else ''

                headers = {}
                if ollama_api_key:
                    headers['Authorization'] = f'Bearer {ollama_api_key}'

                # Query Ollama API for models
                response = requests.get(f"{ollama_url}/api/tags", headers=headers, timeout=10)
                response.raise_for_status()

                data = response.json()
                models = data.get('models', [])
                model_names = [model.get('name', '') for model in models if model.get('name')]

                # Update UI on main thread
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: self._update_ollama_models(model_names))

            except requests.exceptions.ConnectionError:
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: messagebox.showerror(
                        "Connection Error",
                        f"Could not connect to Ollama server at:\n{ollama_url}\n\n"
                        f"Make sure Ollama is running and the URL is correct."))
            except requests.exceptions.Timeout:
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: messagebox.showerror(
                        "Timeout",
                        f"Connection to Ollama server timed out."))
            except requests.exceptions.HTTPError as e:
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    if e.response.status_code == 401:
                        self.dialog.after(0, lambda: messagebox.showerror(
                            "Authentication Error",
                            "Invalid API key. Please check your Ollama API Key."))
                    else:
                        self.dialog.after(0, lambda: messagebox.showerror(
                            "HTTP Error",
                            f"Error from Ollama server:\n{e}"))
            except Exception as e:
                if hasattr(self, 'dialog') and self.dialog.winfo_exists():
                    self.dialog.after(0, lambda: messagebox.showerror(
                        "Scan Error",
                        f"An error occurred while scanning for models:\n{str(e)}"))

        # Start scan in background
        threading.Thread(target=scan_models, daemon=True).start()

    def _update_ollama_models(self, model_names):
        """Update the Ollama model dropdown with scanned models"""
        if not model_names:
            messagebox.showinfo("No Models Found",
                              "No models found on the Ollama server.\n\n"
                              "Use 'ollama pull <model>' to download models.")
            return

        try:
            if hasattr(self, 'ollama_model_dropdown') and self.ollama_model_dropdown.winfo_exists():
                current_value = self.ollama_model_var.get()
                self.ollama_model_dropdown['values'] = model_names

                # Keep current selection if it's still in the list
                if current_value not in model_names and model_names:
                    self.ollama_model_var.set(model_names[0])

                messagebox.showinfo("Models Found",
                                  f"Found {len(model_names)} model(s):\n\n" +
                                  "\n".join(f"• {name}" for name in model_names[:10]) +
                                  (f"\n\n...and {len(model_names) - 10} more" if len(model_names) > 10 else ""))

        except Exception as e:
            print(f"Error updating Ollama models: {e}")

    def _create_dry_run_checkbox(self, parent, row: int):
        """Create dry run checkbox"""
        self.dry_run_var = tk.BooleanVar()
        dry_run_value = self.config.get('DRY_RUN', 'false')
        self.dry_run_var.set(str(dry_run_value).lower() in ('true', '1', 'yes', 'on'))
        
        dry_run_frame = ttk.Frame(parent)
        dry_run_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10, padx=10)
        
        dry_run_checkbox = ttk.Checkbutton(
            dry_run_frame,
            text="🧪 Dry Run Mode (Test without making changes)",
            variable=self.dry_run_var
        )
        dry_run_checkbox.pack(side=tk.LEFT)
        
        help_label = ttk.Label(dry_run_frame, 
                             text="  ℹ️ Simulates operations without creating actual GitHub issues/PRs",
                             font=('Arial', 9), foreground='gray')
        help_label.pack(side=tk.LEFT)
        
        self.entries['DRY_RUN'] = self.dry_run_var
    
    def _scan_repos(self):
        """Scan work items to detect commonly used repositories"""
        try:
            # This is a placeholder - could be enhanced to actually scan work items
            # and suggest repositories based on document URLs found
            pass
        except Exception as e:
            print(f"Could not scan repositories: {e}")
    
    def _bind_events(self):
        """Bind keyboard events"""
        self.dialog.bind('<Return>', lambda e: self._save_clicked())
        self.dialog.bind('<Escape>', lambda e: self._cancel_clicked())
        
        # Set focus to first entry if available
        if self.entries:
            first_entry = next(iter(self.entries.values()))
            if hasattr(first_entry, 'focus_set'):
                first_entry.focus_set()
    
    def _test_connection(self):
        """Test connection to configured services"""
        # Get current values
        config_values = self._get_config_values()
        
        results = []
        
        # REMOVED: Azure DevOps test connection
        # This was specific to Azure DevOps integration

        # Test GitHub
        if config_values.get('GITHUB_PAT'):
            try:
                # Try to import and test GitHub API
                from .github_api import GitHubAPI
                api = GitHubAPI(config_values.get('GITHUB_PAT'))
                
                # Basic connection test
                results.append("GitHub: ✅ Token configured")
                
                if config_values.get('GITHUB_REPO'):
                    results.append(f"GitHub Repository: ✅ {config_values.get('GITHUB_REPO')}")
                else:
                    results.append("GitHub Repository: ⚠️ Not configured")
                    
            except ImportError:
                results.append("GitHub: ⚠️ Token set (API module not available)")
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
            except ImportError:
                results.append(f"AI Provider ({ai_provider}): ⚠️ Configuration set (AI manager not available)")
        else:
            results.append("AI Provider: ℹ️ Disabled (using standard method)")
        
        # Show results
        if results:
            messagebox.showinfo("Connection Test Results", 
                              "\n".join(results) + "\n\n💡 Full validation requires running the application.",
                              parent=self.dialog)
        else:
            messagebox.showwarning("Connection Test", "No configuration to test.", parent=self.dialog)
    
    def _center_dialog(self):
        """Center the dialog over the parent window"""
        self.dialog.update_idletasks()

        # Get parent window position and size
        self.parent.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)

        self.dialog.geometry(f"+{x}+{y}")

    def _get_config_values(self) -> Dict[str, Any]:
        """Get configuration values from entries"""
        config_values = {}
        
        for key, widget in self.entries.items():
            if isinstance(widget, tk.BooleanVar):
                config_values[key] = 'true' if widget.get() else 'false'
            elif isinstance(widget, tk.StringVar):
                config_values[key] = widget.get().strip()
            elif isinstance(widget, scrolledtext.ScrolledText):
                config_values[key] = widget.get('1.0', tk.END).strip()
            elif isinstance(widget, ttk.Combobox):
                config_values[key] = widget.get().strip()
            else:  # Entry widget
                value = widget.get().strip()
                # Special handling for GITHUB_TOKEN placeholder
                if key == 'GITHUB_TOKEN' and value == '(using GitHub PAT)':
                    value = ''  # Save empty string when using placeholder
                config_values[key] = value
        
        return config_values
    
    def _save_clicked(self):
        """Handle save button click"""
        try:
            # Get configuration values
            config_values = self._get_config_values()
            
            # Validate required fields
            required_for_basic = ['GITHUB_PAT']
            missing_basic = [field for field in required_for_basic if not config_values.get(field)]

            if missing_basic:
                messagebox.showwarning(
                    "Missing Configuration",
                    f"The following required fields are missing:\n\n"
                    f"• {', '.join(missing_basic)}\n\n"
                    f"GitHub Personal Access Token is required for basic functionality."
                )
                return
            
            # Check AI provider setup before saving
            ai_provider = config_values.get('AI_PROVIDER', '').strip().lower()
            if ai_provider and ai_provider not in ['none', '']:
                if ai_provider in ['chatgpt', 'claude', 'anthropic', 'github-copilot', 'copilot', 'github_copilot']:
                    try:
                        # Import here to avoid circular imports
                        from .ai_manager import AIManager
                        ai_manager = AIManager()
                        
                        available, missing = ai_manager.check_ai_module_availability(ai_provider)
                        if not available:
                            # Offer to install missing packages
                            install_success = ai_manager.install_ai_packages(missing, self.dialog)
                            if not install_success:
                                # Installation failed or was cancelled, but still save settings
                                messagebox.showwarning("AI Modules Not Installed",
                                                     f"Settings saved, but AI provider '{ai_provider}' "
                                                     f"requires additional packages: {', '.join(missing)}\n\n"
                                                     f"You can install them later with:\n"
                                                     f"pip install {' '.join(missing)}",
                                                     parent=self.dialog)
                    except ImportError:
                        # AIManager not available, skip AI validation
                        pass
            
            # Save configuration using the provided config manager
            if self.config_manager:
                success = self.config_manager.save_configuration(config_values)
            else:
                # Fallback: create new config manager or save directly to file
                try:
                    from .config_manager import ConfigManager
                    config_manager = ConfigManager()
                    success = config_manager.save_configuration(config_values)
                except ImportError:
                    # Fallback to basic file saving if ConfigManager not available
                    success = self._save_to_env_file(config_values)
            
            if success:
                self.result = config_values

                # Ask user if they want to restart the application
                restart = messagebox.askyesno(
                    "Settings Saved",
                    "Settings have been saved to .env file!\n\n"
                    "Would you like to restart the application now to apply changes?",
                    parent=self.dialog
                )

                self.dialog.destroy()

                if restart:
                    self._restart_application()
            else:
                messagebox.showerror("Save Error",
                                   "Failed to save settings to .env file.",
                                   parent=self.dialog)
            
        except Exception as e:
            messagebox.showerror("Save Error",
                               f"Error saving settings:\n{str(e)}",
                               parent=self.dialog)
    
    def _save_to_env_file(self, config_values: Dict[str, Any]) -> bool:
        """Fallback method to save configuration to .env file"""
        try:
            import os
            
            # Create .env content
            env_content = "# GitHub Pulse Configuration\n"
            env_content += "# Generated by Settings Dialog\n\n"
            
            # Add all configuration values
            for key, value in config_values.items():
                if value:  # Only add non-empty values
                    env_content += f"{key}={value}\n"
                else:
                    env_content += f"{key}=\n"
            
            # Write to .env file
            env_path = os.path.join(os.getcwd(), '.env')
            with open(env_path, 'w', encoding='utf-8') as f:
                f.write(env_content)
            
            return True
            
        except Exception as e:
            print(f"Error saving to .env file: {e}")
            return False

    def _on_repo_selected(self, event=None):
        """Handle repo selection from dropdown - informational only for fork workflow"""
        # The detected repo dropdown shows which FORK the AI will work on locally
        # The GITHUB_REPO field is the UPSTREAM repo where PRs are created
        # This supports the fork workflow: work on fork, PR to upstream
        pass

    def _scan_repos(self):
        """Scan for git repositories in the local repo path"""
        try:
            from pathlib import Path

            # Get the local repo path from the entry field
            local_path = self.entries.get('LOCAL_REPO_PATH')
            if local_path and hasattr(local_path, 'get'):
                path_str = local_path.get().strip()
            else:
                path_str = self.config.get('LOCAL_REPO_PATH', '').strip()

            # If no path configured, use default
            if not path_str:
                path_str = str(Path.home() / "Downloads" / "github_repos")

            base_path = Path(path_str)

            # Check if path exists
            if not base_path.exists():
                self.detected_repos_var.set('No repos found (directory does not exist)')
                self.detected_repos_dropdown['values'] = []
                return

            # Scan for git repositories
            repos = []
            try:
                # Look for owner/repo structure: base_path/owner/repo/.git
                for owner_dir in base_path.iterdir():
                    if not owner_dir.is_dir():
                        continue

                    for repo_dir in owner_dir.iterdir():
                        if not repo_dir.is_dir():
                            continue

                        # Check if it's a git repo
                        git_dir = repo_dir / ".git"
                        if git_dir.exists():
                            repo_name = f"{owner_dir.name}/{repo_dir.name}"
                            repos.append(repo_name)

            except PermissionError:
                self.detected_repos_var.set('Permission denied accessing directory')
                self.detected_repos_dropdown['values'] = []
                return
            except Exception as e:
                self.detected_repos_var.set(f'Error scanning: {str(e)[:50]}')
                self.detected_repos_dropdown['values'] = []
                return

            # Update dropdown
            if repos:
                repos.sort()
                self.detected_repos_dropdown['values'] = repos

                # Auto-select if only one repo found
                if len(repos) == 1:
                    self.detected_repos_var.set(repos[0])
                    # Trigger the selection handler to offer auto-populating GITHUB_REPO
                    self.dialog.after(200, self._on_repo_selected)
                else:
                    self.detected_repos_var.set(f'{len(repos)} repo(s) found - select one')
            else:
                self.detected_repos_var.set('No git repositories found')
                self.detected_repos_dropdown['values'] = []

        except Exception as e:
            self.detected_repos_var.set(f'Error: {str(e)[:50]}')
            self.detected_repos_dropdown['values'] = []

    def _restart_application(self):
        """Restart the application"""
        try:
            # Get the parent root window (main application)
            root = self.parent
            while root.master:
                root = root.master

            # Close the main window
            root.quit()

            # Restart the application using the same Python executable and script
            python = sys.executable
            script = sys.argv[0]

            # If running as a module (python -m), preserve that
            if script.endswith('__main__.py'):
                # Running as module, restart with module syntax
                os.execl(python, python, '-m', 'app')
            else:
                # Running as script, restart directly
                os.execl(python, python, script, *sys.argv[1:])

        except Exception as e:
            messagebox.showerror(
                "Restart Failed",
                f"Could not restart application automatically:\n{str(e)}\n\n"
                "Please restart the application manually.",
                parent=self.parent
            )

    def _cancel_clicked(self):
        """Handle cancel button click"""
        self.result = None
        self.dialog.destroy()

    def _clear_cache(self):
        """Clear all cached items"""
        result = messagebox.askyesno(
            "Clear Cache",
            "Are you sure you want to clear all cached items?\n\n"
            "All cached data will be removed.\n"
            "The next time you open the app, it will auto-load fresh data."
        )
        if result:
            try:
                # Use cache manager passed to dialog
                if self.cache_manager:
                    self.cache_manager.invalidate_cache()
                    messagebox.showinfo(
                        "Cache Cleared",
                        "All cached items have been cleared.\n"
                        "Fresh data will be loaded on next app start."
                    )
                else:
                    messagebox.showerror("Error", "Cache manager not available")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear cache: {str(e)}")

    def show(self) -> Optional[Dict[str, Any]]:
        """Show dialog and return result"""
        self.dialog.wait_window()
        return self.result