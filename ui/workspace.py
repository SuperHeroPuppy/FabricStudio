from __future__ import annotations

import tkinter as tk
from pathlib import Path

import customtkinter as ctk

from core.build_runner import BuildRunner
from ui.debug_console import DebugConsole
from ui.editor import EditorPane
from ui.file_tree import FileTree
from ui.theme import COLORS


class WorkspacePage(ctk.CTkFrame):
    def __init__(self, master, on_back):
        super().__init__(master, fg_color=COLORS["bg"])
        self.on_back = on_back
        self.workspace_path: Path | None = None
        self.build_runner = BuildRunner()
        self.is_busy = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=0, height=46)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(top, text="Setup", width=84, command=self.on_back).grid(row=0, column=0, padx=10, pady=8)
        self.title_label = ctk.CTkLabel(top, text="Workspace", anchor="w", text_color=COLORS["muted"])
        self.title_label.grid(row=0, column=1, sticky="ew", padx=4)
        self.compile_button = ctk.CTkButton(top, text="Compile", width=92, command=self.compile_workspace)
        self.compile_button.grid(row=0, column=2, padx=10, pady=8)
        self.install_gradle_button = ctk.CTkButton(top, text="Install Gradle", width=116, command=self.install_gradle)
        self.install_gradle_button.grid(row=0, column=3, padx=(0, 10), pady=8)

        self.main_pane = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg=COLORS["border"],
            sashwidth=5,
            bd=0,
            relief="flat",
        )
        self.main_pane.grid(row=1, column=0, sticky="nsew")

        self.tree = FileTree(self.main_pane, self._open_file)
        self.main_pane.add(self.tree, minsize=180, width=280)

        editor_console_frame = ctk.CTkFrame(self.main_pane, fg_color=COLORS["bg"], corner_radius=0)
        self.editor_pane = tk.PanedWindow(
            editor_console_frame,
            orient=tk.VERTICAL,
            bg=COLORS["border"],
            sashwidth=5,
            bd=0,
            relief="flat",
        )
        self.editor_pane.pack(fill="both", expand=True)
        self.main_pane.add(editor_console_frame, minsize=360)

        self.editor = EditorPane(self.editor_pane)
        self.editor_pane.add(self.editor, minsize=240, height=420)

        self.console = DebugConsole(self.editor_pane)
        self.editor_pane.add(self.console, minsize=120, height=180)

        self.refresh_gradle_state()

    def load_workspace(self, path: Path) -> None:
        self.workspace_path = path
        self.title_label.configure(text=str(path))
        self.tree.load(path)
        self.refresh_gradle_state()

    def _open_file(self, path: Path) -> None:
        self.editor.open_file(path)

    def compile_workspace(self) -> None:
        if not self.workspace_path:
            self.console.write("No workspace is open.\n")
            return

        self.editor.save_current()
        self.is_busy = True
        self.compile_button.configure(state="disabled", text="Compiling")
        self.install_gradle_button.configure(state="disabled")
        self.console.write(f"\nCompiling {self.workspace_path.name}...\n")
        self.build_runner.compile(self.workspace_path, self._write_console, self._compile_finished)

    def install_gradle(self) -> None:
        self.is_busy = True
        self.install_gradle_button.configure(state="disabled", text="Installing")
        self.compile_button.configure(state="disabled")
        self.console.write("\nInstalling Gradle...\n")
        self.build_runner.install_gradle(self.workspace_path,self._write_console,self._install_finished)

    def _write_console(self, text: str) -> None:
        self.after(0, lambda: self.console.write(text))

    def _compile_finished(self, exit_code: int) -> None:
        def finish() -> None:
            self.is_busy = False
            status = "succeeded" if exit_code == 0 else f"failed with exit code {exit_code}"
            self.console.write(f"\nBuild {status}.\n")
            self.compile_button.configure(text="Compile")
            self.install_gradle_button.configure(text="Install Gradle")
            self.refresh_gradle_state()

        self.after(0, finish)

    def _install_finished(self, exit_code: int) -> None:
        def finish() -> None:
            self.is_busy = False
            status = "installed successfully" if exit_code == 0 else f"failed with exit code {exit_code}"
            self.console.write(f"\nGradle install {status}.\n")
            self.install_gradle_button.configure(text="Install Gradle")
            self.refresh_gradle_state()

        self.after(0, finish)

    def refresh_gradle_state(self) -> None:
        available = self.build_runner.is_gradle_available(self.workspace_path)
        if self.is_busy:
            return
        self.compile_button.configure(state="normal" if available and self.workspace_path else "disabled")
        self.install_gradle_button.configure(state="disabled" if available else "normal")
