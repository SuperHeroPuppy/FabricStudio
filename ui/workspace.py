# workspace.py
# developer: SuperHeroPuppy
# version: 1.0.2

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import Menu, filedialog

import customtkinter as ctk

from core.build_runner import BuildRunner
from core.mod_icon import apply_mod_icon, upload_mod_icon
from ui.debug_console import DebugConsole
from ui.file_tree import FileTree
from ui.tab_bar import TabBar
from ui.editor_manager import EditorManager
from core.data_store import COLORS, GENERATORS_ROOT
from ui.generator_window import GeneratorWindow
from core.project_generator import iter_generator_specs
from core.tool_generator_registry import iter_tool_generators
from ui.theme import theme_menu, themed_entry, theme_window
from ui.window_utils import show_on_top

class WorkspacePage(ctk.CTkFrame):
    def __init__(self, master, on_back):
        super().__init__(master, fg_color=COLORS["bg"])

        self.on_back = on_back
        self.workspace_path: Path | None = None

        self.build_runner = BuildRunner()

        self.is_busy = False
        self.open_files: dict[Path, str] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(
            self,
            fg_color=COLORS["panel"],
            corner_radius=0,
            height=46,
        )

        top.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        top.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            top,
            text="Setup",
            width=84,
            command=self.on_back,
        ).grid(
            row=0,
            column=0,
            padx=10,
            pady=8,
        )

        self.title_label = ctk.CTkLabel(
            top,
            text="Workspace",
            anchor="w",
            text_color=COLORS["muted"],
        )

        self.title_label.grid(
            row=0,
            column=1,
            sticky="ew",
            padx=4,
        )

        compile_group = ctk.CTkFrame(top, fg_color="transparent")
        compile_group.grid(
            row=0,
            column=3,
            padx=10,
            pady=8,
        )

        self.settings_button = ctk.CTkButton(
            top,
            text="Settings",
            width=92,
            command=self.open_workspace_settings,
        )

        self.settings_button.grid(
            row=0,
            column=2,
            padx=(0, 10),
            pady=8,
        )

        self.compile_button = ctk.CTkButton(
            compile_group,
            text="Compile",
            width=82,
            command=self.compile_workspace,
        )

        self.compile_button.pack(side="left")

        self.compile_menu_button = ctk.CTkButton(
            compile_group,
            text="v",
            width=28,
            command=self._show_compile_menu,
        )

        self.compile_menu_button.pack(side="left", padx=(4, 0))

        self.compile_menu = Menu(self, tearoff=0)
        theme_menu(self.compile_menu)
        self.compile_menu.add_command(
            label="Build",
            command=self.compile_workspace,
        )
        self.compile_menu.add_command(
            label="Run Client",
            command=lambda: self.run_gradle_task("runClient", "Running Client"),
        )
        self.compile_menu.add_command(
            label="Run Server",
            command=lambda: self.run_gradle_task("runServer", "Running Server"),
        )

        self.generator_button = ctk.CTkButton(
            top,
            text="Generators",
            width=110,
            command=self.open_generators,
        )

        self.generator_button.grid(
            row=0,
            column=4,
            padx=(0, 10),
            pady=8,
        )

        self.install_gradle_button = ctk.CTkButton(
            top,
            text="Install Gradle",
            width=116,
            command=self.install_gradle,
        )

        self.install_gradle_button.grid(
            row=0,
            column=5,
            padx=(0, 10),
            pady=8,
        )

        self.main_pane = tk.PanedWindow(
            self,
            orient=tk.HORIZONTAL,
            bg=COLORS["border"],
            sashwidth=5,
            bd=0,
            relief="flat",
        )

        self.main_pane.grid(
            row=1,
            column=0,
            sticky="nsew",
        )

        self.tree = FileTree(
            self.main_pane,
            self._open_file,
        )

        self.main_pane.add(
            self.tree,
            minsize=180,
            width=280,
        )

        editor_console_frame = ctk.CTkFrame(
            self.main_pane,
            fg_color=COLORS["bg"],
            corner_radius=0,
        )

        self.main_pane.add(
            editor_console_frame,
            minsize=360,
        )

        self.tab_bar = TabBar(
            editor_console_frame,
            self._select_file,
            self._close_file,
            self._split_file,
        )

        self.tab_bar.pack(
            fill="x",
            side="top",
        )

        self.editor_pane = tk.PanedWindow(
            editor_console_frame,
            orient=tk.VERTICAL,
            bg=COLORS["border"],
            sashwidth=5,
            bd=0,
            relief="flat",
        )

        self.editor_pane.pack(
            fill="both",
            expand=True,
            side="top",
        )

        self.editor_manager = EditorManager(
            self.editor_pane
        )

        self.editor_pane.add(
            self.editor_manager,
            minsize=240,
            height=420,
        )


        self.console = DebugConsole(
            self.editor_pane
        )

        self.editor_pane.add(
            self.console,
            minsize=120,
            height=180,
        )

        self.refresh_gradle_state()

    def _split_file(self, path: Path):

        self.editor_manager.split_open(path)

        self.editor_manager.right.set_close_callback(
            self.editor_manager.close_right
        )

    def load_workspace(self, path: Path) -> None:

        self.workspace_path = path

        self.title_label.configure(
            text=str(path)
        )

        self.tree.load(path)

        self.refresh_gradle_state()

    def open_workspace_settings(self) -> None:

        if not self.workspace_path:
            return

        meta = self._read_project_info()
        window = ctk.CTkToplevel(self)
        window.title(f"{self.workspace_path.name} Settings")
        window.geometry("520x380")
        theme_window(window)
        show_on_top(window, self)
        window.grid_columnconfigure(1, weight=1)

        fields: dict[str, ctk.CTkEntry] = {}
        field_specs = [
            ("name", "Mod Name"),
            ("mod_version", "Mod Version"),
            ("author", "Author"),
            ("description", "Description"),
        ]

        for row, (key, label) in enumerate(field_specs):
            ctk.CTkLabel(
                window,
                text=label,
                text_color=COLORS["muted"],
            ).grid(row=row, column=0, sticky="w", padx=18, pady=12)
            entry = themed_entry(window, height=34)
            entry.grid(row=row, column=1, sticky="ew", padx=(0, 18), pady=12)
            entry.insert(0, str(meta.get(key, "")))
            fields[key] = entry

        icon_label = ctk.CTkLabel(
            window,
            text=str(meta.get("icon", "No icon selected")),
            text_color=COLORS["muted"],
            anchor="w",
        )
        icon_label.grid(row=len(field_specs), column=1, sticky="ew", padx=(0, 18), pady=12)
        ctk.CTkLabel(
            window,
            text="Mod Icon",
            text_color=COLORS["muted"],
        ).grid(row=len(field_specs), column=0, sticky="w", padx=18, pady=12)

        def choose_icon() -> None:
            selected = filedialog.askopenfilename(
                title="Upload mod icon",
                filetypes=[("PNG Images", "*.png")],
                parent=window,
            )
            if not selected or not self.workspace_path:
                return

            try:
                icon_path = upload_mod_icon(self.workspace_path, Path(selected), meta)
            except OSError as exc:
                self._show_settings_message(window, f"Could not upload icon: {exc}")
                return

            self._write_workspace_settings(meta)
            icon_label.configure(text=icon_path)

        ctk.CTkButton(
            window,
            text="Upload Icon",
            command=choose_icon,
        ).grid(
            row=len(field_specs) + 1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=18,
            pady=(2, 8),
        )

        def save_settings() -> None:
            updated = {key: entry.get().strip() for key, entry in fields.items()}
            if not updated["mod_version"]:
                updated["mod_version"] = "1.0.0"
            meta.update(updated)
            self._write_workspace_settings(meta)
            self.title_label.configure(text=str(self.workspace_path))
            self.tree.load(self.workspace_path)
            window.destroy()

        ctk.CTkButton(
            window,
            text="Save Settings",
            command=save_settings,
        ).grid(
            row=len(field_specs) + 2,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=18,
            pady=(10, 18),
        )

    def _read_project_info(self) -> dict:

        if not self.workspace_path:
            return {}

        info_path = self.workspace_path / "project_info.json"
        if not info_path.exists():
            return {"name": self.workspace_path.name, "mod_version": "1.0.0"}

        try:
            payload = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"name": self.workspace_path.name, "mod_version": "1.0.0"}

        if not isinstance(payload, dict):
            payload = {}

        payload.setdefault("name", self.workspace_path.name)
        payload.setdefault("mod_version", self._read_gradle_property("mod_version") or "1.0.0")
        return payload

    def _write_workspace_settings(self, meta: dict) -> None:

        if not self.workspace_path:
            return

        info_path = self.workspace_path / "project_info.json"
        info_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        self._write_gradle_property("mod_version", str(meta.get("mod_version") or "1.0.0"))

        mod_json_path = self.workspace_path / "src" / "main" / "resources" / "fabric.mod.json"
        if mod_json_path.exists():
            try:
                payload = json.loads(mod_json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}

            if isinstance(payload, dict):
                payload["name"] = meta.get("name", self.workspace_path.name)
                payload["description"] = meta.get("description", "")
                payload["authors"] = [meta.get("author", "Unknown")]
                if meta.get("icon"):
                    payload["icon"] = meta["icon"]
                mod_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        apply_mod_icon(self.workspace_path, meta)

    def _show_settings_message(self, parent, message: str) -> None:
        window = ctk.CTkToplevel(parent)
        window.title("Settings")
        window.geometry("360x150")
        theme_window(window)
        show_on_top(window, parent)
        ctk.CTkLabel(window, text=message, wraplength=300).pack(expand=True, padx=18, pady=(20, 10))
        ctk.CTkButton(window, text="OK", width=80, command=window.destroy).pack(pady=(0, 16))

    def _read_gradle_property(self, key: str) -> str:

        if not self.workspace_path:
            return ""

        path = self.workspace_path / "gradle.properties"
        if not path.exists():
            return ""

        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
        return ""

    def _write_gradle_property(self, key: str, value: str) -> None:

        if not self.workspace_path:
            return

        path = self.workspace_path / "gradle.properties"
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        updated = False
        for index, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[index] = f"{key}={value}"
                updated = True
                break

        if not updated:
            lines.append(f"{key}={value}")

        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _open_file(self, path: Path) -> None:

        self.tab_bar.add_tab(path)

        self.editor_manager.open_file(path)

        self.open_files[path] = "active"

    def open_generators(self):

        if not self.workspace_path:
            return

        project_info = (
            self.workspace_path
            / "project_info.json"
        )

        if not project_info.exists():
            return

        import json

        payload = json.loads(
            project_info.read_text(
                encoding="utf-8"
            )
        )

        generator_root = self._project_generator_root(payload)

        if generator_root is None:
            self.console.write(
                "\nNo matching project generator was found for this workspace.\n"
            )
            return
        
        GeneratorWindow(
            self,
            iter_tool_generators(generator_root),
            self.workspace_path,    
        )

    def _project_generator_root(self, payload: dict) -> Path | None:

        generator_info = payload.get("generator", {})

        if isinstance(generator_info, dict):

            root = generator_info.get("root")

            if root:

                root_path = Path(root)

                if root_path.exists():
                    return root_path

            generator_id = generator_info.get("id") or payload.get("generator_id")

        else:

            generator_id = payload.get("generator_id")

        specs = iter_generator_specs(GENERATORS_ROOT)

        if generator_id:

            for spec in specs:

                if spec.id == generator_id:
                    return spec.root

        minecraft_version = payload.get("minecraft_version")
        loader = str(payload.get("loader", "fabric")).lower()

        matches = [
            spec
            for spec in specs
            if spec.minecraft_version == minecraft_version
            and spec.loader == loader
        ]

        if not matches:
            return None

        return sorted(
            matches,
            key=lambda spec: spec.generator_version,
            reverse=True,
        )[0].root

    def _select_file(self, path: Path) -> None:

        self.editor_manager.set_active("left")

        self.editor_manager.open_file(path)

    def _close_file(self, path: Path) -> None:

        if path in self.open_files:
            del self.open_files[path]

        if not self.open_files:
            self.editor_manager.clear_all()

    def _show_compile_menu(self) -> None:

        if self.is_busy:
            return

        self.compile_menu.tk_popup(
            self.compile_menu_button.winfo_rootx(),
            self.compile_menu_button.winfo_rooty() + self.compile_menu_button.winfo_height(),
        )

    def compile_workspace(self) -> None:

        self.run_gradle_task("build", "Compiling")

    def run_gradle_task(self, task: str, action_label: str) -> None:

        if not self.workspace_path:
            self.console.write(
                "No workspace is open.\n"
            )
            return

        self.editor_manager.save_all()

        self.is_busy = True

        self.compile_button.configure(
            state="disabled",
            text=action_label,
        )

        self.compile_menu_button.configure(
            state="disabled",
        )

        self.install_gradle_button.configure(
            state="disabled",
        )

        self.console.write(
            f"\n{action_label} {self.workspace_path.name}...\n"
        )

        self.build_runner.run_gradle_task(
            self.workspace_path,
            task,
            self._write_console,
            self._compile_finished,
        )

    def install_gradle(self) -> None:

        self.is_busy = True

        self.install_gradle_button.configure(
            state="disabled",
            text="Installing",
        )

        self.compile_button.configure(
            state="disabled",
        )

        self.compile_menu_button.configure(
            state="disabled",
        )

        self.console.write(
            "\nInstalling Gradle...\n"
        )

        self.build_runner.install_gradle(
            self.workspace_path,
            self._write_console,
            self._install_finished,
        )

    def _write_console(self, text: str) -> None:

        self.after(
            0,
            lambda: self.console.write(text),
        )

    def _compile_finished(self, exit_code: int) -> None:

        def finish() -> None:

            self.is_busy = False

            status = (
                "succeeded"
                if exit_code == 0
                else f"failed with exit code {exit_code}"
            )

            self.console.write(
                f"\nBuild {status}.\n"
            )

            self.compile_button.configure(
                text="Compile"
            )

            self.compile_menu_button.configure(
                state="normal"
            )

            self.install_gradle_button.configure(
                text="Install Gradle"
            )

            self.refresh_gradle_state()

        self.after(0, finish)

    def _install_finished(self, exit_code: int) -> None:

        def finish() -> None:

            self.is_busy = False

            status = (
                "installed successfully"
                if exit_code == 0
                else f"failed with exit code {exit_code}"
            )

            self.console.write(
                f"\nGradle install {status}.\n"
            )

            self.install_gradle_button.configure(
                text="Install Gradle"
            )

            self.refresh_gradle_state()

        self.after(0, finish)

    def refresh_gradle_state(self) -> None:

        available = self.build_runner.is_gradle_available(
            self.workspace_path
        )

        if self.is_busy:
            return

        self.compile_button.configure(
            state="normal"
            if available and self.workspace_path
            else "disabled"
        )

        self.compile_menu_button.configure(
            state="normal"
            if available and self.workspace_path
            else "disabled"
        )

        self.install_gradle_button.configure(
            state="disabled"
            if available
            else "normal"
        )
