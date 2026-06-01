# generator_window.py
# developer: SuperHeroPuppy
# version: 1.1.0

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path

import customtkinter as ctk
from tkinter import BooleanVar, filedialog, messagebox

from core.data_store import COLORS
from ui.theme import themed_combo_box, themed_entry, theme_window
from ui.window_utils import show_on_top

try:
    from PIL import Image
except Exception:
    Image = None


class GeneratorWindow(ctk.CTkToplevel):
    def __init__(self, master, generators, workspace_path):
        super().__init__(master)

        self.title("Tool Generators")
        self.geometry("1060x720")
        self.minsize(920, 620)
        theme_window(self)
        show_on_top(self, master)

        self.workspace_path = Path(workspace_path)
        self.generators = generators
        self.generator_by_id = {generator.id: generator for generator in generators}
        self.project_info = self._load_project_info()
        self.mod_id = self._safe_name(
            self.project_info.get("mod_id", self.workspace_path.name.lower())
        )

        self.active_page = "create"
        self.active_tool = self._first_supported_tool()
        self.editing_record: dict | None = None
        self.draft_values: dict[str, dict] = {}
        self.asset_target: tuple[str, str] | None = None
        self.asset_images: list[ctk.CTkImage] = []
        self.asset_type_var = ctk.StringVar(value="item")
        self.custom_asset_dir: Path | None = None
        self.custom_asset_label: ctk.CTkLabel | None = None

        self.inputs: dict[tuple[str, str], object] = {}
        self.input_wrappers: dict[tuple[str, str], ctk.CTkFrame] = {}
        self.field_conditions: dict[tuple[str, str], dict] = {}

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="Generators",
            font=("Segoe UI", 22, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 6))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self._add_nav_button("create", "Create", 1)
        self._add_nav_button("generated", "Generated", 2)
        self._add_nav_button("assets", "Assets", 3)

        chip_panel = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        chip_panel.grid(row=4, column=0, sticky="nsew", padx=12, pady=(12, 12))
        chip_panel.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            chip_panel,
            text="Generated",
            text_color=COLORS["muted"],
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=6, pady=(0, 6))

        self.chips_frame = ctk.CTkScrollableFrame(
            chip_panel,
            fg_color="transparent",
            width=210,
        )
        self.chips_frame.grid(row=1, column=0, sticky="nsew")

        self.main = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 6))
        header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            header,
            text="Create Elements",
            font=("Segoe UI", 24, "bold"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew")

        self.status_label = ctk.CTkLabel(
            self.main,
            text="Pick a generator and fill in its form.",
            text_color=COLORS["muted"],
            anchor="w",
        )
        self.status_label.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 8))

        self.body = ctk.CTkFrame(self.main, fg_color="transparent")
        self.body.grid(row=2, column=0, sticky="nsew", padx=18, pady=8)
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

        self._refresh_chips()
        self._show_page("create")

    def _add_nav_button(self, page: str, label: str, row: int) -> None:
        button = ctk.CTkButton(
            self.sidebar,
            text=label,
            width=200,
            anchor="w",
            command=lambda target=page: self._show_page(target),
        )
        button.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        self.nav_buttons[page] = button

    def _show_page(self, page: str) -> None:
        if self.active_page == "create":
            self._save_active_draft()
        self.active_page = page
        self._clear_body()

        for name, button in self.nav_buttons.items():
            button.configure(
                fg_color=COLORS["accent"] if name == page else COLORS["panel_alt"]
            )

        if page == "create":
            self.title_label.configure(text="Create Elements")
            self.status_label.configure(text="Pick a generator and fill in its form.")
            self._build_create_page()
            return

        if page == "generated":
            self.title_label.configure(text="Generated Elements")
            self.status_label.configure(text="Edit or delete generated entries.")
            self._build_generated_page()
            return

        self.title_label.configure(text="Assets")
        self.status_label.configure(
            text="Choose, import, or inspect PNG textures from this workspace."
        )
        self._build_assets_page()

    def _build_create_page(self) -> None:
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_rowconfigure(1, weight=0)
        self.body.grid_columnconfigure(0, weight=0)
        self.body.grid_columnconfigure(1, weight=1)

        tool_list = ctk.CTkScrollableFrame(self.body, fg_color="transparent", width=260)
        tool_list.grid(row=0, column=0, sticky="nsew", padx=(0, 12))

        form_panel = ctk.CTkFrame(self.body, fg_color=COLORS["panel"])
        form_panel.grid(row=0, column=1, sticky="nsew")
        form_panel.grid_columnconfigure(0, weight=1)
        form_panel.grid_rowconfigure(1, weight=1)

        for generator in self.generators:
            self._build_tool_card(tool_list, generator)

        if self.active_tool is None:
            ctk.CTkLabel(
                form_panel,
                text="No supported generators are available.",
                text_color=COLORS["muted"],
            ).grid(row=0, column=0, sticky="w", padx=16, pady=16)
            return

        self._build_form(form_panel, self.active_tool)

    def _build_tool_card(self, parent, generator) -> None:
        selected = self.active_tool is not None and generator.id == self.active_tool.id
        frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["panel_alt"] if selected else COLORS["panel"],
            border_width=1 if selected else 0,
            border_color=COLORS["accent"],
        )
        frame.pack(fill="x", pady=6)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text=generator.name,
            font=("Segoe UI", 15, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))

        ctk.CTkLabel(
            frame,
            text=generator.description or "No description.",
            text_color=COLORS["muted"] if generator.supported else "#777777",
            wraplength=210,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 10))

        button_text = "Configure" if generator.supported else "Coming Soon"
        ctk.CTkButton(
            frame,
            text=button_text,
            state="normal" if generator.supported else "disabled",
            command=lambda tool=generator: self._select_tool(tool),
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _build_form(self, parent, tool) -> None:
        self.inputs.clear()
        self.input_wrappers.clear()
        self.field_conditions.clear()

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)

        title = f"Edit {tool.name}" if self.editing_record else f"New {tool.name}"
        ctk.CTkLabel(
            header,
            text=title,
            font=("Segoe UI", 20, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        if self.editing_record:
            ctk.CTkButton(
                header,
                text="Cancel Edit",
                width=100,
                fg_color=COLORS["panel_alt"],
                command=self._cancel_edit,
            ).grid(row=0, column=1, padx=(8, 0))

        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

        if not tool.supported:
            ctk.CTkLabel(
                scroll,
                text="Not supported in this version.",
                text_color="#777777",
            ).pack(anchor="w", padx=8, pady=8)
            return

        for field in tool.manifest.get("forms", []):
            self._build_field(scroll, tool.id, field)

        self._update_field_visibility()

        footer = ctk.CTkFrame(parent, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)

        action = "Save Changes" if self.editing_record else f"Generate {tool.name}"
        self.generate_button = ctk.CTkButton(
            footer,
            text=action,
            width=150,
            command=self._generate_active_tool,
        )
        self.generate_button.grid(row=0, column=1, sticky="e")

    def _build_field(self, parent, tool_id: str, field: dict) -> None:
        field_id = field["id"]
        field_type = field["type"]
        key = (tool_id, field_id)

        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", padx=8, pady=7)
        self.input_wrappers[key] = wrapper

        condition = field.get("visible_if")
        if isinstance(condition, dict):
            self.field_conditions[key] = condition

        if field_type != "boolean":
            ctk.CTkLabel(wrapper, text=field.get("label", field_id)).pack(
                anchor="w",
                pady=(0, 4),
            )

        if field_type == "string":
            entry = themed_entry(wrapper, placeholder_text=field.get("placeholder", ""))
            initial_value = self._initial_value(tool_id, field_id)
            if initial_value is not None:
                entry.insert(0, str(initial_value))
            entry.pack(fill="x")
            self.inputs[key] = entry

        elif field_type == "boolean":
            var = BooleanVar(value=bool(field.get("default", False)))
            initial_value = self._initial_value(tool_id, field_id)
            if initial_value is not None:
                var.set(self._as_bool(initial_value))
            ctk.CTkCheckBox(
                wrapper,
                text=field.get("label", field_id),
                variable=var,
                command=self._update_field_visibility,
            ).pack(anchor="w")
            self.inputs[key] = var

        elif field_type == "select":
            values = [str(value) for value in field.get("values", [])]
            initial_value = self._initial_value(tool_id, field_id)
            selected = str(
                initial_value
                if initial_value is not None
                else field.get("default", values[0] if values else "")
            )
            entry = themed_combo_box(
                wrapper,
                values=values,
                command=lambda _value: self._update_field_visibility(),
            )
            entry.set(selected)
            entry.pack(fill="x")
            self.inputs[key] = entry

        elif field_type == "number":
            entry = themed_entry(wrapper)
            initial_value = self._initial_value(tool_id, field_id)
            entry.insert(
                0,
                str(initial_value if initial_value is not None else field.get("default", 0)),
            )
            entry.pack(fill="x")
            self.inputs[key] = entry

        elif field_type == "array":
            textbox = ctk.CTkTextbox(wrapper, height=90)
            initial_value = self._initial_value(tool_id, field_id)
            if isinstance(initial_value, list):
                textbox.insert("1.0", "\n".join(str(item) for item in initial_value))
            elif initial_value is not None:
                textbox.insert("1.0", str(initial_value))
            textbox.pack(fill="x")
            self.inputs[key] = textbox

        elif field_type == "texture":
            frame = ctk.CTkFrame(wrapper, fg_color="transparent")
            frame.pack(fill="x")
            frame.grid_columnconfigure(0, weight=1)

            var = ctk.StringVar()
            initial_value = self._initial_value(tool_id, field_id)
            if initial_value is not None:
                var.set(str(initial_value))

            themed_entry(frame, textvariable=var).grid(row=0, column=0, sticky="ew")
            ctk.CTkButton(
                frame,
                text="Assets",
                width=90,
                command=lambda tid=tool_id, fid=field_id: self._open_assets_for_field(
                    tid,
                    fid,
                ),
            ).grid(row=0, column=1, padx=(8, 0))
            self.inputs[key] = var

        else:
            ctk.CTkLabel(
                wrapper,
                text=f"Unsupported field type: {field_type}",
                text_color="#777777",
            ).pack(anchor="w")

    def _build_generated_page(self) -> None:
        self.body.grid_rowconfigure(0, weight=1)
        self.body.grid_rowconfigure(1, weight=0)
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_columnconfigure(1, weight=0)
        records = self._generated_records()

        if not records:
            ctk.CTkLabel(
                self.body,
                text="No generated elements yet.",
                text_color=COLORS["muted"],
            ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        scroll = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        for index, record in enumerate(records):
            self._build_generated_card(scroll, record, index)

    def _build_generated_card(self, parent, record: dict, row: int) -> None:
        tool = self._tool_for_record(record)
        title = record.get("display_name") or record.get("id") or "Generated element"
        category = record.get("type") or record.get("tool_id") or "unknown"
        file_count = len(record.get("files", []))

        frame = ctk.CTkFrame(parent, fg_color=COLORS["panel"])
        frame.grid(row=row, column=0, sticky="ew", pady=6)
        frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame,
            text=str(title),
            font=("Segoe UI", 16, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))

        ctk.CTkLabel(
            frame,
            text=f"{category} / {record.get('id', 'unknown')} / {file_count} files",
            text_color=COLORS["muted"],
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 12))

        if tool and tool.supported:
            ctk.CTkButton(
                frame,
                text="Edit",
                width=76,
                command=lambda item=record, spec=tool: self._edit_generated(item, spec),
            ).grid(row=0, column=1, rowspan=2, padx=(0, 8), pady=12)
        else:
            ctk.CTkLabel(
                frame,
                text="Generator unavailable",
                text_color="#777777",
            ).grid(row=0, column=1, rowspan=2, padx=(0, 8), pady=12)

        ctk.CTkButton(
            frame,
            text="Delete",
            width=76,
            fg_color="#b91c1c",
            hover_color="#991b1b",
            command=lambda item=record: self._delete_generated(item),
        ).grid(row=0, column=2, rowspan=2, padx=(0, 14), pady=12)

    def _build_assets_page(self) -> None:
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_columnconfigure(1, weight=0)
        self.body.grid_rowconfigure(0, weight=0)
        self.body.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(self.body, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.grid_columnconfigure(0, weight=1)

        target_text = ""
        if self.asset_target:
            target_text = "Select a texture for the active form."
        ctk.CTkLabel(
            toolbar,
            text=target_text,
            text_color=COLORS["muted"],
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        import_bar = ctk.CTkFrame(toolbar, fg_color="transparent")
        import_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        import_bar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            import_bar,
            text="Import To",
            text_color=COLORS["muted"],
        ).grid(row=0, column=0, padx=(0, 8))

        asset_type = themed_combo_box(
            import_bar,
            values=["item", "block", "custom"],
            variable=self.asset_type_var,
            width=120,
            command=lambda _value: self._update_custom_asset_controls(),
        )
        asset_type.grid(row=0, column=1, padx=(0, 8))

        self.custom_asset_label = ctk.CTkLabel(
            import_bar,
            text=self._custom_asset_text(),
            text_color=COLORS["muted"],
            anchor="w",
        )
        self.custom_asset_label.grid(row=0, column=2, sticky="ew", padx=(0, 8))

        self.custom_asset_button = ctk.CTkButton(
            import_bar,
            text="Choose Folder",
            width=118,
            command=self._choose_custom_asset_dir,
        )
        self.custom_asset_button.grid(row=0, column=3, padx=(0, 8))

        ctk.CTkButton(
            import_bar,
            text="Import PNG",
            width=110,
            command=self._import_asset,
        ).grid(row=0, column=4)

        self._update_custom_asset_controls()

        scroll = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew")

        assets = self._asset_records()
        if not assets:
            ctk.CTkLabel(
                scroll,
                text="No PNG textures found under src/main/resources/assets.",
                text_color=COLORS["muted"],
            ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        self.asset_images.clear()
        columns = 3
        for column in range(columns):
            scroll.grid_columnconfigure(column, weight=1)

        for index, asset in enumerate(assets):
            self._build_asset_card(
                scroll,
                asset,
                row=index // columns,
                column=index % columns,
            )

    def _build_asset_card(self, parent, asset: dict, row: int, column: int) -> None:
        frame = ctk.CTkFrame(parent, fg_color=COLORS["panel"])
        frame.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
        frame.grid_columnconfigure(0, weight=1)

        image_label = None
        if Image is not None:
            try:
                image = Image.open(asset["path"])
                ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(64, 64))
                self.asset_images.append(ctk_image)
                image_label = ctk.CTkLabel(frame, image=ctk_image, text="")
            except Exception:
                image_label = None

        if image_label is None:
            image_label = ctk.CTkLabel(frame, text="PNG", text_color=COLORS["muted"])

        image_label.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))

        ctk.CTkLabel(
            frame,
            text=asset["identifier"],
            font=("Segoe UI", 13, "bold"),
            wraplength=210,
        ).grid(row=1, column=0, sticky="ew", padx=12)

        ctk.CTkLabel(
            frame,
            text=str(asset["path"].relative_to(self.workspace_path)),
            text_color=COLORS["muted"],
            wraplength=210,
        ).grid(row=2, column=0, sticky="ew", padx=12, pady=(2, 8))

        ctk.CTkButton(
            frame,
            text="Select",
            command=lambda item=asset: self._select_asset(item),
        ).grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _refresh_chips(self) -> None:
        for widget in self.chips_frame.winfo_children():
            widget.destroy()

        records = self._generated_records()
        if not records:
            ctk.CTkLabel(
                self.chips_frame,
                text="No chips yet.",
                text_color=COLORS["muted"],
                anchor="w",
            ).pack(fill="x", padx=6, pady=4)
            return

        for record in records:
            tool = self._tool_for_record(record)
            chip = ctk.CTkFrame(self.chips_frame, fg_color=COLORS["panel_alt"], corner_radius=12)
            chip.pack(fill="x", pady=4)
            chip.grid_columnconfigure(0, weight=1)

            title = record.get("display_name") or record.get("id") or "Generated"
            ctk.CTkLabel(
                chip,
                text=str(title),
                anchor="w",
                font=("Segoe UI", 12, "bold"),
            ).grid(row=0, column=0, sticky="ew", padx=(10, 4), pady=(7, 0))

            ctk.CTkLabel(
                chip,
                text=str(record.get("type") or "unknown"),
                text_color=COLORS["muted"],
                anchor="w",
            ).grid(row=1, column=0, sticky="ew", padx=(10, 4), pady=(0, 7))

            if tool and tool.supported:
                ctk.CTkButton(
                    chip,
                    text="Edit",
                    width=42,
                    height=24,
                    command=lambda item=record, spec=tool: self._edit_generated(item, spec),
                ).grid(row=0, column=1, rowspan=2, padx=(0, 4), pady=8)

            ctk.CTkButton(
                chip,
                text="x",
                width=28,
                height=24,
                fg_color="#b91c1c",
                hover_color="#991b1b",
                command=lambda item=record: self._delete_generated(item),
            ).grid(row=0, column=2, rowspan=2, padx=(0, 8), pady=8)

    def _select_tool(self, tool) -> None:
        self._save_active_draft()
        self.active_tool = tool
        self.editing_record = None
        self.asset_target = None
        self._show_page("create")

    def _edit_generated(self, record: dict, tool) -> None:
        self.active_tool = tool
        self.editing_record = record
        self.draft_values[tool.id] = self._form_data_for_record(record, tool)
        self.asset_target = None
        self._show_page("create")
        self.status_label.configure(text=f"Editing {record.get('display_name') or record.get('id')}.")

    def _cancel_edit(self) -> None:
        self.editing_record = None
        if self.active_tool:
            self.draft_values.pop(self.active_tool.id, None)
        self._show_page("create")

    def _open_assets_for_field(self, tool_id: str, field_id: str) -> None:
        self.asset_target = (tool_id, field_id)
        self._show_page("assets")
        self.status_label.configure(text="Select a PNG texture for the active form.")

    def _select_asset(self, asset: dict) -> None:
        if not self.asset_target:
            self.status_label.configure(text=f"Selected asset: {asset['identifier']}")
            return

        tool_id, field_id = self.asset_target
        values = self.draft_values.setdefault(tool_id, {})
        values[field_id] = asset["identifier"]
        self.asset_target = None
        self._show_page("create")
        self.status_label.configure(text=f"Texture set to {asset['identifier']}.")

    def _import_asset(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PNG Files", "*.png")])
        if not path:
            return

        source = Path(path)
        target_dir = self._target_asset_dir()
        if target_dir is None:
            self.status_label.configure(text="Choose a custom asset folder first.")
            return

        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / source.name

        if target.exists() and not messagebox.askyesno(
            "Replace Texture",
            f"{target.name} already exists. Replace it?",
            parent=self,
        ):
            return

        try:
            shutil.copy2(source, target)
        except OSError as exc:
            self.status_label.configure(text=f"Import failed: {exc}")
            return

        self._show_page("assets")
        self.status_label.configure(text=f"Imported {target.name}.")

    def _target_asset_dir(self) -> Path | None:
        assets_root = self._assets_root()
        target_type = self.asset_type_var.get()

        if target_type == "custom":
            if self.custom_asset_dir is None:
                return None
            return self.custom_asset_dir

        return assets_root / self.mod_id / "textures" / target_type

    def _choose_custom_asset_dir(self) -> None:
        textures_root = self._assets_root() / self.mod_id / "textures"
        textures_root.mkdir(parents=True, exist_ok=True)

        selected = filedialog.askdirectory(
            title="Choose texture folder",
            initialdir=textures_root,
        )
        if not selected:
            return

        selected_path = Path(selected)
        try:
            selected_path.relative_to(self._assets_root())
        except ValueError:
            self.status_label.configure(text="Custom asset folders must be inside workspace assets.")
            return

        self.custom_asset_dir = selected_path
        self.asset_type_var.set("custom")
        self._update_custom_asset_controls()
        self.status_label.configure(text=f"Custom import folder set to {selected_path.name}.")

    def _update_custom_asset_controls(self) -> None:
        is_custom = self.asset_type_var.get() == "custom"
        if hasattr(self, "custom_asset_button"):
            self.custom_asset_button.configure(state="normal" if is_custom else "disabled")
        if self.custom_asset_label is not None:
            self.custom_asset_label.configure(
                text=self._custom_asset_text() if is_custom else self._default_asset_text()
            )

    def _custom_asset_text(self) -> str:
        if self.custom_asset_dir is None:
            return "No custom folder selected"
        try:
            return str(self.custom_asset_dir.relative_to(self.workspace_path))
        except ValueError:
            return str(self.custom_asset_dir)

    def _default_asset_text(self) -> str:
        target = self._target_asset_dir()
        if target is None:
            return ""
        try:
            return str(target.relative_to(self.workspace_path))
        except ValueError:
            return str(target)

    def _generate_active_tool(self) -> None:
        if self.active_tool is None:
            return

        payload = self._collect_form_data(visible_only=True)
        registry_name = str(payload.get("registry_name", "")).strip()
        if not registry_name:
            self.status_label.configure(text="Registry Name is required.")
            return

        module = self._load_generator_module(self.active_tool)
        if module is None:
            self.status_label.configure(text=f"Could not load {self.active_tool.name} generator.")
            return

        old_record = self.editing_record
        old_id = str(old_record.get("id", "")) if old_record else ""
        new_id = self._safe_name(registry_name)

        if old_record and old_id and old_id != new_id:
            self._delete_record_files(old_record, confirm=False)

        generate_fn = getattr(module, "generate", None)
        if not callable(generate_fn):
            self.status_label.configure(text=f"{self.active_tool.name} is missing generate().")
            return

        try:
            generate_fn(payload, self.workspace_path, self.active_tool)
        except Exception as exc:
            self.status_label.configure(text=f"Generation failed: {exc}")
            return

        self.editing_record = None
        self.draft_values.pop(self.active_tool.id, None)
        self._refresh_chips()
        self._show_page("generated")
        self.status_label.configure(
            text=f"{self.active_tool.name} {'updated' if old_record else 'generated'}."
        )

    def _delete_generated(self, record: dict) -> None:
        title = record.get("display_name") or record.get("id") or "this generated entry"
        if not messagebox.askyesno(
            "Delete Generated Entry",
            f"Delete {title} and its generated files?",
            parent=self,
        ):
            return

        self._delete_record_files(record, confirm=False)
        if self.editing_record is record:
            self.editing_record = None
        self._refresh_chips()
        self._show_page(self.active_page)
        self.status_label.configure(text=f"Deleted {title}.")

    def _delete_record_files(self, record: dict, confirm: bool = False) -> None:
        tool = self._tool_for_record(record)
        if tool:
            module = self._load_generator_module(tool)
            delete_fn = getattr(module, "delete", None) if module else None
            if callable(delete_fn):
                delete_fn(record, self.workspace_path, tool)
                return

        info_path = record.get("_info_path")
        if isinstance(info_path, Path) and info_path.exists():
            shutil.rmtree(info_path.parent, ignore_errors=True)

    def _save_active_draft(self) -> None:
        if not self.active_tool or not self.inputs:
            return
        self.draft_values[self.active_tool.id] = self._collect_form_data(visible_only=False)

    def _collect_form_data(self, visible_only: bool) -> dict:
        payload: dict = {}

        for (tool_id, field_id), widget in self.inputs.items():
            if self.active_tool and tool_id != self.active_tool.id:
                continue

            wrapper = self.input_wrappers.get((tool_id, field_id))
            if visible_only and wrapper is not None and not wrapper.winfo_ismapped():
                continue

            if isinstance(widget, BooleanVar):
                value = widget.get()
            elif isinstance(widget, ctk.StringVar):
                value = widget.get()
            elif isinstance(widget, ctk.CTkTextbox):
                value = [
                    line.strip()
                    for line in widget.get("1.0", "end").splitlines()
                    if line.strip()
                ]
            else:
                value = widget.get()

            payload[field_id] = value

        return payload

    def _update_field_visibility(self) -> None:
        for key, condition in self.field_conditions.items():
            wrapper = self.input_wrappers.get(key)
            if wrapper is None:
                continue

            if self._condition_met(key[0], condition):
                if not wrapper.winfo_ismapped():
                    wrapper.pack(fill="x", padx=8, pady=7)
            else:
                wrapper.pack_forget()

    def _condition_met(self, tool_id: str, condition: dict) -> bool:
        field_id = condition.get("field")
        expected = condition.get("equals", True)
        if not field_id:
            return True

        widget = self.inputs.get((tool_id, str(field_id)))
        if widget is None:
            return False

        value = widget.get()
        return value == expected

    def _initial_value(self, tool_id: str, field_id: str):
        return self.draft_values.get(tool_id, {}).get(field_id)

    def _generated_records(self) -> list[dict]:
        generated_root = self.workspace_path / "generated"
        if not generated_root.exists():
            return []

        records: list[dict] = []
        for info_path in sorted(generated_root.glob("*/*/generated_info.json")):
            try:
                payload = json.loads(info_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            if isinstance(payload, dict):
                payload["_info_path"] = info_path
                records.append(payload)

        return sorted(
            records,
            key=lambda item: (
                str(item.get("type", "")),
                str(item.get("id", "")),
            ),
        )

    def _asset_records(self) -> list[dict]:
        assets_root = self._assets_root()
        if not assets_root.exists():
            return []

        assets: list[dict] = []
        for path in sorted(assets_root.glob("*/textures/**/*.png")):
            try:
                rel = path.relative_to(assets_root)
            except ValueError:
                continue

            parts = rel.parts
            if len(parts) < 4 or parts[1] != "textures":
                continue

            namespace = parts[0]
            texture_type = parts[2]
            name_parts = list(parts[3:])
            name_parts[-1] = Path(name_parts[-1]).stem
            texture_name = "/".join(name_parts)

            assets.append(
                {
                    "path": path,
                    "identifier": f"{namespace}:{texture_type}/{texture_name}",
                }
            )

        return assets

    def _assets_root(self) -> Path:
        return self.workspace_path / "src" / "main" / "resources" / "assets"

    def _tool_for_record(self, record: dict):
        generator = record.get("generator", {})
        tool_id = generator.get("id") if isinstance(generator, dict) else None
        tool_id = tool_id or record.get("tool_id") or record.get("type")
        return self.generator_by_id.get(str(tool_id))

    def _form_data_for_record(self, record: dict, tool) -> dict:
        form_data = record.get("form_data")
        if isinstance(form_data, dict):
            return dict(form_data)

        values = {}
        for field in tool.manifest.get("forms", []):
            field_id = field.get("id")
            if not field_id:
                continue
            if field_id in record:
                values[field_id] = record[field_id]
            elif field_id == "registry_name":
                values[field_id] = record.get("id", "")
            elif field_id == "display_name":
                values[field_id] = record.get("display_name", "")
            elif field_id == "texture":
                values[field_id] = record.get("texture", "")
        return values

    def _load_generator_module(self, tool):
        generator_file = tool.root / "generator.py"
        if not generator_file.exists():
            return None

        spec = importlib.util.spec_from_file_location(
            f"gen_{tool.id}_{id(tool)}",
            generator_file,
        )
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _first_supported_tool(self):
        for generator in self.generators:
            if generator.supported:
                return generator
        return None

    def _load_project_info(self) -> dict:
        path = self.workspace_path / "project_info.json"
        if not path.exists():
            return {}

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        return payload if isinstance(payload, dict) else {}

    def _clear_body(self) -> None:
        for widget in self.body.winfo_children():
            widget.destroy()

    def _as_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _safe_name(self, name: str) -> str:
        cleaned = re.sub(r"[^a-z0-9_]+", "_", str(name).strip().lower())
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned or "unnamed_item"
