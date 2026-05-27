from __future__ import annotations

import threading

import customtkinter as ctk

from core.data_store import COLORS, TOOL_BUILD, TOOL_NAME, TOOL_VERSION
from core.update_manager import UpdateBuild, UpdateManager, compare_builds
from ui.tools.markdown_formatter import render_markdown


class UpdateManagerPage(ctk.CTkToplevel):
    def __init__(self, master, update_manager: UpdateManager) -> None:
        super().__init__(master)
        self.update_manager = update_manager
        self.updates: list[UpdateBuild] = []

        self.title(f"{TOOL_NAME} Update Manager")
        self.geometry("1100x720")
        self.configure(fg_color=COLORS["bg"])

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=300, fg_color=COLORS["panel"], corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(sidebar, text="Update Manager", font=("Segoe UI", 25, "bold")).grid(
            row=0,
            column=0,
            sticky="w",
            padx=20,
            pady=(20, 6),
        )
        ctk.CTkLabel(
            sidebar,
            text=f"Current: {TOOL_VERSION} {TOOL_BUILD}",
            text_color=COLORS["muted"],
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        self.version_list = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.version_list.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        content = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(content, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(22, 8))
        header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(header, text="Checking GitHub...", font=("Segoe UI", 28, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w")

        self.action_button = ctk.CTkButton(
            header,
            text="Download",
            width=160,
            state="disabled",
            command=self._download_selected,
        )
        self.action_button.grid(row=0, column=1, sticky="e", padx=(12, 0))

        self.status_label = ctk.CTkLabel(header, text="", text_color=COLORS["muted"])
        self.status_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(5, 0))

        self.scroll = ctk.CTkScrollableFrame(
            content,
            fg_color=COLORS["panel"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=24, pady=(18, 24))

        self.selected_update: UpdateBuild | None = None
        self._set_status("Checking GitHub for available builds...")
        threading.Thread(target=self._load_updates, daemon=True).start()

    def _load_updates(self) -> None:
        try:
            updates = self.update_manager.list_remote_updates()
        except Exception as exc:
            message = f"Could not check for updates: {exc}"
            self.after(0, lambda: self._show_error(message))
            return
        self.after(0, lambda: self._show_updates(updates))

    def _show_updates(self, updates: list[UpdateBuild]) -> None:
        self.updates = updates
        for widget in self.version_list.winfo_children():
            widget.destroy()

        if not updates:
            self._show_error("No remote changelogs were found.")
            return

        for update in updates:
            ctk.CTkButton(
                self.version_list,
                text=update.label,
                height=38,
                anchor="w",
                fg_color=COLORS["panel_alt"],
                hover_color=COLORS["accent"],
                command=lambda item=update: self._select_update(item),
            ).pack(fill="x", padx=6, pady=4)

        self._select_update(updates[0])

    def _select_update(self, update: UpdateBuild) -> None:
        self.selected_update = update
        self.title_label.configure(text=update.label)
        render_markdown(self.scroll, update.changelog, COLORS)

        comparison = compare_builds(update.build, TOOL_BUILD)
        if comparison == 0:
            self._set_status("This is the build you are running now.")
        elif comparison > 0:
            self._set_status("This build is newer than your current build.")
        else:
            self._set_status("This build is older than your current build.")

        can_install = self.update_manager.can_install(update.build)
        self.action_button.configure(
            text=self.update_manager.install_label(update.build),
            state="normal" if can_install else "disabled",
        )

    def _download_selected(self) -> None:
        if not self.selected_update:
            return
        update = self.selected_update
        self.action_button.configure(state="disabled")
        self._set_status(f"Downloading {update.label} from GitHub...")
        threading.Thread(target=lambda: self._download(update), daemon=True).start()

    def _download(self, update: UpdateBuild) -> None:
        try:
            destination = self.update_manager.download_update(update)
        except Exception as exc:
            message = f"Download failed: {exc}"
            self.after(0, lambda: self._show_error(message))
            return
        self.after(0, lambda: self._download_finished(destination))

    def _download_finished(self, destination) -> None:
        self._set_status(f"Downloaded update to {destination}")
        if self.selected_update:
            self.action_button.configure(state="normal")

    def _show_error(self, message: str) -> None:
        self.title_label.configure(text="Update Manager")
        self._set_status(message)
        self.action_button.configure(state="disabled")

    def _set_status(self, message: str) -> None:
        self.status_label.configure(text=message)


class StartupUpdatePage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        update_manager: UpdateManager,
        on_continue,
        on_open_update_manager,
    ) -> None:
        super().__init__(master, fg_color=COLORS["bg"])
        self.update_manager = update_manager
        self.on_continue = on_continue
        self.on_open_update_manager = on_open_update_manager
        self.update: UpdateBuild | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(26, 12))
        header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(header, text="Checking for updates...", font=("Segoe UI", 28, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w")

        self.status_label = ctk.CTkLabel(header, text="", text_color=COLORS["muted"], font=("Segoe UI", 14))
        self.status_label.grid(row=1, column=0, sticky="w", pady=(5, 0))

        self.preview = ctk.CTkScrollableFrame(
            self,
            fg_color=COLORS["panel"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.preview.grid(row=1, column=0, sticky="nsew", padx=28, pady=(8, 16))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=28, pady=(0, 24))
        actions.grid_columnconfigure(0, weight=1)

        self.download_button = ctk.CTkButton(
            actions,
            text="Download Latest",
            width=150,
            state="disabled",
            command=self._download_latest,
        )
        self.download_button.grid(row=0, column=1, padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="Update Manager",
            width=150,
            command=self.on_open_update_manager,
        ).grid(row=0, column=2, padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="Continue",
            width=120,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["accent"],
            command=self.on_continue,
        ).grid(row=0, column=3, padx=(8, 0))

    def show_update(self, update: UpdateBuild) -> None:
        self.update = update
        self.title_label.configure(text=f"New build available: {update.build}")
        self.status_label.configure(text=f"You are running {TOOL_BUILD}. Latest GitHub build is {update.build}.")
        render_markdown(self.preview, changelog_preview(update.changelog), COLORS)
        self.download_button.configure(state="normal")

    def show_no_update(self) -> None:
        self.title_label.configure(text="No update found")
        self.status_label.configure(text="You are already on the latest available build.")
        self.download_button.configure(state="disabled")

    def show_error(self, message: str) -> None:
        self.title_label.configure(text="Could not check for updates")
        self.status_label.configure(text=message)
        self.download_button.configure(state="disabled")

    def _download_latest(self) -> None:
        if not self.update:
            return
        update = self.update
        self.download_button.configure(state="disabled")
        self.status_label.configure(text=f"Downloading {update.build} from GitHub...")
        threading.Thread(target=lambda: self._download(update), daemon=True).start()

    def _download(self, update: UpdateBuild) -> None:
        try:
            destination = self.update_manager.download_update(update)
        except Exception as exc:
            message = f"Download failed: {exc}"
            self.after(0, lambda: self.show_error(message))
            return
        self.after(0, lambda: self.status_label.configure(text=f"Downloaded update to {destination}"))


def changelog_preview(changelog: str, max_lines: int = 18) -> str:
    lines = changelog.splitlines()
    if len(lines) <= max_lines:
        return changelog
    return "\n".join(lines[:max_lines] + ["", "More details are available in the Update Manager."])
