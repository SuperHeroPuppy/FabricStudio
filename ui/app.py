# app.py
# developer: SuperHeroPuppy
# version: 1.0.0

from __future__ import annotations

import threading
from pathlib import Path

import customtkinter as ctk

from core.data_store import COLORS, configure_theme
from core.project_generator import ProjectData, ProjectGenerator
from core.update_manager import UpdateManager
from ui.changelog_page import ChangelogPage
from ui.setup_page import SetupPage
from ui.theme import apply_tk_theme, theme_window
from ui.update_manager_page import StartupUpdatePage, UpdateManagerPage
from ui.workspace import WorkspacePage
from ui.window_utils import show_on_top


class FabricStudioApp(ctk.CTk):
    def __init__(self) -> None:
        configure_theme()
        super().__init__()

        self.title("Fabric Studio")
        self.geometry("1100x720")
        self.minsize(980, 620)
        theme_window(self)
        apply_tk_theme(self)
        self.workspaces_root = Path.cwd() / "workspaces"
        self.workspaces_root.mkdir(exist_ok=True)
        self.update_manager = UpdateManager()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.setup_page = SetupPage(
            self,
            self._generate_project,
            self._open_workspace,
            self._open_changelog,
            self._open_update_manager,
            self.workspaces_root,
        )
        self.workspace_page = WorkspacePage(self, self._show_setup)
        self.startup_update_page = StartupUpdatePage(
            self,
            self.update_manager,
            self._show_setup,
            self._open_update_manager,
        )
        self.startup_update_page.grid(row=0, column=0, sticky="nsew")
        self.setup_page.grid(row=0, column=0, sticky="nsew")
        self.startup_update_page.tkraise()
        self._check_for_startup_update()

    def _check_for_startup_update(self) -> None:
        threading.Thread(target=self._check_for_startup_update_worker, daemon=True).start()

    def _check_for_startup_update_worker(self) -> None:
        try:
            update = self.update_manager.check_latest_update()
        except Exception:
            self.after(0, self._show_setup)
            return

        if update is None:
            self.after(0, self._show_setup)
            return

        self.after(0, lambda: self._show_startup_update(update))

    def _show_startup_update(self, update) -> None:
        self.startup_update_page.show_update(update)
        self.startup_update_page.tkraise()

    def _generate_project(self, data: ProjectData) -> None:
        try:
            generator = ProjectGenerator(self.workspaces_root)
            workspace_path = generator.generate(data)
        except ValueError as exc:
            self._show_message(str(exc))
            return
        except OSError as exc:
            self._show_message(f"Could not create project: {exc}")
            return

        self._open_workspace(workspace_path)

    def _open_workspace(self, path: Path) -> None:
        self.setup_page.remember_workspace(path)
        self.workspace_page.load_workspace(path)
        self.workspace_page.grid(row=0, column=0, sticky="nsew")
        self.workspace_page.tkraise()

    def _show_setup(self) -> None:
        self.setup_page.refresh_workspace_lists()
        self.setup_page.tkraise()

    def _open_changelog(self) -> None:
        ChangelogPage(self)

    def _open_update_manager(self) -> None:
        UpdateManagerPage(self, self.update_manager)

    def _show_message(self, message: str) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Fabric Studio")
        window.geometry("360x160")
        theme_window(window)
        show_on_top(window, self)
        ctk.CTkLabel(window, text=message, wraplength=300).pack(expand=True, padx=20, pady=(22, 10))
        ctk.CTkButton(window, text="OK", width=80, command=window.destroy).pack(pady=(0, 18))
