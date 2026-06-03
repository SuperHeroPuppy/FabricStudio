# generator_window.py
# developer: SuperHeroPuppy
# version: 2.0.0

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path
from tkinter import BooleanVar, filedialog, messagebox

import customtkinter as ctk

from core.data_store import COLORS
from ui.theme import themed_combo_box, themed_entry, theme_window
from ui.window_utils import show_on_top

try:
    from PIL import Image
except Exception:
    Image = None


ASSET_TYPES = {
    "textures": {
        "label": "Textures",
        "extensions": {".png"},
        "import_label": "Import Texture",
        "target": ("textures", "item"),
    },
    "audio": {
        "label": "Audio",
        "extensions": {".ogg"},
        "import_label": "Import Audio",
        "target": ("sounds",),
    },
    "models": {
        "label": "Models",
        "extensions": {".json"},
        "import_label": "Import Model",
        "target": ("models", "item"),
    },
}

VANILLA_ITEMS_1_20_1 = [
    "minecraft:air",
    "minecraft:stone",
    "minecraft:granite",
    "minecraft:polished_granite",
    "minecraft:diorite",
    "minecraft:polished_diorite",
    "minecraft:andesite",
    "minecraft:polished_andesite",
    "minecraft:grass_block",
    "minecraft:dirt",
    "minecraft:coarse_dirt",
    "minecraft:podzol",
    "minecraft:cobblestone",
    "minecraft:oak_planks",
    "minecraft:spruce_planks",
    "minecraft:birch_planks",
    "minecraft:jungle_planks",
    "minecraft:acacia_planks",
    "minecraft:dark_oak_planks",
    "minecraft:mangrove_planks",
    "minecraft:cherry_planks",
    "minecraft:bamboo_planks",
    "minecraft:sand",
    "minecraft:red_sand",
    "minecraft:gravel",
    "minecraft:coal_ore",
    "minecraft:iron_ore",
    "minecraft:copper_ore",
    "minecraft:gold_ore",
    "minecraft:redstone_ore",
    "minecraft:emerald_ore",
    "minecraft:lapis_ore",
    "minecraft:diamond_ore",
    "minecraft:nether_gold_ore",
    "minecraft:nether_quartz_ore",
    "minecraft:oak_log",
    "minecraft:spruce_log",
    "minecraft:birch_log",
    "minecraft:jungle_log",
    "minecraft:acacia_log",
    "minecraft:dark_oak_log",
    "minecraft:mangrove_log",
    "minecraft:cherry_log",
    "minecraft:bamboo_block",
    "minecraft:crafting_table",
    "minecraft:furnace",
    "minecraft:chest",
    "minecraft:torch",
    "minecraft:stick",
    "minecraft:bowl",
    "minecraft:string",
    "minecraft:feather",
    "minecraft:gunpowder",
    "minecraft:wheat_seeds",
    "minecraft:wheat",
    "minecraft:bread",
    "minecraft:apple",
    "minecraft:golden_apple",
    "minecraft:enchanted_golden_apple",
    "minecraft:cod",
    "minecraft:salmon",
    "minecraft:tropical_fish",
    "minecraft:pufferfish",
    "minecraft:cooked_cod",
    "minecraft:cooked_salmon",
    "minecraft:cookie",
    "minecraft:melon_slice",
    "minecraft:dried_kelp",
    "minecraft:beef",
    "minecraft:cooked_beef",
    "minecraft:chicken",
    "minecraft:cooked_chicken",
    "minecraft:porkchop",
    "minecraft:cooked_porkchop",
    "minecraft:mutton",
    "minecraft:cooked_mutton",
    "minecraft:rabbit",
    "minecraft:cooked_rabbit",
    "minecraft:rotten_flesh",
    "minecraft:carrot",
    "minecraft:potato",
    "minecraft:baked_potato",
    "minecraft:poisonous_potato",
    "minecraft:pumpkin_pie",
    "minecraft:beetroot",
    "minecraft:beetroot_soup",
    "minecraft:mushroom_stew",
    "minecraft:rabbit_stew",
    "minecraft:honey_bottle",
    "minecraft:milk_bucket",
    "minecraft:bucket",
    "minecraft:water_bucket",
    "minecraft:lava_bucket",
    "minecraft:powder_snow_bucket",
    "minecraft:iron_ingot",
    "minecraft:copper_ingot",
    "minecraft:gold_ingot",
    "minecraft:netherite_ingot",
    "minecraft:diamond",
    "minecraft:emerald",
    "minecraft:lapis_lazuli",
    "minecraft:redstone",
    "minecraft:coal",
    "minecraft:charcoal",
    "minecraft:quartz",
    "minecraft:amethyst_shard",
    "minecraft:nether_star",
    "minecraft:ender_pearl",
    "minecraft:ender_eye",
    "minecraft:blaze_rod",
    "minecraft:blaze_powder",
    "minecraft:bone",
    "minecraft:bone_meal",
    "minecraft:leather",
    "minecraft:paper",
    "minecraft:book",
    "minecraft:slime_ball",
    "minecraft:clay_ball",
    "minecraft:brick",
    "minecraft:flint",
    "minecraft:glass_bottle",
    "minecraft:experience_bottle",
    "minecraft:compass",
    "minecraft:recovery_compass",
    "minecraft:clock",
    "minecraft:shears",
    "minecraft:flint_and_steel",
    "minecraft:fishing_rod",
    "minecraft:bow",
    "minecraft:crossbow",
    "minecraft:arrow",
    "minecraft:spectral_arrow",
    "minecraft:shield",
    "minecraft:wooden_sword",
    "minecraft:stone_sword",
    "minecraft:iron_sword",
    "minecraft:golden_sword",
    "minecraft:diamond_sword",
    "minecraft:netherite_sword",
    "minecraft:wooden_pickaxe",
    "minecraft:stone_pickaxe",
    "minecraft:iron_pickaxe",
    "minecraft:golden_pickaxe",
    "minecraft:diamond_pickaxe",
    "minecraft:netherite_pickaxe",
    "minecraft:wooden_axe",
    "minecraft:stone_axe",
    "minecraft:iron_axe",
    "minecraft:golden_axe",
    "minecraft:diamond_axe",
    "minecraft:netherite_axe",
    "minecraft:wooden_shovel",
    "minecraft:stone_shovel",
    "minecraft:iron_shovel",
    "minecraft:golden_shovel",
    "minecraft:diamond_shovel",
    "minecraft:netherite_shovel",
    "minecraft:wooden_hoe",
    "minecraft:stone_hoe",
    "minecraft:iron_hoe",
    "minecraft:golden_hoe",
    "minecraft:diamond_hoe",
    "minecraft:netherite_hoe",
    "minecraft:leather_helmet",
    "minecraft:leather_chestplate",
    "minecraft:leather_leggings",
    "minecraft:leather_boots",
    "minecraft:chainmail_helmet",
    "minecraft:chainmail_chestplate",
    "minecraft:chainmail_leggings",
    "minecraft:chainmail_boots",
    "minecraft:iron_helmet",
    "minecraft:iron_chestplate",
    "minecraft:iron_leggings",
    "minecraft:iron_boots",
    "minecraft:golden_helmet",
    "minecraft:golden_chestplate",
    "minecraft:golden_leggings",
    "minecraft:golden_boots",
    "minecraft:diamond_helmet",
    "minecraft:diamond_chestplate",
    "minecraft:diamond_leggings",
    "minecraft:diamond_boots",
    "minecraft:netherite_helmet",
    "minecraft:netherite_chestplate",
    "minecraft:netherite_leggings",
    "minecraft:netherite_boots",
    "minecraft:music_disc_13",
    "minecraft:music_disc_cat",
    "minecraft:music_disc_blocks",
    "minecraft:music_disc_chirp",
    "minecraft:music_disc_far",
    "minecraft:music_disc_mall",
    "minecraft:music_disc_mellohi",
    "minecraft:music_disc_stal",
    "minecraft:music_disc_strad",
    "minecraft:music_disc_ward",
    "minecraft:music_disc_11",
    "minecraft:music_disc_wait",
    "minecraft:music_disc_otherside",
    "minecraft:music_disc_5",
    "minecraft:music_disc_pigstep",
    "minecraft:disc_fragment_5",
    "minecraft:oak_boat",
    "minecraft:spruce_boat",
    "minecraft:birch_boat",
    "minecraft:jungle_boat",
    "minecraft:acacia_boat",
    "minecraft:dark_oak_boat",
    "minecraft:mangrove_boat",
    "minecraft:cherry_boat",
    "minecraft:bamboo_raft",
    "minecraft:minecart",
    "minecraft:saddle",
    "minecraft:name_tag",
    "minecraft:lead",
    "minecraft:elytra",
    "minecraft:totem_of_undying",
]

