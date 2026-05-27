from __future__ import annotations

import re

import customtkinter as ctk

from core.data_store import COLORS


class DebugConsole(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["panel"], corner_radius=0)

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Debug Console", font=("Segoe UI", 13, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="Clear", width=68, command=self.clear).grid(row=0, column=1, sticky="e")

        self.output = ctk.CTkTextbox(
            self,
            fg_color="#0f1117",
            text_color=COLORS["text"],
            border_width=1,
            border_color=COLORS["border"],
            font=("Consolas", 12),
            wrap="word",
            height=150,
        )
        self.output.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.write("Debug console ready.\n")

    def write(self, text: str) -> None:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)
        self.output.insert("end", text)
        self.output.see("end")

    def clear(self) -> None:
        self.output.delete("1.0", "end")
