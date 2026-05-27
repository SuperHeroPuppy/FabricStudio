from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from core.data_store import COLORS, TOOL_NAME
from ui.tools.markdown_formatter import render_markdown


class ChangelogPage(ctk.CTkToplevel):
    def __init__(self, master) -> None:
        super().__init__(master)
        self.title(f"{TOOL_NAME} Change Logs")
        self.geometry("1100x720")
        self.configure(fg_color=COLORS["bg"])

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=260, fg_color=COLORS["panel"], corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsw")
        sidebar.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(sidebar, text="Change Logs", font=("Segoe UI", 26, "bold")).grid(
            row=0,
            column=0,
            sticky="w",
            padx=20,
            pady=(20, 10),
        )

        self.version_list = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.version_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        content_frame = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        content_frame.grid(row=0, column=1, sticky="nsew")
        content_frame.grid_rowconfigure(1, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(content_frame, text="", font=("Segoe UI", 28, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w", padx=28, pady=(24, 14))

        self.scroll = ctk.CTkScrollableFrame(
            content_frame,
            fg_color=COLORS["panel"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
        )
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=24, pady=(18, 24))

        self._load_files()

    def _load_files(self) -> None:
        changelog_dir = Path("data") / "change_logs"
        changelog_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(changelog_dir.glob("*.md"), reverse=True, key=lambda path: path.stat().st_mtime)

        if not files:
            ctk.CTkLabel(
                self.version_list,
                text="No changelogs found.",
                text_color=COLORS["muted"],
            ).pack(anchor="w", padx=10, pady=10)
            return

        for file in files:
            ctk.CTkButton(
                self.version_list,
                text=file.stem,
                height=38,
                anchor="w",
                fg_color=COLORS["panel_alt"],
                hover_color=COLORS["accent"],
                command=lambda path=file: self._load_changelog(path),
            ).pack(fill="x", padx=6, pady=4)

        self._load_changelog(files[0])

    def _load_changelog(self, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            content = "# Failed to load changelog"

        self.title_label.configure(text=path.stem)
        render_markdown(self.scroll, content, COLORS)
