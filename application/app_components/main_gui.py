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
from .processing_log_dialog import ProcessingLogDialog


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
        self.active_workflow_item = None  # Currently selected item from All Items list

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
        self.go_button_ref = ft.Ref[ft.ElevatedButton]()

        # Mode and filter refs
        self.tools_mode_ref = ft.Ref[ft.RadioGroup]()
        self.repo_source_ref = ft.Ref[ft.RadioGroup]()
        self.item_type_ref = ft.Ref[ft.RadioGroup]()
        self.create_type_ref = ft.Ref[ft.RadioGroup]()
        self.target_repo_dropdown_ref = ft.Ref[ft.Dropdown]()
        self.forked_repo_dropdown_ref = ft.Ref[ft.Dropdown]()
        self.workflow_item_dropdown_ref = ft.Ref[ft.Dropdown]()
        self.active_item_display_ref = ft.Ref[ft.Container]()
        self.item_counter_ref = ft.Ref[ft.Text]()

        # DataTable ref for all items
        self.items_table_ref = ft.Ref[ft.DataTable]()

        # All items display
        self.all_items_container_ref = ft.Ref[ft.Column]()
        self.all_items_search_ref = ft.Ref[ft.TextField]()
        self.all_items_type_filter_ref = ft.Ref[ft.RadioGroup]()
        self.all_items_repo_filter_ref = ft.Ref[ft.RadioGroup]()
        self.item_detail_dialog_ref = ft.Ref[ft.AlertDialog]()

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
                        icon=ft.icons.LIST_ALT,
                        tooltip="Processing Log",
                        on_click=self._open_processing_log,
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

        # Create hidden log text field for the processing log dialog
        hidden_log_text = ft.TextField(
            ref=self.log_text_ref,
            multiline=True,
            read_only=True,
            text_style=ft.TextStyle(font_family="Courier New"),
            visible=False,  # Hidden from main UI
        )

        # Overall layout: Top nav + bottom section + hidden log field
        app_layout = ft.Column(
            [
                top_nav,
                ft.Divider(height=1),
                bottom_section,
                hidden_log_text,  # Hidden but accessible for dialog
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
        await self._load_custom_instructions()
        await self._init_load_repos()
        # Auto-load cached items after repos are loaded
        await self._auto_load_cached_items()

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
                ft.Text("Active Item", weight=ft.FontWeight.BOLD, size=14),
                ft.Row([
                    ft.Container(
                        ref=self.active_item_display_ref,
                        content=ft.Text(
                            "No item selected",
                            color=ft.colors.GREY_500,
                            italic=True,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        padding=10,
                        border=ft.border.all(1, ft.colors.OUTLINE),
                        border_radius=8,
                        bgcolor=ft.colors.GREY_900,
                        expand=True,
                    ),
                ], spacing=5),
                ft.Divider(height=10),
                ft.Text("All Items", weight=ft.FontWeight.BOLD, size=14),
                ft.Row([
                    ft.ElevatedButton(
                        "📥 Pull PRs/Issues",
                        on_click=lambda e: self.page.run_task(self._load_workflow_items_async),
                    ),
                    ft.Text(ref=self.item_counter_ref, value="No items loaded"),
                ]),
                ft.TextField(
                    ref=self.all_items_search_ref,
                    hint_text="Search items...",
                    prefix_icon=ft.icons.SEARCH,
                    dense=True,
                    on_change=self._on_all_items_search_changed,
                    border_radius=8,
                ),
                ft.Text("Source Repo", weight=ft.FontWeight.BOLD),
                ft.RadioGroup(
                    ref=self.all_items_type_filter_ref,
                    content=ft.Row([
                        ft.Radio(value="both", label="Both"),
                        ft.Radio(value="prs", label="PRs"),
                        ft.Radio(value="issues", label="Issues"),
                    ], spacing=5),
                    value="both",
                    on_change=self._on_all_items_filter_changed,
                ),
                ft.Text("Item Type", weight=ft.FontWeight.BOLD),
                ft.RadioGroup(
                    ref=self.all_items_repo_filter_ref,
                    content=ft.Row([
                        ft.Radio(value="both", label="Both"),
                        ft.Radio(value="target", label="Target"),
                        ft.Radio(value="fork", label="Fork"),
                    ], spacing=5),
                    value="both",
                    on_change=self._on_all_items_filter_changed,
                ),
                ft.Container(
                    content=ft.Column(
                        ref=self.all_items_container_ref,
                        controls=[
                            ft.Text("No items loaded", color=ft.colors.GREY_500, italic=True, text_align=ft.TextAlign.CENTER)
                        ],
                        spacing=10,
                        scroll=ft.ScrollMode.AUTO,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                    height=300,
                    border=ft.border.all(1, ft.colors.OUTLINE),
                    border_radius=8,
                    padding=5,
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
            ],
            expand=True,
        )

        return ft.Container(
            content=tabs,
            expand=True,
        )

    def _create_current_item_tab(self) -> ft.Container:
        """Create the current item tab"""
        # Create a container to hold the dynamic content
        self.current_item_content_ref = ft.Ref[ft.Column]()

        # Default empty state
        default_content = ft.Column(
            [
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.icons.INBOX, size=64, color=ft.colors.GREY_500),
                        ft.Text(
                            "No item selected",
                            size=18,
                            weight=ft.FontWeight.BOLD,
                            color=ft.colors.GREY_500,
                        ),
                        ft.Text(
                            "Select a PR or Issue from the sidebar to view details",
                            size=14,
                            color=ft.colors.GREY_600,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    alignment=ft.alignment.center,
                    expand=True,
                ),
            ],
            ref=self.current_item_content_ref,
            spacing=15,
            scroll=ft.ScrollMode.AUTO,
        )

        return ft.Container(
            content=ft.ListView(
                controls=[default_content],
                spacing=0,
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

    def _create_all_items_tab(self) -> ft.Container:
        """Create the all items tab"""
        # DataTable for items
        items_table = ft.DataTable(
            ref=self.items_table_ref,
            columns=[
                ft.DataColumn(ft.Text("Repo")),
                ft.DataColumn(ft.Text("Type")),
                ft.DataColumn(ft.Text("ID")),
                ft.DataColumn(ft.Text("Title")),
                ft.DataColumn(ft.Text("Author")),
                ft.DataColumn(ft.Text("Status")),
            ],
            rows=[],
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=8,
            heading_row_color=ft.colors.BLUE_GREY_100,
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

        # Auto-load cached items for the newly selected repos
        self.page.run_task(self._auto_load_cached_items_on_repo_change)

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

    def _on_all_items_search_changed(self, e):
        """Handle search field change in All Items list"""
        if not self.all_items_search_ref.current:
            return

        search_query = self.all_items_search_ref.current.value or ""
        type_filter = self.all_items_type_filter_ref.current.value if self.all_items_type_filter_ref.current else "both"
        repo_filter = self.all_items_repo_filter_ref.current.value if self.all_items_repo_filter_ref.current else "both"
        self._populate_all_items(search_query, type_filter, repo_filter)

    def _on_all_items_filter_changed(self, e):
        """Handle filter change in All Items list (type or repo source)"""
        search_query = self.all_items_search_ref.current.value if self.all_items_search_ref.current else ""
        type_filter = self.all_items_type_filter_ref.current.value if self.all_items_type_filter_ref.current else "both"
        repo_filter = self.all_items_repo_filter_ref.current.value if self.all_items_repo_filter_ref.current else "both"
        self._populate_all_items(search_query, type_filter, repo_filter)

    def _filter_workflow_items(self):
        """Collect all workflow items (no filtering since toggles were removed)"""
        print("=" * 60)
        print("COLLECTING WORKFLOW ITEMS")
        print("=" * 60)

        # Collect all items from all categories since filter toggles are removed
        all_items = []
        for key, items in self.workflow_items.items():
            all_items.extend(items)

        self.current_workflow_items = all_items
        print(f"DEBUG: Collected {len(all_items)} total items")
        print(f"DEBUG: Available keys in workflow_items: {list(self.workflow_items.keys())}")

        if self.logger:
            self.logger.log(f"Collected {len(all_items)} workflow items from all categories")
            self.logger.log(f"Available workflow item keys: {list(self.workflow_items.keys())}")

        # Update item counter if it exists
        if self.item_counter_ref.current:
            count_text = f"{len(all_items)} item(s) loaded"
            self.item_counter_ref.current.value = count_text
            print(f"DEBUG: Counter text set to: {count_text}")

        print("DEBUG: Calling page.update()...")
        self.page.update()
        print("DEBUG: page.update() completed")

    def _display_workflow_item(self, item):
        """Display a workflow item in the Current Item tab"""
        if not self.current_item_content_ref.current:
            return

        # Get repo string based on source
        config = self.config_manager.get_config()
        if item.repo_source == "target":
            repo_str = config.get('GITHUB_REPO', '')
        else:
            repo_str = config.get('FORKED_REPO', '')

        # Fetch comments
        comments = []
        pr_files = []
        try:
            workflow_manager = self._get_workflow_manager()
            comments = workflow_manager.fetch_comments(repo_str, item.number, item.item_type == "pull_request")

            # Fetch PR files if this is a pull request
            if item.item_type == "pull_request":
                pr_files = workflow_manager.fetch_pr_files(repo_str, item.number)
        except Exception as e:
            print(f"Error fetching item details: {e}")
            if self.logger:
                self.logger.log(f"Error fetching item details: {e}")

        # Build the display
        controls = []

        # Header section
        header = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Text(
                            "PR" if item.item_type == "pull_request" else "Issue",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.colors.WHITE,
                        ),
                        bgcolor=ft.colors.GREEN if item.item_type == "pull_request" else ft.colors.ORANGE,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=4,
                    ),
                    ft.Text(f"#{item.number}", size=18, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.icons.OPEN_IN_BROWSER,
                        tooltip="Open in GitHub",
                        on_click=lambda e: self.page.launch_url(item.url),
                    ),
                ], alignment=ft.MainAxisAlignment.START),
                ft.Text(item.title, size=20, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            padding=15,
            bgcolor=ft.colors.BLUE_GREY_900,
            border_radius=8,
        )
        controls.append(header)

        # Basic Info section
        info_items = [
            ft.Row([
                ft.Icon(ft.icons.PERSON, size=16, color=ft.colors.BLUE_400),
                ft.Text("Created by:", weight=ft.FontWeight.BOLD, size=14),
                ft.Text(f"@{item.author}", size=14, color=ft.colors.BLUE_300),
            ], spacing=5),
            ft.Row([
                ft.Icon(ft.icons.CALENDAR_TODAY, size=16, color=ft.colors.BLUE_400),
                ft.Text("Created:", weight=ft.FontWeight.BOLD, size=14),
                ft.Text(item.created_at[:10] if item.created_at else 'Unknown', size=14),
            ], spacing=5),
            ft.Row([
                ft.Icon(ft.icons.UPDATE, size=16, color=ft.colors.BLUE_400),
                ft.Text("Last Updated:", weight=ft.FontWeight.BOLD, size=14),
                ft.Text(item.updated_at[:10] if item.updated_at else 'Unknown', size=14),
            ], spacing=5),
            ft.Row([
                ft.Icon(ft.icons.CIRCLE, size=16, color=ft.colors.GREEN if item.state == "open" else ft.colors.PURPLE),
                ft.Text("Status:", weight=ft.FontWeight.BOLD, size=14),
                ft.Text(item.state.capitalize(), size=14, color=ft.colors.GREEN if item.state == "open" else ft.colors.PURPLE),
            ], spacing=5),
        ]

        # Add assignees with assign-to-self button
        if item.assignees:
            assignees_text = ", ".join([f"@{a}" for a in item.assignees])
            info_items.append(
                ft.Row([
                    ft.Icon(ft.icons.ASSIGNMENT_IND, size=16, color=ft.colors.BLUE_400),
                    ft.Text("Assigned to:", weight=ft.FontWeight.BOLD, size=14),
                    ft.Text(assignees_text, size=14, color=ft.colors.BLUE_300),
                    ft.IconButton(
                        icon=ft.icons.PERSON_ADD,
                        icon_size=16,
                        tooltip="Assign to me",
                        on_click=lambda _: self._assign_to_self(item, repo_str),
                    ),
                ], spacing=5)
            )
        else:
            info_items.append(
                ft.Row([
                    ft.Icon(ft.icons.ASSIGNMENT_IND, size=16, color=ft.colors.GREY_600),
                    ft.Text("Assigned to:", weight=ft.FontWeight.BOLD, size=14),
                    ft.Text("Unassigned", size=14, color=ft.colors.GREY_500, italic=True),
                    ft.IconButton(
                        icon=ft.icons.PERSON_ADD,
                        icon_size=16,
                        tooltip="Assign to me",
                        on_click=lambda _: self._assign_to_self(item, repo_str),
                    ),
                ], spacing=5)
            )

        # PR-specific info
        if item.item_type == "pull_request":
            merge_status_color = ft.colors.GREEN if item.merged else (ft.colors.ORANGE if item.state == "open" else ft.colors.GREY_600)
            merge_status_text = "Merged" if item.merged else ("Pending Merge" if item.state == "open" else "Closed without merge")
            info_items.append(
                ft.Row([
                    ft.Icon(ft.icons.MERGE_TYPE, size=16, color=merge_status_color),
                    ft.Text("Merge Status:", weight=ft.FontWeight.BOLD, size=14),
                    ft.Text(merge_status_text, size=14, color=merge_status_color),
                ], spacing=5)
            )

        info_section = ft.Container(
            content=ft.Column(info_items, spacing=8),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=8,
        )
        controls.append(info_section)

        # Description section (collapsible, collapsed by default)
        description_section = ft.ExpansionTile(
            title=ft.Text("Description", size=16, weight=ft.FontWeight.BOLD),
            subtitle=ft.Text("Click to expand", size=12, color=ft.colors.GREY_500),
            initially_expanded=False,
            controls=[
                ft.Container(
                    content=ft.Container(
                        content=ft.Row([
                            ft.Text(
                                item.body if item.body else "No description provided",
                                size=14,
                                selectable=True,
                            ),
                        ], spacing=5),
                        padding=10,
                        border=ft.border.all(1, ft.colors.OUTLINE),
                        border_radius=4,
                        bgcolor=ft.colors.GREY_900,
                    ),
                    margin=ft.margin.only(left=10, right=10, bottom=10),
                ),
            ],
        )
        controls.append(
            ft.Container(
                content=description_section,
                border=ft.border.all(1, ft.colors.OUTLINE),
                border_radius=8,
            )
        )

        # PR Files section
        if item.item_type == "pull_request" and pr_files:
            files_widgets = []
            for file in pr_files:
                status_color = {
                    'added': ft.colors.GREEN,
                    'removed': ft.colors.RED,
                    'modified': ft.colors.ORANGE,
                    'renamed': ft.colors.BLUE,
                }.get(file['status'], ft.colors.GREY_400)

                files_widgets.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.icons.INSERT_DRIVE_FILE, size=16, color=status_color),
                            ft.Text(file['filename'], size=13, expand=True),
                            ft.Container(
                                content=ft.Text(file['status'], size=11, color=ft.colors.WHITE),
                                bgcolor=status_color,
                                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                                border_radius=3,
                            ),
                            ft.Text(f"+{file['additions']} -{file['deletions']}",
                                   size=12,
                                   color=ft.colors.GREY_400),
                        ], spacing=8),
                        padding=8,
                        border=ft.border.all(1, ft.colors.OUTLINE),
                        border_radius=4,
                        bgcolor=ft.colors.GREY_900,
                    )
                )

            files_section = ft.Container(
                content=ft.Column([
                    ft.Text(f"Modified Files ({len(pr_files)})", size=16, weight=ft.FontWeight.BOLD),
                    ft.Column(
                        controls=files_widgets,
                        spacing=5,
                        scroll=ft.ScrollMode.AUTO,
                        height=min(200, len(pr_files) * 50),
                    ),
                ], spacing=8),
                padding=15,
                border=ft.border.all(1, ft.colors.OUTLINE),
                border_radius=8,
            )
            controls.append(files_section)

        # Comments section (collapsible, collapsed by default)
        comments_widgets = []
        if comments:
            for comment in comments:
                comments_widgets.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.icons.PERSON, size=14),
                                ft.Text(f"@{comment['user']}", weight=ft.FontWeight.BOLD, size=13),
                                ft.Text(
                                    comment['created_at'][:10] if comment.get('created_at') else '',
                                    size=11,
                                    color=ft.colors.GREY_600
                                ),
                            ], spacing=5),
                            ft.Text(comment['body'], size=13, selectable=True),
                        ], spacing=5),
                        padding=10,
                        border=ft.border.all(1, ft.colors.OUTLINE),
                        border_radius=4,
                        bgcolor=ft.colors.GREY_900,
                    )
                )
        else:
            comments_widgets.append(
                ft.Text("No comments yet", italic=True, color=ft.colors.GREY_500, size=13)
            )

        comments_section = ft.ExpansionTile(
            title=ft.Text(f"Comments ({len(comments)})", size=16, weight=ft.FontWeight.BOLD),
            subtitle=ft.Text("Click to expand", size=12, color=ft.colors.GREY_500),
            initially_expanded=False,
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=comments_widgets,
                        spacing=8,
                        scroll=ft.ScrollMode.AUTO,
                        height=min(250, max(100, len(comments) * 80)),
                    ),
                    margin=ft.margin.only(left=10, right=10, bottom=10),
                ),
            ],
        )
        controls.append(
            ft.Container(
                content=comments_section,
                border=ft.border.all(1, ft.colors.OUTLINE),
                border_radius=8,
            )
        )

        # AI Analysis section (placeholder for now)
        self.ai_analysis_result_ref = ft.Ref[ft.Column]()
        ai_section = self._create_ai_analysis_section(item, repo_str, pr_files, comments)
        controls.append(ai_section)

        # Update the content
        self.current_item_content_ref.current.controls = controls
        self.page.update()

    def _create_ai_analysis_section(self, item, repo_str, pr_files, comments):
        """Create the AI Analysis section"""
        # Check if AI provider is configured
        config = self.config_manager.get_config()
        ai_provider = config.get('AI_PROVIDER', 'none').lower()
        ai_configured = ai_provider and ai_provider != 'none'

        # Create result container
        ai_result_container = ft.Column(
            ref=self.ai_analysis_result_ref,
            controls=[],
            spacing=10,
        )

        # Create analyze button or disabled message
        if ai_configured:
            # Create a wrapper function that captures the parameters
            async def run_analysis_wrapper():
                await self._run_ai_analysis_async(item, repo_str, pr_files, comments)

            analyze_button = ft.ElevatedButton(
                "Run AI Analysis",
                icon=ft.icons.AUTO_AWESOME,
                on_click=lambda _: self.page.run_task(run_analysis_wrapper),
            )
            button_row = ft.Row([
                analyze_button,
                ft.Text(
                    f"Using {ai_provider.upper()}",
                    size=12,
                    color=ft.colors.BLUE_300,
                    italic=True,
                ),
            ], spacing=10)
        else:
            button_row = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.icons.INFO_OUTLINE, size=16, color=ft.colors.ORANGE),
                    ft.Text(
                        "AI Analysis is not available. Please configure an AI provider in Settings.",
                        size=13,
                        color=ft.colors.ORANGE,
                    ),
                ], spacing=8),
                padding=10,
                border=ft.border.all(1, ft.colors.ORANGE),
                border_radius=4,
                bgcolor=ft.colors.GREY_900,
            )

        ai_section = ft.Container(
            content=ft.Column([
                ft.Text("AI Analysis", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "For PRs: Analyze changes and create a summary. For Issues: Find relevant files and suggest fixes.",
                    size=12,
                    color=ft.colors.GREY_400,
                ),
                button_row,
                ai_result_container,
            ], spacing=10),
            padding=15,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=8,
        )

        return ai_section

    async def _run_ai_analysis_async(self, item, repo_str, pr_files, comments):
        """Run AI analysis on the selected item"""
        if not self.ai_analysis_result_ref.current:
            return

        # Show loading state
        self.ai_analysis_result_ref.current.controls = [
            ft.Container(
                content=ft.Row([
                    ft.ProgressRing(width=16, height=16),
                    ft.Text("Analyzing...", size=14),
                ], spacing=10),
                padding=10,
            )
        ]
        self.page.update()

        def run_analysis():
            try:
                config = self.config_manager.get_config()
                ai_provider = config.get('AI_PROVIDER', 'none').lower()

                if item.item_type == "pull_request":
                    # PR Analysis: Summarize changes
                    result = self._analyze_pr(item, repo_str, pr_files, comments, ai_provider, config)
                else:
                    # Issue Analysis: Find files and suggest fixes
                    result = self._analyze_issue(item, repo_str, comments, ai_provider, config)

                return result

            except Exception as e:
                error_msg = f"Error during AI analysis: {str(e)}"
                if self.logger:
                    self.logger.log(error_msg)
                return {
                    'success': False,
                    'error': error_msg
                }

        # Run in thread
        result = await asyncio.to_thread(run_analysis)

        # Display results
        if result.get('success'):
            result_widgets = [
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.icons.CHECK_CIRCLE, size=16, color=ft.colors.GREEN),
                            ft.Text("Analysis Complete", weight=ft.FontWeight.BOLD, size=14, color=ft.colors.GREEN),
                        ], spacing=5),
                        ft.Divider(height=10),
                        ft.Text(result.get('summary', ''), size=13, selectable=True),
                    ], spacing=10),
                    padding=15,
                    border=ft.border.all(1, ft.colors.GREEN),
                    border_radius=8,
                    bgcolor=ft.colors.GREY_900,
                )
            ]

            # Add suggested files for issues
            if item.item_type == "issue" and result.get('suggested_files'):
                result_widgets.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Suggested Files to Modify:", weight=ft.FontWeight.BOLD, size=14),
                            ft.Column([
                                ft.Text(f"• {file}", size=13, color=ft.colors.BLUE_300)
                                for file in result['suggested_files']
                            ], spacing=5),
                        ], spacing=8),
                        padding=15,
                        border=ft.border.all(1, ft.colors.BLUE),
                        border_radius=8,
                        bgcolor=ft.colors.GREY_900,
                    )
                )

                # Add "Create PR with AI Fix" button
                result_widgets.append(
                    ft.ElevatedButton(
                        "Create PR with AI-Suggested Fix",
                        icon=ft.icons.AUTO_FIX_HIGH,
                        on_click=lambda _: self._create_pr_from_ai_fix(item, result),
                    )
                )

            self.ai_analysis_result_ref.current.controls = result_widgets
        else:
            # Show error
            self.ai_analysis_result_ref.current.controls = [
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.ERROR_OUTLINE, size=16, color=ft.colors.RED),
                        ft.Text(
                            result.get('error', 'Unknown error occurred'),
                            size=13,
                            color=ft.colors.RED,
                        ),
                    ], spacing=8),
                    padding=10,
                    border=ft.border.all(1, ft.colors.RED),
                    border_radius=4,
                    bgcolor=ft.colors.GREY_900,
                )
            ]

        self.page.update()

    def _analyze_pr(self, item, repo_str, pr_files, comments, ai_provider, config):
        """Analyze a Pull Request using AI"""
        try:
            # Build context for AI
            context = f"""Pull Request Analysis Request

Repository: {repo_str}
PR Number: #{item.number}
Title: {item.title}
State: {item.state}
Merged: {item.merged}

Description:
{item.body if item.body else 'No description provided'}

Modified Files ({len(pr_files)}):
"""
            for file in pr_files:
                context += f"\n- {file['filename']} ({file['status']}) [+{file['additions']} -{file['deletions']}]"

            if comments:
                context += f"\n\nComments ({len(comments)}):\n"
                for comment in comments[:5]:  # Limit to first 5 comments
                    context += f"\n@{comment['user']}: {comment['body'][:200]}...\n"

            context += "\n\nPlease provide a comprehensive summary of this pull request, including:\n"
            context += "1. What changes were made\n"
            context += "2. The purpose and impact of these changes\n"
            context += "3. Any notable patterns or concerns from the comments\n"
            context += "4. Overall assessment of the PR"

            # Call AI manager
            summary = self.ai_manager.generate_response(context, ai_provider, config)

            if self.logger:
                self.logger.log(f"AI PR Analysis completed for PR #{item.number}")

            return {
                'success': True,
                'summary': summary
            }

        except Exception as e:
            if self.logger:
                self.logger.log(f"Error in PR analysis: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _analyze_issue(self, item, repo_str, comments, ai_provider, config):
        """Analyze an Issue using AI to suggest fixes"""
        try:
            # Build context for AI
            context = f"""GitHub Issue Analysis Request

Repository: {repo_str}
Issue Number: #{item.number}
Title: {item.title}
State: {item.state}

Description:
{item.body if item.body else 'No description provided'}
"""

            if comments:
                context += f"\n\nComments ({len(comments)}):\n"
                for comment in comments[:5]:  # Limit to first 5 comments
                    context += f"\n@{comment['user']}: {comment['body'][:200]}...\n"

            context += "\n\nPlease analyze this issue and provide:\n"
            context += "1. A summary of the issue\n"
            context += "2. Suggested files or components that might be causing this issue\n"
            context += "3. Recommended approach to fix the issue\n"
            context += "4. Any additional considerations\n"
            context += "\nFor the suggested files, please list them in a clear format like:\n"
            context += "SUGGESTED_FILES: file1.py, file2.js, file3.tsx"

            # Call AI manager
            analysis = self.ai_manager.generate_response(context, ai_provider, config)

            # Try to extract suggested files from the response
            suggested_files = []
            if "SUGGESTED_FILES:" in analysis:
                files_line = analysis.split("SUGGESTED_FILES:")[1].split("\n")[0]
                suggested_files = [f.strip() for f in files_line.split(",") if f.strip()]

            if self.logger:
                self.logger.log(f"AI Issue Analysis completed for Issue #{item.number}")

            return {
                'success': True,
                'summary': analysis,
                'suggested_files': suggested_files
            }

        except Exception as e:
            if self.logger:
                self.logger.log(f"Error in Issue analysis: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _create_pr_from_ai_fix(self, item, _analysis_result):
        """Create a PR with AI-suggested fix for an issue"""
        # TODO: Implement PR creation with AI fix
        # The analysis_result will contain suggested files and fix recommendations
        self._show_snackbar("PR creation with AI fix - Coming soon!", error=False)
        if self.logger:
            self.logger.log(f"PR creation requested for Issue #{item.number}")

    def _assign_to_self(self, item, repo_str):
        """Assign the current PR or Issue to the authenticated user"""
        try:
            # Get GitHub token
            config = self.config_manager.get_config()
            github_token = config.get('GITHUB_PAT', '')

            if not github_token:
                self._show_snackbar("GitHub token not configured", error=True)
                return

            # Parse repository
            if '/' not in repo_str:
                self._show_snackbar("Invalid repository format", error=True)
                return

            owner, repo = repo_str.split('/', 1)

            # Get authenticated user
            import requests
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "github-pulse/1.0"
            }

            # First, get the authenticated user's username
            user_response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
            user_response.raise_for_status()
            username = user_response.json().get('login')

            if not username:
                self._show_snackbar("Could not get authenticated user", error=True)
                return

            # Assign to self using the GitHub API
            # For both PRs and Issues, we use the issues endpoint
            url = f"https://api.github.com/repos/{owner}/{repo}/issues/{item.number}/assignees"

            # Add the authenticated user to assignees
            payload = {
                "assignees": [username]
            }

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()

            # Update the item in memory
            if username not in item.assignees:
                item.assignees.append(username)

            # Refresh the display
            self._display_workflow_item(item)

            self._show_snackbar(f"Successfully assigned to @{username}", error=False)

            if self.logger:
                self.logger.log(f"Assigned {item.item_type} #{item.number} to @{username}")

        except requests.exceptions.RequestException as e:
            error_msg = f"Error assigning to self: {str(e)}"
            self._show_snackbar(error_msg, error=True)
            if self.logger:
                self.logger.log(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._show_snackbar(error_msg, error=True)
            if self.logger:
                self.logger.log(error_msg)

    def _populate_all_items(self, search_query: str = "", type_filter: str = "both", repo_filter: str = "both"):
        """Populate the all items list with all loaded PRs and Issues

        Args:
            search_query: Optional search string to filter items
            type_filter: Filter by item type - "both", "prs", or "issues"
            repo_filter: Filter by repo source - "both", "target", or "fork"
        """
        if not self.all_items_container_ref.current:
            return

        # Collect all items from workflow_items
        all_items = []
        for key, items in self.workflow_items.items():
            all_items.extend(items)

        # Apply repo source filter
        if repo_filter == "target":
            all_items = [item for item in all_items if item.repo_source == "target"]
        elif repo_filter == "fork":
            all_items = [item for item in all_items if item.repo_source == "fork"]
        # "both" shows everything, no filtering needed

        # Apply type filter
        if type_filter == "prs":
            all_items = [item for item in all_items if item.item_type == "pull_request"]
        elif type_filter == "issues":
            all_items = [item for item in all_items if item.item_type == "issue"]
        # "both" shows everything, no filtering needed

        # Apply search filter if provided
        if search_query:
            search_lower = search_query.lower()
            filtered_items = []
            for item in all_items:
                # Search in title, number, state, author, and labels
                if (search_lower in item.title.lower() or
                    search_lower in str(item.number) or
                    search_lower in item.state.lower() or
                    (item.author and search_lower in item.author.lower()) or
                    any(search_lower in label.lower() for label in (item.labels or []))):
                    filtered_items.append(item)
            all_items = filtered_items

        if not all_items:
            if search_query or type_filter != "both" or repo_filter != "both":
                filter_desc = []
                if search_query:
                    filter_desc.append(f"matching '{search_query}'")
                if type_filter == "prs":
                    filter_desc.append("PRs only")
                elif type_filter == "issues":
                    filter_desc.append("Issues only")
                if repo_filter == "target":
                    filter_desc.append("Target repo only")
                elif repo_filter == "fork":
                    filter_desc.append("Fork repo only")

                msg = "No items " + " and ".join(filter_desc) if filter_desc else "No items loaded"
                self.all_items_container_ref.current.controls = [
                    ft.Text(msg, color=ft.colors.GREY_500, italic=True)
                ]
            else:
                self.all_items_container_ref.current.controls = [
                    ft.Text("No items loaded", color=ft.colors.GREY_500, italic=True)
                ]
        else:
            # Sort by updated_at (most recent first)
            all_items.sort(key=lambda x: x.updated_at if hasattr(x, 'updated_at') else '', reverse=True)

            # Create item cards
            cards = []
            for item in all_items:
                cards.append(self._create_item_card(item))

            self.all_items_container_ref.current.controls = cards

        self.page.update()

    def _create_item_card(self, item):
        """Create a card for a workflow item"""
        # Determine repo source label
        repo_label = "Target" if item.repo_source == "target" else "Fork"
        repo_color = ft.colors.BLUE if item.repo_source == "target" else ft.colors.PURPLE

        # Determine type label
        type_label = "PR" if item.item_type == "pull_request" else "Issue"
        type_color = ft.colors.GREEN if item.item_type == "pull_request" else ft.colors.ORANGE

        # Create card
        return ft.Container(
            content=ft.Row(
                [
                    # Repo source badge
                    ft.Container(
                        content=ft.Text(repo_label, size=10, weight=ft.FontWeight.BOLD),
                        bgcolor=repo_color,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=4,
                    ),
                    # Type badge
                    ft.Container(
                        content=ft.Text(type_label, size=10, weight=ft.FontWeight.BOLD),
                        bgcolor=type_color,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=4,
                    ),
                    # Title
                    ft.Text(
                        f"#{item.number}: {item.title}",
                        size=12,
                        expand=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    # Select button
                    ft.IconButton(
                        icon=ft.icons.CHECK_CIRCLE_OUTLINE,
                        icon_size=16,
                        tooltip="Select as current item",
                        on_click=lambda e, it=item: self._select_item_as_current(it),
                    ),
                    # View details button
                    ft.IconButton(
                        icon=ft.icons.OPEN_IN_NEW,
                        icon_size=16,
                        tooltip="View details",
                        on_click=lambda e, it=item: self._show_item_detail(it),
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=8,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            bgcolor=ft.colors.GREY_800,
        )

    def _populate_all_items_table(self):
        """Populate the DataTable in the All Items tab with all loaded PRs and Issues"""
        if not self.items_table_ref.current:
            return

        # Collect all items from workflow_items
        all_items = []
        for key, items in self.workflow_items.items():
            all_items.extend(items)

        if not all_items:
            self.items_table_ref.current.rows = []
        else:
            # Sort by updated_at (most recent first)
            all_items.sort(key=lambda x: x.updated_at if hasattr(x, 'updated_at') else '', reverse=True)

            # Create table rows
            rows = []
            for item in all_items:
                # Determine repo source and type
                repo_source = "Target" if item.repo_source == "target" else "Fork"
                item_type = "PR" if item.item_type == "pull_request" else "Issue"

                # Get author (item.author is already a string, not a dict)
                author = item.author if item.author else 'Unknown'

                # Get state
                state = item.state if hasattr(item, 'state') else 'unknown'

                # Get repo name
                config = self.config_manager.get_config()
                if item.repo_source == "target":
                    repo_name = config.get('GITHUB_REPO', '')
                else:
                    repo_name = config.get('FORKED_REPO', '')

                # Create row with clickable button
                row = ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(f"{repo_source}: {repo_name.split('/')[-1] if '/' in repo_name else repo_name}", size=12)),
                        ft.DataCell(ft.Text(item_type, size=12)),
                        ft.DataCell(ft.Text(f"#{item.number}", size=12)),
                        ft.DataCell(ft.Text(item.title[:50] + "..." if len(item.title) > 50 else item.title, size=12)),
                        ft.DataCell(ft.Text(author, size=12)),
                        ft.DataCell(ft.Text(state, size=12)),
                    ],
                    on_select_changed=lambda e, it=item: self._show_item_detail(it) if e.control.selected else None,
                )
                rows.append(row)

            self.items_table_ref.current.rows = rows

        self.page.update()

    def _select_item_as_current(self, item):
        """Select an item as the current active workflow item"""
        if not self.active_item_display_ref.current:
            return

        # Store the active item
        self.active_workflow_item = item

        # Determine display labels
        repo_label = "Target" if item.repo_source == "target" else "Fork"
        repo_color = ft.colors.BLUE if item.repo_source == "target" else ft.colors.PURPLE
        type_label = "PR" if item.item_type == "pull_request" else "Issue"
        type_color = ft.colors.GREEN if item.item_type == "pull_request" else ft.colors.ORANGE

        # Update the active item display with a nice card
        self.active_item_display_ref.current.content = ft.Column([
            ft.Row([
                # Repo badge
                ft.Container(
                    content=ft.Text(repo_label, size=10, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                    bgcolor=repo_color,
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                ),
                # Type badge
                ft.Container(
                    content=ft.Text(type_label, size=10, weight=ft.FontWeight.BOLD, color=ft.colors.WHITE),
                    bgcolor=type_color,
                    padding=ft.padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                ),
                ft.Container(expand=True),
                # Clear button
                ft.IconButton(
                    icon=ft.icons.CLOSE,
                    icon_size=16,
                    tooltip="Clear selection",
                    on_click=self._clear_active_item,
                ),
            ], spacing=5),
            ft.Text(
                f"#{item.number}: {item.title}",
                size=12,
                weight=ft.FontWeight.BOLD,
            ),
        ], spacing=5)

        # Collect workflow items (filter toggles were removed, so this just collects all items)
        self._filter_workflow_items()

        # Display the item
        self._display_workflow_item(item)

        # Update the page
        self.page.update()

        # Show confirmation
        item_type_label = "PR" if item.item_type == "pull_request" else "Issue"
        repo_label = "Target" if item.repo_source == "target" else "Fork"
        self._show_snackbar(f"Selected {item_type_label} from {repo_label}: {item.title}", error=False)

    def _clear_active_item(self, e=None):
        """Clear the active item selection"""
        if not self.active_item_display_ref.current:
            return

        # Clear the stored active item
        self.active_workflow_item = None

        # Reset the display to default "No item selected"
        self.active_item_display_ref.current.content = ft.Text(
            "No item selected",
            color=ft.colors.GREY_500,
            italic=True,
            text_align=ft.TextAlign.CENTER,
        )

        # Update the page
        self.page.update()

        # Show confirmation
        self._show_snackbar("Active item cleared", error=False)

    def _show_item_detail(self, item):
        """Show detail dialog for a workflow item"""
        # Get repo string for fetching comments
        config = self.config_manager.get_config()
        if item.repo_source == "target":
            repo_str = config.get('GITHUB_REPO', '')
        else:
            repo_str = config.get('FORKED_REPO', '')

        # Build the dialog
        dialog = self._build_item_detail_dialog(item, repo_str)

        # Use Flet 0.28+ API: page.open() instead of page.dialog
        self.page.open(dialog)

    def _build_item_detail_dialog(self, item, repo_str):
        """Build the detail dialog with tabs for Main (Preview) and System (extracted data)"""

        # Get repo name for display
        config = self.config_manager.get_config()
        if item.repo_source == "target":
            repo_name = config.get('GITHUB_REPO', '')
        else:
            repo_name = config.get('FORKED_REPO', '')

        # Create header with repo and item info
        header = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.icons.SOURCE, size=16),
                    ft.Text(repo_name, size=12, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=ft.Text(
                            "PR" if item.item_type == "pull_request" else "Issue",
                            size=10,
                            color=ft.colors.WHITE,
                        ),
                        bgcolor=ft.colors.GREEN if item.item_type == "pull_request" else ft.colors.ORANGE,
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        border_radius=4,
                    ),
                    ft.Text(f"#{item.number}", size=12, color=ft.colors.GREY_400),
                ], spacing=8),
                ft.Text(item.title, size=14, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text(
                        f"by @{item.author if item.author else 'Unknown'}",
                        size=11,
                        color=ft.colors.GREY_400,
                    ),
                    ft.Text(
                        f"• {item.state}",
                        size=11,
                        color=ft.colors.GREEN if item.state == "open" else ft.colors.PURPLE,
                    ),
                ], spacing=5),
            ], spacing=5),
            padding=10,
            bgcolor=ft.colors.GREY_900,
            border_radius=8,
        )

        # Create body preview
        body_preview = ft.Container(
            content=ft.Column([
                ft.Text("Description", size=12, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Text(
                        item.body if item.body else "No description provided",
                        size=11,
                        selectable=True,
                    ),
                    padding=10,
                    border=ft.border.all(1, ft.colors.OUTLINE),
                    border_radius=4,
                    bgcolor=ft.colors.GREY_900,
                ),
            ], spacing=5),
        )

        # Fetch comments
        comments = []
        if repo_str:
            try:
                workflow_manager = self._get_workflow_manager()
                comments = workflow_manager.fetch_comments(repo_str, item.number, item.item_type == "pull_request")
                print(f"Fetched {len(comments)} comments for {item.item_type} #{item.number}")
            except Exception as e:
                print(f"Error fetching comments: {e}")
                if self.logger:
                    self.logger.log(f"Error fetching comments: {e}")

        # Build comments display
        comments_widgets = []
        if comments:
            for comment in comments:
                comments_widgets.append(
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Row([
                                    ft.Text(f"@{comment['user']}", weight=ft.FontWeight.BOLD, size=12),
                                    ft.Text(comment['created_at'][:10] if comment.get('created_at') else '', size=10, color=ft.colors.GREY_600),
                                ]),
                                ft.Text(comment['body'], size=11, selectable=True),
                            ],
                            spacing=5,
                        ),
                        padding=8,
                        margin=ft.margin.only(bottom=8),
                        border=ft.border.all(1, ft.colors.OUTLINE),
                        border_radius=4,
                        bgcolor=ft.colors.GREY_800,
                    )
                )
        else:
            comments_widgets.append(ft.Text("No comments yet", italic=True, color=ft.colors.GREY_500, size=11))

        # Comments section
        comments_section = ft.Container(
            content=ft.Column([
                ft.Text(f"Comments ({len(comments)})", size=12, weight=ft.FontWeight.BOLD),
                ft.Column(
                    controls=comments_widgets,
                    spacing=5,
                    scroll=ft.ScrollMode.AUTO,
                ),
            ], spacing=5),
        )

        # Main content (no tabs, just single scrollable content)
        main_content = ft.Container(
            content=ft.Column(
                [
                    header,
                    body_preview,
                    comments_section,
                    ft.Row([
                        ft.ElevatedButton(
                            "Open in GitHub",
                            icon=ft.icons.OPEN_IN_BROWSER,
                            on_click=lambda e: self.page.launch_url(item.url),
                        ),
                        ft.TextButton(
                            "Copy URL",
                            icon=ft.icons.COPY,
                            on_click=lambda e: self._copy_to_clipboard(item.url),
                        ),
                    ], spacing=10),
                ],
                spacing=15,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
            expand=True,
        )

        # Create close handler that will close this specific dialog
        def close_handler(e):
            self.page.close(dialog)

        # Create dialog
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"{item.item_type.upper()} #{item.number}: {item.title}"),
            content=ft.Container(
                content=main_content,
                width=800,
                height=600,
            ),
            actions=[
                ft.TextButton("Close", on_click=close_handler),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        return dialog

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard and show notification"""
        self.page.set_clipboard(text)
        self._show_snackbar("URL copied to clipboard!", error=False)

    def _get_workflow_manager(self):
        """Get or create a WorkflowManager instance"""
        github_token = self.config_manager.get_config().get('GITHUB_PAT', '')
        if not github_token:
            raise ValueError("GitHub token not configured")

        from .workflow import WorkflowManager
        return WorkflowManager(github_token, self.logger)

    def _previous_item(self, e):
        """Navigate to previous item"""
        if self.current_item_index > 0:
            self.current_item_index -= 1
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
        """Auto-load cached items on startup if available"""
        print("=" * 60)
        print("🔄 Auto-loading cached items on startup...")
        print("=" * 60)

        def load_cached():
            try:
                # Get configured repos
                target_repo = self.target_repo_dropdown_ref.current.value if self.target_repo_dropdown_ref.current else None
                forked_repo = self.forked_repo_dropdown_ref.current.value if self.forked_repo_dropdown_ref.current else None

                if not target_repo and not forked_repo:
                    print("No repositories configured, skipping auto-load")
                    return

                github_token = self.config_manager.get_config().get('GITHUB_PAT', '')
                if not github_token:
                    print("No GitHub token configured, skipping auto-load")
                    return

                items_loaded = False

                # Try to load target repo items from cache
                if target_repo and not target_repo.startswith('---') and '/' in target_repo:
                    cached_prs = self.cache_manager.load_from_cache('target_prs', target_repo) if self.cache_manager else None
                    cached_issues = self.cache_manager.load_from_cache('target_issues', target_repo) if self.cache_manager else None

                    if cached_prs is not None:
                        from .workflow import WorkflowItem
                        self.workflow_items['target_prs'] = [WorkflowItem.from_dict(item) for item in cached_prs]
                        print(f"✓ Auto-loaded {len(cached_prs)} PRs from cache (target)")
                        if self.logger:
                            self.logger.log(f"✅ Auto-loaded {len(cached_prs)} PRs from cache (target)")
                        items_loaded = True

                    if cached_issues is not None:
                        from .workflow import WorkflowItem
                        self.workflow_items['target_issues'] = [WorkflowItem.from_dict(item) for item in cached_issues]
                        print(f"✓ Auto-loaded {len(cached_issues)} issues from cache (target)")
                        if self.logger:
                            self.logger.log(f"✅ Auto-loaded {len(cached_issues)} issues from cache (target)")
                        items_loaded = True

                # Try to load fork repo items from cache
                if forked_repo and not forked_repo.startswith('---') and '/' in forked_repo:
                    cached_fork_prs = self.cache_manager.load_from_cache('fork_prs', forked_repo) if self.cache_manager else None
                    cached_fork_issues = self.cache_manager.load_from_cache('fork_issues', forked_repo) if self.cache_manager else None

                    if cached_fork_prs is not None:
                        from .workflow import WorkflowItem
                        self.workflow_items['fork_prs'] = [WorkflowItem.from_dict(item) for item in cached_fork_prs]
                        print(f"✓ Auto-loaded {len(cached_fork_prs)} PRs from cache (fork)")
                        if self.logger:
                            self.logger.log(f"✅ Auto-loaded {len(cached_fork_prs)} PRs from cache (fork)")
                        items_loaded = True

                    if cached_fork_issues is not None:
                        from .workflow import WorkflowItem
                        self.workflow_items['fork_issues'] = [WorkflowItem.from_dict(item) for item in cached_fork_issues]
                        print(f"✓ Auto-loaded {len(cached_fork_issues)} issues from cache (fork)")
                        if self.logger:
                            self.logger.log(f"✅ Auto-loaded {len(cached_fork_issues)} issues from cache (fork)")
                        items_loaded = True

                if items_loaded:
                    # Filter and update UI
                    self.page.run_task(self._filter_workflow_items_async)

                    # Populate all items list in sidebar
                    self._populate_all_items()

                    print("✅ Auto-load completed successfully")
                else:
                    print("No cached items found, waiting for manual load")

            except Exception as e:
                print(f"Error during auto-load: {e}")
                if self.logger:
                    self.logger.log(f"Error during auto-load: {e}")

        await asyncio.to_thread(load_cached)

    async def _auto_load_cached_items_on_repo_change(self):
        """Auto-load cached items when repository selection changes"""
        print("🔄 Repository changed - checking for cached items...")

        def load_cached():
            try:
                # Get configured repos
                target_repo = self.target_repo_dropdown_ref.current.value if self.target_repo_dropdown_ref.current else None
                forked_repo = self.forked_repo_dropdown_ref.current.value if self.forked_repo_dropdown_ref.current else None

                github_token = self.config_manager.get_config().get('GITHUB_PAT', '')
                if not github_token:
                    print("No GitHub token configured")
                    return

                items_loaded = False

                # Try to load target repo items from cache
                if target_repo and not target_repo.startswith('---') and '/' in target_repo:
                    cached_prs = self.cache_manager.load_from_cache('target_prs', target_repo) if self.cache_manager else None
                    cached_issues = self.cache_manager.load_from_cache('target_issues', target_repo) if self.cache_manager else None

                    if cached_prs is not None:
                        from .workflow import WorkflowItem
                        self.workflow_items['target_prs'] = [WorkflowItem.from_dict(item) for item in cached_prs]
                        print(f"✓ Loaded {len(cached_prs)} cached PRs for target: {target_repo}")
                        if self.logger:
                            self.logger.log(f"✅ Loaded {len(cached_prs)} cached PRs for target: {target_repo}")
                        items_loaded = True

                    if cached_issues is not None:
                        from .workflow import WorkflowItem
                        self.workflow_items['target_issues'] = [WorkflowItem.from_dict(item) for item in cached_issues]
                        print(f"✓ Loaded {len(cached_issues)} cached issues for target: {target_repo}")
                        if self.logger:
                            self.logger.log(f"✅ Loaded {len(cached_issues)} cached issues for target: {target_repo}")
                        items_loaded = True

                # Try to load fork repo items from cache
                if forked_repo and not forked_repo.startswith('---') and '/' in forked_repo:
                    cached_fork_prs = self.cache_manager.load_from_cache('fork_prs', forked_repo) if self.cache_manager else None
                    cached_fork_issues = self.cache_manager.load_from_cache('fork_issues', forked_repo) if self.cache_manager else None

                    if cached_fork_prs is not None:
                        from .workflow import WorkflowItem
                        self.workflow_items['fork_prs'] = [WorkflowItem.from_dict(item) for item in cached_fork_prs]
                        print(f"✓ Loaded {len(cached_fork_prs)} cached PRs for fork: {forked_repo}")
                        if self.logger:
                            self.logger.log(f"✅ Loaded {len(cached_fork_prs)} cached PRs for fork: {forked_repo}")
                        items_loaded = True

                    if cached_fork_issues is not None:
                        from .workflow import WorkflowItem
                        self.workflow_items['fork_issues'] = [WorkflowItem.from_dict(item) for item in cached_fork_issues]
                        print(f"✓ Loaded {len(cached_fork_issues)} cached issues for fork: {forked_repo}")
                        if self.logger:
                            self.logger.log(f"✅ Loaded {len(cached_fork_issues)} cached issues for fork: {forked_repo}")
                        items_loaded = True

                if items_loaded:
                    # Filter and update UI
                    self.page.run_task(self._filter_workflow_items_async)

                    # Populate all items list in sidebar
                    self._populate_all_items()

                    print("✅ Cached items loaded for selected repositories")
                    if self.logger:
                        self.logger.log("✅ Cached items loaded for selected repositories")
                else:
                    print("No cached items found for selected repositories")

            except Exception as e:
                print(f"Error loading cached items on repo change: {e}")
                if self.logger:
                    self.logger.log(f"Error loading cached items on repo change: {e}")

        await asyncio.to_thread(load_cached)

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
        # Create search dialog
        search_input = ft.TextField(
            label="Search for repository",
            hint_text="Enter owner/repo or search term",
            expand=True,
            autofocus=True,
        )

        results_list = ft.ListView(
            expand=True,
            spacing=5,
            padding=10,
        )

        def perform_search(e):
            search_term = search_input.value.strip()
            if not search_term:
                return

            # Clear previous results
            results_list.controls.clear()
            results_list.controls.append(
                ft.Text("Searching...", color=ft.colors.GREY_400, italic=True)
            )
            self.page.update()

            # Search GitHub
            try:
                github_token = self.config_manager.get_config().get('GITHUB_PAT', '')
                if not github_token:
                    results_list.controls.clear()
                    results_list.controls.append(
                        ft.Text("GitHub token not configured", color=ft.colors.RED)
                    )
                    self.page.update()
                    return

                from .workflow import GitHubRepoFetcher
                repo_fetcher = GitHubRepoFetcher(github_token, self.logger)

                # Check if it's a direct repo reference (owner/repo)
                if '/' in search_term and len(search_term.split('/')) == 2:
                    # Try to get the specific repo
                    repos = repo_fetcher.search_repositories(search_term, per_page=1)
                    if repos:
                        results_list.controls.clear()
                        for repo in repos:
                            repo_name = repo_fetcher.get_repo_names([repo])[0] if repo_fetcher.get_repo_names([repo]) else None
                            if repo_name:
                                results_list.controls.append(
                                    self._create_repo_result_item(repo_name, repo, search_dialog)
                                )
                    else:
                        results_list.controls.clear()
                        results_list.controls.append(
                            ft.Text("Repository not found or you don't have access", color=ft.colors.ORANGE)
                        )
                else:
                    # Search for repos
                    repos = repo_fetcher.search_repositories(search_term, per_page=10)
                    results_list.controls.clear()

                    if repos:
                        for repo in repos:
                            repo_name = repo_fetcher.get_repo_names([repo])[0] if repo_fetcher.get_repo_names([repo]) else None
                            if repo_name:
                                results_list.controls.append(
                                    self._create_repo_result_item(repo_name, repo, search_dialog)
                                )
                    else:
                        results_list.controls.append(
                            ft.Text("No repositories found", color=ft.colors.GREY_400)
                        )

                self.page.update()

            except Exception as ex:
                results_list.controls.clear()
                results_list.controls.append(
                    ft.Text(f"Error searching: {str(ex)}", color=ft.colors.RED)
                )
                self.page.update()

        # Create dialog
        def close_dialog(e):
            self.page.close(search_dialog)

        search_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Search GitHub Repositories"),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        search_input,
                        ft.IconButton(
                            icon=ft.icons.SEARCH,
                            tooltip="Search",
                            on_click=perform_search,
                        ),
                    ]),
                    ft.Divider(),
                    results_list,
                ], spacing=10),
                width=600,
                height=400,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # Handle Enter key in search input
        search_input.on_submit = perform_search

        self.page.open(search_dialog)

    def _create_repo_result_item(self, repo_name, repo_data, dialog):
        """Create a repository result item"""
        # Get repo description
        description = repo_data.get('description', 'No description')
        if not description:
            description = 'No description'

        # Get visibility
        is_private = repo_data.get('private', False)
        visibility_text = "Private" if is_private else "Public"
        visibility_color = ft.colors.ORANGE if is_private else ft.colors.GREEN

        def select_repo(e):
            # Add to dropdown options if not already there
            if self.target_repo_dropdown_ref.current:
                current_options = [opt.key for opt in self.target_repo_dropdown_ref.current.options]
                if repo_name not in current_options:
                    self.target_repo_dropdown_ref.current.options.append(
                        ft.dropdown.Option(repo_name)
                    )

                # Select this repo
                self.target_repo_dropdown_ref.current.value = repo_name

                # Save to config
                config = self.config_manager.get_config()
                config['GITHUB_REPO'] = repo_name
                self.config_manager.save_configuration(config)

                self.page.update()

            # Close dialog
            self.page.close(dialog)
            self._show_snackbar(f"Selected repository: {repo_name}", error=False)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(repo_name, weight=ft.FontWeight.BOLD, size=14),
                    ft.Container(
                        content=ft.Text(visibility_text, size=10, color=ft.colors.WHITE),
                        bgcolor=visibility_color,
                        padding=ft.padding.symmetric(horizontal=8, vertical=2),
                        border_radius=4,
                    ),
                ], spacing=10),
                ft.Text(description, size=12, color=ft.colors.GREY_400),
            ], spacing=5),
            padding=10,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=4,
            bgcolor=ft.colors.GREY_800,
            on_click=select_repo,
            ink=True,
        )

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
        # Check if items are already loaded to determine if this is a refresh
        items_already_loaded = any(len(items) > 0 for items in self.workflow_items.values())
        force_refresh = items_already_loaded

        if force_refresh:
            print("=" * 60)
            print("🔄 Refreshing Items (forcing API fetch)...")
            print("=" * 60)
            if self.logger:
                self.logger.log("=" * 60)
                self.logger.log("🔄 Refreshing Items - forcing fresh fetch from GitHub API")
                self.logger.log("=" * 60)
        else:
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

                    # Try to load from cache first (unless forcing refresh)
                    cached_prs = None if force_refresh else (self.cache_manager.load_from_cache('target_prs', target_repo) if self.cache_manager else None)
                    cached_issues = None if force_refresh else (self.cache_manager.load_from_cache('target_issues', target_repo) if self.cache_manager else None)

                    if cached_prs is not None and not force_refresh:
                        # Convert cached dicts back to WorkflowItem objects
                        from .workflow import WorkflowItem
                        self.workflow_items['target_prs'] = [WorkflowItem.from_dict(item) for item in cached_prs]
                        print(f"✓ Loaded {len(cached_prs)} PRs from cache")
                        if self.logger:
                            self.logger.log(f"✅ Loaded {len(cached_prs)} PRs from cache")
                    else:
                        print(f"Calling workflow_manager.fetch_pull_requests('{target_repo}')...")
                        self.workflow_items['target_prs'] = workflow_manager.fetch_pull_requests(target_repo, repo_source='target')
                        # Convert to dicts and save to cache
                        if self.cache_manager:
                            items_as_dicts = [item.to_dict() for item in self.workflow_items['target_prs']]
                            self.cache_manager.save_to_cache('target_prs', target_repo, items_as_dicts)

                    if cached_issues is not None and not force_refresh:
                        # Convert cached dicts back to WorkflowItem objects
                        from .workflow import WorkflowItem
                        self.workflow_items['target_issues'] = [WorkflowItem.from_dict(item) for item in cached_issues]
                        print(f"✓ Loaded {len(cached_issues)} issues from cache")
                        if self.logger:
                            self.logger.log(f"✅ Loaded {len(cached_issues)} issues from cache")
                    else:
                        print(f"Calling workflow_manager.fetch_issues('{target_repo}')...")
                        self.workflow_items['target_issues'] = workflow_manager.fetch_issues(target_repo, repo_source='target')
                        # Convert to dicts and save to cache
                        if self.cache_manager:
                            items_as_dicts = [item.to_dict() for item in self.workflow_items['target_issues']]
                            self.cache_manager.save_to_cache('target_issues', target_repo, items_as_dicts)

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

                    # Try to load from cache first (unless forcing refresh)
                    cached_fork_prs = None if force_refresh else (self.cache_manager.load_from_cache('fork_prs', forked_repo) if self.cache_manager else None)
                    cached_fork_issues = None if force_refresh else (self.cache_manager.load_from_cache('fork_issues', forked_repo) if self.cache_manager else None)

                    if cached_fork_prs is not None and not force_refresh:
                        # Convert cached dicts back to WorkflowItem objects
                        from .workflow import WorkflowItem
                        self.workflow_items['fork_prs'] = [WorkflowItem.from_dict(item) for item in cached_fork_prs]
                        print(f"✓ Loaded {len(cached_fork_prs)} PRs from cache (fork)")
                        if self.logger:
                            self.logger.log(f"✅ Loaded {len(cached_fork_prs)} PRs from cache (fork)")
                    else:
                        self.workflow_items['fork_prs'] = workflow_manager.fetch_pull_requests(forked_repo, repo_source='fork')
                        # Convert to dicts and save to cache
                        if self.cache_manager:
                            items_as_dicts = [item.to_dict() for item in self.workflow_items['fork_prs']]
                            self.cache_manager.save_to_cache('fork_prs', forked_repo, items_as_dicts)

                    if cached_fork_issues is not None and not force_refresh:
                        # Convert cached dicts back to WorkflowItem objects
                        from .workflow import WorkflowItem
                        self.workflow_items['fork_issues'] = [WorkflowItem.from_dict(item) for item in cached_fork_issues]
                        print(f"✓ Loaded {len(cached_fork_issues)} issues from cache (fork)")
                        if self.logger:
                            self.logger.log(f"✅ Loaded {len(cached_fork_issues)} issues from cache (fork)")
                    else:
                        self.workflow_items['fork_issues'] = workflow_manager.fetch_issues(forked_repo, repo_source='fork')
                        # Convert to dicts and save to cache
                        if self.cache_manager:
                            items_as_dicts = [item.to_dict() for item in self.workflow_items['fork_issues']]
                            self.cache_manager.save_to_cache('fork_issues', forked_repo, items_as_dicts)

                    if self.logger:
                        self.logger.log(f"Loaded {len(self.workflow_items.get('fork_prs', []))} PRs and {len(self.workflow_items.get('fork_issues', []))} issues from forked repo")

                # Filter and update UI
                self.page.run_task(self._filter_workflow_items_async)

                # Populate all items list in sidebar
                self._populate_all_items()

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

    def _open_processing_log(self, e):
        """Open processing log dialog"""
        try:
            print("Processing Log button clicked!")

            processing_log_dialog = ProcessingLogDialog(
                self.page,
                self.log_text_ref
            )
            print("ProcessingLogDialog created")

            processing_log_dialog.show()
            print("ProcessingLogDialog.show() completed")

        except Exception as ex:
            print(f"Error in _open_processing_log: {ex}")
            import traceback
            traceback.print_exc()
            self._show_snackbar(f"Error opening processing log: {ex}", error=True)

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
