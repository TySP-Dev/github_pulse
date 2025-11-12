"""
Main GUI Interface
The primary user interface for the application
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import os
import threading
import webbrowser
from typing import List, Dict, Any, Optional

from .utils import Logger
from .settings_dialog import SettingsDialog
# Removed imports: WorkItemProcessor, AzureDevOpsAPI, DataverseAPI
# These were specific to Azure DevOps integration


class HyperlinkDialog:
    """Dialog with clickable hyperlinks"""
    
    def __init__(self, parent, title: str, message: str, url: str):
        self.result = None
        self.url = url
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("500x280")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center on parent
        self.dialog.geometry("+%d+%d" % (
            parent.winfo_rootx() + 50,
            parent.winfo_rooty() + 50
        ))
        
        # Message
        message_label = tk.Label(self.dialog, text=message, wraplength=450, justify=tk.LEFT)
        message_label.pack(pady=20, padx=20)
        
        # URL link
        link_label = tk.Label(self.dialog, text=url, fg="blue", cursor="hand2", wraplength=450)
        link_label.pack(pady=(0, 20), padx=20)
        link_label.bind("<Button-1>", self._open_url)

        # Button frame
        button_frame = tk.Frame(self.dialog)
        button_frame.pack(pady=(0, 20))

        # Copy Link button
        copy_button = ttk.Button(button_frame, text="Copy Link", command=self._copy_link)
        copy_button.pack(side=tk.LEFT, padx=5)

        # OK button
        ok_button = ttk.Button(button_frame, text="OK", command=self._ok_clicked)
        ok_button.pack(side=tk.LEFT, padx=5)

        # Focus and bindings
        ok_button.focus_set()
        self.dialog.bind('<Return>', lambda e: self._ok_clicked())
        self.dialog.bind('<Escape>', lambda e: self._ok_clicked())
    
    def _open_url(self, event=None):
        """Open URL in browser"""
        webbrowser.open(self.url)

    def _copy_link(self):
        """Copy URL to clipboard"""
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(self.url)
        self.dialog.update()  # Required to finalize clipboard operation

        # Show a brief confirmation (update button text temporarily)
        # Find the copy button and change its text
        for widget in self.dialog.winfo_children():
            if isinstance(widget, tk.Frame):
                for button in widget.winfo_children():
                    if isinstance(button, ttk.Button) and button.cget('text') == 'Copy Link':
                        original_text = button.cget('text')
                        button.config(text='Copied!')
                        self.dialog.after(1500, lambda: button.config(text=original_text))
                        break

    def _ok_clicked(self):
        """Handle OK button click"""
        self.result = True
        self.dialog.destroy()
    
    def show(self):
        """Show dialog and wait for result"""
        self.dialog.wait_window()
        return self.result


class DryRunVar:
    """Compatibility class for dry run variable"""
    
    def __init__(self, app):
        self.app = app
    
    def get(self):
        return self.app.dry_run_enabled
    
    def set(self, value):
        self.app.dry_run_enabled = bool(value)


class MainGUI:
    """Main GUI interface for the application"""
    
    def __init__(self, root, config_manager, ai_manager, app):
        self.root = root
        self.config_manager = config_manager
        self.ai_manager = ai_manager
        self.app = app
        
        # Application state
        self.current_work_items = []
        self.current_item_index = 0
        self.current_organization = None
        self.edit_mode = False
        
        # API instances
        self.azure_api = None
        self.dataverse_api = None
        
        # Create dry run compatibility wrapper
        self.dry_run_var = DryRunVar(app)
        
        # Create GUI
        self.create_gui()
        
        # Initialize logger after GUI is created
        self.logger = Logger(self.log_text)

        # Initialize work item processor - REMOVED (was Azure DevOps specific)
        # self.work_item_processor = WorkItemProcessor(self.logger, self.config_manager.get_config())
        self.work_item_processor = None  # Placeholder for future implementation

        # Initialize cache manager
        from .cache_manager import CacheManager
        self.cache_manager = CacheManager(cache_duration_hours=24)

        # Initialize diff display
        self.update_diff_display("")

        # Auto-load cached items on startup
        self.root.after(500, self._auto_load_cached_items)
        
        # Load custom instructions after GUI is ready
        self.root.after(100, self._load_custom_instructions)
    
    def create_gui(self):
        """Create the main GUI interface"""
        # Configure custom styles
        self._configure_styles()
        
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Create sections
        self._create_title_section(main_frame)
        self._create_controls_section(main_frame)
        self._create_status_section(main_frame)
        self._create_tabs_section(main_frame)
    
    def _configure_styles(self):
        """Configure custom styles for the GUI"""
        style = ttk.Style()
        
        # Grouped sections
        style.configure('Config.TLabelframe', relief='solid', borderwidth=1)
        style.configure('Config.TLabelframe.Label', font=('Arial', 11, 'bold'))
        style.configure('WorkItem.TLabelframe', relief='solid', borderwidth=1)
        style.configure('WorkItem.TLabelframe.Label', font=('Arial', 11, 'bold'))
        
        # Notebook tabs
        style.configure('TNotebook.Tab', background='lightblue', foreground='black', padding=[10, 5])
        style.map('TNotebook.Tab',
                 background=[('selected', 'lightblue'), ('active', '#87CEEB')],
                 foreground=[('selected', 'black'), ('active', 'black')])
        
        # Blue edit button
        style.configure('BlueEdit.TButton', 
                       background='#2196F3', foreground='black', font=('Arial', 9, 'bold'),
                       relief='raised', borderwidth=2, focuscolor='none')
        style.map('BlueEdit.TButton',
                 background=[('active', '#1976D2'), ('pressed', '#0D47A1'), ('!disabled', '#2196F3')],
                 foreground=[('active', 'black'), ('pressed', 'black'), ('!disabled', 'black')],
                 relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
        
        # Orange save button
        style.configure('OrangeSave.TButton', 
                       background='#FF9800', foreground='black', font=('Arial', 9, 'bold'),
                       relief='raised', borderwidth=2, focuscolor='none')
        style.map('OrangeSave.TButton',
                 background=[('active', '#F57C00'), ('pressed', '#E65100'), ('!disabled', '#FF9800')],
                 foreground=[('active', 'black'), ('pressed', 'black'), ('!disabled', 'black')],
                 relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
        
        # Green save button for custom instructions
        style.configure('GreenSave.TButton', 
                       background='#4CAF50', foreground='black', font=('Arial', 9, 'bold'),
                       relief='raised', borderwidth=2, focuscolor='none')
        style.map('GreenSave.TButton',
                 background=[('active', '#388E3C'), ('pressed', '#2E7D32'), ('!disabled', '#4CAF50')],
                 foreground=[('active', 'black'), ('pressed', 'black'), ('!disabled', 'black')],
                 relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
    
    def _create_title_section(self, parent):
        """Create title section with settings button"""
        title_frame = ttk.Frame(parent)
        title_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        title_frame.columnconfigure(0, weight=1)
        
        # Title
        title_label = ttk.Label(title_frame, text="GitHub Pulse",
                               font=('Arial', 16, 'bold'))
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        # AI Modules button
        self.ai_modules_button = ttk.Button(title_frame, text="🤖 AI Modules",
                                           command=self.check_ai_modules_manual)
        self.ai_modules_button.grid(row=0, column=1, sticky=tk.E, padx=(10, 5))
        
        # Settings button
        self.settings_button = ttk.Button(title_frame, text="⚙️ Settings",
                                         command=self.open_settings)
        self.settings_button.grid(row=0, column=2, sticky=tk.E, padx=(5, 0))
    
    def _create_controls_section(self, parent):
        """Create GitHub Tools section"""
        # GitHub Tools group frame
        tools_frame = ttk.LabelFrame(parent, text="🔧 GitHub Tools",
                                     style='WorkItem.TLabelframe', padding="15")
        tools_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15), padx=5)
        tools_frame.columnconfigure(1, weight=1)

        # Initialize workflow data
        self.target_repos = []
        self.forked_repos = []
        self.workflow_items = []
        self.current_workflow_items = []

        # Get current config
        config = self.config_manager.get_config()

        # Row 0: Mode Selection
        mode_frame = ttk.Frame(tools_frame)
        mode_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10), padx=5)

        ttk.Label(mode_frame, text="Mode:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10))

        self.tools_mode_var = tk.StringVar(value="action")
        create_radio = ttk.Radiobutton(mode_frame, text="✏️ Create PR/Issue", variable=self.tools_mode_var,
                                      value="create", command=self._on_mode_changed)
        create_radio.grid(row=0, column=1, padx=(0, 15))

        action_radio = ttk.Radiobutton(mode_frame, text="📋 Action Existing PR/Issue", variable=self.tools_mode_var,
                                      value="action", command=self._on_mode_changed)
        action_radio.grid(row=0, column=2, padx=(0, 10))

        # Separator
        ttk.Separator(tools_frame, orient='horizontal').grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 10))

        # Row 2: Target Repository
        self.target_repo_label = ttk.Label(tools_frame, text="Target Repository:", font=('Arial', 10, 'bold'))
        self.target_repo_label.grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)

        target_frame = ttk.Frame(tools_frame)
        target_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        target_frame.columnconfigure(0, weight=1)

        self.target_repo_var = tk.StringVar(value=config.get('GITHUB_REPO', ''))
        self.target_repo_dropdown = ttk.Combobox(target_frame, textvariable=self.target_repo_var,
                                                values=[''], width=60)
        self.target_repo_dropdown.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.target_repo_dropdown.bind('<KeyRelease>', self._on_target_repo_search)
        self.target_repo_dropdown.bind('<<ComboboxSelected>>', lambda e: self._on_repo_selection_changed())

        refresh_target_btn = ttk.Button(target_frame, text="🔄", width=3,
                                       command=self._refresh_target_repos)
        refresh_target_btn.grid(row=0, column=1, padx=(0, 2))

        search_target_btn = ttk.Button(target_frame, text="🔍", width=3,
                                      command=self._search_target_repos)
        search_target_btn.grid(row=0, column=2)

        # Row 3: Forked Repository
        self.forked_repo_label = ttk.Label(tools_frame, text="Forked Repository:", font=('Arial', 10, 'bold'))
        self.forked_repo_label.grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)

        self.fork_frame = ttk.Frame(tools_frame)
        self.fork_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        self.fork_frame.columnconfigure(0, weight=1)

        self.forked_repo_var = tk.StringVar(value=config.get('FORKED_REPO', ''))
        self.forked_repo_dropdown = ttk.Combobox(self.fork_frame, textvariable=self.forked_repo_var,
                                                values=[''], width=60)
        self.forked_repo_dropdown.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        self.forked_repo_dropdown.bind('<<ComboboxSelected>>', lambda e: self._on_repo_selection_changed())

        refresh_fork_btn = ttk.Button(self.fork_frame, text="🔄", width=3,
                                     command=self._refresh_forked_repos)
        refresh_fork_btn.grid(row=0, column=1, padx=(0, 2))

        clone_fork_btn = ttk.Button(self.fork_frame, text="📥", width=3,
                                   command=self._clone_forked_repo)
        clone_fork_btn.grid(row=0, column=2)

        # Row 4: Action Mode Controls (View toggles and load button)
        self.action_controls_row = ttk.Frame(tools_frame)
        self.action_controls_row.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 5), padx=5)
        self.action_controls_row.columnconfigure(2, weight=1)

        # Repo source toggle
        ttk.Label(self.action_controls_row, text="View:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))

        self.repo_source_var = tk.StringVar(value="target")
        target_radio = ttk.Radiobutton(self.action_controls_row, text="Target", variable=self.repo_source_var,
                                      value="target", command=self._filter_workflow_items)
        target_radio.grid(row=0, column=1, padx=(0, 5))

        fork_radio = ttk.Radiobutton(self.action_controls_row, text="Fork", variable=self.repo_source_var,
                                    value="fork", command=self._filter_workflow_items)
        fork_radio.grid(row=0, column=2, padx=(0, 15))

        # Item type toggle
        self.item_type_var = tk.StringVar(value="pull_request")
        pr_radio = ttk.Radiobutton(self.action_controls_row, text="PRs", variable=self.item_type_var,
                                  value="pull_request", command=self._filter_workflow_items)
        pr_radio.grid(row=0, column=3, padx=(0, 5))

        issue_radio = ttk.Radiobutton(self.action_controls_row, text="Issues", variable=self.item_type_var,
                                     value="issue", command=self._filter_workflow_items)
        issue_radio.grid(row=0, column=4, padx=(0, 15))

        # Fetch button
        self.fetch_workflow_btn = ttk.Button(self.action_controls_row, text="📥 Load Items",
                                            command=self._load_workflow_items)
        self.fetch_workflow_btn.grid(row=0, column=5, padx=(0, 10))

        # Item counter
        self.item_counter_label = ttk.Label(self.action_controls_row, text="No items loaded",
                                           font=('Arial', 9, 'italic'))
        self.item_counter_label.grid(row=0, column=6, sticky=tk.E)

        # Row 5: Workflow items dropdown (Action Mode)
        self.action_item_label = ttk.Label(tools_frame, text="Select Item:", font=('Arial', 10, 'bold'))
        self.action_item_label.grid(row=5, column=0, sticky=tk.W, pady=5, padx=5)

        action_item_dropdown_frame = ttk.Frame(tools_frame)
        action_item_dropdown_frame.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        action_item_dropdown_frame.columnconfigure(0, weight=1)

        self.workflow_item_var = tk.StringVar()
        self.workflow_item_dropdown = ttk.Combobox(action_item_dropdown_frame, textvariable=self.workflow_item_var,
                                                   values=[''], width=60, state='readonly')
        self.workflow_item_dropdown.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.workflow_item_dropdown.bind('<<ComboboxSelected>>', self._on_workflow_item_selected)

        # Row 4-5: Create Mode Controls (hidden by default)
        self.create_controls_row = ttk.Frame(tools_frame)
        self.create_controls_row.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 5), padx=5)
        self.create_controls_row.columnconfigure(1, weight=1)

        # Create type selection
        ttk.Label(self.create_controls_row, text="Create:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))

        self.create_type_var = tk.StringVar(value="pull_request")
        create_pr_radio = ttk.Radiobutton(self.create_controls_row, text="📝 Pull Request",
                                         variable=self.create_type_var, value="pull_request")
        create_pr_radio.grid(row=0, column=1, padx=(0, 15), sticky=tk.W)

        create_issue_radio = ttk.Radiobutton(self.create_controls_row, text="🐛 Issue",
                                            variable=self.create_type_var, value="issue")
        create_issue_radio.grid(row=0, column=2, padx=(0, 15), sticky=tk.W)

        # Create button
        self.create_item_btn = ttk.Button(self.create_controls_row, text="✏️ Create New",
                                         command=self._create_new_item)
        self.create_item_btn.grid(row=0, column=3, padx=(0, 10))

        # Store references for show/hide
        self.action_mode_widgets = [
            self.action_controls_row,
            self.action_item_label,
            action_item_dropdown_frame
        ]

        self.create_mode_widgets = [
            self.create_controls_row
        ]

        # Initialize mode (show action, hide create)
        self._on_mode_changed()

        # Start loading repos
        self.root.after(100, self._init_load_repos)
    
    def _create_status_section(self, parent):
        """Create progress and status section"""
        # Progress bar
        self.progress = ttk.Progressbar(parent, mode='indeterminate')
        self.progress.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # Status label
        self.status_label = ttk.Label(parent, text="Ready to fetch work items...")
        self.status_label.grid(row=6, column=0, columnspan=3, pady=5)
    
    def _create_tabs_section(self, parent):
        """Create tabbed interface section"""
        # Create notebook
        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        parent.rowconfigure(7, weight=1)
        
        # Create tabs
        self._create_current_item_tab(self.notebook)
        self._create_diff_tab(self.notebook)
        self._create_log_tab(self.notebook)
        self._create_all_items_tab(self.notebook)
    
    def _create_current_item_tab(self, notebook):
        """Create current work item tab"""
        item_frame = ttk.Frame(notebook)
        notebook.add(item_frame, text="Current Work Item")
        item_frame.columnconfigure(1, weight=1)
        
        # Work Item ID
        ttk.Label(item_frame, text="Work Item ID:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.work_item_id_label = ttk.Label(item_frame, text="Not loaded")
        self.work_item_id_label.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.work_item_id_label.bind("<Button-1>", self.open_work_item_url)
        self.work_item_id_label.bind("<Enter>", self.on_work_item_hover_enter)
        self.work_item_id_label.bind("<Leave>", self.on_work_item_hover_leave)
        
        # Nature of Request
        ttk.Label(item_frame, text="Nature of Request:", font=('Arial', 10, 'bold')).grid(
            row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.nature_text = tk.Text(item_frame, height=1, width=70, state='disabled', wrap=tk.WORD)
        self.nature_text.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Document URL
        ttk.Label(item_frame, text="Live Doc URL:", font=('Arial', 10, 'bold')).grid(
            row=2, column=0, sticky=tk.W, pady=5, padx=5)
        self.doc_url_text = tk.Text(item_frame, height=1, width=70, state='disabled', wrap=tk.WORD)
        self.doc_url_text.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Text to Change
        ttk.Label(item_frame, text="Text to Change:", font=('Arial', 10, 'bold')).grid(
            row=3, column=0, sticky=tk.W, pady=5, padx=5)
        self.text_to_change_display = scrolledtext.ScrolledText(item_frame, height=5, width=70, state='disabled')
        self.text_to_change_display.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Proposed New Text with Edit functionality
        new_text_frame = ttk.Frame(item_frame)
        new_text_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5, padx=5)
        new_text_frame.columnconfigure(1, weight=1)
        
        ttk.Label(new_text_frame, text="Proposed New Text:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=5)
        
        self.edit_button = ttk.Button(new_text_frame, text="✏️ Edit", 
                                     command=self.toggle_edit_mode, state='disabled',
                                     style='BlueEdit.TButton')
        self.edit_button.grid(row=0, column=1, sticky=tk.E, pady=5, padx=(5, 0))
        
        self.new_text_display = scrolledtext.ScrolledText(new_text_frame, height=5, width=70, state='disabled')
        self.new_text_display.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Custom AI Instructions with Save functionality
        custom_instructions_frame = ttk.Frame(item_frame)
        custom_instructions_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5, padx=5)
        custom_instructions_frame.columnconfigure(1, weight=1)
        
        ttk.Label(custom_instructions_frame, text="Custom AI Instructions:", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=5)
        
        # Button frame to hold both save and clear buttons
        button_frame = ttk.Frame(custom_instructions_frame)
        button_frame.grid(row=0, column=1, sticky=tk.E, pady=5, padx=(5, 0))
        
        self.save_instructions_button = ttk.Button(button_frame, text="💾 Save", 
                                                  command=self.save_custom_instructions,
                                                  style='GreenSave.TButton')
        self.save_instructions_button.grid(row=0, column=0, padx=(0, 5))
        
        self.clear_instructions_button = ttk.Button(button_frame, text="🗑️ Clear", 
                                                   command=self.clear_custom_instructions)
        self.clear_instructions_button.grid(row=0, column=1)
        
        self.custom_instructions_display = scrolledtext.ScrolledText(custom_instructions_frame, height=4, width=70)
        self.custom_instructions_display.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # Configure row weights
        for i in range(6):
            item_frame.rowconfigure(i, weight=1)
    
    def _create_diff_tab(self, notebook):
        """Create diff view tab"""
        diff_frame = ttk.Frame(notebook)
        notebook.add(diff_frame, text="View Diff")
        
        diff_frame.columnconfigure(0, weight=1)
        diff_frame.rowconfigure(1, weight=1)  # Give weight to row 1 (diff_text) instead of row 0 (header)
        
        # Add a header label
        header_frame = ttk.Frame(diff_frame)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=5, pady=5)
        header_frame.columnconfigure(0, weight=1)
        
        ttk.Label(header_frame, text="Diff Viewer", font=('Arial', 12, 'bold')).grid(
            row=0, column=0, sticky=tk.W, pady=5)
        
        # Add button to find existing diff files
        self.find_diff_button = ttk.Button(header_frame, text="Find .diff Files", 
                                          command=self.find_and_load_diff_files)
        self.find_diff_button.grid(row=0, column=1, sticky=tk.E, pady=5, padx=(0, 5))
        
        self.clear_diff_button = ttk.Button(header_frame, text="Clear Diff", 
                                          command=self.clear_diff_display, state='disabled')
        self.clear_diff_button.grid(row=0, column=2, sticky=tk.E, pady=5)
        
        # Create the diff display area with syntax highlighting-like colors
        self.diff_text = scrolledtext.ScrolledText(diff_frame, 
                                                 font=('Courier New', 9), 
                                                 state='disabled',
                                                 bg='#f8f8f8')
        self.diff_text.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # Configure diff syntax highlighting tags
        self.diff_text.tag_config('diff_header', foreground='#0066cc', font=('Courier New', 9, 'bold'))
        self.diff_text.tag_config('diff_file', foreground='#666666', font=('Courier New', 9, 'bold'))
        self.diff_text.tag_config('diff_add', foreground='#008800', background='#e8ffe8')
        self.diff_text.tag_config('diff_remove', foreground='#cc0000', background='#ffe8e8')
        self.diff_text.tag_config('diff_context', foreground='#666666')
        self.diff_text.tag_config('diff_line_numbers', foreground='#999999')
    
    def _create_log_tab(self, notebook):
        """Create processing log tab"""
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="Processing Log")
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=25, width=100)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
    
    def _create_all_items_tab(self, notebook):
        """Create all work items tab"""
        items_frame = ttk.Frame(notebook)
        notebook.add(items_frame, text="All Work Items")
        
        items_frame.columnconfigure(0, weight=1)
        items_frame.rowconfigure(0, weight=1)  # Treeview gets the weight
        # Row 1 (button frame) will not have weight, so it stays fixed size
        
        # Treeview for all items
        columns = ('ID', 'Title', 'Nature', 'GitHub Repo', 'ms.author', 'Status')
        self.items_tree = ttk.Treeview(items_frame, columns=columns, show='headings', height=20)
        
        # Define headings
        self.items_tree.heading('ID', text='Work Item ID', anchor=tk.W)
        self.items_tree.heading('Title', text='Title', anchor=tk.W)
        self.items_tree.heading('Nature', text='Nature of Request', anchor=tk.W)
        self.items_tree.heading('GitHub Repo', text='GitHub Repository', anchor=tk.W)
        self.items_tree.heading('ms.author', text='ms.author', anchor=tk.W)
        self.items_tree.heading('Status', text='Processing Status', anchor=tk.W)
        
        # Configure columns
        self.items_tree.column('ID', width=100, anchor=tk.W)
        self.items_tree.column('Title', width=220, anchor=tk.W)
        self.items_tree.column('Nature', width=160, anchor=tk.W)
        self.items_tree.column('GitHub Repo', width=160, anchor=tk.W)
        self.items_tree.column('ms.author', width=100, anchor=tk.W)
        self.items_tree.column('Status', width=100, anchor=tk.W)
        
        self.items_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        
        # Add selection functionality
        self.items_tree.bind('<Double-1>', self._on_item_double_click)
        self.items_tree.bind('<<TreeviewSelect>>', self._on_item_select)
        
        # Add button frame for selection actions
        button_frame = ttk.Frame(items_frame)
        button_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        self.select_item_button = ttk.Button(button_frame, text="� Set as Current Item", 
                                           command=self._select_current_item, state='disabled')
        self.select_item_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(button_frame, text="Double-click an item or use the button above to set it as the current work item", 
                 font=('Arial', 9), foreground='#666666').pack(side=tk.LEFT, padx=10)
        
        # Scrollbar
        items_scrollbar = ttk.Scrollbar(items_frame, orient=tk.VERTICAL, command=self.items_tree.yview)
        items_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.items_tree.configure(yscrollcommand=items_scrollbar.set)
        
        # Track selected item for enabling/disabling button
        self.selected_tree_item = None
    
    # Event handlers and methods
    def update_status(self, message: str):
        """Update status label"""
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def _check_ai_modules_manual(self):
        """Manually check AI modules"""
        config = self.config_manager.get_config()
        ai_provider = config.get('AI_PROVIDER', '').strip().lower()
        self.ai_manager.show_ai_modules_info(ai_provider, self.root)
    
    def _open_settings(self):
        """Open settings dialog"""
        try:
            config = self.config_manager.get_config()
            dialog = SettingsDialog(self.root, config, self.config_manager, self.cache_manager)
            result = dialog.show()
            
            if result:
                # Reload configuration
                self.config_manager.load_configuration()
                config = self.config_manager.get_config()
                self.app.update_config(config)
                
                # Update dry run state
                dry_run_config = config.get('DRY_RUN', 'false')
                self.app.dry_run_enabled = str(dry_run_config).lower() in ('true', '1', 'yes', 'on')
                
                self.update_status("✅ Settings saved and loaded successfully!")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open settings dialog:\n{str(e)}")
    
    def _start_fetch_work_items(self):
        """Start fetching work items"""
        config = self.config_manager.get_config()
        query_url = config.get('AZURE_DEVOPS_QUERY', '').strip()
        azure_token = config.get('AZURE_DEVOPS_PAT', '').strip()
        
        if not query_url:
            messagebox.showerror("Error", "Please enter an Azure DevOps Query URL in Settings")
            return
        
        if not azure_token:
            messagebox.showerror("Error", "Please enter your Azure DevOps token in Settings")
            return
        
        # Clear previous data
        self._clear_data()
        
        # Start processing thread
        thread = threading.Thread(target=self._fetch_work_items, args=(query_url, azure_token))
        thread.daemon = True
        thread.start()
    
    def _start_fetch_uuf_items(self):
        """Start fetching UUF items"""
        config = self.config_manager.get_config()
        
        # Check configuration
        required_fields = [
            'DATAVERSE_ENVIRONMENT_URL',
            'DATAVERSE_TABLE_NAME', 
            'AZURE_AD_CLIENT_ID',
            'AZURE_AD_CLIENT_SECRET',
            'AZURE_AD_TENANT_ID'
        ]
        
        if not all(config.get(field) for field in required_fields):
            messagebox.showerror(
                "Configuration Missing",
                "PowerApp/Dataverse configuration is not complete.\n\n"
                "Please ensure all required fields are set in Settings."
            )
            return
        
        # Clear previous data
        self._clear_data()
        
        # Start processing thread
        thread = threading.Thread(target=self._fetch_uuf_items)
        thread.daemon = True
        thread.start()
    
    def _clear_data(self):
        """Clear previous data"""
        self.current_work_items = []
        self.current_item_index = 0
        self._clear_current_item_display()
        self._clear_all_items_tree()

    def _auto_load_cached_items(self):
        """Automatically load cached items on app startup"""
        try:
            config = self.config_manager.get_config()

            # Try to load Azure DevOps cache first
            query_url = config.get('AZURE_DEVOPS_QUERY', '').strip()
            azure_token = config.get('AZURE_DEVOPS_PAT', '').strip()

            if query_url and azure_token:
                cache_id = query_url
                cached_items = self.cache_manager.load_from_cache('azure_devops', cache_id)

                if cached_items:
                    self.logger.log("=== Auto-loading cached work items ===")
                    self.logger.log(f"✅ Loaded {len(cached_items)} items from cache")
                    self.current_work_items = cached_items

                    # Setup Azure API for operations
                    temp_api = AzureDevOpsAPI("", azure_token, self.logger)
                    org, _, _ = temp_api.parse_query_url(query_url)
                    self.current_organization = org
                    self.azure_api = AzureDevOpsAPI(org, azure_token, self.logger)

                    self._update_after_fetch()
                    self.update_status(f"Loaded {len(cached_items)} items from cache")
                    return

            # Try to load UUF cache if Azure DevOps cache not available
            uuf_env_url = config.get('DATAVERSE_ENVIRONMENT_URL', '').strip()
            uuf_table = config.get('DATAVERSE_TABLE_NAME', '').strip()

            if uuf_env_url and uuf_table:
                cache_id = f"{uuf_env_url}_{uuf_table}"
                cached_items = self.cache_manager.load_from_cache('uuf', cache_id)

                if cached_items:
                    self.logger.log("=== Auto-loading cached UUF items ===")
                    self.logger.log(f"✅ Loaded {len(cached_items)} items from cache")
                    self.current_work_items = cached_items

                    # Setup Dataverse API for operations
                    self.dataverse_api = DataverseAPI(config, self.logger)

                    self._update_after_fetch()
                    self.update_status(f"Loaded {len(cached_items)} UUF items from cache")
                    return

            # No cache available
            self.logger.log("No cached items found")

        except Exception as e:
            self.logger.log(f"⚠️ Error auto-loading cache: {str(e)}")

    def _fetch_work_items(self, query_url: str, azure_token: str):
        """Fetch work items from Azure DevOps (always from server)"""
        try:
            self.fetch_button.config(state='disabled')
            self.progress.start()

            cache_id = query_url
            self.update_status("Fetching work items from Azure DevOps...")
            self.logger.log("=== Fetching work items from Azure DevOps ===")

            # Initialize Azure DevOps API
            temp_api = AzureDevOpsAPI("", azure_token, self.logger)

            # Parse query URL
            org, project, query_id = temp_api.parse_query_url(query_url)
            self.current_organization = org
            self.logger.log(f"Parsed query - Org: {org}, Project: {project}, Query ID: {query_id}")

            # Create proper API instance
            self.azure_api = AzureDevOpsAPI(org, azure_token, self.logger)

            # Execute query and process items
            work_items = self.azure_api.execute_query(org, project, query_id, azure_token)
            self.logger.log(f"Found {len(work_items)} work items")

            # Process items
            self.current_work_items = []
            for item in work_items:
                # REMOVED: Azure DevOps specific processing
                # processed_item = self.work_item_processor.process_work_item(item)
                # TODO: Implement custom item processing here
                processed_item = item  # Placeholder
                if processed_item:
                    self.current_work_items.append(processed_item)

            self.logger.log(f"Successfully processed {len(self.current_work_items)} work items")

            # Save to cache
            if self.cache_manager.save_to_cache('azure_devops', cache_id, self.current_work_items):
                self.logger.log("✅ Work items cached for faster loading next time")

            # Update GUI
            self._update_after_fetch()

        except Exception as e:
            error_msg = f"Error fetching work items: {str(e)}"
            self.logger.log(error_msg)
            self.update_status("Fetch failed!")
            messagebox.showerror("Fetch Error", error_msg)
        finally:
            self.progress.stop()
            self.fetch_button.config(state='normal')
    
    def _fetch_uuf_items(self):
        """Fetch UUF items from Dataverse (always from server)"""
        try:
            self.fetch_uuf_button.config(state='disabled')
            self.progress.start()

            config = self.config_manager.get_config()

            # Create cache ID from config
            cache_id = f"{config.get('DATAVERSE_ENVIRONMENT_URL')}_{config.get('DATAVERSE_TABLE_NAME')}"

            self.update_status("Fetching UUF items from PowerApp/Dataverse...")
            self.logger.log("=== Fetching UUF items from Dataverse ===")

            # Initialize Dataverse API
            self.dataverse_api = DataverseAPI(
                config['DATAVERSE_ENVIRONMENT_URL'],
                config['DATAVERSE_TABLE_NAME'],
                self.logger
            )

            # Authenticate and fetch
            auth_success = self.dataverse_api.authenticate(
                config['AZURE_AD_CLIENT_ID'],
                config['AZURE_AD_CLIENT_SECRET'],
                config['AZURE_AD_TENANT_ID']
            )

            if not auth_success:
                raise RuntimeError("Failed to authenticate with Azure AD")

            uuf_items = self.dataverse_api.fetch_uuf_items()
            self.logger.log(f"Found {len(uuf_items)} UUF items")

            # Process items
            self.current_work_items = []
            for item in uuf_items:
                # REMOVED: UUF/Dataverse specific processing
                # processed_item = self.work_item_processor.process_uuf_item(item)
                # TODO: Implement custom item processing here
                processed_item = item  # Placeholder
                if processed_item:
                    self.current_work_items.append(processed_item)

            self.logger.log(f"Successfully processed {len(self.current_work_items)} UUF items")

            # Save to cache
            if self.cache_manager.save_to_cache('uuf', cache_id, self.current_work_items):
                self.logger.log("✅ UUF items cached for faster loading next time")

            # Update GUI
            self._update_after_fetch()

        except Exception as e:
            error_msg = f"Error fetching UUF items: {str(e)}"
            self.logger.log(error_msg)
            self.update_status("Fetch failed!")
            messagebox.showerror("Fetch Error", error_msg)
        finally:
            self.progress.stop()
            self.fetch_uuf_button.config(state='normal')
    
    def _update_after_fetch(self):
        """Update GUI after successful fetch"""
        self._update_all_items_tree()
        if self.current_work_items:
            self.current_item_index = 0
            self._display_current_item()
            self._update_navigation_buttons()
            self.update_status(f"Loaded {len(self.current_work_items)} items")
        else:
            self.update_status("No valid items found")
    
    def _clear_current_item_display(self):
        """Clear current item display"""
        self.work_item_id_label.config(text="Not loaded", foreground="black", cursor="")
        
        # Clear text widgets
        for widget in [self.nature_text, self.doc_url_text, self.text_to_change_display, self.new_text_display]:
            widget.config(state='normal')
            widget.delete(1.0, tk.END)
            widget.config(state='disabled')
        
        # Reset edit mode
        self.edit_mode = False
        self.edit_button.config(text="✏️ Edit", state='disabled', style='BlueEdit.TButton')
    
    def _clear_all_items_tree(self):
        """Clear all items tree"""
        for item in self.items_tree.get_children():
            self.items_tree.delete(item)
    
    def _display_current_item(self):
        """Display current work item"""
        if not self.current_work_items or self.current_item_index >= len(self.current_work_items):
            return
        
        item = self.current_work_items[self.current_item_index]
        
        # Update work item ID with hyperlink styling
        self.work_item_id_label.config(
            text=f"#{item['id']} - {item['title']}", 
            foreground="blue", 
            cursor="hand2"
        )
        
        # Update text fields
        self._update_text_widget(self.nature_text, item['nature_of_request'])
        self._update_text_widget(self.doc_url_text, item['mydoc_url'])
        self._update_text_widget(self.text_to_change_display, item['text_to_change'])
        self._update_text_widget(self.new_text_display, item['new_text'])
        
        # Reset edit mode
        self.edit_mode = False
        self.edit_button.config(text="✏️ Edit", state='normal', style='BlueEdit.TButton')
        
        # Update dropdown based on source
        if item.get('source') == 'UUF':
            self.action_type_dropdown.set("Create PR")
            self.action_type_dropdown.config(state='disabled')
        else:
            self.action_type_dropdown.config(state='readonly')
        
        # Update counter
        self.item_counter_label.config(text=f"Item {self.current_item_index + 1} of {len(self.current_work_items)}")
        
        # Update highlighting in All Work Items treeview
        self._update_treeview_selection()
    
    def _update_text_widget(self, widget, text):
        """Update a text widget with new content"""
        widget.config(state='normal')
        widget.delete(1.0, tk.END)
        widget.insert(1.0, text)
        widget.config(state='disabled')
    
    def _update_all_items_tree(self):
        """Update all items treeview"""
        self._clear_all_items_tree()
        current_item_id = None
        
        # Get current item ID if available
        if hasattr(self, 'current_work_items') and self.current_work_items and hasattr(self, 'current_item_index'):
            if 0 <= self.current_item_index < len(self.current_work_items):
                current_item_id = self.current_work_items[self.current_item_index]['id']
        
        for item in self.current_work_items:
            nature_preview = item['nature_of_request'][:50] + "..." if len(item['nature_of_request']) > 50 else item['nature_of_request']
            
            github_info = item.get('github_info', {})
            github_repo = ""
            ms_author = ""
            
            if github_info.get('owner') and github_info.get('repo'):
                github_repo = f"{github_info['owner']}/{github_info['repo']}"
            elif github_info.get('error'):
                github_repo = "Error extracting"
            else:
                github_repo = "Not determined"
            
            ms_author = github_info.get('ms_author') or "Not found"
            
            item_id = self.items_tree.insert('', 'end', values=(
                item['id'],
                item['title'][:40] + "..." if len(item['title']) > 40 else item['title'],
                nature_preview,
                github_repo,
                ms_author,
                item['status']
            ))
            
            # Highlight the current item
            if current_item_id and item['id'] == current_item_id:
                self.items_tree.selection_set(item_id)
                self.items_tree.focus(item_id)
                # Configure a tag for highlighting the current item
                self.items_tree.set(item_id, 'Status', f"★ {item['status']}")  # Add star to status

    def _update_treeview_selection(self):
        """Update the selection highlighting in the All Work Items treeview to match current item"""
        if not hasattr(self, 'items_tree') or not self.current_work_items:
            return
            
        try:
            # Get current item ID
            if not (0 <= self.current_item_index < len(self.current_work_items)):
                return
                
            current_item_id = self.current_work_items[self.current_item_index]['id']
            
            # Clear current selection
            self.items_tree.selection_remove(self.items_tree.selection())
            
            # Find and select the current item in the treeview
            for item_id in self.items_tree.get_children():
                item_values = self.items_tree.item(item_id, 'values')
                if item_values and item_values[0] == current_item_id:
                    self.items_tree.selection_set(item_id)
                    self.items_tree.focus(item_id)
                    self.items_tree.see(item_id)  # Scroll to make sure it's visible
                    break
                    
        except Exception as e:
            # Silently handle errors to avoid disrupting the UI
            pass
    
    def _update_navigation_buttons(self):
        """Update navigation button states"""
        has_items = len(self.current_work_items) > 0
        
        self.prev_button.config(state='normal' if has_items and self.current_item_index > 0 else 'disabled')
        self.next_button.config(state='normal' if has_items and self.current_item_index < len(self.current_work_items) - 1 else 'disabled')
        
        # Enable GO button if current item has valid GitHub info
        if has_items:
            current_item = self.current_work_items[self.current_item_index]
            github_info = current_item['github_info']
            has_valid_github = github_info.get('owner') and github_info.get('repo')
            self.go_button.config(state='normal' if has_valid_github else 'disabled')
        else:
            self.go_button.config(state='disabled')
    
    def _previous_item(self):
        """Navigate to previous item"""
        if self.current_item_index > 0:
            self.current_item_index -= 1
            self._display_current_item()
            self._update_navigation_buttons()
    
    def _next_item(self):
        """Navigate to next item"""
        if self.current_item_index < len(self.current_work_items) - 1:
            self.current_item_index += 1
            self._display_current_item()
            self._update_navigation_buttons()
    
    def _toggle_edit_mode(self):
        """Toggle edit mode for proposed new text"""
        if not self.current_work_items or self.current_item_index >= len(self.current_work_items):
            return
        
        if not self.edit_mode:
            # Enter edit mode
            self.edit_mode = True
            self.new_text_display.config(state='normal')
            self.edit_button.config(text="💾 Save", style='OrangeSave.TButton')
            self.logger.log(f"Editing mode enabled for work item #{self.current_work_items[self.current_item_index]['id']}")
        else:
            # Save changes
            current_item = self.current_work_items[self.current_item_index]
            new_text = self.new_text_display.get(1.0, tk.END).strip()
            current_item['new_text'] = new_text
            
            self.edit_mode = False
            self.new_text_display.config(state='disabled')
            self.edit_button.config(text="✏️ Edit", style='BlueEdit.TButton')
            
            self.logger.log(f"Proposed new text updated for work item #{current_item['id']}")
            messagebox.showinfo("Saved", "Proposed new text has been updated!")
    
    def _load_custom_instructions(self):
        """Load custom instructions from config on startup"""
        try:
            config = self.config_manager.get_config()
            custom_instructions = config.get('CUSTOM_INSTRUCTIONS', '')
            
            # Set the text in the custom instructions display
            if hasattr(self, 'custom_instructions_display'):
                self.custom_instructions_display.delete('1.0', tk.END)
                if custom_instructions:
                    self.custom_instructions_display.insert('1.0', custom_instructions)
        except Exception as e:
            self.logger.log(f"Error loading custom instructions: {str(e)}")
    
    def save_custom_instructions(self):
        """Save custom instructions to .env file"""
        try:
            # Get the current instructions from the text widget
            current_instructions = self.custom_instructions_display.get('1.0', tk.END).strip()
            
            # Save to config
            config_values = {'CUSTOM_INSTRUCTIONS': current_instructions}
            success = self.config_manager.save_configuration(config_values)
            
            if success:
                self.logger.log("Custom AI instructions saved to .env file")
                messagebox.showinfo("Saved", "Custom AI instructions have been saved to .env file!")
            else:
                self.logger.log("Failed to save custom AI instructions")
                messagebox.showerror("Error", "Failed to save custom AI instructions to .env file.")
                
        except Exception as e:
            self.logger.log(f"Error saving custom instructions: {str(e)}")
            messagebox.showerror("Error", f"Error saving custom instructions: {str(e)}")
    
    def clear_custom_instructions(self):
        """Clear custom instructions from both UI and .env file"""
        try:
            # Clear the text widget
            if hasattr(self, 'custom_instructions_display'):
                self.custom_instructions_display.delete('1.0', tk.END)
            
            # Save empty value to config
            config_values = {'CUSTOM_INSTRUCTIONS': ''}
            success = self.config_manager.save_configuration(config_values)
            
            if success:
                self.logger.log("Custom AI instructions cleared from .env file")
                messagebox.showinfo("Cleared", "Custom AI instructions have been cleared!")
            else:
                self.logger.log("Failed to clear custom AI instructions")
                messagebox.showerror("Error", "Failed to clear custom AI instructions from .env file.")
                
        except Exception as e:
            self.logger.log(f"Error clearing custom instructions: {str(e)}")
            messagebox.showerror("Error", f"Error clearing custom instructions: {str(e)}")
    
    def _extract_file_path_from_github_url(self, url: str) -> str:
        """Extract file path from GitHub URL
        
        Example: https://github.com/owner/repo/blob/main/path/to/file.md -> path/to/file.md
        """
        if not url or 'github.com' not in url or '/blob/' not in url:
            return ''
        
        try:
            # Split by /blob/ to separate the repo part from the file part
            parts = url.split('/blob/', 1)
            if len(parts) != 2:
                return ''
            
            # Split the second part by / to get branch and file path
            path_parts = parts[1].split('/', 1)
            if len(path_parts) == 2:
                # Return everything after the branch name
                return path_parts[1]
        except Exception as e:
            self.logger.log(f"Warning: Failed to extract file path from URL {url}: {e}")
        
        return ''
    
    def _on_work_item_hover_enter(self, event=None):
        """Handle mouse enter on work item ID"""
        if self.current_work_items and self.current_item_index < len(self.current_work_items):
            self.work_item_id_label.configure(font=('Arial', 10, 'underline'))
    
    def _on_work_item_hover_leave(self, event=None):
        """Handle mouse leave on work item ID"""
        if self.current_work_items and self.current_item_index < len(self.current_work_items):
            self.work_item_id_label.configure(font=('Arial', 10))
    
    def _open_work_item_url(self, event=None):
        """Open work item URL in browser"""
        if not self.current_work_items or self.current_item_index >= len(self.current_work_items):
            return
        
        item = self.current_work_items[self.current_item_index]
        work_item_id = item['id']
        
        if self.current_organization:
            work_item_url = f"https://dev.azure.com/{self.current_organization}/_workitems/edit/{work_item_id}"
            webbrowser.open(work_item_url)
            self.logger.log(f"Opened work item #{work_item_id} in browser: {work_item_url}")
        else:
            messagebox.showwarning("Warning", "Organization not available. Cannot open work item URL.")
    
    def _create_github_resource(self):
        """Create GitHub resource (PR) with cross-repository support and repository verification"""
        try:
            if not self.current_work_items or self.current_item_index >= len(self.current_work_items):
                messagebox.showerror("Error", "No work item selected")
                return
            
            # Get current work item first
            current_item = self.current_work_items[self.current_item_index]
            
            # Get configuration
            config = self.config_manager.get_config()
            github_token = config.get('GITHUB_PAT', '').strip()
            target_repo = config.get('GITHUB_REPO', '').strip()  # Where PR will be created
            forked_repo = config.get('FORKED_REPO', '').strip()  # User's fork where changes will be made
            local_repo_path = config.get('LOCAL_REPO_PATH', '').strip()
            
            if not github_token and not self.dry_run_var.get():
                messagebox.showerror("Error", "Please configure your GitHub token in Settings or enable dry run mode")
                return
            
            if not target_repo:
                messagebox.showerror("Configuration Error", "GitHub target repository not configured.")
                return
            
            # Use forked repo for changes, fall back to target repo if not specified
            source_repo = forked_repo if forked_repo else target_repo
            
            # Check if AI provider is configured to determine workflow
            ai_provider = config.get('AI_PROVIDER', 'none').strip().lower()
            use_ai_workflow = ai_provider and ai_provider not in ['none', '']
            
            # If using AI workflow, automatically ensure local repository exists
            if use_ai_workflow and local_repo_path:
                work_item_repo = self._get_work_item_repository(current_item)
                if work_item_repo:
                    self.logger.log(f"🔄 AI workflow detected - ensuring repository {work_item_repo} is available locally...")
                    try:
                        self._ensure_local_repo(work_item_repo, local_repo_path, github_token)
                    except Exception as e:
                        self.logger.log(f"⚠️ Could not ensure local repository: {str(e)}")
                        # Continue anyway - the AI workflow may still work
            
            # Determine if creating issue or PR
            is_uuf = current_item.get('source') == 'UUF'
            create_pr = self.action_type_var.get() == "Create PR"
            
            # Start appropriate workflow in separate thread
            if is_uuf or (create_pr and not use_ai_workflow):
                # Use cross-repo workflow for UUF items or PRs without AI
                thread = threading.Thread(target=self._process_cross_repo_pr, args=(source_repo, target_repo))
            elif create_pr and use_ai_workflow:
                # Use AI-assisted workflow for PRs with AI provider configured
                thread = threading.Thread(target=self._process_github_pr_with_verification, args=(target_repo, source_repo))
            else:
                # Create GitHub issue
                thread = threading.Thread(target=self._process_github_issue)
            
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            self.logger.log(f"❌ Error in _create_github_resource: {str(e)}")
            messagebox.showerror("Error", f"Failed to create GitHub resource: {str(e)}")
    
    def _process_cross_repo_pr(self, source_repo: str, target_repo: str):
        """Process cross-repository PR creation with auto-cloning"""
        try:
            self.go_button.config(state='disabled')
            self.progress.start()
            
            # Get current work item and config
            current_item = self.current_work_items[self.current_item_index]
            config = self.config_manager.get_config()
            github_token = config.get('GITHUB_PAT', '')
            local_repo_path = config.get('LOCAL_REPO_PATH', '')
            
            # If no source repo specified, try to auto-detect from forked repo config
            if not source_repo or source_repo == target_repo:
                source_repo = config.get('FORKED_REPO', '')
                if not source_repo:
                    # Try to extract from document URL or use target repo
                    github_info = current_item.get('github_info', {})
                    doc_url = github_info.get('mydoc_url', '')
                    if doc_url and 'github.com' in doc_url:
                        # Try to detect repo from URL
                        source_repo = self._detect_repo_from_url(doc_url, github_token)
                    
                    if not source_repo:
                        source_repo = target_repo
            
            # Parse repository information
            try:
                if '/' not in target_repo:
                    raise ValueError("Invalid target repository format")
                target_owner, target_repo_name = target_repo.split('/', 1)
                
                if '/' not in source_repo:
                    raise ValueError("Invalid source repository format") 
                source_owner, source_repo_name = source_repo.split('/', 1)
            except ValueError as e:
                self.logger.log(f"❌ Repository format error: {e}")
                messagebox.showerror("Configuration Error", 
                                   f"Invalid repository format. Use 'owner/repo' format.\n"
                                   f"Target: {target_repo}\nSource: {source_repo}")
                return
            
            # Check if local repository exists, clone if needed
            if local_repo_path and source_owner != target_owner:
                local_source_path = self._ensure_local_repo(source_repo, local_repo_path, github_token)
                if local_source_path:
                    self.logger.log(f"Using local repository: {local_source_path}")
            
            # Initialize GitHub API
            github_api = self.app.create_github_api(github_token)
            github_info = current_item['github_info']
            
            # Create a unique branch name
            from .utils import PRNumberManager
            pr_number = PRNumberManager.get_next_pr_number("cross_repo")
            branch_name = f"docs-update-{pr_number}"
            
            self.logger.log("=== Starting Cross-Repository PR Creation ===")
            self.logger.log(f"Source Repository: {source_owner}/{source_repo_name}")
            self.logger.log(f"Target Repository: {target_owner}/{target_repo_name}")
            self.logger.log(f"Branch Name: {branch_name}")
            
            # Step 1: Create branch in source repository with placeholder commit
            self.logger.log("Creating branch with placeholder commit in source repository...")
            
            # Build instructions for the placeholder
            instructions = f"""