class GeneratorWindow(ctk.CTkToplevel):
    def __init__(self, master, generators, workspace_path):
        super().__init__(master)

        self.title("Tool Generators")
        self.geometry("1160x760")
        self.minsize(980, 640)
        theme_window(self)
        show_on_top(self, master)

        self.workspace_path = Path(workspace_path)
        self.generators = generators
        self.generator_by_id = {generator.id: generator for generator in generators}
        self.project_info = self._load_project_info()
        self.mod_id = self._safe_name(
            self.project_info.get("mod_id", self.workspace_path.name.lower())
        )

        self.active_page = "home"
        self.active_tool = self._first_supported_tool()
        self.active_category = "display"
        self.editing_record: dict | None = None
        self.asset_target: tuple[str, str] | None = None
        self.selected_asset: dict | None = None
        self.asset_kind_var = ctk.StringVar(value="textures")
        self.texture_folder_var = ctk.StringVar(value="item")
        self.model_folder_var = ctk.StringVar(value="item")
        self.asset_import_folder: dict[str, Path | None] = {
            "textures": None,
            "audio": None,
            "models": None,
        }

        self.draft_values: dict[str, dict] = {}
        self.inputs: dict[tuple[str, str], object] = {}
        self.input_wrappers: dict[tuple[str, str], ctk.CTkFrame] = {}
        self.field_conditions: dict[tuple[str, str], dict] = {}
        self.preview_widgets: dict[tuple[str, str], dict[str, object]] = {}
        self.asset_images: list[ctk.CTkImage] = []

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.access_bar = ctk.CTkFrame(self, fg_color=COLORS["panel"], corner_radius=0)
        self.access_bar.grid(row=0, column=0, sticky="nsew")
        self.access_bar.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self.access_bar,
            text="Generators",
            font=("Segoe UI", 21, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 6))

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self._add_nav_button("home", "Home", 1)
        self._add_nav_button("assets", "Asset Browser", 2)

        self.main = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self.main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 6))
        header.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            header,
            text="Generated Things",
            font=("Segoe UI", 26, "bold"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew")

        self.header_action_frame = ctk.CTkFrame(header, fg_color="transparent")
        self.header_action_frame.grid(row=0, column=1, sticky="e")

        self.status_label = ctk.CTkLabel(
            self.main,
            text="Start from a chip or create a new one.",
            text_color=COLORS["muted"],
            anchor="w",
        )
        self.status_label.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))

        self.body = ctk.CTkFrame(self.main, fg_color="transparent")
        self.body.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 18))
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

        self._show_page("home")

    def _add_nav_button(self, page: str, label: str, row: int) -> None:
        button = ctk.CTkButton(
            self.access_bar,
            text=label,
            width=210,
            height=34,
            anchor="w",
            corner_radius=6,
            command=lambda target=page: self._show_page(target),
        )
        button.grid(row=row, column=0, sticky="ew", padx=12, pady=4)
        self.nav_buttons[page] = button

    def _show_page(self, page: str) -> None:
        if self.active_page == "configure":
            self._save_active_draft()

        self.active_page = page
        self._clear_body()
        self._clear_header_actions()
        if page == "assets":
            self.status_label.grid_remove()
        else:
            self.status_label.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))

        for name, button in self.nav_buttons.items():
            button.configure(
                fg_color=COLORS["accent"] if name == page else COLORS["panel_alt"]
            )

        if page == "assets":
            self.title_label.configure(text="Asset Browser")
            self.status_label.configure(
                text="Browse textures, audio, and models. Selecting an asset can fill the active chip."
            )
            self._build_assets_page()
            return

        if page == "configure":
            self.title_label.configure(
                text=f"Configure {self.active_tool.name if self.active_tool else 'Chip'}"
            )
            self.status_label.configure(text="Tune the chip by category, then generate it.")
            self._build_configure_page()
            return

        self.title_label.configure(text="Generated Things")
        self.status_label.configure(text="Start from a chip or create a new one.")
        self._build_home_page()

    def _build_home_page(self) -> None:
        ctk.CTkButton(
            self.header_action_frame,
            text="+",
            width=44,
            height=40,
            font=("Segoe UI", 24, "bold"),
            fg_color=COLORS["accent"],
            hover_color="#2563eb",
            command=self._new_chip,
        ).pack(side="right")

        panel = ctk.CTkFrame(self.body, fg_color="transparent")
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            panel,
            text="Your generated chips",
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        scroll.grid(row=1, column=0, sticky="nsew")

        records = self._generated_records()
        if not records:
            self._build_empty_home(scroll)
            return

        columns = 3
        for column in range(columns):
            scroll.grid_columnconfigure(column, weight=1, uniform="chips")

        for index, record in enumerate(records):
            self._build_home_chip(
                scroll,
                record,
                row=index // columns,
                column=index % columns,
            )

    def _build_empty_home(self, parent) -> None:
        empty = ctk.CTkFrame(parent, fg_color=COLORS["panel"], corner_radius=8)
        empty.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        empty.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            empty,
            text="No generated chips yet.",
            font=("Segoe UI", 18, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 4))

        ctk.CTkLabel(
            empty,
            text="Press the blue plus button to start configuring a new chip.",
            text_color=COLORS["muted"],
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))

    def _build_home_chip(self, parent, record: dict, row: int, column: int) -> None:
        tool = self._tool_for_record(record)
        title = record.get("display_name") or record.get("id") or "Generated chip"
        category = record.get("type") or record.get("tool_id") or "unknown"
        texture = record.get("texture") or record.get("form_data", {}).get("texture")
        if not texture:
            block_textures = record.get("block_textures") or record.get("form_data", {}).get("block_textures")
            if isinstance(block_textures, dict):
                texture = (
                    block_textures.get("top")
                    or block_textures.get("north")
                    or next(iter(block_textures.values()), "")
                )

        chip = ctk.CTkFrame(parent, fg_color=COLORS["panel"], corner_radius=8)
        chip.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
        chip.grid_columnconfigure(0, weight=1)

        preview = self._asset_by_identifier(str(texture)) if texture else None
        image_widget = self._thumbnail_label(chip, preview, size=(84, 84), fallback=category.upper())
        image_widget.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))

        ctk.CTkLabel(
            chip,
            text=str(title),
            font=("Segoe UI", 16, "bold"),
            anchor="w",
            wraplength=230,
        ).grid(row=1, column=0, sticky="ew", padx=14)

        ctk.CTkLabel(
            chip,
            text=f"{category} / {record.get('id', 'unknown')}",
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=230,
        ).grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 12))

        actions = ctk.CTkFrame(chip, fg_color="transparent")
        actions.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 14))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        if tool and tool.supported:
            ctk.CTkButton(
                actions,
                text="Edit",
                height=32,
                command=lambda item=record, spec=tool: self._edit_generated(item, spec),
            ).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        else:
            ctk.CTkButton(actions, text="Unavailable", state="disabled").grid(
                row=0,
                column=0,
                sticky="ew",
                padx=(0, 5),
            )

        ctk.CTkButton(
            actions,
            text="Delete",
            height=32,
            fg_color="#b91c1c",
            hover_color="#991b1b",
            command=lambda item=record: self._delete_generated(item),
        ).grid(row=0, column=1, sticky="ew", padx=(5, 0))

    def _build_configure_page(self) -> None:
        self.inputs.clear()
        self.input_wrappers.clear()
        self.field_conditions.clear()
        self.preview_widgets.clear()

        if self.active_tool is None:
            ctk.CTkLabel(
                self.body,
                text="No supported generators are available.",
                text_color=COLORS["muted"],
            ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        ctk.CTkButton(
            self.header_action_frame,
            text="Home",
            width=88,
            fg_color=COLORS["panel_alt"],
            command=lambda: self._show_page("home"),
        ).pack(side="right", padx=(8, 0))

        if self.editing_record:
            ctk.CTkButton(
                self.header_action_frame,
                text="Cancel Edit",
                width=110,
                fg_color=COLORS["panel_alt"],
                command=self._cancel_edit,
            ).pack(side="right", padx=(8, 0))

        editor = ctk.CTkFrame(self.body, fg_color=COLORS["panel"], corner_radius=8)
        editor.grid(row=0, column=0, sticky="nsew")
        editor.grid_columnconfigure(0, weight=1)
        editor.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(editor, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)

        title = self._draft_title()
        ctk.CTkLabel(
            header,
            text=title,
            font=("Segoe UI", 20, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")

        content = ctk.CTkScrollableFrame(editor, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        content.grid_columnconfigure(0, weight=1)

        fields = self._fields_for_category(self.active_tool, self.active_category)
        if not fields:
            ctk.CTkLabel(
                content,
                text="No fields in this category yet.",
                text_color=COLORS["muted"],
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        else:
            for row, field in enumerate(fields):
                self._build_field(content, self.active_tool.id, field, row)

        self._update_field_visibility()

        footer = ctk.CTkFrame(editor, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 16))
        footer.grid_columnconfigure(0, weight=1)

        category_bar = ctk.CTkFrame(footer, fg_color=COLORS["panel_alt"], corner_radius=8)
        category_bar.grid(row=0, column=0, sticky="w")

        for index, category in enumerate(self._tool_categories(self.active_tool)):
            selected = category["id"] == self.active_category
            ctk.CTkButton(
                category_bar,
                text=category["label"],
                width=150,
                height=34,
                corner_radius=6,
                fg_color=COLORS["accent"] if selected else COLORS["panel_alt"],
                hover_color="#2563eb" if selected else COLORS["border"],
                command=lambda cid=category["id"]: self._select_category(cid),
            ).grid(row=0, column=index, padx=4, pady=4)

        action = "Save Changes" if self.editing_record else f"Generate {self.active_tool.name}"
        ctk.CTkButton(
            footer,
            text=action,
            width=160,
            height=38,
            command=self._generate_active_tool,
        ).grid(row=0, column=1, sticky="e")

    def _build_field(self, parent, tool_id: str, field: dict, row: int) -> None:
        field_id = field["id"]
        field_type = field["type"]
        key = (tool_id, field_id)

        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.grid(row=row, column=0, sticky="ew", padx=8, pady=8)
        wrapper.grid_columnconfigure(0, weight=1)
        self.input_wrappers[key] = wrapper

        condition = field.get("visible_if")
        if isinstance(condition, dict):
            self.field_conditions[key] = condition

        if field_type != "boolean":
            ctk.CTkLabel(
                wrapper,
                text=field.get("label", field_id),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", pady=(0, 5))

        if field_type == "string":
            entry = themed_entry(wrapper, placeholder_text=field.get("placeholder", ""))
            initial_value = self._initial_value(tool_id, field_id)
            if initial_value is not None:
                entry.insert(0, str(initial_value))
            entry.grid(row=1, column=0, sticky="ew")
            self.inputs[key] = entry
            return

        if field_type == "boolean":
            var = BooleanVar(value=bool(field.get("default", False)))
            initial_value = self._initial_value(tool_id, field_id)
            if initial_value is not None:
                var.set(self._as_bool(initial_value))
            ctk.CTkCheckBox(
                wrapper,
                text=field.get("label", field_id),
                variable=var,
                command=self._update_field_visibility,
            ).grid(row=0, column=0, sticky="w")
            self.inputs[key] = var
            return

        if field_type == "select":
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
                command=lambda value, tid=tool_id, fid=field_id: self._on_select_changed(
                    tid,
                    fid,
                    value,
                ),
            )
            entry.set(selected)
            entry.grid(row=1, column=0, sticky="ew")
            self.inputs[key] = entry
            return

        if field_type == "number":
            entry = themed_entry(wrapper)
            initial_value = self._initial_value(tool_id, field_id)
            entry.insert(
                0,
                str(initial_value if initial_value is not None else field.get("default", 0)),
            )
            entry.grid(row=1, column=0, sticky="ew")
            self.inputs[key] = entry
            return

        if field_type == "array":
            textbox = ctk.CTkTextbox(wrapper, height=96)
            initial_value = self._initial_value(tool_id, field_id)
            if isinstance(initial_value, list):
                textbox.insert("1.0", "\n".join(str(item) for item in initial_value))
            elif initial_value is not None:
                textbox.insert("1.0", str(initial_value))
            textbox.grid(row=1, column=0, sticky="ew")
            self.inputs[key] = textbox
            return

        if field_type in {"texture", "audio", "model"}:
            self._build_asset_selector(wrapper, tool_id, field, field_type)
            return

        if field_type == "block_textures":
            self._build_block_texture_selector(wrapper, tool_id, field)
            return

        if field_type == "hitbox_table":
            self._build_hitbox_table(wrapper, tool_id, field)
            return

        if field_type == "element_reference":
            self._build_element_reference_selector(wrapper, tool_id, field)
            return

        ctk.CTkLabel(
            wrapper,
            text=f"Unsupported field type: {field_type}",
            text_color="#777777",
        ).grid(row=1, column=0, sticky="w")

    def _build_asset_selector(self, parent, tool_id: str, field: dict, field_type: str) -> None:
        field_id = field["id"]
        key = (tool_id, field_id)
        kind = {"texture": "textures", "audio": "audio", "model": "models"}[field_type]

        frame = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], corner_radius=8)
        frame.grid(row=1, column=0, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)

        var = ctk.StringVar()
        initial_value = self._initial_value(tool_id, field_id)
        if initial_value is not None:
            var.set(str(initial_value))

        preview = self._asset_by_identifier(var.get()) if var.get() else None
        preview_label = self._thumbnail_label(frame, preview, size=(72, 72), fallback=kind.upper())
        preview_label.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=10, pady=10)

        entry = themed_entry(frame, textvariable=var)
        entry.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(10, 4))

        buttons = ctk.CTkFrame(frame, fg_color="transparent")
        buttons.grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(4, 10))
        buttons.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            buttons,
            text="Browse Assets",
            width=128,
            command=lambda tid=tool_id, fid=field_id, asset_kind=kind: self._open_assets_for_field(
                tid,
                fid,
                asset_kind,
            ),
        ).grid(row=0, column=1, sticky="e")

        self.inputs[key] = var
        self.preview_widgets[key] = {
            "label": preview_label,
            "kind": kind,
        }

    def _build_block_texture_selector(self, parent, tool_id: str, field: dict) -> None:
        sides = [
            ("top", "Top"),
            ("bottom", "Bottom"),
            ("north", "North"),
            ("south", "South"),
            ("east", "East"),
            ("west", "West"),
        ]
        initial = self._initial_value(tool_id, field["id"])
        if not isinstance(initial, dict):
            initial = {}

        grid = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], corner_radius=8)
        grid.grid(row=1, column=0, sticky="ew")
        for column in range(3):
            grid.grid_columnconfigure(column, weight=1, uniform="block_texture_sides")

        for index, (side_id, label) in enumerate(sides):
            side_key = (tool_id, f"{field['id']}_{side_id}")
            side = ctk.CTkFrame(grid, fg_color=COLORS["panel"], corner_radius=8)
            side.grid(row=index // 3, column=index % 3, sticky="nsew", padx=6, pady=6)
            side.grid_columnconfigure(0, weight=1)

            value = str(initial.get(side_id, ""))
            var = ctk.StringVar(value=value)
            preview = self._asset_by_identifier(value) if value else None
            preview_label = self._thumbnail_label(side, preview, size=(64, 64), fallback=label.upper())
            preview_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))

            ctk.CTkLabel(
                side,
                text=label,
                font=("Segoe UI", 13, "bold"),
            ).grid(row=1, column=0, sticky="ew", padx=10)

            themed_entry(side, textvariable=var).grid(
                row=2,
                column=0,
                sticky="ew",
                padx=10,
                pady=(4, 6),
            )
            ctk.CTkButton(
                side,
                text="Browse",
                height=30,
                command=lambda tid=tool_id, fid=f"{field['id']}_{side_id}:block_textures": self._open_assets_for_field(
                    tid,
                    fid,
                    "textures",
                ),
            ).grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))

            self.inputs[side_key] = var

    def _build_hitbox_table(self, parent, tool_id: str, field: dict) -> None:
        field_id = field["id"]
        initial = self._initial_value(tool_id, field_id)
        if not isinstance(initial, dict):
            initial = {}

        defaults = {
            "min_x": 0,
            "min_y": 0,
            "min_z": 0,
            "max_x": 16,
            "max_y": 16,
            "max_z": 16,
        }

        table = ctk.CTkFrame(parent, fg_color=COLORS["panel_alt"], corner_radius=8)
        table.grid(row=1, column=0, sticky="ew")
        for column in range(4):
            table.grid_columnconfigure(column, weight=1, uniform="hitbox_table")

        ctk.CTkLabel(table, text="", width=64).grid(row=0, column=0, padx=8, pady=(10, 4))
        for column, axis in enumerate(("X", "Y", "Z"), start=1):
            ctk.CTkLabel(
                table,
                text=axis,
                font=("Segoe UI", 13, "bold"),
            ).grid(row=0, column=column, sticky="ew", padx=6, pady=(10, 4))

        for row, (prefix, label) in enumerate((("min", "Min"), ("max", "Max")), start=1):
            ctk.CTkLabel(
                table,
                text=label,
                anchor="w",
            ).grid(row=row, column=0, sticky="ew", padx=(12, 6), pady=6)

            for column, axis in enumerate(("x", "y", "z"), start=1):
                key_name = f"{prefix}_{axis}"
                input_id = f"custom_hitbox_{key_name}"
                value = self._initial_value(tool_id, input_id)
                if value is None:
                    value = initial.get(key_name, defaults[key_name])
                var = ctk.StringVar(value=str(value))
                themed_entry(table, textvariable=var, width=82).grid(
                    row=row,
                    column=column,
                    sticky="ew",
                    padx=6,
                    pady=6,
                )
                self.inputs[(tool_id, input_id)] = var

    def _build_element_reference_selector(self, parent, tool_id: str, field: dict) -> None:
        field_id = field["id"]
        key = (tool_id, field_id)
        source_field = str(field.get("source_field", "consumed_result_source"))
        source = str(self.draft_values.get(tool_id, {}).get(source_field, "vanilla"))
        values = self._element_reference_values(source)
        initial_value = self._initial_value(tool_id, field_id)

        entry = themed_combo_box(parent, values=values or [""])
        entry.set(str(initial_value if initial_value is not None else (values[0] if values else "")))
        entry.grid(row=1, column=0, sticky="ew")
        self.inputs[key] = entry

    def _build_assets_page(self) -> None:
        ctk.CTkButton(
            self.header_action_frame,
            text="Home",
            width=88,
            fg_color=COLORS["panel_alt"],
            command=lambda: self._show_page("home"),
        ).pack(side="right", padx=(8, 0))

        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(1, weight=0)
        self.body.grid_rowconfigure(2, weight=1)

        toolbar = ctk.CTkFrame(self.body, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.grid_columnconfigure(6, weight=1)

        for index, kind in enumerate(ASSET_TYPES):
            selected = self.asset_kind_var.get() == kind
            ctk.CTkButton(
                toolbar,
                text=ASSET_TYPES[kind]["label"],
                width=108,
                fg_color=COLORS["accent"] if selected else COLORS["panel_alt"],
                command=lambda asset_kind=kind: self._select_asset_kind(asset_kind),
            ).grid(row=0, column=index, padx=(0, 8))

        action_column = 3
        if self.asset_kind_var.get() == "textures":
            asset_target = themed_combo_box(
                toolbar,
                values=["item", "block"],
                variable=self.texture_folder_var,
                width=92,
                command=lambda _value: self._show_page("assets"),
            )
            asset_target.grid(row=0, column=3, padx=(8, 8))
            action_column = 4
        elif self.asset_kind_var.get() == "models":
            asset_target = themed_combo_box(
                toolbar,
                values=["item", "block"],
                variable=self.model_folder_var,
                width=92,
                command=lambda _value: self._show_page("assets"),
            )
            asset_target.grid(row=0, column=3, padx=(8, 8))
            action_column = 4

        ctk.CTkButton(
            toolbar,
            text="Choose Folder",
            width=122,
            fg_color=COLORS["panel_alt"],
            command=self._choose_asset_folder,
        ).grid(row=0, column=action_column, padx=(8, 8))

        ctk.CTkButton(
            toolbar,
            text=ASSET_TYPES[self.asset_kind_var.get()]["import_label"],
            width=126,
            command=self._import_asset,
        ).grid(row=0, column=action_column + 1)

        current_folder = self._current_asset_import_dir()
        try:
            folder_text = str(current_folder.relative_to(self.workspace_path))
        except ValueError:
            folder_text = str(current_folder)

        ctk.CTkLabel(
            toolbar,
            text=folder_text,
            text_color=COLORS["muted"],
            anchor="w",
        ).grid(row=1, column=0, columnspan=7, sticky="ew", pady=(6, 0))

        if self.selected_asset:
            preview_panel = ctk.CTkFrame(self.body, fg_color=COLORS["panel"], corner_radius=8)
            preview_panel.grid(row=1, column=0, sticky="ew", pady=(0, 10))
            preview_panel.grid_columnconfigure(1, weight=1)
            self._build_inline_asset_preview(preview_panel)

        grid_panel = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        grid_panel.grid(row=2, column=0, sticky="nsew")
        columns = 5
        for column in range(columns):
            grid_panel.grid_columnconfigure(column, weight=1, uniform="asset_grid")

        assets = self._asset_records(self.asset_kind_var.get())
        if not assets:
            ctk.CTkLabel(
                grid_panel,
                text=f"No {ASSET_TYPES[self.asset_kind_var.get()]['label'].lower()} found yet.",
                text_color=COLORS["muted"],
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        else:
            for index, asset in enumerate(assets):
                self._build_asset_grid_card(
                    grid_panel,
                    asset,
                    row=index // columns,
                    column=index % columns,
                )

    def _build_asset_grid_card(self, parent, asset: dict, row: int, column: int) -> None:
        selected = self.selected_asset and self.selected_asset.get("path") == asset.get("path")
        frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["panel_alt"] if selected else COLORS["panel"],
            corner_radius=8,
            border_width=1 if selected else 0,
            border_color=COLORS["accent"],
        )
        frame.grid(row=row, column=column, sticky="nsew", padx=6, pady=6)
        frame.grid_columnconfigure(0, weight=1)

        thumb = self._thumbnail_label(frame, asset, size=(92, 92), fallback=asset["kind"].upper())
        thumb.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))

        ctk.CTkLabel(
            frame,
            text=asset["identifier"],
            font=("Segoe UI", 12, "bold"),
            anchor="center",
            wraplength=150,
        ).grid(row=1, column=0, sticky="ew", padx=10)

        ctk.CTkButton(
            frame,
            text="Select" if self.asset_target else "Preview",
            height=30,
            command=lambda item=asset: self._select_asset(item),
        ).grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 10))

    def _build_inline_asset_preview(self, parent) -> None:
        asset = self.selected_asset
        if not asset:
            return

        thumb = self._thumbnail_label(parent, asset, size=(78, 78), fallback=asset["kind"].upper())
        thumb.grid(row=0, column=0, rowspan=2, padx=12, pady=10)

        ctk.CTkLabel(
            parent,
            text=asset["identifier"],
            font=("Segoe UI", 15, "bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(12, 0))

        ctk.CTkLabel(
            parent,
            text=str(asset["path"].relative_to(self.workspace_path)),
            text_color=COLORS["muted"],
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 12))

        if self.asset_target:
            ctk.CTkButton(
                parent,
                text="Use In Chip",
                width=120,
                command=lambda item=asset: self._use_asset_for_target(item),
            ).grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 12), pady=12)

    def _build_asset_row(self, parent, asset: dict, row: int) -> None:
        selected = self.selected_asset and self.selected_asset.get("path") == asset.get("path")
        frame = ctk.CTkFrame(
            parent,
            fg_color=COLORS["panel_alt"] if selected else COLORS["panel"],
            corner_radius=8,
            border_width=1 if selected else 0,
            border_color=COLORS["accent"],
        )
        frame.grid(row=row, column=0, sticky="ew", pady=5)
        frame.grid_columnconfigure(1, weight=1)

        thumb = self._thumbnail_label(frame, asset, size=(52, 52), fallback=asset["kind"].upper())
        thumb.grid(row=0, column=0, rowspan=2, padx=10, pady=10)

        ctk.CTkLabel(
            frame,
            text=asset["identifier"],
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(10, 0))

        ctk.CTkLabel(
            frame,
            text=str(asset["path"].relative_to(self.workspace_path)),
            text_color=COLORS["muted"],
            anchor="w",
            wraplength=480,
        ).grid(row=1, column=1, sticky="ew", padx=(0, 10), pady=(0, 10))

        ctk.CTkButton(
            frame,
            text="Select",
            width=82,
            command=lambda item=asset: self._select_asset(item),
        ).grid(row=0, column=2, rowspan=2, padx=(0, 10), pady=10)

    def _build_asset_preview(self, parent) -> None:
        asset = self.selected_asset
        if not asset:
            ctk.CTkLabel(
                parent,
                text="Select an asset",
                font=("Segoe UI", 18, "bold"),
            ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 4))
            ctk.CTkLabel(
                parent,
                text="The preview will appear here.",
                text_color=COLORS["muted"],
            ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))
            return

        thumb = self._thumbnail_label(parent, asset, size=(180, 180), fallback=asset["kind"].upper())
        thumb.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))

        ctk.CTkLabel(
            parent,
            text=asset["identifier"],
            font=("Segoe UI", 16, "bold"),
            wraplength=250,
        ).grid(row=1, column=0, sticky="ew", padx=18)

        ctk.CTkLabel(
            parent,
            text=str(asset["path"].relative_to(self.workspace_path)),
            text_color=COLORS["muted"],
            wraplength=250,
        ).grid(row=2, column=0, sticky="ew", padx=18, pady=(4, 12))

        if self.asset_target:
            ctk.CTkButton(
                parent,
                text="Use In Chip",
                command=lambda item=asset: self._use_asset_for_target(item),
            ).grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))

    def _thumbnail_label(self, parent, asset: dict | None, size=(64, 64), fallback="ASSET"):
        if asset and asset.get("kind") == "textures" and Image is not None:
            try:
                image = Image.open(asset["path"])
                ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=size)
                self.asset_images.append(ctk_image)
                return ctk.CTkLabel(parent, image=ctk_image, text="")
            except Exception:
                pass

        text = fallback
        if asset and asset.get("kind") == "audio":
            text = "AUDIO"
        elif asset and asset.get("kind") == "models":
            text = "MODEL"

        return ctk.CTkLabel(
            parent,
            text=text,
            text_color=COLORS["muted"],
            width=size[0],
            height=size[1],
        )

    def _refresh_side_chips(self) -> None:
        return

    def _new_chip(self, tool=None) -> None:
        if tool is None:
            self._open_new_chip_dialog()
            return

        self.active_tool = tool
        if self.active_tool is None:
            self.status_label.configure(text="No supported generators are available.")
            return

        self.editing_record = None
        self.active_category = "display"
        self.asset_target = None
        self.draft_values[self.active_tool.id] = self._default_draft(self.active_tool)
        self._show_page("configure")

    def _open_new_chip_dialog(self) -> None:
        supported = [generator for generator in self.generators if generator.supported]
        if not supported:
            self.status_label.configure(text="No supported generators are available.")
            return

        window = ctk.CTkToplevel(self)
        window.title("Create Chip")
        window.geometry("320x220")
        theme_window(window)
        show_on_top(window, self)
        window.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            window,
            text="Create",
            font=("Segoe UI", 22, "bold"),
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 6))

        for row, generator in enumerate(supported, start=1):
            ctk.CTkButton(
                window,
                text=generator.name,
                height=40,
                command=lambda tool=generator: (window.destroy(), self._new_chip(tool)),
            ).grid(row=row, column=0, sticky="ew", padx=18, pady=6)

    def _edit_generated(self, record: dict, tool) -> None:
        if tool is None or not tool.supported:
            self.status_label.configure(text="That chip's generator is not available.")
            return

        self.active_tool = tool
        self.editing_record = record
        self.active_category = "display"
        self.asset_target = None
        self.draft_values[tool.id] = self._form_data_for_record(record, tool)
        self._show_page("configure")
        self.status_label.configure(text=f"Editing {record.get('display_name') or record.get('id')}.")

    def _cancel_edit(self) -> None:
        self.editing_record = None
        if self.active_tool:
            self.draft_values.pop(self.active_tool.id, None)
        self._show_page("home")

    def _select_tool_by_name(self, name: str) -> None:
        self._save_active_draft()
        for generator in self.generators:
            if generator.name == name:
                self.active_tool = generator
                self.active_category = "display"
                self.editing_record = None
                self.status_label.configure(text=f"{generator.name} selected.")
                return

    def _select_category(self, category_id: str) -> None:
        self._save_active_draft()
        self.active_category = category_id
        self._show_page("configure")

    def _on_select_changed(self, tool_id: str, field_id: str, value: str) -> None:
        self.draft_values.setdefault(tool_id, {})[field_id] = value
        self._update_field_visibility()
        if field_id == "consumed_result_source":
            self._show_page("configure")

    def _select_asset_kind(self, kind: str) -> None:
        self.asset_kind_var.set(kind)
        if kind == "models" and self.active_tool:
            self.model_folder_var.set("block" if self.active_tool.id == "block" else "item")
        self.selected_asset = None
        self._show_page("assets")

    def _open_assets_for_field(self, tool_id: str, field_id: str, kind: str) -> None:
        self._save_active_draft()
        self.asset_target = (tool_id, field_id)
        self.asset_kind_var.set(kind)
        if field_id.endswith(":block_textures"):
            self.texture_folder_var.set("block")
        if kind == "models":
            self.model_folder_var.set("block" if tool_id == "block" else "item")
        self.selected_asset = None
        self._show_page("assets")
        self.status_label.configure(text="Select an asset for the active chip.")

    def _select_asset(self, asset: dict) -> None:
        self.selected_asset = asset
        if self.asset_target:
            self._use_asset_for_target(asset)
            return
        self._show_page("assets")
        self.status_label.configure(text=f"Selected asset: {asset['identifier']}")

    def _use_asset_for_target(self, asset: dict) -> None:
        if not self.asset_target:
            return

        tool_id, field_id = self.asset_target
        values = self.draft_values.setdefault(tool_id, {})
        if ":" in field_id:
            actual_field_id, field_type = field_id.split(":", 1)
        else:
            actual_field_id, field_type = field_id, ""

        synced_duration = None
        if field_type == "block_textures" and "_" in actual_field_id:
            base_field, side = actual_field_id.rsplit("_", 1)
            block_textures = values.setdefault(base_field, {})
            if not isinstance(block_textures, dict):
                block_textures = {}
                values[base_field] = block_textures
            block_textures[side] = asset["identifier"]
        else:
            values[actual_field_id] = asset["identifier"]
            if actual_field_id == "music_disc_sound":
                synced_duration = self._sync_music_disc_length(tool_id, asset)

        self.asset_target = None
        self.selected_asset = asset
        self._show_page("configure")
        if synced_duration is None:
            self.status_label.configure(text=f"Asset set to {asset['identifier']}.")
        else:
            self.status_label.configure(
                text=f"Asset set to {asset['identifier']}; length synced to {synced_duration} seconds."
            )

    def _sync_music_disc_length(self, tool_id: str, asset: dict) -> int | None:
        if tool_id != "item" or asset.get("kind") != "audio":
            return None

        values = self.draft_values.setdefault(tool_id, {})
        if not self._as_bool(values.get("music_disc_auto_sync_length", True)):
            return None

        duration = self._ogg_vorbis_duration_seconds(Path(asset["path"]))
        if duration is None:
            return None

        values["music_disc_length_seconds"] = duration
        return duration

    def _ogg_vorbis_duration_seconds(self, path: Path) -> int | None:
        if not path.exists():
            return None

        try:
            data = path.read_bytes()
        except OSError:
            return None

        header_index = data.find(b"\x01vorbis")
        if header_index < 0 or header_index + 16 > len(data):
            return None

        sample_rate = int.from_bytes(data[header_index + 12 : header_index + 16], "little")
        if sample_rate <= 0:
            return None

        max_granule = -1
        index = 0
        while True:
            page_index = data.find(b"OggS", index)
            if page_index < 0 or page_index + 27 > len(data):
                break

            segment_count = data[page_index + 26]
            segment_table_start = page_index + 27
            segment_table_end = segment_table_start + segment_count
            if segment_table_end > len(data):
                break

            body_size = sum(data[segment_table_start:segment_table_end])
            page_end = segment_table_end + body_size
            granule = int.from_bytes(
                data[page_index + 6 : page_index + 14],
                "little",
                signed=True,
            )
            if granule >= 0:
                max_granule = max(max_granule, granule)

            index = page_end if page_end > page_index else page_index + 4

        if max_granule < 0:
            return None

        return max(1, int((max_granule + sample_rate - 1) // sample_rate))

    def _choose_asset_folder(self) -> None:
        base = self._default_asset_import_dir(self.asset_kind_var.get())
        base.mkdir(parents=True, exist_ok=True)

        selected = filedialog.askdirectory(
            title="Choose asset folder",
            initialdir=base,
        )
        if not selected:
            return

        selected_path = Path(selected)
        try:
            selected_path.relative_to(self._assets_root())
        except ValueError:
            self.status_label.configure(text="Asset folders must be inside workspace assets.")
            return

        self.asset_import_folder[self.asset_kind_var.get()] = selected_path
        self._show_page("assets")
        self.status_label.configure(text=f"Import folder set to {selected_path.name}.")

    def _import_asset(self) -> None:
        kind = self.asset_kind_var.get()
        extensions = sorted(ASSET_TYPES[kind]["extensions"])
        filetypes = [(f"{ASSET_TYPES[kind]['label']} Files", " ".join(f"*{ext}" for ext in extensions))]
        path = filedialog.askopenfilename(filetypes=filetypes)
        if not path:
            return

        source = Path(path)
        target_dir = self._current_asset_import_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

        target_name = self._safe_asset_filename(source.name)
        target = target_dir / target_name

        if target.exists() and not messagebox.askyesno(
            "Replace Asset",
            f"{target.name} already exists. Replace it?",
            parent=self,
        ):
            return

        try:
            shutil.copy2(source, target)
        except OSError as exc:
            self.status_label.configure(text=f"Import failed: {exc}")
            return

        self.selected_asset = self._asset_record_for_path(target, kind)
        self._show_page("assets")
        self.status_label.configure(text=f"Imported {target.name}.")

    def _generate_active_tool(self) -> None:
        if self.active_tool is None:
            return

        self._save_active_draft()
        payload = dict(self.draft_values.get(self.active_tool.id, {}))
        registry_name = str(payload.get("registry_name", "")).strip()
        if not registry_name:
            self.status_label.configure(text="Registration name is required.")
            return
        if self._as_bool(payload.get("music_disc")) and not str(
            payload.get("music_disc_sound", "")
        ).strip():
            self.status_label.configure(text="Music discs need an audio asset selected.")
            return
        if self._as_bool(payload.get("food_enabled")) and self._as_bool(
            payload.get("consumed_result_enabled")
        ):
            result_id = str(payload.get("consumed_result_item", "")).strip()
            result_source = str(payload.get("consumed_result_source", "vanilla"))
            if not result_id or ":" not in result_id:
                self.status_label.configure(text="Consumed result needs a namespaced item id.")
                return
            namespace = result_id.split(":", 1)[0]
            if result_source == "other_mod" and namespace in {"minecraft", self.mod_id}:
                self.status_label.configure(text="Other mod results need another mod id namespace.")
                return

        module = self._load_generator_module(self.active_tool)
        if module is None:
            self.status_label.configure(text=f"Could not load {self.active_tool.name} generator.")
            return

        old_record = self.editing_record
        old_id = str(old_record.get("id", "")) if old_record else ""
        new_id = self._safe_name(registry_name)
        conflict = self._registry_id_conflict(new_id, old_record)
        if conflict:
            self.status_label.configure(
                text=f"Registry name '{new_id}' is already used by a generated {conflict}."
            )
            return

        if old_record and old_id and old_id != new_id:
            self._delete_record_files(old_record)

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
        self._show_page("home")
        self.status_label.configure(
            text=f"{self.active_tool.name} {'updated' if old_record else 'generated'}."
        )

    def _delete_generated(self, record: dict) -> None:
        title = record.get("display_name") or record.get("id") or "this generated chip"
        if not messagebox.askyesno(
            "Delete Generated Chip",
            f"Delete {title} and its generated files?",
            parent=self,
        ):
            return

        self._delete_record_files(record)
        if self.editing_record is record:
            self.editing_record = None
        self._show_page("home")
        self.status_label.configure(text=f"Deleted {title}.")

    def _delete_record_files(self, record: dict) -> None:
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

        existing = dict(self.draft_values.get(self.active_tool.id, {}))
        existing.update(self._collect_form_data(visible_only=False))
        self.draft_values[self.active_tool.id] = existing

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

            if field_id.startswith("block_textures_"):
                side = field_id.removeprefix("block_textures_")
                payload.setdefault("block_textures", {})[side] = value
            else:
                payload[field_id] = value

        return payload

    def _update_field_visibility(self) -> None:
        for key, condition in self.field_conditions.items():
            wrapper = self.input_wrappers.get(key)
            if wrapper is None:
                continue

            if self._condition_met(key[0], condition):
                wrapper.grid()
            else:
                wrapper.grid_remove()

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

    def _tool_categories(self, tool) -> list[dict]:
        categories = tool.manifest.get("categories")
        if isinstance(categories, list) and categories:
            return [
                {
                    "id": str(category.get("id", "")),
                    "label": str(category.get("label", category.get("id", "Category"))),
                }
                for category in categories
                if category.get("id")
            ]

        return [
            {"id": "display", "label": "Display Setup"},
            {"id": "additional", "label": "Additional Content"},
        ]

    def _fields_for_category(self, tool, category_id: str) -> list[dict]:
        fields = tool.manifest.get("forms", [])
        explicit = [field for field in fields if field.get("category") == category_id]
        if explicit:
            return explicit

        if category_id == "display":
            display_ids = {"registry_name", "display_name", "texture", "block_textures", "model"}
            return [field for field in fields if field.get("id") in display_ids]

        display_ids = {"registry_name", "display_name", "texture", "block_textures", "model"}
        return [field for field in fields if field.get("id") not in display_ids]

    def _default_draft(self, tool) -> dict:
        values: dict = {}
        for field in tool.manifest.get("forms", []):
            field_id = field.get("id")
            if not field_id:
                continue
            if "default" in field:
                values[field_id] = field["default"]
            elif field.get("type") == "select":
                field_values = field.get("values", [])
                if field_values:
                    values[field_id] = field_values[0]
        return values

    def _initial_value(self, tool_id: str, field_id: str):
        return self.draft_values.get(tool_id, {}).get(field_id)

    def _draft_title(self) -> str:
        if not self.active_tool:
            return "Chip"

        values = self.draft_values.get(self.active_tool.id, {})
        display = values.get("display_name") or values.get("registry_name")
        if display:
            return str(display)
        return f"New {self.active_tool.name} Chip"

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
                str(item.get("display_name") or item.get("id", "")),
            ),
        )

    def _registry_id_conflict(self, registry_id: str, current_record: dict | None) -> str:
        current_type = str(current_record.get("type", "")) if current_record else ""
        current_id = str(current_record.get("id", "")) if current_record else ""
        for record in self._generated_records():
            record_type = str(record.get("type", ""))
            if record_type not in {"block", "item"}:
                continue

            record_id = str(record.get("id", ""))
            if record_id != registry_id:
                continue

            if current_record and record_type == current_type and record_id == current_id:
                continue

            return record_type

        return ""

    def _asset_records(self, kind: str | None = None) -> list[dict]:
        assets_root = self._assets_root()
        if not assets_root.exists():
            return []

        kinds = [kind] if kind else list(ASSET_TYPES)
        assets: list[dict] = []
        for asset_kind in kinds:
            for path in sorted(assets_root.glob("**/*")):
                if not path.is_file() or path.suffix.lower() not in ASSET_TYPES[asset_kind]["extensions"]:
                    continue

                record = self._asset_record_for_path(path, asset_kind)
                if record:
                    assets.append(record)

        return sorted(assets, key=lambda item: item["identifier"])

    def _asset_record_for_path(self, path: Path, kind: str) -> dict | None:
        try:
            rel = path.relative_to(self._assets_root())
        except ValueError:
            return None

        parts = rel.parts
        if len(parts) < 2:
            return None

        namespace = parts[0]
        if kind == "textures":
            if len(parts) < 4 or parts[1] != "textures":
                return None
            texture_type = parts[2]
            name_parts = list(parts[3:])
            name_parts[-1] = Path(name_parts[-1]).stem
            identifier = f"{namespace}:{texture_type}/{'/'.join(name_parts)}"
        elif kind == "audio":
            if len(parts) < 3 or parts[1] != "sounds":
                return None
            name_parts = list(parts[2:])
            name_parts[-1] = Path(name_parts[-1]).stem
            identifier = f"{namespace}:sounds/{'/'.join(name_parts)}"
        else:
            if len(parts) < 4 or parts[1] != "models":
                return None
            model_type = parts[2]
            name_parts = list(parts[3:])
            name_parts[-1] = Path(name_parts[-1]).stem
            identifier = f"{namespace}:{model_type}/{'/'.join(name_parts)}"

        return {
            "path": path,
            "identifier": identifier,
            "kind": kind,
        }

    def _asset_by_identifier(self, identifier: str) -> dict | None:
        if not identifier:
            return None
        for asset in self._asset_records():
            if asset["identifier"] == identifier:
                return asset
            if asset["kind"] == "models" and self._legacy_model_identifier(asset) == identifier:
                return asset
        return None

    def _legacy_model_identifier(self, asset: dict) -> str:
        identifier = str(asset.get("identifier", ""))
        if ":" not in identifier:
            return identifier

        namespace, model_path = identifier.split(":", 1)
        return f"{namespace}:models/{model_path}"

    def _element_reference_values(self, source: str) -> list[str]:
        source = str(source or "vanilla")
        if source == "this_mod":
            values = []
            for record in self._generated_records():
                item_id = record.get("id")
                if record.get("type") == "item" and item_id:
                    values.append(f"{self.mod_id}:{item_id}")
            return sorted(values)

        if source == "other_mod":
            return ["mod_id:item_name"]

        return VANILLA_ITEMS_1_20_1

    def _current_asset_import_dir(self) -> Path:
        kind = self.asset_kind_var.get()
        return self.asset_import_folder.get(kind) or self._default_asset_import_dir(kind)

    def _default_asset_import_dir(self, kind: str) -> Path:
        target_parts = ASSET_TYPES[kind]["target"]
        if kind == "textures":
            target_parts = ("textures", self.texture_folder_var.get() or "item")
        elif kind == "models":
            target_parts = ("models", self.model_folder_var.get() or "item")
        return self._assets_root() / self.mod_id / Path(*target_parts)

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
            values = self._default_draft(tool)
            values.update(form_data)
            return values

        values = self._default_draft(tool)
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
            elif field_id == "block_textures":
                values[field_id] = record.get("block_textures", {})
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

    def _clear_header_actions(self) -> None:
        for widget in self.header_action_frame.winfo_children():
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

    def _safe_asset_filename(self, filename: str) -> str:
        path = Path(filename)
        stem = self._safe_name(path.stem)
        extension = re.sub(r"[^a-z0-9.]+", "", path.suffix.lower())
        return f"{stem}{extension}"
