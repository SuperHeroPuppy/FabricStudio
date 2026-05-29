# editor.py
# developer: SuperHeroPuppy
# version: 1.0.1

from __future__ import annotations

from importlib.resources import path
import keyword
import re
from pathlib import Path
from ui.texture_viewer import TextureViewer

import customtkinter as ctk

from core.data_store import COLORS


class EditorPane(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])
        self.current_file: Path | None = None
        self.word_wrap = False
        self._highlight_job: str | None = None
        self.close_side_callback = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=0, height=42)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(0, weight=1)
        

        self.path_label = ctk.CTkLabel(bar, text="No file open", anchor="w", text_color=COLORS["muted"])
        self.path_label.grid(row=0, column=0, sticky="ew", padx=14, pady=8)
        self.wrap_switch = ctk.CTkSwitch(bar, text="Wrap", width=70, command=self.toggle_word_wrap)
        self.wrap_switch.grid(row=0, column=1, padx=(0, 8), pady=7)
        self.save_button = ctk.CTkButton(bar, text="Save", width=70, command=self.save_current)
        self.save_button.grid(row=0, column=2, sticky="e", padx=(0, 10), pady=7)

        self.close_side_button = ctk.CTkButton(
            bar,
            text="×",
            width=32,
            command=self._close_side,
        )

        self.close_side_button.grid(
            row=0,
            column=3,
            padx=(0, 10),
            pady=7,
        )

        self.close_side_button.grid_remove()

        self.content_frame = ctk.CTkFrame( self, fg_color="transparent", ) 
        self.content_frame.grid( row=1, column=0, sticky="nsew", )
        self.content_frame.grid_rowconfigure(0, weight=1) 
        self.content_frame.grid_columnconfigure(0, weight=1)

        self.textbox = ctk.CTkTextbox( self.content_frame, fg_color="#0f1117", text_color=COLORS["text"], border_color=COLORS["border"], border_width=1, font=("Consolas", 13), wrap="none", undo=True, )
        self.textbox.grid( row=0, column=0, sticky="nsew", padx=10, pady=10, )
        self.textbox.insert( "1.0", "Open a file from Explorer to start editing." )
        self.textbox.bind( "<KeyRelease>", self._queue_highlight, )
        
        self.texture_viewer = TextureViewer( self.content_frame )
        self.texture_viewer.grid( row=0, column=0, sticky="nsew", )
        self.texture_viewer.grid_remove() 
        self._configure_tags()

    def load_content(self, path: Path, content: str) -> None:
        self.current_file = path
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", content)
        self.path_label.configure(text=str(path))
        self._highlight_syntax()

    def open_file(self, path: Path) -> None:

        self.current_file = path

        suffix = path.suffix.lower()

        self.path_label.configure(
            text=str(path)
        )

        if suffix in {".png"}:

            self.textbox.grid_remove()

            self.texture_viewer.grid()

            self.texture_viewer.open_texture(path)

            return

        self.texture_viewer.grid_remove()

        self.textbox.grid()

        content = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        self.load_content(path, content)


    def save_current(self) -> None:
        if not self.current_file:
            return
        content = self.textbox.get("1.0", "end-1c")
        self.current_file.write_text(content, encoding="utf-8")

    def clear(self):
        self.current_file = None

        self.texture_viewer.grid_remove() 
        self.textbox.grid()

        self.textbox.delete("1.0", "end")
        self.textbox.insert(
            "1.0",
            "Open a file from Explorer to start editing."
        )

        self.path_label.configure(text="No file open")

    def set_close_callback(self, callback):
        self.close_side_callback = callback
        self.close_side_button.grid()

    def hide_close_button(self):
        self.close_side_button.grid_remove()

    def _close_side(self):
        if self.close_side_callback:
            self.close_side_callback()

    def toggle_word_wrap(self) -> None:
        self.word_wrap = bool(self.wrap_switch.get())
        self.textbox.configure(wrap="word" if self.word_wrap else "none")

    def _configure_tags(self) -> None:
        self.textbox.tag_config("keyword", foreground="#569cd6")
        self.textbox.tag_config("type", foreground="#4ec9b0")
        self.textbox.tag_config("string", foreground="#ce9178")
        self.textbox.tag_config("comment", foreground="#6a9955")
        self.textbox.tag_config("number", foreground="#b5cea8")

    def _queue_highlight(self, _event=None) -> None:
        if self._highlight_job is not None:
            self.after_cancel(self._highlight_job)
        self._highlight_job = self.after(120, self._highlight_syntax)

    def _highlight_syntax(self) -> None:
        self._highlight_job = None
        content = self.textbox.get("1.0", "end-1c")
        for tag in ("keyword", "type", "string", "comment", "number"):
            self.textbox.tag_remove(tag, "1.0", "end")

        suffix = self.current_file.suffix.lower() if self.current_file else ""
        if suffix in {".java", ".gradle"}:
            self._apply_matches(content, r'"(?:[^"\\]|\\.)*"', "string")
            self._apply_matches(content, r"//.*?$", "comment", re.MULTILINE)
            self._apply_matches(content, r"\b\d+(?:\.\d+)?\b", "number")
            self._apply_matches(content, r"\b(?:class|public|private|protected|package|import|return|new|void|static|final|implements|extends|if|else)\b", "keyword")
            self._apply_matches(content, r"\b(?:String|Integer|Boolean|Path|ModInitializer)\b", "type")
        elif suffix in {".json", ".properties"}:
            self._apply_matches(content, r'"(?:[^"\\]|\\.)*"', "string")
            self._apply_matches(content, r"#.*?$", "comment", re.MULTILINE)
            self._apply_matches(content, r"\b\d+(?:\.\d+)?\b", "number")
        elif suffix == ".py":
            self._apply_matches(content, r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', "string")
            self._apply_matches(content, r"#.*?$", "comment", re.MULTILINE)
            self._apply_matches(content, r"\b\d+(?:\.\d+)?\b", "number")
            self._apply_matches(content, rf"\b(?:{'|'.join(keyword.kwlist)})\b", "keyword")

    def _apply_matches(self, content: str, pattern: str, tag: str, flags: int = 0) -> None:
        for match in re.finditer(pattern, content, flags):
            start = self._index_from_offset(match.start())
            end = self._index_from_offset(match.end())
            self.textbox.tag_add(tag, start, end)

    def _index_from_offset(self, offset: int) -> str:
        return f"1.0+{offset}c"