Work Item #{current_item.get('id', 'unknown')}: {current_item.get('title', 'Update documentation')}

**Description:**
{current_item.get('description', 'No description available')}

**Changes needed:**
{current_item.get('new_text', 'See work item details')}
"""
            
            if not github_api.create_branch_with_placeholder(source_owner, source_repo_name, branch_name, instructions):
                self.logger.log("❌ Failed to create branch with placeholder in source repository")
                messagebox.showerror("Error", "Failed to create branch with placeholder in source repository.")
                return
            
            # Step 2: Make documentation changes if AI provider is configured
            ai_provider = config.get('AI_PROVIDER', 'none').strip().lower()
            if ai_provider and ai_provider not in ['none', '']:
                self.logger.log(f"AI provider ({ai_provider}) configured - attempting AI-assisted changes...")
                
                # Try to make documentation changes if we have a file path
                if github_info.get('file_path'):
                    self.logger.log("Making AI-assisted documentation changes...")
                    
                    file_path = github_info['file_path']
                    old_text = current_item.get('text_to_change', '')
                    new_text = current_item.get('new_text', '')
                    commit_message = f"Update documentation - Work Item #{current_item.get('id', 'unknown')}"
                    
                    if github_api.make_documentation_change(
                        source_owner, source_repo_name, branch_name, 
                        file_path, old_text, new_text, commit_message
                    ):
                        self.logger.log("✅ Documentation changes committed successfully")
                    else:
                        self.logger.log("⚠️ Failed to make documentation changes, continuing with PR creation...")
                else:
                    # No file path specified, but AI provider is configured
                    # The AI-assisted workflow should handle this in the full PR creation process
                    self.logger.log("ℹ️ AI provider configured but no specific file path - will use AI in PR workflow")
            else:
                self.logger.log("ℹ️ Using placeholder commit for PR creation (no AI provider configured)")
            
            # Step 3: Create Pull Request
            from .utils import ContentBuilders
            pr_title = ContentBuilders.build_pr_title(current_item)
            pr_body = ContentBuilders.build_pr_body(current_item, github_info)
            
            if source_owner != target_owner or source_repo_name != target_repo_name:
                # Cross-repository PR
                self.logger.log("Creating cross-repository pull request...")
                pr_id, pr_url, pr_num = github_api.create_cross_repo_pull_request(
                    source_owner, source_repo_name, target_owner, target_repo_name,
                    pr_title, pr_body, branch_name
                )
            else:
                # Same repository PR
                self.logger.log("Creating pull request in same repository...")
                target_repo_id = github_api.get_repo_id(target_owner, target_repo_name)
                pr_id, pr_url, pr_num = github_api.create_pull_request(
                    target_repo_id, pr_title, pr_body, branch_name
                )
            
            # Step 4: Handle GitHub Copilot workflow based on AI provider setting
            ai_provider = config.get('AI_PROVIDER', 'none').strip().lower()
            
            if ai_provider and ai_provider not in ['none', '']:
                # AI provider is configured - skip Copilot assignment and comments
                self.logger.log(f"✅ Using AI provider ({ai_provider}) - Skipping GitHub Copilot @mention workflow")
            else:
                # No AI provider - use GitHub Copilot workflow
                self.logger.log("Using GitHub Copilot workflow (no AI provider configured)")
                
                # Assign to GitHub Copilot if available
                copilot_actor_id, copilot_login = github_api.get_copilot_actor_id(target_owner, target_repo_name)
                if copilot_actor_id:
                    self.logger.log(f"Assigning PR to GitHub Copilot ({copilot_login})...")
                    success = github_api.assign_to_copilot(pr_id, [copilot_actor_id])
                    if not success:
                        self.logger.log("ℹ️ Copilot assignment failed due to permissions - this is normal for many repositories")
                        self.logger.log("   The @copilot comment below will still notify Copilot to work on the PR")
                else:
                    self.logger.log("ℹ️ GitHub Copilot not available for assignment in this repository")
                
                # Add Copilot comment with instructions
                self.logger.log("Adding Copilot instruction comment...")
                file_path = github_info.get('file_path', '')
                
                # Extract file path from GitHub URLs if not already set
                if not file_path:
                    # Try extracting from mydoc_url if it's a GitHub URL
                    mydoc_url = github_info.get('mydoc_url', '')
                    if mydoc_url:
                        extracted_path = self._extract_file_path_from_github_url(mydoc_url)
                        if extracted_path:
                            file_path = extracted_path
                            self.logger.log(f"Extracted file path from GitHub URL: {file_path}")
                        else:
                            file_path = f"File path not specified in work item (URL: {mydoc_url})"
                    else:
                        file_path = "See work item description for file details"
                
                # Get custom instructions from config
                custom_instructions = config.get('CUSTOM_INSTRUCTIONS', '')
                
                github_api.add_copilot_comment(
                    target_owner, target_repo_name, pr_num,
                    file_path,
                    current_item.get('text_to_change', ''),
                    current_item.get('new_text', ''),
                    branch_name,
                    str(current_item.get('id', 'unknown')),
                    current_item.get('source', 'Work Item'),
                    github_info.get('mydoc_url', ''),
                    custom_instructions
                )
                
                self.logger.log(f"✅ @copilot comment added with work instructions")
                if copilot_actor_id:
                    self.logger.log(f"📋 Note: Check the PR to see if Copilot assignment worked or needs manual assignment")
            
            self.logger.log(f"✅ Cross-repository PR created successfully: {pr_url}")
            
            # Show success dialog with hyperlink
            self.root.after(0, lambda: HyperlinkDialog(
                self.root,
                "PR Created Successfully!",
                f"Pull request created successfully!\n\n"
                f"Source: {source_owner}/{source_repo_name}:{branch_name}\n"
                f"Target: {target_owner}/{target_repo_name}\n"
                f"PR Number: #{pr_num}",
                pr_url
            ).show())
            
        except Exception as e:
            error_msg = f"Failed to create cross-repository PR: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
        finally:
            self.root.after(0, lambda: self.progress.stop())
            self.root.after(0, lambda: self.go_button.config(state='normal'))
    
    def _ensure_local_repo(self, repo_name: str, local_path: str, github_token: str) -> Optional[str]:
        """Ensure local repository exists, clone if needed"""
        try:
            from .utils import LocalRepositoryScanner
            
            repo_folder = repo_name.split('/')[-1]  # Get just the repo name
            local_repo_path = os.path.join(local_path, repo_folder)
            
            if os.path.exists(local_repo_path):
                # Check if it's actually a Git repo
                if os.path.exists(os.path.join(local_repo_path, '.git')):
                    self.logger.log(f"Local repository already exists: {local_repo_path}")
                    return local_repo_path
                else:
                    self.logger.log(f"Directory exists but not a Git repo: {local_repo_path}")
            
            # Need to clone
            self.logger.log(f"Cloning repository {repo_name} to {local_repo_path}")
            repo_url = f"https://github.com/{repo_name}.git"
            
            if LocalRepositoryScanner.clone_repository(repo_url, local_path, repo_name):
                return local_repo_path
            else:
                self.logger.log(f"❌ Failed to clone repository {repo_name}")
                return None
                
        except Exception as e:
            self.logger.log(f"❌ Error ensuring local repo: {str(e)}")
            return None
    
    def _detect_repo_from_url(self, doc_url: str, github_token: str) -> str:
        """Detect user's fork repository from document URL"""
        try:
            # Extract the base repo from URL
            from urllib.parse import urlparse
            parsed = urlparse(doc_url)
            
            if 'docs.microsoft.com' in parsed.netloc:
                # Try to map Microsoft Docs URL to repository
                if 'fabric' in doc_url.lower():
                    base_repo = 'fabric-docs'
                elif 'azure' in doc_url.lower():
                    base_repo = 'azure-docs'
                elif 'powerbi' in doc_url.lower():
                    base_repo = 'powerbi-docs'
                else:
                    return ''
                
                # Get user's forks to find matching repo
                github_api = self.app.create_github_api(github_token)
                user_forks = github_api.get_user_forks()
                
                for fork in user_forks:
                    if base_repo in fork:
                        self.logger.log(f"Auto-detected forked repository: {fork}")
                        return fork
            
        except Exception as e:
            self.logger.log(f"Error detecting repo from URL: {str(e)}")
        
        return ''

    def _get_work_item_repository(self, work_item: Dict[str, Any]) -> str:
        """Extract repository name from work item"""
        try:
            # First check if github_info has repo information
            github_info = work_item.get('github_info', {})
            if github_info.get('owner') and github_info.get('repo'):
                return f"{github_info['owner']}/{github_info['repo']}"
            
            # Try to detect from mydoc_url
            doc_url = work_item.get('mydoc_url', '')
            if doc_url and 'github.com' in doc_url:
                # Parse GitHub URL to extract repo
                from urllib.parse import urlparse
                parsed = urlparse(doc_url)
                path_parts = parsed.path.strip('/').split('/')
                if len(path_parts) >= 2:
                    return f"{path_parts[0]}/{path_parts[1]}"
            
            # Try to infer from docs URL
            if doc_url and 'docs.microsoft.com' in doc_url:
                if 'fabric' in doc_url.lower():
                    return 'microsoftdocs/fabric-docs'
                elif 'azure' in doc_url.lower():
                    return 'microsoftdocs/azure-docs'
                elif 'powerbi' in doc_url.lower():
                    return 'microsoftdocs/powerbi-docs'
            
            return ''
            
        except Exception as e:
            self.logger.log(f"Error extracting repository from work item: {str(e)}")
            return ''
    
    def _process_github_issue(self):
        """Process GitHub issue creation"""
        try:
            self.go_button.config(state='disabled')
            self.progress.start()

            # Get current work item
            current_item = self.current_work_items[self.current_item_index]
            github_info = current_item['github_info']

            # Get configuration
            config = self.config_manager.get_config()
            github_token = config.get('GITHUB_PAT', '').strip()

            # Get dry run setting from config (most up-to-date value)
            dry_run_config = config.get('DRY_RUN', 'false')
            is_dry_run = str(dry_run_config).lower() in ('true', '1', 'yes', 'on')

            self.logger.log(f"=== Creating GitHub Issue for {current_item.get('source', 'Azure DevOps')} item #{current_item['id']} ===")
            if is_dry_run:
                self.logger.log("🧪 DRY RUN MODE ENABLED - No actual changes will be made")
            self.update_status("Creating GitHub issue...")

            # Create GitHub API instance
            from .github_api import GitHubAPI
            from .utils import ContentBuilders

            github_api = GitHubAPI(github_token, self.logger, is_dry_run)

            # Get repository ID
            owner = github_info['owner']
            repo = github_info['repo']

            self.logger.log(f"Target repository: {owner}/{repo}")
            repo_id = github_api.get_repo_id(owner, repo)

            # Build issue content
            issue_title = ContentBuilders.build_issue_title(current_item)
            issue_body = ContentBuilders.build_issue_body(current_item, github_info)

            self.logger.log(f"Creating issue: {issue_title}")

            # Create the issue
            issue_id, issue_url, issue_number = github_api.create_issue(repo_id, issue_title, issue_body)

            self.logger.log(f"✅ Issue created successfully: {issue_url}")
            self.update_status(f"Issue #{issue_number} created successfully!")

            # Get Copilot actor ID and assign to Copilot if available
            copilot_id, copilot_login = github_api.get_copilot_actor_id(owner, repo)
            
            if copilot_id and issue_id:
                github_api.assign_to_copilot(issue_id, [copilot_id])
                self.logger.log("✅ Assigned to Copilot")
            else:
                self.logger.log("⚠️ Skipped assigning to Copilot (not found)")

            # Update work item status
            current_item['status'] = f'Issue #{issue_number} created'
            current_item['github_url'] = issue_url
            self._update_all_items_tree()

            # Link back to Azure DevOps if applicable (non-critical)
            if current_item.get('source') == 'Azure DevOps' and self.azure_api:
                try:
                    link_title = f"GitHub Issue #{issue_number}"
                    success = self.azure_api.add_github_link_to_work_item(
                        str(current_item['id']),
                        issue_url,
                        link_title
                    )
                    if not success:
                        self.logger.log("⚠️ Could not link issue back to Azure DevOps work item (non-critical)")
                        self.logger.log("   Possible causes: PAT expired, insufficient permissions, or work item locked")
                        self.logger.log("   The issue was created successfully - you can manually link it if needed")
                except Exception as e:
                    self.logger.log(f"⚠️ Could not link issue to Azure DevOps (non-critical): {str(e)}")
                    self.logger.log("   The issue was created successfully - you can manually link it if needed")

            # Show success dialog with clickable link
            HyperlinkDialog(
                self.root,
                "Issue Created",
                f"GitHub Issue #{issue_number} has been created successfully!",
                issue_url
            ).show()

        except Exception as e:
            error_msg = f"Error creating GitHub issue: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.update_status("Issue creation failed!")
            messagebox.showerror("Issue Creation Error", error_msg)
        finally:
            self.progress.stop()
            self.go_button.config(state='normal')

    def _process_github_pr_with_verification(self, target_repo: str, source_repo: str):
        """Process GitHub PR creation with verified repositories"""
        try:
            self.go_button.config(state='disabled')
            self.progress.start()

            # Get current work item
            current_item = self.current_work_items[self.current_item_index]
            github_info = current_item['github_info']

            self.logger.log(f"=== Creating GitHub PR for {current_item.get('source', 'Azure DevOps')} item #{current_item['id']} ===")
            self.logger.log(f"Target Repository: {target_repo}")
            self.logger.log(f"Source Repository: {source_repo}")
            self.update_status("Creating GitHub PR...")

            # Get configuration
            config = self.config_manager.get_config()
            github_token = config.get('GITHUB_PAT', '').strip()
            ai_provider = config.get('AI_PROVIDER', 'none').strip().lower()

            # Get dry run setting from config (most up-to-date value)
            dry_run_config = config.get('DRY_RUN', 'false')
            is_dry_run = str(dry_run_config).lower() in ('true', '1', 'yes', 'on')

            if is_dry_run:
                self.logger.log("🧪 DRY RUN MODE ENABLED - No actual changes will be made")

            # Update config temporarily for this workflow
            temp_config = config.copy()
            temp_config['GITHUB_REPO'] = target_repo
            temp_config['FORKED_REPO'] = source_repo

            # Check if AI provider is configured
            if ai_provider and ai_provider not in ['none', '']:
                # Use AI-assisted workflow with verified repos
                self._process_github_pr_with_ai(current_item, github_info, temp_config)
                return

            # Otherwise use Copilot workflow with verified repos
            self.logger.log("Using GitHub Copilot workflow with verified repositories")

            # Create GitHub API instance
            from .github_api import GitHubAPI
            from .utils import ContentBuilders

            github_api = GitHubAPI(github_token, self.logger, is_dry_run)
            
            # Continue with the standard PR creation but using verified repos
            # Parse repository information
            if '/' not in target_repo:
                raise ValueError("Invalid target repository format")
            target_owner, target_repo_name = target_repo.split('/', 1)
            
            if '/' not in source_repo:
                raise ValueError("Invalid source repository format") 
            source_owner, source_repo_name = source_repo.split('/', 1)

            # Get repository ID for API calls
            repository_id = github_api.get_repo_id(target_owner, target_repo_name)

            # Build PR content
            builders = ContentBuilders()
            pr_title = builders.build_pr_title(current_item)
            pr_body = builders.build_pr_body(current_item, github_info)

            # Create branch and PR
            from .utils import PRNumberManager
            pr_number = PRNumberManager.get_next_pr_number(f"{source_owner}_{source_repo_name}")
            branch_name = f"docs-update-{pr_number}"

            # Create branch in source repo
            if github_api.create_branch_from_main(source_owner, source_repo_name, branch_name):
                self.logger.log(f"✅ Branch '{branch_name}' created in {source_owner}/{source_repo_name}")

                # Create cross-repo PR
                pr_url, pr_html_url, pr_num = github_api.create_cross_repo_pull_request(
                    source_owner, source_repo_name, target_owner, target_repo_name,
                    branch_name, pr_title, pr_body
                )

                if pr_url:
                    self.logger.log(f"✅ Pull request created: {pr_html_url}")
                    
                    # Add Copilot comment with proper parameters
                    file_path = github_info.get('file_path', '')
                    
                    # Extract file path from GitHub URLs if not already set
                    if not file_path:
                        # Try extracting from mydoc_url if it's a GitHub URL
                        mydoc_url = github_info.get('mydoc_url', '')
                        if mydoc_url:
                            extracted_path = self._extract_file_path_from_github_url(mydoc_url)
                            if extracted_path:
                                file_path = extracted_path
                                self.logger.log(f"Extracted file path from GitHub URL: {file_path}")
                            else:
                                file_path = f"File path not specified in work item (URL: {mydoc_url})"
                        else:
                            file_path = "See work item description for file details"
                    
                    # Get custom instructions from config
                    custom_instructions = config.get('CUSTOM_INSTRUCTIONS', '')
                    
                    github_api.add_copilot_comment(
                        target_owner, target_repo_name, pr_num,
                        file_path,
                        current_item.get('text_to_change', ''),
                        current_item.get('new_text', ''),
                        branch_name,
                        str(current_item.get('id', 'unknown')),
                        current_item.get('source', 'Work Item'),
                        github_info.get('mydoc_url', ''),
                        custom_instructions
                    )

                    # Show success dialog
                    dialog = HyperlinkDialog(
                        self.root,
                        "PR Created Successfully",
                        f"Pull request #{pr_num} has been created successfully:",
                        pr_html_url
                    )
                    dialog.show()

                    self.update_status(f"PR #{pr_num} created successfully")
                else:
                    messagebox.showerror("Error", "Failed to create pull request")

        except Exception as e:
            self.logger.log(f"❌ Error creating GitHub PR: {str(e)}")
            messagebox.showerror("Error", f"Failed to create GitHub PR: {str(e)}")

        finally:
            self.progress.stop()
            self.go_button.config(state='normal')

    def _process_github_pr(self):
        """Process GitHub PR creation"""
        try:
            self.go_button.config(state='disabled')
            self.progress.start()

            # Get current work item
            current_item = self.current_work_items[self.current_item_index]
            github_info = current_item['github_info']

            self.logger.log(f"=== Creating GitHub PR for {current_item.get('source', 'Azure DevOps')} item #{current_item['id']} ===")
            self.update_status("Creating GitHub PR...")

            # Get configuration
            config = self.config_manager.get_config()
            github_token = config.get('GITHUB_PAT', '').strip()
            ai_provider = config.get('AI_PROVIDER', 'none').strip().lower()

            # Get dry run setting from config (most up-to-date value)
            dry_run_config = config.get('DRY_RUN', 'false')
            is_dry_run = str(dry_run_config).lower() in ('true', '1', 'yes', 'on')

            if is_dry_run:
                self.logger.log("🧪 DRY RUN MODE ENABLED - No actual changes will be made")

            # Check if AI provider is configured
            if ai_provider and ai_provider not in ['none', '']:
                # Use AI-assisted workflow
                self._process_github_pr_with_ai(current_item, github_info, config)
                return

            # Otherwise use Copilot workflow
            self.logger.log("Using GitHub Copilot workflow (no AI provider configured)")

            # Create GitHub API instance
            from .github_api import GitHubAPI
            from .utils import ContentBuilders

            github_api = GitHubAPI(github_token, self.logger, is_dry_run)

            # Get UPSTREAM repository info (where PR will be created)
            upstream_repo = config.get('GITHUB_REPO', '').strip()
            if not upstream_repo or '/' not in upstream_repo:
                raise ValueError("GITHUB_REPO not configured. Set it in Settings (e.g., microsoft/fabric-docs-pr)")

            upstream_parts = upstream_repo.split('/', 1)
            upstream_owner = upstream_parts[0].strip()
            upstream_repo_name = upstream_parts[1].strip()

            self.logger.log(f"Upstream repository (for PR): {upstream_owner}/{upstream_repo_name}")

            # Get FORK repository info (where branch will be created)
            fork_owner = github_info['owner']
            fork_repo = github_info['repo']

            self.logger.log(f"Fork repository (for branch): {fork_owner}/{fork_repo}")

            # Get upstream repository ID (for creating PR)
            upstream_repo_id = github_api.get_repo_id(upstream_owner, upstream_repo_name)

            # Generate unique branch name
            pr_number = self.config_manager.get_next_pr_number('gh_copilot')
            source_prefix = 'uuf' if current_item.get('source') == 'UUF' else 'ab'
            branch_name = f"{source_prefix}-{current_item['id']}-pr-{pr_number}"

            self.logger.log(f"Creating branch on fork: {branch_name}")

            # Extract file path from GitHub URL
            file_path = None
            if github_info.get('original_content_git_url'):
                # Parse file path from URL
                import re
                url = github_info['original_content_git_url']
                # Match pattern: .../blob/branch/path/to/file.md
                match = re.search(r'/blob/[^/]+/(.+)$', url)
                if match:
                    file_path = match.group(1)
                    self.logger.log(f"Extracted file path: {file_path}")

            # Build PR content
            pr_title = ContentBuilders.build_pr_title(current_item)
            pr_body = ContentBuilders.build_pr_body(current_item, github_info)

            # Build instructions for placeholder commit
            instructions = f"""Update documentation file: {file_path or 'See PR description'}

Current text to replace:
{current_item['text_to_change']}

Proposed new text:
{current_item['new_text']}
"""

            # Create branch on FORK with placeholder commit (so PR can be created)
            self.logger.log("Creating branch on fork with placeholder commit...")
            branch_created = github_api.create_branch_with_placeholder(fork_owner, fork_repo, branch_name, instructions)

            if not branch_created:
                raise RuntimeError("Failed to create branch on fork. Check permissions and try again.")

            # Create the PR on UPSTREAM using fork's branch
            # For fork workflow: head ref must be "fork-owner:branch-name"
            head_ref = f"{fork_owner}:{branch_name}"
            self.logger.log(f"Creating pull request on upstream: {pr_title}")
            self.logger.log(f"PR head: {head_ref} -> base: main on {upstream_owner}/{upstream_repo_name}")

            _, pr_url, pr_number_actual = github_api.create_pull_request(
                upstream_repo_id, pr_title, pr_body, head_ref, "main"
            )

            self.logger.log(f"✅ Pull request created: {pr_url}")

            # Add Copilot comment with instructions (to the fork's branch)
            self.logger.log("Adding instructions for Copilot...")
            
            # Extract file path from GitHub URLs if not already set
            if not file_path:
                # Try extracting from mydoc_url if it's a GitHub URL
                mydoc_url = current_item.get('mydoc_url', '')
                if mydoc_url:
                    extracted_path = self._extract_file_path_from_github_url(mydoc_url)
                    if extracted_path:
                        file_path = extracted_path
                        self.logger.log(f"Extracted file path from GitHub URL: {file_path}")
                    else:
                        file_path = f"File path not specified in work item (URL: {mydoc_url})"
                else:
                    file_path = "See work item description for file details"
            
            # Get custom instructions from config
            config = self.config_manager.get_config()
            custom_instructions = config.get('CUSTOM_INSTRUCTIONS', '')
            
            github_api.add_copilot_comment(
                fork_owner, fork_repo, pr_number_actual,
                file_path,
                current_item['text_to_change'],
                current_item['new_text'],
                branch_name,
                str(current_item['id']),
                current_item.get('source'),
                current_item.get('mydoc_url'),
                custom_instructions
            )

            self.logger.log(f"✅ PR #{pr_number_actual} created successfully with Copilot instructions")
            self.update_status(f"PR #{pr_number_actual} created successfully!")

            # Update work item status
            current_item['status'] = f'PR #{pr_number_actual} created'
            current_item['github_url'] = pr_url
            self._update_all_items_tree()

            # Link back to Azure DevOps if applicable (non-critical)
            if current_item.get('source') == 'Azure DevOps' and self.azure_api:
                try:
                    link_title = f"GitHub PR #{pr_number_actual}"
                    success = self.azure_api.add_github_link_to_work_item(
                        str(current_item['id']),
                        pr_url,
                        link_title
                    )
                    if not success:
                        self.logger.log("⚠️ Could not link PR back to Azure DevOps work item (non-critical)")
                        self.logger.log("   Possible causes: PAT expired, insufficient permissions, or work item locked")
                        self.logger.log("   The PR was created successfully - you can manually link it if needed")
                except Exception as e:
                    self.logger.log(f"⚠️ Could not link PR to Azure DevOps (non-critical): {str(e)}")
                    self.logger.log("   The PR was created successfully - you can manually link it if needed")

            # Show success dialog with clickable link
            HyperlinkDialog(
                self.root,
                "Pull Request Created",
                f"GitHub PR #{pr_number_actual} has been created successfully!\n\n"
                f"Copilot has been instructed to make the requested changes.",
                pr_url
            ).show()

        except Exception as e:
            error_msg = f"Error creating GitHub PR: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.update_status("PR creation failed!")
            messagebox.showerror("PR Creation Error", error_msg)
        finally:
            self.progress.stop()
            self.go_button.config(state='normal')

    def _process_github_pr_with_ai(self, current_item: Dict[str, Any], github_info: Dict[str, Any], config: Dict[str, Any]):
        """Process GitHub PR creation using AI provider (ChatGPT/Claude)"""
        try:
            self.logger.log("=== Using AI-Assisted PR Creation ===")

            # Get AI configuration
            ai_provider = config.get('AI_PROVIDER', '').strip().lower()
            if ai_provider == 'claude':
                api_key = config.get('CLAUDE_API_KEY', '').strip()
            elif ai_provider in ['chatgpt', 'openai', 'gpt']:
                api_key = config.get('OPENAI_API_KEY', '').strip()
            elif ai_provider in ['github-copilot', 'copilot', 'github_copilot']:
                api_key = config.get('GITHUB_TOKEN', '').strip()
            elif ai_provider == 'ollama':
                api_key = config.get('OLLAMA_API_KEY', '').strip()  # Optional for Ollama
            else:
                api_key = ''
            github_token = config.get('GITHUB_PAT', '').strip()
            local_repo_path = config.get('LOCAL_REPO_PATH', '').strip() or None

            # Validate API key (except for Ollama where it's optional)
            if not api_key and ai_provider != 'ollama':
                raise ValueError(f"No API key configured for {ai_provider}. Please configure in Settings.")

            # Get Ollama-specific configuration
            ollama_url = None
            ollama_model = None
            if ai_provider == 'ollama':
                ollama_url = config.get('OLLAMA_URL', '').strip()
                ollama_model = config.get('OLLAMA_MODEL', '').strip()
                if not ollama_url:
                    raise ValueError("Ollama Server URL not configured. Please configure in Settings.")
                if not ollama_model:
                    raise ValueError("Ollama Model not selected. Please configure in Settings.")

            self.logger.log(f"Using AI Provider: {ai_provider.upper()}")

            # Create AI manager
            from .ai_manager import AIManager
            ai_manager = AIManager(self.logger)

            # Create AI provider instance
            ai_provider_instance = ai_manager.create_ai_provider(ai_provider, api_key, ollama_url, ollama_model)
            if not ai_provider_instance:
                raise ValueError(f"Failed to create {ai_provider} provider")

            # Create LocalGitManager
            git_manager = ai_manager.create_local_git_manager(github_token)
            if not git_manager:
                raise ValueError("Failed to create git manager")

            # Get UPSTREAM repository info (where PR will be created)
            upstream_repo = config.get('GITHUB_REPO', '').strip()
            if not upstream_repo or '/' not in upstream_repo:
                raise ValueError("GITHUB_REPO not configured. Set it in Settings (e.g., microsoft/fabric-docs-pr)")

            upstream_parts = upstream_repo.split('/', 1)
            upstream_owner = upstream_parts[0].strip()
            upstream_repo_name = upstream_parts[1].strip()

            self.logger.log(f"Upstream repository (for PR): {upstream_owner}/{upstream_repo_name}")

            # Get FORK repository info (where we work locally)
            # Use github_info from document metadata as the fork
            fork_owner = github_info['owner']
            fork_repo = github_info['repo']

            self.logger.log(f"Fork repository (local work): {fork_owner}/{fork_repo}")
            self.logger.log(f"Local repository base path: {local_repo_path}")

            # Extract file path from GitHub URL
            file_path = None
            if github_info.get('original_content_git_url'):
                import re
                url = github_info['original_content_git_url']
                match = re.search(r'/blob/[^/]+/(.+)$', url)
                if match:
                    file_path = match.group(1)
                    self.logger.log(f"File to modify: {file_path}")

            if not file_path:
                raise ValueError("Could not extract file path from document URL")

            # Generate unique branch name
            pr_number = self.config_manager.get_next_pr_number(ai_provider)
            source_prefix = 'uuf' if current_item.get('source') == 'UUF' else 'ab'
            branch_name = f"{source_prefix}-{current_item['id']}-{ai_provider}-pr-{pr_number}"

            self.logger.log(f"Branch name: {branch_name}")

            # Build commit message
            commit_message = f"Update {file_path}\n\nWork Item: {current_item['id']}\nTitle: {current_item['title']}"

            # Get custom instructions from config
            custom_instructions = config.get('CUSTOM_INSTRUCTIONS', '').strip() or None

            # Make AI-assisted changes on FORK
            self.logger.log("Starting AI-assisted workflow on fork...")
            success, error_msg = git_manager.make_ai_assisted_change(
                fork_owner, fork_repo, branch_name,
                file_path,
                current_item['text_to_change'],
                current_item['new_text'],
                commit_message,
                ai_provider_instance,
                local_repo_path,
                custom_instructions
            )

            if not success:
                raise RuntimeError(error_msg or "AI-assisted change failed")

            # Update the diff display with the actual git diff
            try:
                # Construct the full repository path for git diff
                if local_repo_path:
                    full_repo_path = os.path.join(local_repo_path, fork_owner, fork_repo)
                else:
                    # Fallback to default Downloads location
                    from pathlib import Path
                    full_repo_path = str(Path.home() / "Downloads" / "github_repos" / fork_owner / fork_repo)
                
                diff_content = git_manager.get_git_diff_from_repo(full_repo_path, branch_name)
                if diff_content:
                    self.update_diff_display(diff_content)
                    self.logger.log("📋 Git diff content updated in View Diff tab")
                else:
                    self.logger.log("⚠️ No git diff content found")
            except Exception as e:
                self.logger.log(f"⚠️ Could not update diff display: {e}")

            # Create PR on UPSTREAM repository
            from .github_api import GitHubAPI
            from .utils import ContentBuilders

            self.logger.log(f"Creating PR on upstream: {upstream_owner}/{upstream_repo_name}")
            github_api = GitHubAPI(github_token, self.logger, False)
            repo_id = github_api.get_repo_id(upstream_owner, upstream_repo_name)

            pr_title = ContentBuilders.build_pr_title(current_item)
            pr_body = ContentBuilders.build_pr_body(current_item, github_info)
            pr_body += f"\n\n---\n*Changes made by {ai_provider.upper()} via AI-assisted workflow*"

            # For fork workflow: head ref must be "fork-owner:branch-name"
            head_ref = f"{fork_owner}:{branch_name}"
            self.logger.log(f"Creating pull request: {pr_title}")
            self.logger.log(f"PR head: {head_ref} -> base: main on {upstream_owner}/{upstream_repo_name}")

            _, pr_url, pr_number_actual = github_api.create_pull_request(
                repo_id, pr_title, pr_body, head_ref, "main"
            )

            self.logger.log(f"✅ PR #{pr_number_actual} created successfully with AI-generated changes")
            self.update_status(f"PR #{pr_number_actual} created successfully!")

            # Update work item status
            current_item['status'] = f'PR #{pr_number_actual} created ({ai_provider.upper()})'
            current_item['github_url'] = pr_url
            self._update_all_items_tree()

            # Link back to Azure DevOps if applicable (non-critical)
            if current_item.get('source') == 'Azure DevOps' and self.azure_api:
                try:
                    link_title = f"GitHub PR #{pr_number_actual}"
                    success = self.azure_api.add_github_link_to_work_item(
                        str(current_item['id']),
                        pr_url,
                        link_title
                    )
                    if not success:
                        self.logger.log("⚠️ Could not link PR back to Azure DevOps work item (non-critical)")
                except Exception as e:
                    self.logger.log(f"⚠️ Could not link PR to Azure DevOps (non-critical): {str(e)}")

            # Show success dialog
            HyperlinkDialog(
                self.root,
                "Pull Request Created",
                f"GitHub PR #{pr_number_actual} has been created successfully!\n\n"
                f"{ai_provider.upper()} has made the requested changes and pushed them to the branch.",
                pr_url
            ).show()

        except Exception as e:
            error_msg = f"Error creating AI-assisted PR: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.update_status("AI-assisted PR creation failed!")
            messagebox.showerror("PR Creation Error", error_msg)
        finally:
            self.progress.stop()
            self.go_button.config(state='normal')

    def next_item(self):
        """Navigate to next work item"""
        if self.current_item_index < len(self.current_work_items) - 1:
            self.current_item_index += 1
            self._display_current_item()
            self._update_navigation_buttons()
    
    def previous_item(self):
        """Navigate to previous work item"""
        if self.current_item_index > 0:
            self.current_item_index -= 1
            self._display_current_item()
            self._update_navigation_buttons()

    def _on_item_select(self, event):
        """Handle item selection in the All Work Items treeview"""
        selection = self.items_tree.selection()
        if selection:
            self.selected_tree_item = selection[0]
            self.select_item_button.config(state='normal')
        else:
            self.selected_tree_item = None
            self.select_item_button.config(state='disabled')

    def _on_item_double_click(self, event):
        """Handle double-click on item in the All Work Items treeview"""
        selection = self.items_tree.selection()
        if selection:
            self.selected_tree_item = selection[0]
            self._select_current_item()

    def _select_current_item(self):
        """Select the highlighted item from the treeview as the current work item"""
        if not self.selected_tree_item:
            return
            
        try:
            # Get the work item ID from the selected tree item
            item_values = self.items_tree.item(self.selected_tree_item, 'values')
            if not item_values:
                return
                
            selected_work_item_id = item_values[0]  # ID is in the first column
            
            # Debug logging
            self.logger.log(f"Looking for work item ID: {selected_work_item_id} (type: {type(selected_work_item_id)})")
            self.logger.log(f"Available work items: {len(self.current_work_items)}")
            if self.current_work_items:
                self.logger.log(f"Sample work item ID: {self.current_work_items[0]['id']} (type: {type(self.current_work_items[0]['id'])})")
            
            # Find the work item in the current_work_items list (which contains all loaded items)
            if not self.current_work_items:
                messagebox.showwarning("No Work Items", "No work items are loaded.")
                return
                
            selected_work_item = None
            for work_item in self.current_work_items:
                # Convert both IDs to strings for comparison to handle type mismatches
                if str(work_item['id']) == str(selected_work_item_id):
                    selected_work_item = work_item
                    break
                    
            if not selected_work_item:
                messagebox.showerror("Item Not Found", 
                                   f"Work item #{selected_work_item_id} was not found in the loaded work items.")
                return
            
            # Find the index of the selected work item in the current list
            selected_index = -1
            for i, work_item in enumerate(self.current_work_items):
                if str(work_item['id']) == str(selected_work_item_id):
                    selected_index = i
                    break
            
            if selected_index == -1:
                messagebox.showerror("Item Not Found", 
                                   f"Work item #{selected_work_item_id} was not found in the loaded work items.")
                return
            
            # Set the current item index to the selected item (keeping the full list intact)
            self.current_item_index = selected_index
            
            # Update the display
            self._display_current_item()
            self._update_navigation_buttons()
            
            # Switch to the main work item tab to show the selected item
            self.notebook.select(0)  # Select the first tab (main work item tab)
            
            # Log the selection
            self.logger.log(f"📌 Selected work item #{selected_work_item_id} as current item")
            self.logger.log(f"Title: {selected_work_item['title']}")
                                 
        except Exception as e:
            self.logger.log(f"❌ Error selecting work item: {e}")
            messagebox.showerror("Error", f"Failed to select work item:\n{str(e)}")
    
    def create_github_resource(self):
        """Create GitHub issue or PR for current work item"""
        return self._create_github_resource()
    
    def start_fetch_work_items(self):
        """Start fetching work items"""
        return self._start_fetch_work_items()
    
    def start_fetch_uuf_items(self):
        """Start fetching UUF items"""
        return self._start_fetch_uuf_items()

    def toggle_edit_mode(self):
        """Toggle edit mode for the Proposed New Text field"""
        return self._toggle_edit_mode()
    
    def on_work_item_hover_enter(self, event=None):
        """Handle mouse enter on work item ID label"""
        return self._on_work_item_hover_enter(event)
    
    def on_work_item_hover_leave(self, event=None):
        """Handle mouse leave on work item ID label"""
        return self._on_work_item_hover_leave(event)
    
    def open_work_item_url(self, event=None):
        """Open the Azure DevOps work item URL in the browser"""
        return self._open_work_item_url(event)
    
    def check_ai_modules_manual(self):
        """Manually check AI modules"""
        return self._check_ai_modules_manual()
    
    def open_settings(self):
        """Open settings dialog"""
        return self._open_settings()
    
    def update_action_button_text(self):
        """Update action button text based on dropdown selection"""
        action_type = self.action_type_var.get()
        if action_type == "Create PR":
            self.go_button.config(text="🚀 Create PR")
        else:
            self.go_button.config(text="🚀 Create Issue")
    
    def check_ai_provider_setup(self):
        """Check AI provider setup and offer to install missing modules"""
        try:
            config = self.config_manager.get_config()
            ai_provider = config.get('AI_PROVIDER', '').strip().lower()

            if not ai_provider or ai_provider == 'none' or ai_provider == '':
                return  # No AI provider selected

            # Check if this provider requires special modules
            if ai_provider not in ['chatgpt', 'claude', 'anthropic', 'github-copilot', 'copilot', 'github_copilot']:
                return  # Unknown provider, skip check

            # Check module availability using AI manager
            self.ai_manager.check_and_install_ai_modules(ai_provider, self.root)

        except Exception as e:
            self.logger.log(f"Error checking AI provider setup: {str(e)}")

    # ===== GitHub Tools Methods =====

    def _init_load_repos(self):
        """Initialize loading of repositories"""
        self._load_target_repos_async()
        self._load_forked_repos_async()

    def _load_target_repos_async(self):
        """Load target repositories asynchronously"""
        def load_repos():
            try:
                config = self.config_manager.get_config()
                github_token = config.get('GITHUB_PAT', '')
                if not github_token:
                    return

                from .workflow import GitHubRepoFetcher
                repo_fetcher = GitHubRepoFetcher(github_token, self.logger)
                repos = repo_fetcher.fetch_repos_with_permissions(min_permission='push')
                self.target_repos = repo_fetcher.get_repo_names(repos)

                # Update dropdown on main thread
                self.root.after(0, self._update_target_dropdown)

            except Exception as e:
                self.logger.log(f"Error loading target repos: {e}")

        threading.Thread(target=load_repos, daemon=True).start()

    def _update_target_dropdown(self):
        """Update the target repository dropdown"""
        try:
            current_values = ['']  # Start with empty option

            # Add user's repos with edit access
            if self.target_repos:
                current_values.append('--- Your Repos (with edit access) ---')
                current_values.extend(self.target_repos)

            self.target_repo_dropdown['values'] = current_values

        except Exception as e:
            self.logger.log(f"Error updating target dropdown: {e}")

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
                config = self.config_manager.get_config()
                github_token = config.get('GITHUB_PAT', '')
                if not github_token:
                    return

                from .workflow import GitHubRepoFetcher
                repo_fetcher = GitHubRepoFetcher(github_token, self.logger)
                repos = repo_fetcher.search_repositories(query, per_page=50)
                search_results = repo_fetcher.get_repo_names(repos)

                # Update dropdown on main thread
                self.root.after(0, lambda: self._update_target_search_results(search_results))

            except Exception as e:
                self.logger.log(f"Error searching repos: {e}")

        threading.Thread(target=search_repos, daemon=True).start()

    def _update_target_search_results(self, search_results):
        """Update target dropdown with search results"""
        try:
            current_values = ['']

            # Add user's repos
            if self.target_repos:
                current_values.append('--- Your Repos (with edit access) ---')
                current_values.extend(self.target_repos)

            # Add search results
            if search_results:
                current_values.append('--- Search Results ---')
                current_values.extend(search_results)

            self.target_repo_dropdown['values'] = current_values

        except Exception as e:
            self.logger.log(f"Error updating search results: {e}")

    def _on_target_repo_search(self, _event):
        """Handle typing in target repo field for auto-search"""
        # Debounce: only search after user stops typing for 500ms
        if hasattr(self, '_search_timer'):
            self.root.after_cancel(self._search_timer)

        query = self.target_repo_var.get().strip()
        if len(query) >= 3:  # Only search if at least 3 characters
            self._search_timer = self.root.after(500, self._search_target_repos)

    def _load_forked_repos_async(self):
        """Load forked repositories asynchronously"""
        def load_forks():
            try:
                config = self.config_manager.get_config()
                github_token = config.get('GITHUB_PAT', '')
                local_repo_path = config.get('LOCAL_REPO_PATH', '')

                # Load local repos
                local_repos = []
                if local_repo_path:
                    try:
                        from .utils import LocalRepositoryScanner
                        local_repos = LocalRepositoryScanner.scan_local_repos(local_repo_path)
                    except Exception as e:
                        self.logger.log(f"Error scanning local repos: {e}")

                # Load GitHub repos
                github_repos = []
                if github_token:
                    try:
                        from .workflow import GitHubRepoFetcher
                        repo_fetcher = GitHubRepoFetcher(github_token, self.logger)
                        repos = repo_fetcher.fetch_user_repos(repo_type='owner')
                        github_repos = repo_fetcher.get_repo_names(repos)
                    except Exception as e:
                        self.logger.log(f"Error loading GitHub repos: {e}")

                self.forked_repos = {'local': local_repos, 'github': github_repos}

                # Update dropdown on main thread
                self.root.after(0, self._update_forked_dropdown)

            except Exception as e:
                self.logger.log(f"Error loading forked repos: {e}")

        threading.Thread(target=load_forks, daemon=True).start()

    def _update_forked_dropdown(self):
        """Update the forked repository dropdown"""
        try:
            current_values = ['']  # Start with empty option

            # Add local repos
            if self.forked_repos.get('local'):
                current_values.append('--- Local Repositories ---')
                current_values.extend(self.forked_repos['local'])

            # Add GitHub repos
            if self.forked_repos.get('github'):
                current_values.append('--- Your GitHub Forks ---')
                current_values.extend(self.forked_repos['github'])

            self.forked_repo_dropdown['values'] = current_values

        except Exception as e:
            self.logger.log(f"Error updating forked dropdown: {e}")

    def _refresh_forked_repos(self):
        """Refresh forked repositories"""
        self._load_forked_repos_async()

    def _clone_forked_repo(self):
        """Clone the selected forked repository"""
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

        config = self.config_manager.get_config()
        local_repo_path = config.get('LOCAL_REPO_PATH', '').strip()
        if not local_repo_path:
            messagebox.showwarning("Local Path Not Configured",
                                 "Please configure the Local Repository Path in settings first.")
            return

        # Clone logic (similar to settings_dialog.py)
        import subprocess
        import os

        try:
            os.makedirs(local_repo_path, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Directory Error",
                               f"Could not create local repository directory:\n{str(e)}")
            return

        # Extract repo name
        repo_name = selected_repo
        if '/' not in repo_name:
            messagebox.showerror("Invalid Repository",
                               "Repository must be in 'owner/repo' format.")
            return

        folder_name = repo_name.split('/')[-1]
        target_path = os.path.join(local_repo_path, folder_name)

        if os.path.exists(target_path):
            response = messagebox.askyesno("Directory Exists",
                                          f"The directory '{folder_name}' already exists.\n\n"
                                          f"Do you want to continue anyway?")
            if not response:
                return

        clone_url = f"https://github.com/{repo_name}.git"

        def clone_repo():
            try:
                result = subprocess.run(
                    ['git', 'clone', clone_url, target_path],
                    capture_output=True,
                    text=True,
                    timeout=300
                )

                if result.returncode == 0:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Clone Successful",
                        f"Successfully cloned {repo_name}!"))
                    self.root.after(0, self._refresh_forked_repos)
                else:
                    error_msg = result.stderr if result.stderr else result.stdout
                    self.root.after(0, lambda: messagebox.showerror(
                        "Clone Failed",
                        f"Failed to clone {repo_name}.\n\n{error_msg}"))

            except subprocess.TimeoutExpired:
                self.root.after(0, lambda: messagebox.showerror(
                    "Clone Timeout",
                    f"Cloning {repo_name} timed out after 5 minutes."))
            except FileNotFoundError:
                self.root.after(0, lambda: messagebox.showerror(
                    "Git Not Found",
                    "Git is not installed or not found in PATH."))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(
                    "Clone Error",
                    f"An error occurred while cloning:\n{str(e)}"))

        messagebox.showinfo("Cloning Repository",
                          f"Cloning {repo_name} to:\n{target_path}\n\n"
                          f"This may take a few moments...")

        threading.Thread(target=clone_repo, daemon=True).start()

    def _on_mode_changed(self):
        """Handle mode change between Create and Action"""
        mode = self.tools_mode_var.get()

        if mode == "action":
            # Show action mode widgets
            for widget in self.action_mode_widgets:
                widget.grid()

            # Hide create mode widgets
            for widget in self.create_mode_widgets:
                widget.grid_remove()
        else:  # create mode
            # Hide action mode widgets
            for widget in self.action_mode_widgets:
                widget.grid_remove()

            # Show create mode widgets
            for widget in self.create_mode_widgets:
                widget.grid()

    def _create_new_item(self):
        """Handle creating a new PR or Issue"""
        create_type = self.create_type_var.get()
        target_repo = self.target_repo_var.get().strip()

        # Skip section headers
        if target_repo.startswith('---'):
            target_repo = ''

        if not target_repo:
            messagebox.showwarning("No Repository Selected",
                                 "Please select a target repository.")
            return

        if create_type == "pull_request":
            # TODO: Implement PR creation workflow
            messagebox.showinfo("Create Pull Request",
                              f"PR creation workflow for {target_repo} will be implemented here.\n\n"
                              "This will open the PR creation interface in the tabs below.")
        else:  # issue
            # TODO: Implement Issue creation workflow
            messagebox.showinfo("Create Issue",
                              f"Issue creation workflow for {target_repo} will be implemented here.\n\n"
                              "This will open the Issue creation interface in the tabs below.")

    def _on_repo_selection_changed(self):
        """Handle repository selection change"""
        # Clear workflow items when repos change
        self.workflow_items = []
        self.current_workflow_items = []
        self.workflow_item_dropdown['values'] = ['']
        self.workflow_item_var.set('')
        self.item_counter_label.config(text="No items loaded")

    def _load_workflow_items(self):
        """Load workflow items from selected repositories"""
        target_repo = self.target_repo_var.get().strip()
        forked_repo = self.forked_repo_var.get().strip()

        # Skip section headers
        if target_repo.startswith('---'):
            target_repo = ''
        if forked_repo.startswith('---'):
            forked_repo = ''

        if not target_repo and not forked_repo:
            messagebox.showwarning("No Repositories Selected",
                                 "Please select at least one repository.")
            return

        self.progress.start()
        self.update_status("Loading workflow items...")

        def load_items():
            try:
                config = self.config_manager.get_config()
                github_token = config.get('GITHUB_PAT', '')

                from .workflow import WorkflowManager
                workflow_manager = WorkflowManager(github_token, self.logger)

                # Fetch all items
                results = workflow_manager.fetch_all_workflow_items(
                    target_repo=target_repo if target_repo else None,
                    fork_repo=forked_repo if forked_repo else None,
                    include_issues=True,
                    include_prs=True,
                    state='open'  # Only load open items
                )

                self.workflow_items = results

                # Update UI on main thread
                self.root.after(0, self._on_workflow_items_loaded)

            except Exception as e:
                self.logger.log(f"Error loading workflow items: {e}")
                self.root.after(0, lambda: self.update_status("Failed to load workflow items"))
                self.root.after(0, lambda: messagebox.showerror(
                    "Load Error",
                    f"Failed to load workflow items:\n{str(e)}"))
            finally:
                self.root.after(0, self.progress.stop)

        threading.Thread(target=load_items, daemon=True).start()

    def _on_workflow_items_loaded(self):
        """Handle workflow items loaded"""
        total_items = sum(len(items) for items in self.workflow_items.values())
        self.logger.log(f"Loaded {total_items} workflow items")
        self.update_status(f"Loaded {total_items} workflow items")

        # Apply current filters
        self._filter_workflow_items()

    def _filter_workflow_items(self):
        """Filter workflow items based on current selections"""
        if not self.workflow_items:
            return

        repo_source = self.repo_source_var.get()  # 'target' or 'fork'
        item_type = self.item_type_var.get()  # 'pull_request' or 'issue'

        # Get the appropriate list
        # WorkflowManager returns keys like: 'target_prs', 'target_issues', 'fork_prs', 'fork_issues'
        key = f"{repo_source}_prs" if item_type == 'pull_request' else f"{repo_source}_issues"
        filtered_items = self.workflow_items.get(key, [])

        # Update dropdown
        self.current_workflow_items = filtered_items
        item_options = [
            f"#{item.number} - {item.title}" for item in filtered_items
        ]

        self.workflow_item_dropdown['values'] = item_options if item_options else ['']
        self.workflow_item_var.set('')

        # Update counter
        count = len(filtered_items)
        source_name = "Target" if repo_source == "target" else "Fork"
        type_name = "PRs" if item_type == "pull_request" else "Issues"
        self.item_counter_label.config(text=f"{count} {source_name} {type_name}")

    def _on_workflow_item_selected(self, _event):
        """Handle workflow item selection"""
        selected = self.workflow_item_var.get()
        if not selected:
            return

        # Extract item number from selection
        try:
            item_number = int(selected.split('#')[1].split(' ')[0])

            # Find the item
            for item in self.current_workflow_items:
                if item.number == item_number:
                    self._display_workflow_item(item)
                    break

        except Exception as e:
            self.logger.log(f"Error selecting workflow item: {e}")

    def _display_workflow_item(self, item):
        """Display workflow item details"""
        # Update Current Work Item tab
        self.work_item_id_label.config(text=f"{item.item_type.upper()} #{item.number}")

        # Update nature text
        self.nature_text.config(state='normal')
        self.nature_text.delete('1.0', tk.END)
        self.nature_text.insert('1.0', item.title)
        self.nature_text.config(state='disabled')

        # Update URL
        self.doc_url_text.config(state='normal')
        self.doc_url_text.delete('1.0', tk.END)
        self.doc_url_text.insert('1.0', item.url)
        self.doc_url_text.config(state='disabled')

        # Update description
        self.description_text.config(state='normal')
        self.description_text.delete('1.0', tk.END)
        self.description_text.insert('1.0', item.body or 'No description')
        self.description_text.config(state='disabled')

        self.logger.log(f"Displaying {item.item_type} #{item.number}: {item.title}")
    
    def display_current_item(self):
        """Display current work item (public method for compatibility)"""
        return self._display_current_item()
    
    def update_navigation_buttons(self):
        """Update navigation button states (public method for compatibility)"""
        return self._update_navigation_buttons()
    
    def update_all_items_tree(self):
        """Update all items tree (public method for compatibility)"""
        return self._update_all_items_tree()
    
    def process_github_issue(self):
        """Process GitHub issue creation (public method for compatibility)"""
        return self._process_github_issue()
    
    def process_github_pr(self):
        """Process GitHub PR creation (public method for compatibility)"""
        return self._process_github_pr()
    
    def update_diff_display(self, diff_content):
        """Update the diff display with AI-generated patch content"""
        try:
            self.diff_text.config(state='normal')
            self.diff_text.delete('1.0', tk.END)
            
            if not diff_content or diff_content.strip() == "":
                self.diff_text.insert(tk.END, "No diff content available yet.\nDiffs will be generated from git changes or you can load existing .diff files using the 'Find .diff Files' button.")
                self.diff_text.config(state='disabled')
                self.clear_diff_button.config(state='disabled')
                return
            
            # Clean and validate diff content
            diff_content = self._clean_diff_content(diff_content)
            
            # Parse and highlight diff content
            lines = diff_content.split('\n')
            for line in lines:
                if line.startswith('---') or line.startswith('+++'):
                    self.diff_text.insert(tk.END, line + '\n', 'diff_file')
                elif line.startswith('@@'):
                    self.diff_text.insert(tk.END, line + '\n', 'diff_line_numbers')
                elif line.startswith('+') and not line.startswith('+++'):
                    self.diff_text.insert(tk.END, line + '\n', 'diff_add')
                elif line.startswith('-') and not line.startswith('---'):
                    self.diff_text.insert(tk.END, line + '\n', 'diff_remove')
                elif line.startswith('diff ') or line.startswith('index '):
                    self.diff_text.insert(tk.END, line + '\n', 'diff_header')
                else:
                    self.diff_text.insert(tk.END, line + '\n', 'diff_context')
            
            self.diff_text.config(state='disabled')
            self.clear_diff_button.config(state='normal')
            
            # Log the diff update
            self.logger.log("✅ Diff content displayed in View Diff tab")
            
        except Exception as e:
            self.logger.log(f"❌ Error updating diff display: {e}")
    
    def clear_diff_display(self):
        """Clear the diff display"""
        try:
            self.diff_text.config(state='normal')
            self.diff_text.delete('1.0', tk.END)
            self.diff_text.insert(tk.END, "Diff cleared.\nUse 'Find .diff Files' button to load existing diff files from local repositories.")
            self.diff_text.config(state='disabled')
            self.clear_diff_button.config(state='disabled')
            self.logger.log("🧹 Diff display cleared")
        except Exception as e:
            self.logger.log(f"❌ Error clearing diff display: {e}")

    def find_and_load_diff_files(self):
        """Find and load existing .diff files from local repositories"""
        try:
            import os
            import glob
            from tkinter import messagebox
            from pathlib import Path
            
            # Get local repo path from settings
            local_repo_path = self.config_manager.get('LOCAL_REPO_PATH', '').strip()
            if not local_repo_path or not os.path.exists(local_repo_path):
                self.logger.log("⚠️ No local repo path configured or path doesn't exist")
                messagebox.showwarning("No Local Repo Path", 
                                     "Please configure LOCAL_REPO_PATH in Settings to find diff files.")
                return
            
            base_path = Path(local_repo_path)
            diff_files = []
            
            # First, try to find detected repositories (owner/repo structure)
            detected_repos = []
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
                            detected_repos.append(repo_dir)
                            self.logger.log(f"🔍 Scanning for diff files in: {owner_dir.name}/{repo_dir.name}")
            except Exception as e:
                self.logger.log(f"⚠️ Error scanning for repositories: {e}")
            
            # Search for .diff files in detected repositories first
            if detected_repos:
                for repo_path in detected_repos:
                    for root, dirs, files in os.walk(repo_path):
                        for file in files:
                            if file.endswith('.diff'):
                                full_path = os.path.join(root, file)
                                relative_path = os.path.relpath(full_path, local_repo_path)
                                diff_files.append((relative_path, full_path))
            
            # If no diff files found in detected repos, fallback to searching entire base path
            if not diff_files:
                self.logger.log("🔍 No diff files found in detected repositories, searching entire base path...")
                for root, dirs, files in os.walk(local_repo_path):
                    for file in files:
                        if file.endswith('.diff'):
                            full_path = os.path.join(root, file)
                            relative_path = os.path.relpath(full_path, local_repo_path)
                            diff_files.append((relative_path, full_path))
            
            if not diff_files:
                self.logger.log("ℹ️ No .diff files found in local repositories")
                messagebox.showinfo("No Diff Files Found", 
                                  f"No .diff files found in {local_repo_path}\n\nSearched in:\n" + 
                                  "\n".join([f"  • {repo.parent.name}/{repo.name}" for repo in detected_repos]) if detected_repos else f"  • {local_repo_path}")
                return
            
            self.logger.log(f"📁 Found {len(diff_files)} diff file(s)")
            
            # If only one diff file, load it directly
            if len(diff_files) == 1:
                file_path = diff_files[0][1]
                self._load_diff_file(file_path)
                return
            
            # If multiple files, show selection dialog
            self._show_diff_file_selection(diff_files)
            
        except Exception as e:
            self.logger.log(f"❌ Error finding diff files: {e}")
            messagebox.showerror("Error", f"Error finding diff files: {e}")

    def _show_diff_file_selection(self, diff_files):
        """Show dialog to select which diff file to load"""
        try:
            import tkinter as tk
            from tkinter import ttk, messagebox
            
            # Create selection dialog
            selection_window = tk.Toplevel(self.root)
            selection_window.title("Select Diff File")
            selection_window.geometry("600x400")
            selection_window.transient(self.root)
            selection_window.grab_set()
            
            # Center the window
            selection_window.geometry("+%d+%d" % 
                                    (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
            
            frame = ttk.Frame(selection_window)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # Title
            ttk.Label(frame, text="Select a .diff file to view:", 
                     font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(0, 10))
            
            # Listbox with scrollbar
            listbox_frame = ttk.Frame(frame)
            listbox_frame.pack(fill=tk.BOTH, expand=True)
            
            scrollbar = ttk.Scrollbar(listbox_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, 
                                font=('Courier New', 9))
            listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            
            # Populate listbox
            for relative_path, full_path in diff_files:
                listbox.insert(tk.END, relative_path)
            
            # Buttons
            button_frame = ttk.Frame(frame)
            button_frame.pack(fill=tk.X, pady=(10, 0))
            
            def load_selected():
                selection = listbox.curselection()
                if selection:
                    selected_file = diff_files[selection[0]][1]
                    selection_window.destroy()
                    self._load_diff_file(selected_file)
                else:
                    messagebox.showwarning("No Selection", "Please select a diff file to load.")
            
            ttk.Button(button_frame, text="Load Selected", command=load_selected).pack(side=tk.LEFT)
            ttk.Button(button_frame, text="Cancel", 
                      command=selection_window.destroy).pack(side=tk.LEFT, padx=(10, 0))
            
            # Double-click to load
            listbox.bind('<Double-Button-1>', lambda e: load_selected())
            
        except Exception as e:
            self.logger.log(f"❌ Error showing diff file selection: {e}")

    def _load_diff_file(self, file_path):
        """Load and display a specific diff file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                diff_content = f.read()
            
            if diff_content.strip():
                self.update_diff_display(diff_content)
                self.logger.log(f"✅ Loaded diff file: {os.path.basename(file_path)}")
            else:
                self.logger.log(f"⚠️ Diff file is empty: {file_path}")
                
        except Exception as e:
            self.logger.log(f"❌ Error loading diff file {file_path}: {e}")
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error loading diff file:\n{e}")
    
    def _clean_diff_content(self, diff_content: str) -> str:
        """Clean and fix common issues with AI-generated diff content"""
        try:
            lines = diff_content.split('\n')
            cleaned_lines = []
            
            for i, line in enumerate(lines):
                # Remove duplicate +++ lines that sometimes appear
                if line.startswith('+++') and i > 0:
                    # Check if previous line was also +++
                    prev_line = lines[i-1] if i > 0 else ""
                    if prev_line.startswith('+++'):
                        continue  # Skip duplicate
                
                # Fix malformed file headers
                if line.startswith('title:') and not line.startswith('---'):
                    # This looks like metadata that shouldn't be removed
                    continue
                
                cleaned_lines.append(line)
            
            cleaned_diff = '\n'.join(cleaned_lines)
            
            # If the diff looks seriously malformed, add a warning
            if '+++' in cleaned_diff and cleaned_diff.count('+++') > 2:
                warning = "⚠️ WARNING: This diff may have formatting issues. Please review carefully.\n\n"
                return warning + cleaned_diff
            
            return cleaned_diff
            
        except Exception as e:
            self.logger.log(f"⚠️ Error cleaning diff content: {e}")
            return diff_content  # Return original if cleaning fails