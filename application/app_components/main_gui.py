"""
Main GUI Interface (Flet version)
The primary user interface for the application
"""

import flet as ft
# Compatibility fix for Flet 0.28+ (Icons vs icons, Colors vs colors)
ft.icons = ft.Icons
ft.colors = ft.Colors
import os
import threading
import webbrowser
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from .utils import Logger
from .settings_dialog import SettingsDialog


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

    def __init__(self, page: ft.Page, config_manager, ai_manager, app):
        self.page = page
        self.config_manager = config_manager
        self.ai_manager = ai_manager
        self.app = app

        # Application state
        self.current_work_items = []
        self.current_item_index = 0
        self.current_organization = None
        self.edit_mode = False
        self.workflow_items = {}
        self.current_workflow_items = []

        # Repository data
        self.target_repos = []
        self.forked_repos = {'local': [], 'github': []}

        # Create dry run compatibility wrapper
        self.dry_run_var = DryRunVar(app)

        # UI References
        self.status_text_ref = ft.Ref[ft.Text]()
        self.progress_bar_ref = ft.Ref[ft.ProgressBar]()
        self.work_item_id_ref = ft.Ref[ft.Text]()
        self.nature_text_ref = ft.Ref[ft.TextField]()
        self.live_doc_url_ref = ft.Ref[ft.TextField]()
        self.text_to_change_ref = ft.Ref[ft.TextField]()
        self.proposed_new_text_ref = ft.Ref[ft.TextField]()
        self.custom_instructions_ref = ft.Ref[ft.TextField]()
        self.diff_text_ref = ft.Ref[ft.TextField]()
        self.log_text_ref = ft.Ref[ft.TextField]()
        self.edit_button_ref = ft.Ref[ft.IconButton]()
        self.prev_button_ref = ft.Ref[ft.IconButton]()
        self.next_button_ref = ft.Ref[ft.IconButton]()
        self.go_button_ref = ft.Ref[ft.ElevatedButton]()

        # Mode and filter refs
        self.tools_mode_ref = ft.Ref[ft.RadioGroup]()
        self.repo_source_ref = ft.Ref[ft.RadioGroup]()
        self.item_type_ref = ft.Ref[ft.RadioGroup]()
        self.create_type_ref = ft.Ref[ft.RadioGroup]()
        self.target_repo_dropdown_ref = ft.Ref[ft.Dropdown]()
        self.forked_repo_dropdown_ref = ft.Ref[ft.Dropdown]()
        self.workflow_item_dropdown_ref = ft.Ref[ft.Dropdown]()
        self.item_counter_ref = ft.Ref[ft.Text]()

        # DataTable ref for all items
        self.items_table_ref = ft.Ref[ft.DataTable]()

        # Sidebar state
        self.sidebar_visible = True
        self.sidebar_ref = ft.Ref[ft.Container]()
        self.tools_content_ref = ft.Ref[ft.Column]()

        # Initialize cache manager
        from .cache_manager import CacheManager
        self.cache_manager = CacheManager(cache_duration_hours=24)

        # Initialize logger
        self.logger = None  # Will be set after UI is created

        # Register settings change listener for live updates
        self.config_manager.register_listener(self._on_settings_changed)

    def build(self) -> ft.Container:
        """Build and return the main UI with VS Code-style layout"""
        # Top navigation bar with branding and buttons
        top_nav = ft.Container(
            content=ft.Row(
                [
                    ft.IconButton(
                        icon=ft.icons.MENU,
                        tooltip="Toggle GitHub Tools",
                        on_click=self._toggle_sidebar,
                    ),
                    ft.Icon(ft.icons.BOLT, color="blue", size=24),
                    ft.Text(
                        "GitHub Pulse",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color="blue",
                    ),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.icons.PSYCHOLOGY,
                        tooltip="Check AI Modules",
                        on_click=self._check_ai_modules_manual,
                    ),
                    ft.IconButton(
                        icon=ft.icons.SETTINGS,
                        tooltip="Settings",
                        on_click=self._open_settings,
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=15,
            bgcolor=ft.colors.BLUE_GREY_900,
        )

        # Create sidebar (GitHub Tools) - collapsible
        sidebar = ft.Container(
            ref=self.sidebar_ref,
            content=self._create_sidebar_content(),
            width=350,
            bgcolor=ft.colors.BLUE_GREY_900,
            padding=15,
        )

        # Create main content area (tabs + status)
        main_content = ft.Column(
            [
                self._create_status_section(),
                self._create_tabs_section(),
            ],
            spacing=10,
            expand=True,
        )

        # Bottom section: Sidebar on left, content on right
        bottom_section = ft.Row(
            [
                sidebar,
                ft.VerticalDivider(width=1),
                ft.Container(
                    content=main_content,
                    expand=True,
                    padding=20,
                ),
            ],
            spacing=0,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        # Overall layout: Top nav + bottom section
        app_layout = ft.Column(
            [
                top_nav,
                ft.Divider(height=1),
                bottom_section,
            ],
            spacing=0,
            expand=True,
        )

        # Initialize logger after UI is created
        if self.log_text_ref.current:
            self.logger = Logger(self.log_text_ref.current)

        # Start async initialization
        self.page.run_task(self._async_init)

        return ft.Container(
            content=app_layout,
            expand=True,
        )

    async def _async_init(self):
        """Async initialization"""
        await asyncio.sleep(0.5)
        await self._auto_load_cached_items()
        await self._load_custom_instructions()
        await self._init_load_repos()

    def _toggle_sidebar(self, e):
        """Toggle sidebar visibility"""
        self.sidebar_visible = not self.sidebar_visible
        if self.sidebar_ref.current:
            if self.sidebar_visible:
                self.sidebar_ref.current.width = 350
                self.sidebar_ref.current.visible = True
            else:
                self.sidebar_ref.current.width = 0
                self.sidebar_ref.current.visible = False
            self.page.update()

    def _create_title_section(self) -> ft.Container:
        """Create the title section with buttons"""
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.icons.PSYCHOLOGY,
                        tooltip="Check AI Modules",
                        on_click=self._check_ai_modules_manual,
                    ),
                    ft.IconButton(
                        icon=ft.icons.SETTINGS,
                        tooltip="Settings",
                        on_click=self._open_settings,
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
            padding=ft.padding.only(bottom=10),
        )

    def _create_sidebar_content(self) -> ft.Column:
        """Create the controls section"""
        # Mode selection
        mode_controls = ft.RadioGroup(
            ref=self.tools_mode_ref,
            content=ft.Row([
                ft.Radio(value="create", label="Create PR/Issue"),
                ft.Radio(value="action", label="Action Existing PR/Issue"),
            ]),
            value="action",
            on_change=self._on_mode_changed,
        )

        # Target Repository
        target_repo_row = ft.Row(
            [
                ft.Dropdown(
                    ref=self.target_repo_dropdown_ref,
                    label="Target Repository",
                    hint_text="Select target repository",
                    options=[],
                    expand=True,
                    on_change=self._on_repo_selection_changed,
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

        # Forked Repository
        forked_repo_row = ft.Row(
            [
                ft.Dropdown(
                    ref=self.forked_repo_dropdown_ref,
                    label="Forked Repository",
                    hint_text="Select forked repository",
                    options=[],
                    expand=True,
                    on_change=self._on_repo_selection_changed,
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

        # Action controls (for action mode)
        action_controls = ft.Column(
            [
                ft.Text("View", weight=ft.FontWeight.BOLD),
                ft.RadioGroup(
                    ref=self.repo_source_ref,
                    content=ft.Row([
                        ft.Radio(value="target", label="Target"),
                        ft.Radio(value="fork", label="Fork"),
                    ]),
                    value="target",
                    on_change=lambda e: self._filter_workflow_items(),
                ),
                ft.Text("Item Type", weight=ft.FontWeight.BOLD),
                ft.RadioGroup(
                    ref=self.item_type_ref,
                    content=ft.Row([
                        ft.Radio(value="pull_request", label="PRs"),
                        ft.Radio(value="issue", label="Issues"),
                    ]),
                    value="pull_request",
                    on_change=lambda e: self._filter_workflow_items(),
                ),
                ft.Row([
                    ft.ElevatedButton(
                        "📥 Load Items",
                        on_click=lambda e: self.page.run_task(self._load_workflow_items_async),
                    ),
                    ft.Text(ref=self.item_counter_ref, value="No items loaded"),
                ]),
                ft.Dropdown(
                    ref=self.workflow_item_dropdown_ref,
                    label="Select Workflow Item",
                    hint_text="Select an item",
                    options=[],
                    expand=True,
                    on_change=self._on_workflow_item_selected,
                ),
            ],
            spacing=10,
        )

        # Create controls (for create mode)
        create_controls = ft.Column(
            [
                ft.Text("Create Type", weight=ft.FontWeight.BOLD),
                ft.RadioGroup(
                    ref=self.create_type_ref,
                    content=ft.Row([
                        ft.Radio(value="pull_request", label="Pull Request"),
                        ft.Radio(value="issue", label="Issue"),
                    ]),
                    value="pull_request",
                ),
                ft.ElevatedButton(
                    "✏️ Create New",
                    on_click=self._create_new_item,
                ),
            ],
            spacing=10,
            visible=False,
        )

        # GitHub Tools content
        return ft.Column(
            [
                ft.Row([
                    ft.Icon(ft.icons.SOURCE, size=20),
                    ft.Text("GitHub Tools", size=18, weight=ft.FontWeight.BOLD),
                ]),
                ft.Divider(height=20),
                mode_controls,
                ft.Divider(height=10),
                target_repo_row,
                forked_repo_row,
                ft.Divider(height=10),
                action_controls,
                create_controls,
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True,  # Make column expand to fill available space
        )

    def _create_status_section(self) -> ft.Container:
        """Create the status section"""
        return ft.Container(
            content=ft.Column([
                ft.ProgressBar(ref=self.progress_bar_ref, visible=False),
                ft.Text(ref=self.status_text_ref, value="Ready", size=14),
            ]),
            padding=ft.padding.symmetric(vertical=10),
        )

    def _create_tabs_section(self) -> ft.Container:
        """Create the tabbed interface"""
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Current Item",
                    icon=ft.icons.DESCRIPTION,
                    content=self._create_current_item_tab()
                ),
                ft.Tab(
                    text="View Diff",
                    icon=ft.icons.DIFFERENCE,
                    content=self._create_diff_tab()
                ),
                ft.Tab(
                    text="Processing Log",
                    icon=ft.icons.LIST_ALT,
                    content=self._create_log_tab()
                ),
                ft.Tab(
                    text="All Items",
                    icon=ft.icons.VIEW_LIST,
                    content=self._create_all_items_tab()
                ),
            ],
            expand=True,
        )

        return ft.Container(
            content=tabs,
            expand=True,
        )

    def _create_current_item_tab(self) -> ft.Container:
        """Create the current item tab"""
        # Navigation buttons
        nav_buttons = ft.Row(
            [
                ft.IconButton(
                    ref=self.prev_button_ref,
                    icon=ft.icons.ARROW_BACK,
                    tooltip="Previous",
                    on_click=self._previous_item,
                    disabled=True,
                ),
                ft.IconButton(
                    ref=self.next_button_ref,
                    icon=ft.icons.ARROW_FORWARD,
                    tooltip="Next",
                    on_click=self._next_item,
                    disabled=True,
                ),
                ft.Container(expand=True),
                ft.ElevatedButton(
                    "Go",
                    ref=self.go_button_ref,
                    icon=ft.icons.PLAY_ARROW,
                    on_click=self._create_github_resource,
                    disabled=True,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Work Item ID (clickable)
        work_item_id = ft.Text(
            ref=self.work_item_id_ref,
            value="No item selected",
            size=16,
            weight=ft.FontWeight.BOLD,
            color="blue",
        )

        # Fields
        nature_text = ft.TextField(
            ref=self.nature_text_ref,
            label="Nature of Request",
            multiline=True,
            min_lines=2,
            max_lines=4,
            read_only=True,
            expand=True,
        )

        live_doc_url = ft.TextField(
            ref=self.live_doc_url_ref,
            label="Live Doc URL",
            read_only=True,
            expand=True,
        )

        text_to_change = ft.TextField(
            ref=self.text_to_change_ref,
            label="Text to Change",
            multiline=True,
            min_lines=5,
            max_lines=10,
            read_only=True,
            expand=True,
        )

        # Proposed New Text with Edit button
        proposed_header = ft.Row(
            [
                ft.Text("Proposed New Text", weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    ref=self.edit_button_ref,
                    icon=ft.icons.EDIT,
                    tooltip="Edit",
                    on_click=self._toggle_edit_mode,
                    disabled=True,
                ),
            ],
        )

        proposed_new_text = ft.TextField(
            ref=self.proposed_new_text_ref,
            multiline=True,
            min_lines=5,
            max_lines=10,
            read_only=True,
            expand=True,
        )

        # Custom Instructions
        custom_instructions_header = ft.Row(
            [
                ft.Text("Custom AI Instructions", weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.icons.SAVE,
                    tooltip="Save Instructions",
                    on_click=self.save_custom_instructions,
                ),
                ft.IconButton(
                    icon=ft.icons.DELETE,
                    tooltip="Clear Instructions",
                    on_click=self.clear_custom_instructions,
                ),
            ],
        )

        custom_instructions = ft.TextField(
            ref=self.custom_instructions_ref,
            hint_text="Enter custom instructions for AI processing...",
            multiline=True,
            min_lines=3,
            max_lines=6,
            expand=True,
        )

        return ft.Container(
            content=ft.ListView(
                controls=[
                    nav_buttons,
                    work_item_id,
                    ft.Divider(),
                    nature_text,
                    live_doc_url,
                    text_to_change,
                    proposed_header,
                    proposed_new_text,
                    ft.Divider(),
                    custom_instructions_header,
                    custom_instructions,
                ],
                spacing=15,
                padding=20,
            ),
            expand=True,
        )

    def _create_diff_tab(self) -> ft.Container:
        """Create the diff view tab"""
        diff_buttons = ft.Row(
            [
                ft.ElevatedButton(
                    "Find .diff Files",
                    icon=ft.icons.SEARCH,
                    on_click=self.find_and_load_diff_files,
                ),
                ft.ElevatedButton(
                    "Clear Diff",
                    icon=ft.icons.CLEAR,
                    on_click=self.clear_diff_display,
                ),
            ],
            spacing=10,
        )

        diff_text = ft.TextField(
            ref=self.diff_text_ref,
            multiline=True,
            read_only=True,
            expand=True,
            text_style=ft.TextStyle(font_family="Courier New"),
        )

        return ft.Container(
            content=ft.Column([
                diff_buttons,
                diff_text,
            ], spacing=10, expand=True),
            padding=20,
            expand=True,
        )

    def _create_log_tab(self) -> ft.Container:
        """Create the processing log tab"""
        log_text = ft.TextField(
            ref=self.log_text_ref,
            multiline=True,
            read_only=True,
            expand=True,
            text_style=ft.TextStyle(font_family="Courier New"),
        )

        return ft.Container(
            content=log_text,
            padding=20,
            expand=True,
        )

    def _create_all_items_tab(self) -> ft.Container:
        """Create the all items tab"""
        # DataTable for items
        items_table = ft.DataTable(
            ref=self.items_table_ref,
            columns=[
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("Title")),
                ft.DataColumn(ft.Text("Nature")),
                ft.DataColumn(ft.Text("GitHub Repo")),
                ft.DataColumn(ft.Text("ms.author")),
                ft.DataColumn(ft.Text("Status")),
            ],
            rows=[],
        )

        set_current_button = ft.ElevatedButton(
            "Set as Current Item",
            icon=ft.icons.CHECK_CIRCLE,
            on_click=self._select_current_item,
        )

        return ft.Container(
            content=ft.Column([
                set_current_button,
                ft.ListView(
                    controls=[items_table],
                    expand=True,
                ),
            ], spacing=10, expand=True),
            padding=20,
            expand=True,
        )

    # ===== Event Handlers =====

    def _on_settings_changed(self, key: str, value: any):
        """
        Handle settings changes from settings dialog (live updates).

        Args:
            key: Setting key that changed
            value: New value
        """
        # Update repository dropdowns when repos change in settings
        if key == 'GITHUB_REPO':
            if self.target_repo_dropdown_ref.current:
                self.target_repo_dropdown_ref.current.value = value
                self.page.update()
                print(f"✓ Main GUI: Target repo updated to {value}")

        elif key == 'FORKED_REPO':
            if self.forked_repo_dropdown_ref.current:
                self.forked_repo_dropdown_ref.current.value = value
                self.page.update()
                print(f"✓ Main GUI: Forked repo updated to {value}")

    def _on_mode_changed(self, e):
        """Handle mode change between create and action"""
        # This would toggle visibility of create vs action controls
        # Implementation depends on UI structure
        pass

    def _on_repo_selection_changed(self, e):
        """Handle repository selection change"""
        # Save selected repos to settings
        config = self.config_manager.get_config()

        if self.target_repo_dropdown_ref.current and self.target_repo_dropdown_ref.current.value:
            target_value = self.target_repo_dropdown_ref.current.value
            # Don't save separator headers
            if not target_value.startswith('---'):
                config['GITHUB_REPO'] = target_value

        if self.forked_repo_dropdown_ref.current and self.forked_repo_dropdown_ref.current.value:
            forked_value = self.forked_repo_dropdown_ref.current.value
            # Don't save separator headers
            if not forked_value.startswith('---'):
                config['FORKED_REPO'] = forked_value

        # Save to config
        self.config_manager.save_configuration(config)

        # Clear workflow items when repos change
        self.workflow_items = {}
        self.current_workflow_items = []
        if self.workflow_item_dropdown_ref.current:
            self.workflow_item_dropdown_ref.current.options = []
            self.page.update()

    def _on_workflow_item_selected(self, e):
        """Handle workflow item selection"""
        if not self.workflow_item_dropdown_ref.current:
            return

        selected = self.workflow_item_dropdown_ref.current.value
        if selected:
            # Find the item and display it
            for item in self.current_workflow_items:
                if hasattr(item, 'title') and item.title == selected:
                    self._display_workflow_item(item)
                    break

    def _filter_workflow_items(self):
        """Filter workflow items based on current selections"""
        print("=" * 60)
        print("FILTER METHOD CALLED")
        print("=" * 60)

        if not self.repo_source_ref.current or not self.item_type_ref.current:
            print("ERROR: repo_source or item_type ref not available")
            if self.logger:
                self.logger.log("Cannot filter: repo source or item type not selected")
            return

        source = self.repo_source_ref.current.value
        item_type = self.item_type_ref.current.value
        print(f"DEBUG: source='{source}', item_type='{item_type}'")

        # Map item_type to the correct key suffix
        # "pull_request" → "prs", "issue" → "issues"
        if item_type == "pull_request":
            type_suffix = "prs"
        elif item_type == "issue":
            type_suffix = "issues"
        else:
            type_suffix = f"{item_type}s"

        key = f"{source}_{type_suffix}"
        print(f"DEBUG: Mapped item_type '{item_type}' to suffix '{type_suffix}'")
        print(f"DEBUG: Looking for key '{key}'")
        print(f"DEBUG: Available keys in workflow_items: {list(self.workflow_items.keys())}")

        self.current_workflow_items = self.workflow_items.get(key, [])
        print(f"DEBUG: Found {len(self.current_workflow_items)} items for key '{key}'")

        if self.logger:
            self.logger.log(f"Filtering workflow items: source={source}, type={item_type}, key={key}")
            self.logger.log(f"Available workflow item keys: {list(self.workflow_items.keys())}")
            self.logger.log(f"Found {len(self.current_workflow_items)} items for key '{key}'")

        # Update dropdown
        if self.workflow_item_dropdown_ref.current:
            options = []
            for item in self.current_workflow_items:
                if hasattr(item, 'title'):
                    options.append(ft.dropdown.Option(item.title))
                    print(f"  - Added item: {item.title}")
                else:
                    print(f"  - WARNING: Item has no title attribute: {item}")

            print(f"DEBUG: Created {len(options)} dropdown options")
            self.workflow_item_dropdown_ref.current.options = options

            if self.item_counter_ref.current:
                count_text = f"{len(options)} item(s) loaded"
                if len(options) == 0:
                    count_text = f"No {item_type}s found in {source} repo"
                self.item_counter_ref.current.value = count_text
                print(f"DEBUG: Counter text set to: {count_text}")

            print("DEBUG: Calling page.update()...")
            self.page.update()
            print("DEBUG: page.update() completed")
        else:
            print("ERROR: workflow_item_dropdown_ref.current is None!")

    def _display_workflow_item(self, item):
        """Display a workflow item"""
        # Implementation would populate fields with workflow item data
        pass

    def _previous_item(self, e):
        """Navigate to previous item"""
        if self.current_item_index > 0:
            self.current_item_index -= 1
            self._display_current_item()
            self._update_navigation_buttons()

    def _next_item(self, e):
        """Navigate to next item"""
        if self.current_item_index < len(self.current_work_items) - 1:
            self.current_item_index += 1
            self._display_current_item()
            self._update_navigation_buttons()

    def _toggle_edit_mode(self, e):
        """Toggle edit mode for proposed new text"""
        if not self.proposed_new_text_ref.current or not self.edit_button_ref.current:
            return

        self.edit_mode = not self.edit_mode

        if self.edit_mode:
            self.proposed_new_text_ref.current.read_only = False
            self.edit_button_ref.current.icon = ft.icons.SAVE
            self.edit_button_ref.current.tooltip = "Save"
        else:
            # Save the changes
            if self.current_work_items and self.current_item_index < len(self.current_work_items):
                self.current_work_items[self.current_item_index]['new_text'] = \
                    self.proposed_new_text_ref.current.value

            self.proposed_new_text_ref.current.read_only = True
            self.edit_button_ref.current.icon = ft.icons.EDIT
            self.edit_button_ref.current.tooltip = "Edit"

        self.page.update()

    def save_custom_instructions(self, e):
        """Save custom AI instructions"""
        if not self.custom_instructions_ref.current:
            return

        instructions = self.custom_instructions_ref.current.value
        config_values = {'CUSTOM_INSTRUCTIONS': instructions}
        success = self.config_manager.save_configuration(config_values)

        if success:
            self._show_snackbar("Custom instructions saved successfully!")
        else:
            self._show_snackbar("Failed to save custom instructions", error=True)

    def clear_custom_instructions(self, e):
        """Clear custom instructions"""
        if self.custom_instructions_ref.current:
            self.custom_instructions_ref.current.value = ""
            self.page.update()

    def _create_github_resource(self, e):
        """Create GitHub resource (PR or Issue)"""
        # Implementation would handle GitHub resource creation
        self._show_snackbar("Creating GitHub resource...")

    def _create_new_item(self, e):
        """Create new PR/Issue"""
        # Implementation for creating new items
        pass

    def _select_current_item(self, e):
        """Set selected item as current from table"""
        # Implementation to set current item from table selection
        pass

    def find_and_load_diff_files(self, e):
        """Find and load .diff files"""
        # Implementation to find and load diff files
        pass

    def clear_diff_display(self, e):
        """Clear the diff display"""
        if self.diff_text_ref.current:
            self.diff_text_ref.current.value = ""
            self.page.update()

    # ===== Async Operations =====

    async def _auto_load_cached_items(self):
        """Auto-load cached items on startup"""
        try:
            # Try to load from cache
            if self.cache_manager:
                # Implementation would load cached items
                pass
        except Exception as e:
            print(f"Error auto-loading cached items: {e}")

    async def _load_custom_instructions(self):
        """Load custom instructions from config"""
        try:
            config = self.config_manager.get_config()
            instructions = config.get('CUSTOM_INSTRUCTIONS', '')

            if self.custom_instructions_ref.current:
                self.custom_instructions_ref.current.value = instructions
                self.page.update()
        except Exception as e:
            print(f"Error loading custom instructions: {e}")

    async def _init_load_repos(self):
        """Initialize repository loading"""
        await self._load_target_repos_async()
        await self._load_forked_repos_async()

    async def _load_target_repos_async(self):
        """Load target repositories"""
        def load_repos():
            try:
                github_token = self.config_manager.get_config().get('GITHUB_PAT', '')
                if not github_token:
                    return

                from .workflow import GitHubRepoFetcher
                repo_fetcher = GitHubRepoFetcher(github_token, self.logger)
                repos = repo_fetcher.fetch_repos_with_permissions(min_permission='push')
                self.target_repos = repo_fetcher.get_repo_names(repos)

                # Update UI
                if self.target_repo_dropdown_ref.current:
                    self.page.run_task(self._update_target_dropdown_async)

            except Exception as e:
                if self.logger:
                    self.logger.log(f"Error loading target repos: {e}")

        await asyncio.to_thread(load_repos)

    async def _update_target_dropdown_async(self):
        """Update target repository dropdown"""
        if not self.target_repo_dropdown_ref.current:
            return

        options = []
        if self.target_repos:
            options.append(ft.dropdown.Option("--- Your Repos (with edit access) ---", disabled=True))
            options.extend([ft.dropdown.Option(repo) for repo in self.target_repos])

        self.target_repo_dropdown_ref.current.options = options

        # Set value from saved settings
        saved_repo = self.config_manager.get_config().get('GITHUB_REPO', '')
        if saved_repo:
            self.target_repo_dropdown_ref.current.value = saved_repo

        self.page.update()

    async def _refresh_target_repos_async(self):
        """Refresh target repositories"""
        await self._load_target_repos_async()

    async def _search_target_repos_async(self):
        """Search for repositories on GitHub"""
        # Implementation would search GitHub repos
        pass

    async def _load_forked_repos_async(self):
        """Load forked repositories"""
        def load_forks():
            try:
                # Load local repos
                local_repo_path = self.config_manager.get_config().get('LOCAL_REPO_PATH', '')
                if local_repo_path:
                    try:
                        from .utils import LocalRepositoryScanner
                        self.forked_repos['local'] = LocalRepositoryScanner.scan_local_repos(local_repo_path)
                    except Exception as e:
                        print(f"Error scanning local repos: {e}")

                # Load GitHub repos
                github_token = self.config_manager.get_config().get('GITHUB_PAT', '')
                if github_token:
                    from .workflow import GitHubRepoFetcher
                    repo_fetcher = GitHubRepoFetcher(github_token, self.logger)
                    repos = repo_fetcher.fetch_user_repos(repo_type='owner')
                    self.forked_repos['github'] = repo_fetcher.get_repo_names(repos)

                # Update UI
                if self.forked_repo_dropdown_ref.current:
                    self.page.run_task(self._update_forked_dropdown_async)

            except Exception as e:
                if self.logger:
                    self.logger.log(f"Error loading forked repos: {e}")

        await asyncio.to_thread(load_forks)

    async def _update_forked_dropdown_async(self):
        """Update forked repository dropdown"""
        if not self.forked_repo_dropdown_ref.current:
            return

        options = []

        # Add local repos
        if self.forked_repos.get('local'):
            options.append(ft.dropdown.Option("--- Local Repositories ---", disabled=True))
            options.extend([ft.dropdown.Option(repo) for repo in self.forked_repos['local']])

        # Add GitHub repos
        if self.forked_repos.get('github'):
            options.append(ft.dropdown.Option("--- Your GitHub Repos ---", disabled=True))
            options.extend([ft.dropdown.Option(repo) for repo in self.forked_repos['github']])

        self.forked_repo_dropdown_ref.current.options = options

        # Set value from saved settings
        saved_repo = self.config_manager.get_config().get('FORKED_REPO', '')
        if saved_repo:
            self.forked_repo_dropdown_ref.current.value = saved_repo

        self.page.update()

    async def _refresh_forked_repos_async(self):
        """Refresh forked repositories"""
        await self._load_forked_repos_async()

    def _clone_forked_repo(self, e):
        """Clone forked repository"""
        # Implementation would clone the selected repo
        pass

    async def _load_workflow_items_async(self):
        """Load workflow items (PRs/Issues)"""
        print("=" * 60)
        print("🔄 Load Items button clicked!")
        print("=" * 60)
        if self.logger:
            self.logger.log("=" * 60)
            self.logger.log("🔄 Load Items button clicked - starting workflow item load")
            self.logger.log("=" * 60)

        def load_items():
            try:
                print(f"DEBUG: target_repo_dropdown exists: {self.target_repo_dropdown_ref.current is not None}")
                print(f"DEBUG: forked_repo_dropdown exists: {self.forked_repo_dropdown_ref.current is not None}")

                if self.target_repo_dropdown_ref.current:
                    print(f"DEBUG: target_repo value = '{self.target_repo_dropdown_ref.current.value}'")
                if self.forked_repo_dropdown_ref.current:
                    print(f"DEBUG: forked_repo value = '{self.forked_repo_dropdown_ref.current.value}'")

                if not self.target_repo_dropdown_ref.current and not self.forked_repo_dropdown_ref.current:
                    if self.logger:
                        self.logger.log("❌ No repositories dropdown controls found")
                    print("ERROR: No repo dropdowns found!")
                    return

                github_token = self.config_manager.get_config().get('GITHUB_PAT', '')
                if not github_token:
                    if self.logger:
                        self.logger.log("❌ No GitHub token configured")
                    print("ERROR: No GitHub token!")
                    return

                from .workflow import WorkflowManager
                workflow_manager = WorkflowManager(github_token, self.logger)

                # Load from target repo
                target_repo = self.target_repo_dropdown_ref.current.value if self.target_repo_dropdown_ref.current else None
                print(f"DEBUG: target_repo extracted = '{target_repo}'")
                print(f"DEBUG: Validation checks:")
                print(f"  - target_repo is not None: {target_repo is not None}")
                print(f"  - not starts with '---': {not target_repo.startswith('---') if target_repo else 'N/A'}")
                print(f"  - contains '/': {'/' in target_repo if target_repo else 'N/A'}")

                # Filter out separator headers and None values
                if target_repo and not target_repo.startswith('---') and '/' in target_repo:
                    print(f"✓ Validation PASSED for target repo: {target_repo}")
                    if self.logger:
                        self.logger.log(f"📥 Loading PRs and issues from target repo: {target_repo}")

                    print(f"Calling workflow_manager.fetch_pull_requests('{target_repo}')...")
                    self.workflow_items['target_prs'] = workflow_manager.fetch_pull_requests(target_repo)
                    print(f"Calling workflow_manager.fetch_issues('{target_repo}')...")
                    self.workflow_items['target_issues'] = workflow_manager.fetch_issues(target_repo)

                    pr_count = len(self.workflow_items.get('target_prs', []))
                    issue_count = len(self.workflow_items.get('target_issues', []))
                    print(f"✓ Loaded {pr_count} PRs and {issue_count} issues from target repo")

                    if self.logger:
                        self.logger.log(f"✅ Loaded {pr_count} PRs and {issue_count} issues from target repo")
                else:
                    print(f"✗ Validation FAILED for target repo: {target_repo}")

                # Load from forked repo
                forked_repo = self.forked_repo_dropdown_ref.current.value if self.forked_repo_dropdown_ref.current else None
                # Filter out separator headers and None values
                if forked_repo and not forked_repo.startswith('---') and '/' in forked_repo:
                    if self.logger:
                        self.logger.log(f"Loading PRs and issues from forked repo: {forked_repo}")
                    self.workflow_items['fork_prs'] = workflow_manager.fetch_pull_requests(forked_repo)
                    self.workflow_items['fork_issues'] = workflow_manager.fetch_issues(forked_repo)
                    if self.logger:
                        self.logger.log(f"Loaded {len(self.workflow_items.get('fork_prs', []))} PRs and {len(self.workflow_items.get('fork_issues', []))} issues from forked repo")

                # Filter and update UI
                self.page.run_task(self._filter_workflow_items_async)

            except Exception as e:
                if self.logger:
                    self.logger.log(f"Error loading workflow items: {e}")
                    import traceback
                    self.logger.log(traceback.format_exc())

        await asyncio.to_thread(load_items)

    async def _filter_workflow_items_async(self):
        """Filter workflow items async"""
        self._filter_workflow_items()

    # ===== Helper Methods =====

    def _display_current_item(self):
        """Display the current work item"""
        if not self.current_work_items or self.current_item_index >= len(self.current_work_items):
            return

        item = self.current_work_items[self.current_item_index]

        # Update UI fields
        if self.work_item_id_ref.current:
            self.work_item_id_ref.current.value = f"Work Item {item.get('id', 'N/A')}"

        if self.nature_text_ref.current:
            self.nature_text_ref.current.value = item.get('nature', '')

        if self.live_doc_url_ref.current:
            self.live_doc_url_ref.current.value = item.get('live_doc_url', '')

        if self.text_to_change_ref.current:
            self.text_to_change_ref.current.value = item.get('old_text', '')

        if self.proposed_new_text_ref.current:
            self.proposed_new_text_ref.current.value = item.get('new_text', '')

        self.page.update()
        self._update_navigation_buttons()

    def _update_navigation_buttons(self):
        """Update navigation button states"""
        if self.prev_button_ref.current:
            self.prev_button_ref.current.disabled = (self.current_item_index == 0)

        if self.next_button_ref.current:
            self.next_button_ref.current.disabled = (
                self.current_item_index >= len(self.current_work_items) - 1
            )

        self.page.update()

    def update_status(self, message: str):
        """Update status message"""
        if self.status_text_ref.current:
            self.status_text_ref.current.value = message
            self.page.update()

    def _show_progress(self):
        """Show progress bar"""
        if self.progress_bar_ref.current:
            self.progress_bar_ref.current.visible = True
            self.page.update()

    def _hide_progress(self):
        """Hide progress bar"""
        if self.progress_bar_ref.current:
            self.progress_bar_ref.current.visible = False
            self.page.update()

    def _show_snackbar(self, message: str, error: bool = False):
        """Show snackbar notification"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor="error" if error else "green",
        )
        self.page.snack_bar.open = True
        self.page.update()

    def _open_settings(self, e):
        """Open settings dialog"""
        try:
            print("Settings button clicked!")

            # Use Flet 0.28+ API: page.open() instead of page.dialog
            config = self.config_manager.get_config()
            print(f"Got config: {config.keys() if config else 'None'}")

            settings_dialog = SettingsDialog(
                self.page,
                config,
                self.config_manager,
                self.cache_manager
            )
            print("SettingsDialog created")

            def on_settings_result(result):
                if result:
                    # Reload configuration
                    self.config_manager.load_configuration()
                    self._show_snackbar("Settings saved successfully!")

            print("Calling settings_dialog.show()...")
            settings_dialog.show(on_result=on_settings_result)
            print("settings_dialog.show() completed")

        except Exception as ex:
            print(f"Error in _open_settings: {ex}")
            import traceback
            traceback.print_exc()
            self._show_snackbar(f"Error opening settings: {ex}", error=True)

    def _show_real_settings(self):
        """Show the real settings dialog"""
        try:
            config = self.config_manager.get_config()
            print(f"Got config: {config.keys() if config else 'None'}")

            settings_dialog = SettingsDialog(
                self.page,
                config,
                self.config_manager,
                self.cache_manager
            )
            print("SettingsDialog created")

            def on_settings_result(result):
                if result:
                    # Reload configuration
                    self.config_manager.load_configuration()
                    self._show_snackbar("Settings saved successfully!")

            print("Calling settings_dialog.show()...")
            settings_dialog.show(on_result=on_settings_result)
            print("settings_dialog.show() completed")
        except Exception as ex:
            print(f"Error in _show_real_settings: {ex}")
            import traceback
            traceback.print_exc()
            self._show_snackbar(f"Error showing settings: {ex}", error=True)

    def _check_ai_modules_manual(self, e):
        """Manually check AI modules"""
        config = self.config_manager.get_config()
        ai_provider = config.get('AI_PROVIDER', 'none').lower()

        if ai_provider and ai_provider != 'none':
            self.page.run_task(lambda: self._check_ai_provider_async(ai_provider))
        else:
            self._show_snackbar("No AI provider configured")

    async def _check_ai_provider_async(self, ai_provider: str):
        """Check AI provider setup"""
        try:
            available, missing = self.ai_manager.check_ai_module_availability(ai_provider)

            if available:
                self._show_snackbar(f"AI Provider ({ai_provider}): All modules available!")
            else:
                self._show_snackbar(
                    f"AI Provider ({ai_provider}): Missing packages: {', '.join(missing)}",
                    error=True
                )
        except Exception as e:
            self._show_snackbar(f"Error checking AI provider: {e}", error=True)

    def update_diff_display(self, diff_content: str):
        """Update diff display"""
        if self.diff_text_ref.current:
            self.diff_text_ref.current.value = diff_content
            self.page.update()


class Logger:
    """Logger class for Flet"""

    def __init__(self, text_field: ft.TextField):
        self.text_field = text_field

    def log(self, message: str):
        """Log a message"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        if self.text_field:
            current = self.text_field.value or ""
            self.text_field.value = current + log_message
            # Auto-scroll is handled by Flet
