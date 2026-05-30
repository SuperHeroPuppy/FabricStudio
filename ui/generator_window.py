# generator_window.py
# developer: SuperHeroPuppy
# version: 1.0.2

from __future__ import annotations

import json

import customtkinter as ctk

from core.data_store import COLORS
from ui.theme import theme_window
from ui.generator_config_window import GeneratorConfigWindow
from ui.window_utils import show_on_top


class GeneratorWindow(ctk.CTkToplevel):

    def __init__(self, master, generators, workspace_path):
        super().__init__(master)

        self.title("Tool Generators")
        self.geometry("720x520")
        theme_window(self)
        show_on_top(self, master)

        self.workspace_path = workspace_path
        self.generators = generators
        self.generator_by_id = {
            generator.id: generator
            for generator in generators
        }
        self.active_page = "create"

        self.selected: dict[str, ctk.BooleanVar] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            header,
            text="Tool Generators",
            font=("Segoe UI", 22, "bold"),
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 8))

        self.create_button = ctk.CTkButton(
            nav,
            text="Create New",
            width=120,
            command=lambda: self._show_page("create"),
        )
        self.create_button.pack(side="left")

        self.generated_button = ctk.CTkButton(
            nav,
            text="Generated",
            width=120,
            fg_color=COLORS["panel_alt"],
            hover_color=COLORS["accent"],
            command=lambda: self._show_page("generated"),
        )
        self.generated_button.pack(side="left", padx=(8, 0))

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=16, pady=8)

        self.continue_button = ctk.CTkButton(
            self,
            text="Continue",
            state="disabled",
            command=self._continue,
        )
        self.continue_button.grid(row=3, column=0, sticky="e", padx=20, pady=16)

        self._show_page("create")

    def _show_page(self, page: str) -> None:

        self.active_page = page
        self._clear_scroll()

        if page == "create":
            self.title_label.configure(text="Create Elements")
            self.create_button.configure(fg_color=COLORS["accent"])
            self.generated_button.configure(fg_color=COLORS["panel_alt"])
            self.continue_button.grid()
            self._build_create_page()
            self._update_continue()
            return

        self.title_label.configure(text="Generated Elements")
        self.create_button.configure(fg_color=COLORS["panel_alt"])
        self.generated_button.configure(fg_color=COLORS["accent"])
        self.continue_button.grid_remove()
        self._build_generated_page()

    def _build_create_page(self):

        self.selected.clear()

        for generator in self.generators:

            frame = ctk.CTkFrame(self.scroll, fg_color=COLORS["panel"])
            frame.pack(fill="x", pady=6)

            var = ctk.BooleanVar(value=False)

            checkbox = ctk.CTkCheckBox(
                frame,
                text=generator.name,
                variable=var,
                state="normal" if generator.supported else "disabled",
                command=self._update_continue,
            )
            checkbox.pack(anchor="w", padx=14, pady=(12, 2))

            ctk.CTkLabel(
                frame,
                text=generator.description,
                text_color=COLORS["muted"] if generator.supported else "#777777",
                wraplength=580,
                justify="left",
            ).pack(anchor="w", padx=38, pady=(0, 12))

            if not generator.supported:
                ctk.CTkLabel(
                    frame,
                    text="Coming Soon",
                    text_color="#777777",
                ).pack(anchor="e", padx=12, pady=(0, 10))

            self.selected[generator.id] = var

    def _build_generated_page(self):

        records = self._generated_records()

        if not records:
            ctk.CTkLabel(
                self.scroll,
                text="No generated elements yet.",
                text_color=COLORS["muted"],
            ).pack(anchor="w", padx=8, pady=8)
            return

        for record in records:

            tool = self._tool_for_record(record)
            title = record.get("display_name") or record.get("id") or "Generated element"
            category = record.get("type") or record.get("tool_id") or "unknown"
            file_count = len(record.get("files", []))

            frame = ctk.CTkFrame(self.scroll, fg_color=COLORS["panel"])
            frame.pack(fill="x", pady=6)
            frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                frame,
                text=str(title),
                font=("Segoe UI", 16, "bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))

            ctk.CTkLabel(
                frame,
                text=f"{category} - {record.get('id', 'unknown')} - {file_count} files",
                text_color=COLORS["muted"],
                anchor="w",
            ).grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 12))

            if tool and tool.supported:
                ctk.CTkButton(
                    frame,
                    text="Edit",
                    width=90,
                    command=lambda item=record, spec=tool: self._edit_generated(item, spec),
                ).grid(row=0, column=1, rowspan=2, padx=14, pady=12)
            else:
                ctk.CTkLabel(
                    frame,
                    text="Generator unavailable",
                    text_color="#777777",
                ).grid(row=0, column=1, rowspan=2, padx=14, pady=12)

    def _update_continue(self):

        self.continue_button.configure(
            state=(
                "normal"
                if any(v.get() for v in self.selected.values())
                else "disabled"
            )
        )

    def _continue(self):

        selected_ids = [
            gid for gid, var in self.selected.items() if var.get()
        ]

        selected_generators = [
            g for g in self.generators if g.id in selected_ids
        ]

        GeneratorConfigWindow(
            master=self,
            tools=selected_generators,
            workspace_path=self.workspace_path,
            on_complete=self._refresh_generated_page,
        )

    def _edit_generated(self, record: dict, tool) -> None:

        GeneratorConfigWindow(
            master=self,
            tools=[tool],
            workspace_path=self.workspace_path,
            initial_values={
                tool.id: self._form_data_for_record(record, tool)
            },
            on_complete=self._refresh_generated_page,
        )

    def _refresh_generated_page(self) -> None:

        if self.active_page == "generated":
            self._show_page("generated")

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

            if not isinstance(payload, dict):
                continue

            payload["_info_path"] = info_path
            records.append(payload)

        return sorted(
            records,
            key=lambda item: (
                str(item.get("type", "")),
                str(item.get("id", "")),
            ),
        )

    def _tool_for_record(self, record: dict):

        generator = record.get("generator", {})

        if isinstance(generator, dict):
            tool_id = generator.get("id")
        else:
            tool_id = None

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

    def _clear_scroll(self) -> None:

        for widget in self.scroll.winfo_children():
            widget.destroy()
