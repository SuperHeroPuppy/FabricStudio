from __future__ import annotations

import json
import shutil
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.project_generator import ProjectData
from data.versions import FABRIC_VERSIONS, MINECRAFT_VERSIONS
from ui.theme import COLORS


class SetupPage(ctk.CTkFrame):
    def __init__(self, master, on_generate, on_open_workspace, workspaces_root: Path):
        super().__init__(master, fg_color=COLORS["bg"])
        self.on_generate = on_generate
        self.on_open_workspace = on_open_workspace
        self.workspaces_root = workspaces_root
        self.recent_file = self.workspaces_root / ".recent_workspaces.json"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(24, 12))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="Fabric Studio", font=("Segoe UI", 30, "bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Create a workspace, reopen earlier ones, and manage project settings from the landing page.",
            text_color=COLORS["muted"],
            font=("Segoe UI", 14),
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        ctk.CTkButton(header, text="Open Folder", width=132, command=self._open_folder).grid(row=0, column=1, rowspan=2, sticky="e")

        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=28, pady=(8, 24))
        content.grid_columnconfigure(0, weight=1)

        body = ctk.CTkFrame(content, fg_color=COLORS["panel"], corner_radius=8, border_width=1, border_color=COLORS["border"])
        body.grid(row=0, column=0, sticky="ew")
        body.grid_columnconfigure(1, weight=1)

        self.name_entry = self._entry(body, "Workspace Name", 0)
        self.mod_id_entry = self._entry(body, "Mod ID", 1)
        self.author_entry = self._entry(body, "Author", 2)
        self.description_entry = self._entry(body, "Description", 3)
        self.package_root_entry = self._entry(body, "Package Root", 4, "com")
        self.package_name_entry = self._entry(body, "Package Name", 5)

        self.minecraft_menu = self._menu(body, "Minecraft Version", MINECRAFT_VERSIONS, 6)
        self.minecraft_menu.set("1.20.1")
        self.minecraft_menu.configure(command=self._on_minecraft_changed)

        self.fabric_menu = self._menu(body, "Fabric Loader", FABRIC_VERSIONS["1.20.1"], 7)
        self.fabric_menu.set(FABRIC_VERSIONS["1.20.1"][0])

        ctk.CTkButton(body, text="Generate Workspace", height=38, command=self._generate).grid(
            row=8, column=0, columnspan=2, sticky="ew", padx=22, pady=(18, 22)
        )

        self.workspace_panel = ctk.CTkFrame(content, fg_color=COLORS["panel"], corner_radius=8, border_width=1, border_color=COLORS["border"])
        self.workspace_panel.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        self.workspace_panel.grid_columnconfigure(0, weight=1)
        self.workspace_panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.workspace_panel, text="Workspaces", font=("Segoe UI", 17, "bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 8)
        )
        self.workspace_list = ctk.CTkScrollableFrame(self.workspace_panel, fg_color="transparent")
        self.workspace_list.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        self.refresh_workspace_lists()

    def _entry(self, parent, label: str, row: int, default: str = "") -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, text_color=COLORS["muted"]).grid(row=row, column=0, sticky="w", padx=22, pady=10)
        entry = ctk.CTkEntry(parent, height=34)
        entry.grid(row=row, column=1, sticky="ew", padx=(4, 22), pady=10)
        if default:
            entry.insert(0, default)
        return entry

    def _menu(self, parent, label: str, values: list[str], row: int) -> ctk.CTkComboBox:
        ctk.CTkLabel(parent, text=label, text_color=COLORS["muted"]).grid(row=row, column=0, sticky="w", padx=22, pady=10)
        menu = ctk.CTkComboBox(parent, values=values, height=34)
        menu.grid(row=row, column=1, sticky="ew", padx=(4, 22), pady=10)
        return menu

    def _on_minecraft_changed(self, value: str) -> None:
        versions = FABRIC_VERSIONS.get(value, ["Generator pending"])
        self.fabric_menu.configure(values=versions)
        self.fabric_menu.set(versions[0])

    def _generate(self) -> None:
        package_name = self.package_name_entry.get().strip() or self.mod_id_entry.get().strip()
        data = ProjectData(
            name=self.name_entry.get().strip(),
            minecraft_version=self.minecraft_menu.get(),
            fabric_version=self.fabric_menu.get(),
            author=self.author_entry.get().strip(),
            mod_id=self.mod_id_entry.get().strip(),
            package_root=self.package_root_entry.get().strip(),
            package_name=package_name,
            description=self.description_entry.get().strip() or "A Fabric mod generated by Fabric Studio.",
        )
        self.on_generate(data)

    def _open_folder(self) -> None:
        selected = filedialog.askdirectory(title="Open Fabric workspace", initialdir=self.workspaces_root)
        if selected:
            self.on_open_workspace(Path(selected))

    def refresh_workspace_lists(self) -> None:
        self._clear_panel(self.workspace_list)
        workspaces = self._combined_workspaces()
        if not workspaces:
            ctk.CTkLabel(self.workspace_list, text="No workspaces yet.", text_color=COLORS["muted"]).pack(anchor="w", padx=8, pady=8)
            self._configure_scrollbar()
            return

        for workspace in workspaces:
            self._workspace_row(self.workspace_list, workspace)
        self._configure_scrollbar()

    def remember_workspace(self, path: Path) -> None:
        entries = [item for item in self._load_recent() if item != str(path)]
        entries.insert(0, str(path))
        self._save_recent(entries[:12])
        self.refresh_workspace_lists()

    def _combined_workspaces(self) -> list[Path]:
        seen: set[str] = set()
        ordered: list[Path] = []

        for path in sorted([item for item in self.workspaces_root.iterdir() if item.is_dir()], key=lambda item: item.name.lower()):
            seen.add(str(path))
            ordered.append(path)

        for item in self._load_recent():
            if item in seen:
                continue
            path = Path(item)
            if path.exists():
                seen.add(item)
                ordered.append(path)

        return ordered

    def _workspace_row(self, parent, workspace: Path) -> None:
        row = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], corner_radius=6)
        row.pack(fill="x", padx=6, pady=4)
        row.grid_columnconfigure(0, weight=1)

        meta = self._read_workspace_meta(workspace)
        subtitle = meta.get("description") or str(workspace)

        ctk.CTkLabel(row, text=workspace.name, anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 0))
        ctk.CTkLabel(row, text=subtitle, anchor="w", text_color=COLORS["muted"]).grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        ctk.CTkButton(row, text="Open", width=70, command=lambda item=workspace: self.on_open_workspace(item)).grid(row=0, column=1, rowspan=2, padx=(8, 6), pady=8)
        ctk.CTkButton(row, text="Settings", width=78, command=lambda item=workspace: self._open_settings_editor(item)).grid(row=0, column=2, rowspan=2, padx=(0, 6), pady=8)
        if workspace.parent == self.workspaces_root:
            ctk.CTkButton(
                row,
                text="Delete",
                width=70,
                fg_color="#b33939",
                hover_color="#962c2c",
                command=lambda item=workspace: self._delete_workspace(item),
            ).grid(row=0, column=3, rowspan=2, padx=(0, 8), pady=8)

    def _open_settings_editor(self, workspace: Path) -> None:
        meta = self._read_workspace_meta(workspace)
        window = ctk.CTkToplevel(self)
        window.title(f"{workspace.name} Settings")
        window.geometry("460x320")
        window.transient(self)
        window.grid_columnconfigure(1, weight=1)

        fields: dict[str, ctk.CTkEntry] = {}
        field_specs = [
            ("name", "Name"),
            ("author", "Author"),
            ("description", "Description"),
            ("mod_id", "Mod ID"),
        ]
        for row, (key, label) in enumerate(field_specs):
            ctk.CTkLabel(window, text=label, text_color=COLORS["muted"]).grid(row=row, column=0, sticky="w", padx=18, pady=12)
            entry = ctk.CTkEntry(window, height=34)
            entry.grid(row=row, column=1, sticky="ew", padx=(0, 18), pady=12)
            entry.insert(0, str(meta.get(key, "")))
            fields[key] = entry

        def save_settings() -> None:
            meta.update({key: entry.get().strip() for key, entry in fields.items()})
            self._write_workspace_meta(workspace, meta)
            self.refresh_workspace_lists()
            window.destroy()

        ctk.CTkButton(window, text="Save Settings", command=save_settings).grid(row=len(field_specs), column=0, columnspan=2, sticky="ew", padx=18, pady=(10, 18))

    def _delete_workspace(self, workspace: Path) -> None:
        if workspace.parent != self.workspaces_root or not workspace.exists():
            return
        shutil.rmtree(workspace)
        self._save_recent([item for item in self._load_recent() if item != str(workspace)])
        self.refresh_workspace_lists()

    def _read_workspace_meta(self, workspace: Path) -> dict:
        info_path = workspace / "project_info.json"
        if not info_path.exists():
            return {"name": workspace.name, "description": str(workspace)}
        try:
            return json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"name": workspace.name, "description": str(workspace)}

    def _write_workspace_meta(self, workspace: Path, meta: dict) -> None:
        info_path = workspace / "project_info.json"
        info_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        mod_json_path = workspace / "src" / "main" / "resources" / "fabric.mod.json"
        if mod_json_path.exists():
            try:
                payload = json.loads(mod_json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}
            payload["name"] = meta.get("name", workspace.name)
            payload["description"] = meta.get("description", "")
            payload["authors"] = [meta.get("author", "Unknown")]
            mod_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _clear_panel(self, panel: ctk.CTkScrollableFrame) -> None:
        for widget in panel.winfo_children():
            widget.destroy()

    def _configure_scrollbar(self) -> None:
        self.update_idletasks()
        canvas = self.workspace_list._parent_canvas
        scrollbar = self.workspace_list._scrollbar
        needs_scroll = canvas.yview() != (0.0, 1.0)
        if needs_scroll:
            scrollbar.grid()
        else:
            scrollbar.grid_remove()

    def _load_recent(self) -> list[str]:
        if not self.recent_file.exists():
            return []
        try:
            data = json.loads(self.recent_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [item for item in data if isinstance(item, str)]

    def _save_recent(self, entries: list[str]) -> None:
        self.recent_file.write_text(json.dumps(entries, indent=2), encoding="utf-8")
