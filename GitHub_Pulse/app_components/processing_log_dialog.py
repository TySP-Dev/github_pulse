"""
Processing Log Dialog
Displays the processing log in a separate dialog window
"""

import flet as ft
# Compatibility fix for Flet 0.28+ (Icons vs icons, Colors vs colors)
ft.icons = ft.Icons
ft.colors = ft.Colors


class ProcessingLogDialog:
    """Processing log display dialog"""

    def __init__(self, page: ft.Page, log_text_ref: ft.Ref):
        self.page = page
        self.log_text_ref = log_text_ref
        self.dialog_ref = ft.Ref[ft.AlertDialog]()
        self.log_display_ref = ft.Ref[ft.TextField]()

    def show(self):
        """Show the processing log dialog"""
        try:
            print("ProcessingLogDialog.show() called")

            # Create the dialog
            dialog = self._create_dialog()
            self.dialog_ref.current = dialog

            # Sync the log content before showing
            self._sync_log_content()

            # Open the dialog
            self.page.open(dialog)
            self.page.update()

        except Exception as ex:
            print(f"Error in ProcessingLogDialog.show(): {ex}")
            import traceback
            traceback.print_exc()

    def _sync_log_content(self):
        """Sync log content from main log to dialog display"""
        if self.log_text_ref.current and self.log_display_ref.current:
            self.log_display_ref.current.value = self.log_text_ref.current.value
            if self.page:
                self.page.update()

    def _create_dialog(self) -> ft.AlertDialog:
        """Create the processing log dialog"""
        # Create a display field that will show a copy of the log
        # This is synced from the main log field
        log_display = ft.TextField(
            ref=self.log_display_ref,
            value=self.log_text_ref.current.value if self.log_text_ref.current else "",
            multiline=True,
            read_only=True,
            expand=True,
            text_style=ft.TextStyle(font_family="Courier New"),
            min_lines=20,
            max_lines=30,
        )

        # Refresh button
        refresh_button = ft.TextButton(
            "Refresh",
            icon=ft.icons.REFRESH,
            on_click=self._refresh_log,
        )

        # Clear button
        clear_button = ft.TextButton(
            "Clear Log",
            icon=ft.icons.DELETE_OUTLINE,
            on_click=self._clear_log,
        )

        # Close button
        close_button = ft.TextButton(
            "Close",
            on_click=self._close_clicked,
        )

        dialog = ft.AlertDialog(
            ref=self.dialog_ref,
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.icons.LIST_ALT, color="blue"),
                    ft.Text("Processing Log", size=20, weight=ft.FontWeight.BOLD),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            content=ft.Container(
                content=log_display,
                width=800,
                height=500,
            ),
            actions=[
                refresh_button,
                clear_button,
                close_button,
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        return dialog

    def _refresh_log(self, e):
        """Refresh the log content from the main log"""
        self._sync_log_content()

    def _clear_log(self, e):
        """Clear the log"""
        # Clear both the main log and the display
        if self.log_text_ref.current:
            self.log_text_ref.current.value = ""
        if self.log_display_ref.current:
            self.log_display_ref.current.value = ""
        self.page.update()

    def _close_clicked(self, e):
        """Handle close button click"""
        if self.dialog_ref.current:
            self.page.close(self.dialog_ref.current)
