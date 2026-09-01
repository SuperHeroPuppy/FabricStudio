# editor_manager.py
# developer: SuperHeroPuppy
# version: 1.0.0

import customtkinter as ctk
from pathlib import Path

from ui.editor import EditorPane
from core.data_store import COLORS


class EditorManager(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.left = EditorPane(self)
        self.right = EditorPane(self)

        self.left.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self.right_visible = False
        self.active = self.left

    def show_right(self):
        if self.right_visible:
            return

        self.grid_columnconfigure(1, weight=1)

        self.left.grid_configure(padx=(6, 3))

        self.right.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(3, 6),
            pady=6,
        )

        self.right_visible = True

    def clear_active(self):
        self.active.clear()

    def clear_all(self):
        self.left.clear()
        self.right.clear()

    def hide_right(self):
        if not self.right_visible:
            return

        self.right.clear()

        self.right.grid_remove()

        # remove second column weight
        self.grid_columnconfigure(1, weight=0)

        # force left editor to reclaim space
        self.left.grid_configure(
            row=0,
            column=0,
            sticky="nsew",
            padx=6,
            pady=6,
        )

        self.update_idletasks()

        self.right_visible = False
        self.active = self.left

        self.left.focus_set()

    def set_active(self, side: str):
        self.active = self.left if side == "left" else self.right

    def open_file(self, path: Path, side: str | None = None):
        target = self.active if side is None else (
            self.left if side == "left" else self.right
        )

        target.open_file(path)
        return target

    def split_open(self, path: Path):
        self.show_right()
        self.right.open_file(path)
        self.active = self.right

    def close_right(self):
        self.hide_right()

    def save_all(self):
        self.left.save_current()

        if self.right_visible:
            self.right.save_current()

    def refresh_path(self, path: Path) -> None:
        self.left.refresh_if_clean(path)
        if self.right_visible:
            self.right.refresh_if_clean(path)

    def refresh_open_files(self) -> None:
        if self.left.current_file is not None:
            self.left.refresh_if_clean(self.left.current_file)
        if self.right_visible and self.right.current_file is not None:
            self.right.refresh_if_clean(self.right.current_file)
