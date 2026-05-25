from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from tkinter import Menu, messagebox, simpledialog

import customtkinter as ctk

from ui.theme import COLORS


class FileTree(ctk.CTkFrame):
    def __init__(self, master, on_open_file):
        super().__init__(master, fg_color=COLORS["panel"], corner_radius=0)
        self.on_open_file = on_open_file
        self.root_path: Path | None = None
        self.collapsed_paths: set[Path] = set()
        self.menu = Menu(self, tearoff=0)
        self.menu_target: Path | None = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text="Explorer", font=("Segoe UI", 15, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(top, text="Refresh", width=76, command=self.refresh).grid(row=0, column=1, sticky="e")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=COLORS["panel"])
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 8))

    def load(self, root_path: Path) -> None:
        self.root_path = root_path
        self.collapsed_paths.clear()
        self.refresh()

    def refresh(self) -> None:
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        if not self.root_path:
            return
        self._add_directory(self.root_path, depth=0)
        self._configure_scrollbar()

    def _add_directory(self, path: Path, depth: int) -> None:
        for child in sorted(
            path.iterdir(),
            key=lambda item: (item.is_file(), item.name.lower()),
        ):

            # Fully hidden folders
            if child.name in {
                ".gradle",
                ".gradle-runtime",
                ".git",
                "bin",
                "__pycache__",
            }:
                continue

            # Special handling for build/
            if child.name == "build":

                self._add_row(child, depth)

                libs_dir = child / "libs"

                if libs_dir.exists():
                    self._add_row(libs_dir, depth + 1)

                    if libs_dir not in self.collapsed_paths:
                        self._add_directory(libs_dir, depth + 2)

                continue

            self._add_row(child, depth)

            if child.is_dir() and child not in self.collapsed_paths:
                self._add_directory(child, depth + 1)

    def _add_row(self, path: Path, depth: int) -> None:
        row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        row.pack(fill="x", padx=4, pady=1)
        row.grid_columnconfigure(0, weight=1)

        prefix = ""
        if path.is_dir():
            prefix = "+" if path in self.collapsed_paths else "-"
            text = f"{'    ' * depth}{prefix} {path.name}"
        else:
            text = f"{'    ' * depth}  {path.name}"

        button = ctk.CTkButton(
            row,
            text=text,
            anchor="w",
            fg_color="transparent",
            hover_color=COLORS["panel_alt"],
            text_color=COLORS["text"] if path.is_file() else COLORS["muted"],
            command=lambda item=path: self._select(item),
        )
        button.grid(row=0, column=0, sticky="ew")
        button.bind("<Button-3>", lambda event, item=path: self._show_menu(event, item))

    def _select(self, path: Path) -> None:
        if path.is_dir():
            if path in self.collapsed_paths:
                self.collapsed_paths.remove(path)
            else:
                self.collapsed_paths.add(path)
            self.refresh()
            return
        self.on_open_file(path)

    def _show_menu(self, event, path: Path) -> None:
        self.menu_target = path
        self.menu.delete(0, "end")
        if path.is_dir():
            self.menu.add_command(label="New Folder", command=self._new_folder)
            self.menu.add_command(label="New Java File", command=self._new_java_file)
            self.menu.add_command(label="New JSON File", command=self._new_json_file)
            self.menu.add_separator()
            self.menu.add_command(label="Find Location", command=self._find_location)
        else:
            self.menu.add_command(label="Edit", command=self._edit_file)
            self.menu.add_command(label="Delete", command=self._delete_path)
            self.menu.add_command(label="Find Location", command=self._find_location)
        self.menu.tk_popup(event.x_root, event.y_root)

    def _new_folder(self) -> None:
        target = self.menu_target
        if not target or not target.is_dir():
            return
        name = simpledialog.askstring("New Folder", "Folder name:", parent=self)
        if not name:
            return
        (target / name).mkdir(parents=False, exist_ok=True)
        self.refresh()

    def _new_java_file(self) -> None:
        target = self.menu_target
        if not target or not target.is_dir():
            return
        name = simpledialog.askstring("New Java File", "Java file name:", parent=self)
        if not name:
            return
        if not name.endswith(".java"):
            name += ".java"
        file_path = target / name
        class_name = file_path.stem
        package = self._infer_java_package(target)
        content = f"package {package};\n\npublic class {class_name} {{\n}}\n" if package else f"public class {class_name} {{\n}}\n"
        file_path.write_text(content, encoding="utf-8")
        self.refresh()
        self.on_open_file(file_path)

    def _new_json_file(self) -> None:
        target = self.menu_target
        if not target or not target.is_dir():
            return
        name = simpledialog.askstring("New JSON File", "JSON file name:", parent=self)
        if not name:
            return
        if not name.endswith(".json"):
            name += ".json"
        file_path = target / name
        file_path.write_text("{\n  \n}\n", encoding="utf-8")
        self.refresh()
        self.on_open_file(file_path)

    def _edit_file(self) -> None:
        target = self.menu_target
        if target and target.is_file():
            self.on_open_file(target)

    def _delete_path(self) -> None:
        target = self.menu_target
        if not target:
            return
        confirmed = messagebox.askyesno("Delete", f"Delete {target.name}?", parent=self)
        if not confirmed:
            return
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        self.refresh()

    def _find_location(self) -> None:
        target = self.menu_target
        if not target:
            return
        subprocess.Popen(["explorer", "/select,", str(target)])

    def _infer_java_package(self, folder: Path) -> str:
        parts = list(folder.parts)
        if "java" not in parts:
            return ""
        index = parts.index("java")
        package_parts = parts[index + 1 :]
        return ".".join(package_parts)

    def _configure_scrollbar(self) -> None:
        self.update_idletasks()
        canvas = self.list_frame._parent_canvas
        scrollbar = self.list_frame._scrollbar
        if canvas.yview() == (0.0, 1.0):
            scrollbar.grid_remove()
        else:
            scrollbar.grid()
