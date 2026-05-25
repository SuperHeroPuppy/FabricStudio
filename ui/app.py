from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from core.project_generator import ProjectData, ProjectGenerator
from ui.setup_page import SetupPage
from ui.theme import COLORS, configure_theme
from ui.workspace import WorkspacePage


class FabricStudioApp(ctk.CTk):
    def __init__(self) -> None:
        configure_theme()
        super().__init__()

        self.title("Fabric Studio")
        self.geometry("1100x720")
        self.minsize(980, 620)
        self.configure(fg_color=COLORS["bg"])
        self.workspaces_root = Path.cwd() / "workspaces"
        self.workspaces_root.mkdir(exist_ok=True)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.setup_page = SetupPage(self, self._generate_project, self._open_workspace, self.workspaces_root)
        self.workspace_page = WorkspacePage(self, self._show_setup)
        self.setup_page.grid(row=0, column=0, sticky="nsew")

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

    def _show_message(self, message: str) -> None:
        window = ctk.CTkToplevel(self)
        window.title("Fabric Studio")
        window.geometry("360x160")
        window.transient(self)
        ctk.CTkLabel(window, text=message, wraplength=300).pack(expand=True, padx=20, pady=(22, 10))
        ctk.CTkButton(window, text="OK", width=80, command=window.destroy).pack(pady=(0, 18))
