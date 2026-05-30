# generator_config_window.py
# developer: SuperHeroPuppy
# version: 1.0.3

from __future__ import annotations

from pathlib import Path
import importlib.util
from collections.abc import Callable

import customtkinter as ctk
from tkinter import BooleanVar, filedialog

from core.data_store import COLORS
from ui.theme import themed_combo_box, themed_entry, theme_window
from ui.window_utils import show_on_top


class GeneratorConfigWindow(ctk.CTkToplevel):

    def __init__(
        self,
        master,
        tools,
        workspace_path: Path,
        initial_values: dict[str, dict] | None = None,
        on_complete: Callable[[], None] | None = None,
    ):
        super().__init__(master)

        self.tools = tools
        self.workspace_path = workspace_path
        self.initial_values = initial_values or {}
        self.on_complete = on_complete

        self.title("Configure Generators")
        self.geometry("700x600")
        theme_window(self)
        show_on_top(self, master)

        # (tool_id, field_id) -> widget/var
        self.inputs: dict[tuple[str, str], object] = {}
        self.input_wrappers: dict[tuple[str, str], ctk.CTkFrame] = {}
        self.field_conditions: dict[tuple[str, str], dict] = {}

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=14, pady=14)

        self.build_forms()

        self.generate_button = ctk.CTkButton(
            self,
            text="Generate",
            command=self.generate,
        )
        self.generate_button.pack(pady=(0, 14))


    def build_forms(self):

        for tool in self.tools:

            forms = tool.manifest.get("forms", [])

            section = ctk.CTkFrame(self.scroll, fg_color=COLORS["panel"])
            section.pack(fill="x", pady=(0, 12))

            ctk.CTkLabel(
                section,
                text=tool.name,
                font=("Segoe UI", 18, "bold"),
            ).pack(anchor="w", padx=14, pady=(12, 6))

            if not tool.supported:
                ctk.CTkLabel(
                    section,
                    text="Not supported in this version",
                    text_color="#777777",
                ).pack(anchor="w", padx=14, pady=(0, 10))
                continue

            for field in forms:
                self.build_field(section, tool.id, field)

        self._update_field_visibility()

    def build_field(self, parent, tool_id: str, field: dict):

        field_id = field["id"]
        field_type = field["type"]

        key = (tool_id, field_id)

        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.pack(fill="x", padx=14, pady=6)
        self.input_wrappers[key] = wrapper

        condition = field.get("visible_if")
        if isinstance(condition, dict):
            self.field_conditions[key] = condition

        if field_type != "boolean":
            ctk.CTkLabel(wrapper, text=field.get("label", field_id)).pack(
                anchor="w",
                pady=(0, 4),
            )

        # STRING
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

            checkbox = ctk.CTkCheckBox(
                wrapper,
                text=field.get("label", field_id),
                variable=var,
                command=self._update_field_visibility,
            )
            checkbox.pack(anchor="w")
            self.inputs[key] = var

            return

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

        # NUMBER
        elif field_type == "number":

            entry = themed_entry(wrapper)
            initial_value = self._initial_value(tool_id, field_id)
            entry.insert(
                0,
                str(initial_value if initial_value is not None else field.get("default", 0)),
            )
            entry.pack(fill="x")
            self.inputs[key] = entry

        # ARRAY
        elif field_type == "array":

            textbox = ctk.CTkTextbox(wrapper, height=90)
            initial_value = self._initial_value(tool_id, field_id)
            if isinstance(initial_value, list):
                textbox.insert("1.0", "\n".join(str(item) for item in initial_value))
            elif initial_value is not None:
                textbox.insert("1.0", str(initial_value))
            textbox.pack(fill="x")
            self.inputs[key] = textbox

        # TEXTURE
        elif field_type == "texture":

            frame = ctk.CTkFrame(wrapper, fg_color="transparent")
            frame.pack(fill="x")

            var = ctk.StringVar()
            initial_value = self._initial_value(tool_id, field_id)
            if initial_value is not None:
                var.set(str(initial_value))

            entry = themed_entry(frame, textvariable=var)
            entry.pack(side="left", fill="x", expand=True)

            def browse():
                assets_root = self.workspace_path / "src" / "main" / "resources" / "assets"

                path = filedialog.askopenfilename(
                    initialdir=assets_root,
                    filetypes=[("PNG Files", "*.png")],
                )

                if not path:
                    return

                try:
                    rel = Path(path).relative_to(assets_root)
                except ValueError:
                    print("[ERROR] Texture must be inside workspace assets folder.")
                    return

                parts = rel.parts

                # expected: modid/textures/item/filename.png
                if len(parts) < 4:
                    print("[ERROR] Invalid texture path structure.")
                    return

                modid = parts[0]
                tex_type = parts[2]  # item or block
                file_name = Path(parts[-1]).stem

                minecraft_style = f"{modid}:{tex_type}/{file_name}"
                var.set(minecraft_style)

            ctk.CTkButton(
                frame,
                text="Browse",
                width=90,
                command=browse,
            ).pack(side="left", padx=(8, 0))

            self.inputs[key] = var

        else:
            ctk.CTkLabel(
                wrapper,
                text=f"Unsupported field type: {field_type}",
                text_color="#777777",
            ).pack(anchor="w")

    def _initial_value(self, tool_id: str, field_id: str):

        return self.initial_values.get(tool_id, {}).get(field_id)

    def _update_field_visibility(self) -> None:

        for key, condition in self.field_conditions.items():

            wrapper = self.input_wrappers.get(key)

            if wrapper is None:
                continue

            if self._condition_met(key[0], condition):

                if not wrapper.winfo_ismapped():
                    wrapper.pack(fill="x", padx=14, pady=6)

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

        if isinstance(widget, BooleanVar):
            value = widget.get()
        else:
            value = widget.get()

        return value == expected

    def _as_bool(self, value) -> bool:

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}

        return bool(value)

    def generate(self):

        workspace_root = self.workspace_path
        if not workspace_root:
            print("No workspace selected.")
            return

        # build payload
        payload: dict[str, dict] = {}

        for (tool_id, field_id), widget in self.inputs.items():

            wrapper = self.input_wrappers.get((tool_id, field_id))

            if wrapper is not None and not wrapper.winfo_ismapped():
                continue

            payload.setdefault(tool_id, {})

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

            payload[tool_id][field_id] = value

        # run each tool generator
        generated_any = False

        for tool in self.tools:

            if not tool.supported:
                continue

            tool_id = tool.id

            if tool_id not in payload:
                continue

            generator_file = tool.root / "generator.py"

            if not generator_file.exists():
                print(f"[ERROR] Missing generator.py for {tool_id}")
                continue

            spec = importlib.util.spec_from_file_location(
                f"gen_{tool_id}",
                generator_file,
            )

            if not spec or not spec.loader:
                print(f"[ERROR] Failed to load {tool_id}")
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            generate_fn = getattr(module, "generate", None)

            if not callable(generate_fn):
                print(f"[ERROR] {tool_id} missing generate()")
                continue

            try:
                generate_fn(
                    payload[tool_id],
                    workspace_root,
                    tool,
                )
                generated_any = True
                print(f"[OK] Generated {tool_id}")

            except Exception as e:
                print(f"[ERROR] {tool_id}: {e}")

        if generated_any:

            if self.on_complete:
                self.on_complete()

            self.destroy()
