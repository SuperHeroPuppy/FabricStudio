import tkinter as tk
import customtkinter as ctk
from pathlib import Path
from core.data_store import COLORS


class TabBar(ctk.CTkFrame):
    def __init__(self, master, on_select, on_close, on_split=None):
        super().__init__(master, fg_color=COLORS["panel"], height=36)

        self.on_select = on_select
        self.on_close = on_close
        self.on_split = on_split

        self.tabs: dict[Path, ctk.CTkFrame] = {}

        self.canvas = tk.Canvas(
            self,
            bg=COLORS["panel"],
            highlightthickness=0,
            bd=0,
            height=36,
        )

        self.inner = ctk.CTkFrame(self.canvas, fg_color=COLORS["panel"])

        self.inner_id = self.canvas.create_window(
            (0, 0),
            window=self.inner,
            anchor="nw",
        )

        self.canvas.pack(fill="both", expand=True)

        self.inner.bind("<Configure>", self._resize)

        self.canvas.bind(
            "<MouseWheel>",
            lambda e: self.canvas.xview_scroll(int(-e.delta / 120), "units"),
        )

    def _resize(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def add_tab(self, path: Path):
        if path in self.tabs:
            return

        frame = ctk.CTkFrame(
            self.inner,
            fg_color=COLORS["panel_alt"],
            corner_radius=8,
            height=28,
        )
        frame.pack(side="left", padx=4, pady=4)

        btn = ctk.CTkButton(
            frame,
            text=path.name,
            width=140,
            height=26,
            fg_color="transparent",
            hover_color=COLORS["panel"],
            anchor="w",
            command=lambda: self.on_select(path),
        )
        btn.pack(side="left", padx=(6, 0))

        split_btn = ctk.CTkButton(
            frame,
            text="⇱",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color=COLORS["panel"],
            command=lambda: self._split_tab(path),
        )
        split_btn.pack(side="left", padx=(4, 0))

        close_btn = ctk.CTkButton(
            frame,
            text="×",
            width=24,
            height=24,
            fg_color="transparent",
            hover_color="#7a1f1f",
            command=lambda: self.remove_tab(path),
        )
        close_btn.pack(side="left", padx=(2, 4))

        self.tabs[path] = frame

    def _split_tab(self, path: Path):
        if self.on_split:
            self.on_split(path)

    def remove_tab(self, path: Path):
        if path not in self.tabs:
            return

        self.tabs[path].destroy()
        del self.tabs[path]

        self.on_close(path)
