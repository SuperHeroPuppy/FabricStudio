# generator.py
# developer: SuperHeroPuppy
# version: 1.0.3
# generator type: item

from __future__ import annotations

from datetime import datetime
import json
import re
from pathlib import Path


FABRIC_API_VERSION = "0.92.9+1.20.1"


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", name.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "unnamed_item"


def generate(data: dict, workspace_root: Path, tool) -> None:
    item_name = safe_name(data.get("registry_name", "unnamed_item"))
    display_name = data.get("display_name") or _title_from_id(item_name)
    project = _load_project_info(workspace_root)
    mod_id = safe_name(project.get("mod_id", workspace_root.name.lower()))
    package_name = _package_declaration(project, mod_id)
    main_class = _class_name(mod_id)
    texture_path = _normalize_texture(data.get("texture"), mod_id, item_name)
    form_data = _form_data(data, item_name, display_name, texture_path, mod_id)

    java_root = workspace_root / "src" / "main" / "java" / Path(*package_name.split("."))
    resources_root = workspace_root / "src" / "main" / "resources"
    assets_root = resources_root / "assets" / mod_id

    touched_files: list[Path] = []
    _ensure_fabric_api_dependency(workspace_root)

    mod_items_path = java_root / "item" / "ModItems.java"
    _write_mod_items(mod_items_path, package_name, main_class, mod_id, item_name, form_data)
    touched_files.append(mod_items_path)

    main_class_path = java_root / f"{main_class}.java"
    _update_main_class(main_class_path, package_name, main_class, mod_id)
    touched_files.append(main_class_path)

    model_path = assets_root / "models" / "item" / f"{item_name}.json"
    _write_json(
        model_path,
        {
            "parent": "item/generated",
            "textures": {
                "layer0": texture_path,
            },
        },
    )
    touched_files.append(model_path)

    if _as_bool(form_data.get("music_disc", False)):
        mod_sounds_path = java_root / "sound" / "ModSounds.java"
        _write_mod_sounds(mod_sounds_path, package_name, main_class, mod_id, item_name)
        touched_files.append(mod_sounds_path)

        music_discs_tag = resources_root / "data" / "minecraft" / "tags" / "items" / "music_discs.json"
        _update_tag_json(music_discs_tag, f"{mod_id}:{item_name}")
        touched_files.append(music_discs_tag)

        sounds_path = assets_root / "sounds.json"
        _update_sounds_json(
            sounds_path,
            item_name,
            _sound_file_identifier(form_data.get("music_disc_sound"), mod_id, item_name),
            form_data.get("music_disc_subtitle_key"),
        )
        touched_files.append(sounds_path)
        _update_main_class_for_sounds(main_class_path, package_name, main_class, mod_id)

    lang_path = assets_root / "lang" / "en_us.json"
    _update_lang(lang_path, f"item.{mod_id}.{item_name}", display_name)
    if _as_bool(form_data.get("music_disc", False)):
        _update_lang(
            lang_path,
            f"item.{mod_id}.{item_name}.desc",
            form_data.get("music_disc_description") or display_name,
        )
        _update_lang(
            lang_path,
            form_data.get("music_disc_subtitle_key"),
            form_data.get("music_disc_subtitle") or f"{display_name} plays",
        )
    touched_files.append(lang_path)

    base_root = workspace_root / "generated" / "item" / item_name
    base_root.mkdir(parents=True, exist_ok=True)

    generated_info = {
        "type": "item",
        "id": item_name,
        "display_name": display_name,
        "texture": texture_path,
        "form_data": form_data,
        "files": [_relative_to_workspace(path, workspace_root) for path in touched_files],
        "generator": {
            "id": tool.id,
            "name": tool.name,
            "version": tool.manifest.get("version", "unknown"),
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    _write_json(base_root / "generated_info.json", generated_info)


def delete(record: dict, workspace_root: Path, tool) -> None:
    item_name = safe_name(record.get("id", "unnamed_item"))
    project = _load_project_info(workspace_root)
    mod_id = safe_name(project.get("mod_id", workspace_root.name.lower()))
    package_name = _package_declaration(project, mod_id)
    main_class = _class_name(mod_id)
    java_root = workspace_root / "src" / "main" / "java" / Path(*package_name.split("."))
    resources_root = workspace_root / "src" / "main" / "resources"
    assets_root = resources_root / "assets" / mod_id

    _remove_mod_item(java_root / "item" / "ModItems.java", item_name)
    _remove_sound_event(java_root / "sound" / "ModSounds.java", item_name)
    _remove_sounds_json_entry(assets_root / "sounds.json", item_name)
    _remove_tag_json_entry(
        resources_root / "data" / "minecraft" / "tags" / "items" / "music_discs.json",
        f"{mod_id}:{item_name}",
    )
    _remove_lang_entry(assets_root / "lang" / "en_us.json", f"item.{mod_id}.{item_name}")
    _remove_lang_entry(assets_root / "lang" / "en_us.json", f"item.{mod_id}.{item_name}.desc")
    _remove_lang_entry(assets_root / "lang" / "en_us.json", f"subtitles.{mod_id}.{item_name}")

    model_path = assets_root / "models" / "item" / f"{item_name}.json"
    if model_path.exists():
        model_path.unlink()

    info_path = record.get("_info_path")
    if isinstance(info_path, Path) and info_path.exists():
        _remove_empty_generated_dir(info_path.parent)
    else:
        _remove_empty_generated_dir(workspace_root / "generated" / "item" / item_name)


def _load_project_info(workspace_root: Path) -> dict:
    path = workspace_root / "project_info.json"
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_mod_items(
    path: Path,
    package_name: str,
    main_class: str,
    mod_id: str,
    item_name: str,
    data: dict,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    field_name = _java_constant(item_name)
    field_line = _item_field_source(field_name, item_name, data)

    if not path.exists():
        path.write_text(
            _mod_items_source(package_name, main_class, mod_id, item_name, data),
            encoding="utf-8",
        )
        return

    content = path.read_text(encoding="utf-8")
    content = _ensure_imports(content, _item_imports(data, package_name))
    content = _upsert_creative_inventory_entry(content, field_name, data)

    field_pattern = (
        rf"    public static final Item {re.escape(field_name)} = "
        r"registerItem\([\s\S]*?\);\n"
    )
    if re.search(field_pattern, content):
        content = re.sub(field_pattern, field_line, content, count=1)
        path.write_text(content, encoding="utf-8")
        return

    marker = "    private static Item registerItem("
    if marker in content:
        content = content.replace(marker, field_line + "\n" + marker, 1)
    else:
        content = content.replace("\n}", "\n" + field_line + "}\n", 1)

    path.write_text(content, encoding="utf-8")


def _mod_items_source(
    package_name: str,
    main_class: str,
    mod_id: str,
    item_name: str,
    data: dict,
) -> str:
    field_name = _java_constant(item_name)
    imports = "\n".join(
        [
            f"import {package_name}.{main_class};",
            *_item_imports(data, package_name),
            "import net.minecraft.registry.Registries;",
            "import net.minecraft.registry.Registry;",
            "import net.minecraft.util.Identifier;",
        ]
    )
    return f"""package {package_name}.item;

{imports}

public class ModItems {{
{_item_field_source(field_name, item_name, data).rstrip()}

    private static Item registerItem(String name, Item item) {{
        return Registry.register(Registries.ITEM, new Identifier({main_class}.MOD_ID, name), item);
    }}

    public static void registerModItems() {{
{_creative_inventory_source(field_name, data)}\
        System.out.println("Registering items for {mod_id}");
    }}
}}
"""


def _update_main_class(path: Path, package_name: str, main_class: str, mod_id: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_main_class_source(package_name, main_class, mod_id), encoding="utf-8")
        return

    content = path.read_text(encoding="utf-8")
    import_line = f"import {package_name}.item.ModItems;"

    if import_line not in content:
        content = _insert_import(content, import_line)

    if "public static final String MOD_ID" not in content:
        class_marker = f"public class {main_class} implements ModInitializer {{"
        replacement = (
            f"{class_marker}\n"
            f'    public static final String MOD_ID = "{mod_id}";'
        )
        content = content.replace(class_marker, replacement, 1)

    call = "        ModItems.registerModItems();"
    if call not in content:
        content = _insert_on_initialize_call(content, call)

    path.write_text(content, encoding="utf-8")


def _main_class_source(package_name: str, main_class: str, mod_id: str) -> str:
    return f"""package {package_name};

import {package_name}.item.ModItems;
import net.fabricmc.api.ModInitializer;

public class {main_class} implements ModInitializer {{
    public static final String MOD_ID = "{mod_id}";

    @Override
    public void onInitialize() {{
        ModItems.registerModItems();
        System.out.println("{main_class} loaded.");
    }}
}}
"""


def _insert_import(content: str, import_line: str) -> str:
    imports = list(re.finditer(r"^import .+;$", content, flags=re.MULTILINE))
    if imports:
        last_import = imports[-1]
        return content[: last_import.end()] + "\n" + import_line + content[last_import.end() :]

    package_match = re.search(r"^package .+;$", content, flags=re.MULTILINE)
    if package_match:
        return content[: package_match.end()] + "\n\n" + import_line + content[package_match.end() :]

    return import_line + "\n" + content


def _insert_on_initialize_call(content: str, call: str) -> str:
    method_match = re.search(
        r"(public void onInitialize\(\) \{\n)",
        content,
        flags=re.MULTILINE,
    )
    if method_match:
        return content[: method_match.end()] + call + "\n" + content[method_match.end() :]

    return content


def _update_lang(path: Path, key: str, value: str) -> None:
    payload = {}

    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}

        if isinstance(existing, dict):
            payload = existing

    payload[key] = value
    _write_json(path, payload)


def _remove_lang_entry(path: Path, key: str) -> None:
    if not path.exists():
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    if not isinstance(payload, dict) or key not in payload:
        return

    del payload[key]
    _write_json(path, payload)


def _normalize_texture(texture: str | None, mod_id: str, item_name: str) -> str:
    if not texture:
        return f"{mod_id}:item/{item_name}"

    return texture.replace("\\", "/")


def _form_data(
    data: dict,
    item_name: str,
    display_name: str,
    texture_path: str,
    mod_id: str,
) -> dict:
    food_enabled = _as_bool(data.get("food_enabled", False))
    music_disc = _as_bool(data.get("music_disc", False))
    payload = {
        "registry_name": item_name,
        "display_name": display_name,
        "texture": texture_path,
        "max_stack_size": _clamped_int(data.get("max_stack_size", 64), 1, 64, 64),
        "creative_inventory": _creative_inventory(data.get("creative_inventory", "ingredients")),
        "music_disc": music_disc,
        "food_enabled": food_enabled,
    }

    if music_disc:
        payload.update(
            {
                "music_disc_sound": _normalize_sound_asset(data.get("music_disc_sound"), item_name),
                "music_disc_description": str(
                    data.get("music_disc_description") or display_name
                ),
                "music_disc_subtitle": str(
                    data.get("music_disc_subtitle") or f"{display_name} plays"
                ),
                "music_disc_subtitle_key": f"subtitles.{mod_id}.{item_name}",
                "music_disc_length_seconds": _as_int(
                    data.get("music_disc_length_seconds", 120),
                    120,
                ),
                "music_disc_comparator_output": _as_int(
                    data.get("music_disc_comparator_output", 1),
                    1,
                ),
            }
        )

    if food_enabled:
        payload.update(
            {
                "nutrition": _as_int(data.get("nutrition", 4), 4),
                "saturation_modifier": _as_float(data.get("saturation_modifier", 0.3), 0.3),
                "use_animation": _use_animation(data.get("use_animation", "eat")),
                "use_duration_ticks": _as_int(data.get("use_duration_ticks", 32), 32),
                "always_edible": _as_bool(data.get("always_edible", False)),
                "pet_food": _as_bool(data.get("pet_food", False)),
                "consumed_result_enabled": _as_bool(
                    data.get("consumed_result_enabled", False)
                ),
                "consumed_result_source": str(
                    data.get("consumed_result_source") or "vanilla"
                ),
                "consumed_result_item": _normalize_item_identifier(
                    data.get("consumed_result_item")
                ),
            }
        )

    return payload


def _item_imports(data: dict, package_name: str) -> list[str]:
    imports = [
        "import net.fabricmc.fabric.api.item.v1.FabricItemSettings;",
        "import net.minecraft.item.Item;",
    ]
    if _creative_inventory(data.get("creative_inventory", "ingredients")) != "none":
        imports.extend(
            [
                "import net.fabricmc.fabric.api.itemgroup.v1.ItemGroupEvents;",
                "import net.minecraft.item.ItemGroups;",
            ]
        )
    if _as_bool(data.get("music_disc", False)):
        imports.extend(
            [
                f"import {package_name}.sound.ModSounds;",
                "import net.minecraft.item.MusicDiscItem;",
            ]
        )
    if _as_bool(data.get("food_enabled", False)):
        imports.append("import net.minecraft.item.FoodComponent;")
        if _requires_custom_use(data):
            imports.extend(
                [
                    "import net.minecraft.item.ItemStack;",
                    "import net.minecraft.util.UseAction;",
                ]
            )
        if _has_consumed_result(data):
            imports.extend(
                [
                    "import net.minecraft.entity.LivingEntity;",
                    "import net.minecraft.entity.player.PlayerEntity;",
                    "import net.minecraft.item.ItemStack;",
                    "import net.minecraft.world.World;",
                ]
            )
    return _dedupe(imports)


def _ensure_imports(content: str, imports: list[str]) -> str:
    for import_line in imports:
        if import_line not in content:
            content = _insert_import(content, import_line)
    return content


def _item_field_source(field_name: str, item_name: str, data: dict) -> str:
    return (
        f'    public static final Item {field_name} = registerItem("{item_name}", '
        f"{_item_initializer(data)});\n"
    )


def _item_initializer(data: dict) -> str:
    settings = f"new FabricItemSettings().maxCount({_max_stack_size(data)})"
    if _as_bool(data.get("food_enabled", False)):
        settings += f".food({_food_component_source(data)})"

    if _as_bool(data.get("music_disc", False)):
        return (
            "new MusicDiscItem("
            f"{_as_int(data.get('music_disc_comparator_output', 1), 1)}, "
            f"ModSounds.{_java_constant(str(data.get('registry_name', 'unnamed_item')))}, "
            f"{settings}, "
            f"{_as_int(data.get('music_disc_length_seconds', 120), 120)}"
            ") {}"
        )

    item_source = f"new Item({settings})"
    if (
        not _as_bool(data.get("food_enabled", False))
        or (not _requires_custom_use(data) and not _has_consumed_result(data))
    ):
        return item_source

    overrides = []
    if _requires_custom_use(data):
        overrides.append(
            f"""        @Override
        public UseAction getUseAction(ItemStack stack) {{
            return UseAction.{_use_action(data)};
        }}

        @Override
        public int getMaxUseTime(ItemStack stack) {{
            return {_as_int(data.get("use_duration_ticks", 32), 32)};
        }}"""
        )

    if _has_consumed_result(data):
        overrides.append(_consumed_result_override(data))

    return f"""{item_source} {{
{chr(10).join(overrides)}
    }}"""

def _food_component_source(data: dict) -> str:
    builder = (
        "new FoodComponent.Builder()"
        f".hunger({_as_int(data.get('nutrition', 4), 4)})"
        f".saturationModifier({_float_literal(data.get('saturation_modifier', 0.3))})"
    )

    if _as_bool(data.get("always_edible", False)):
        builder += ".alwaysEdible()"

    if _as_bool(data.get("pet_food", False)):
        builder += ".meat()"

    return builder + ".build()"


def _max_stack_size(data: dict) -> int:
    return _clamped_int(data.get("max_stack_size", 64), 1, 64, 64)


def _has_consumed_result(data: dict) -> bool:
    return (
        _as_bool(data.get("food_enabled", False))
        and _as_bool(data.get("consumed_result_enabled", False))
        and bool(str(data.get("consumed_result_item", "")).strip())
    )


def _consumed_result_override(data: dict) -> str:
    item_id = _normalize_item_identifier(data.get("consumed_result_item"))
    return f"""        @Override
        public ItemStack finishUsing(ItemStack stack, World world, LivingEntity user) {{
            ItemStack result = super.finishUsing(stack, world, user);
            if (world.isClient) {{
                return result;
            }}

            ItemStack consumedResult = new ItemStack(Registries.ITEM.get(new Identifier("{item_id}")));
            if (result.isEmpty()) {{
                return consumedResult;
            }}

            if (user instanceof PlayerEntity player && !player.getInventory().insertStack(consumedResult)) {{
                player.dropItem(consumedResult, false);
            }}

            return result;
        }}"""


def _normalize_item_identifier(value) -> str:
    text = str(value or "").strip().lower().replace("\\", "/")
    if ":" not in text:
        return ""

    namespace, path = text.split(":", 1)
    namespace = safe_name(namespace)
    path = re.sub(r"[^a-z0-9_./-]+", "_", path).strip("_/")
    if not namespace or not path:
        return ""
    return f"{namespace}:{path}"


def _creative_inventory(value) -> str:
    normalized = safe_name(str(value or "ingredients"))
    return normalized if normalized in _creative_inventory_groups() else "ingredients"


def _creative_inventory_groups() -> dict[str, str]:
    return {
        "ingredients": "INGREDIENTS",
        "combat": "COMBAT",
        "tools": "TOOLS",
        "food_and_drink": "FOOD_AND_DRINK",
        "building_blocks": "BUILDING_BLOCKS",
        "natural": "NATURAL",
        "functional": "FUNCTIONAL",
        "redstone": "REDSTONE",
        "colored_blocks": "COLORED_BLOCKS",
        "operator": "OPERATOR",
        "none": "",
    }


def _creative_inventory_source(field_name: str, data: dict) -> str:
    creative_inventory = _creative_inventory(data.get("creative_inventory", "ingredients"))
    group = _creative_inventory_groups().get(creative_inventory, "")
    if not group:
        return ""

    return (
        f"        ItemGroupEvents.modifyEntriesEvent(ItemGroups.{group})"
        f".register(entries -> entries.add({field_name}));\n"
    )


def _upsert_creative_inventory_entry(content: str, field_name: str, data: dict) -> str:
    pattern = (
        r"        ItemGroupEvents\.modifyEntriesEvent\(ItemGroups\.[A-Z_]+\)"
        rf"\.register\(entries -> entries\.add\({re.escape(field_name)}\)\);\n"
    )
    content = re.sub(pattern, "", content)
    line = _creative_inventory_source(field_name, data)
    if not line:
        return content

    marker = "        System.out.println("
    if marker in content:
        return content.replace(marker, line + marker, 1)

    return content


def _write_mod_sounds(
    path: Path,
    package_name: str,
    main_class: str,
    mod_id: str,
    item_name: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    field_name = _java_constant(item_name)
    field_line = (
        f'    public static final SoundEvent {field_name} = registerSoundEvent("{item_name}");\n'
    )

    if not path.exists():
        path.write_text(
            _mod_sounds_source(package_name, main_class, mod_id, field_line),
            encoding="utf-8",
        )
        return

    content = path.read_text(encoding="utf-8")
    field_pattern = (
        rf"    public static final SoundEvent {re.escape(field_name)} = "
        r"registerSoundEvent\(\"[^\"]+\"\);\n"
    )
    if re.search(field_pattern, content):
        content = re.sub(field_pattern, field_line, content, count=1)
    else:
        marker = "    private static SoundEvent registerSoundEvent("
        content = content.replace(marker, field_line + "\n" + marker, 1)

    path.write_text(content, encoding="utf-8")


def _mod_sounds_source(
    package_name: str,
    main_class: str,
    mod_id: str,
    field_line: str,
) -> str:
    return f"""package {package_name}.sound;

import {package_name}.{main_class};
import net.minecraft.registry.Registries;
import net.minecraft.registry.Registry;
import net.minecraft.sound.SoundEvent;
import net.minecraft.util.Identifier;

public class ModSounds {{
{field_line.rstrip()}

    private static SoundEvent registerSoundEvent(String name) {{
        Identifier id = new Identifier({main_class}.MOD_ID, name);
        return Registry.register(Registries.SOUND_EVENT, id, SoundEvent.of(id));
    }}

    public static void registerSoundEvents() {{
        System.out.println("Registering sounds for {mod_id}");
    }}
}}
"""


def _update_main_class_for_sounds(
    path: Path,
    package_name: str,
    main_class: str,
    mod_id: str,
) -> None:
    _update_main_class(path, package_name, main_class, mod_id)
    content = path.read_text(encoding="utf-8")
    import_line = f"import {package_name}.sound.ModSounds;"

    if import_line not in content:
        content = _insert_import(content, import_line)

    call = "        ModSounds.registerSoundEvents();"
    if call not in content:
        content = _insert_on_initialize_call(content, call)

    path.write_text(content, encoding="utf-8")


def _update_sounds_json(
    path: Path,
    sound_event: str,
    sound_file: str,
    subtitle_key: str | None,
) -> None:
    payload = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if isinstance(existing, dict):
            payload = existing

    sound_payload = {
        "sounds": [
            {
                "name": sound_file,
                "stream": True,
            }
        ]
    }
    if subtitle_key:
        sound_payload["subtitle"] = subtitle_key

    payload[sound_event] = sound_payload
    _write_json(path, payload)


def _remove_sound_event(path: Path, item_name: str) -> None:
    if not path.exists():
        return

    field_name = _java_constant(item_name)
    content = path.read_text(encoding="utf-8")
    pattern = (
        rf"\n?    public static final SoundEvent {re.escape(field_name)} = "
        r"registerSoundEvent\(\"[^\"]+\"\);\n"
    )
    updated = re.sub(pattern, "\n", content, count=1)
    updated = re.sub(r"\n{3,}", "\n\n", updated)
    if updated != content:
        path.write_text(updated, encoding="utf-8")


def _remove_sounds_json_entry(path: Path, sound_event: str) -> None:
    if not path.exists():
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    if not isinstance(payload, dict) or sound_event not in payload:
        return

    del payload[sound_event]
    _write_json(path, payload)


def _update_tag_json(path: Path, identifier: str) -> None:
    payload = {"replace": False, "values": []}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if isinstance(existing, dict):
            payload["replace"] = bool(existing.get("replace", False))
            values = existing.get("values", [])
            if isinstance(values, list):
                payload["values"] = [value for value in values if isinstance(value, str)]

    if identifier not in payload["values"]:
        payload["values"].append(identifier)

    _write_json(path, payload)


def _remove_tag_json_entry(path: Path, identifier: str) -> None:
    if not path.exists():
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    if not isinstance(payload, dict):
        return

    values = payload.get("values", [])
    if not isinstance(values, list) or identifier not in values:
        return

    payload["values"] = [value for value in values if value != identifier]
    _write_json(path, payload)


def _normalize_sound_asset(value, item_name: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    return text or f"sounds/{item_name}"


def _sound_file_identifier(value, mod_id: str, item_name: str) -> str:
    text = _normalize_sound_asset(value, item_name)
    namespace = mod_id
    path = text

    if ":" in text:
        namespace, path = text.split(":", 1)

    if path.startswith("sounds/"):
        path = path[len("sounds/") :]

    return f"{safe_name(namespace)}:{path}"


def _requires_custom_use(data: dict) -> bool:
    if not _as_bool(data.get("food_enabled", False)):
        return False

    return (
        _use_animation(data.get("use_animation", "eat")) != "eat"
        or _as_int(data.get("use_duration_ticks", 32), 32) != 32
    )


def _use_action(data: dict) -> str:
    return "DRINK" if _use_animation(data.get("use_animation", "eat")) == "drink" else "EAT"


def _use_animation(value) -> str:
    normalized = str(value or "eat").strip().lower()
    return "drink" if normalized == "drink" else "eat"


def _remove_mod_item(path: Path, item_name: str) -> None:
    if not path.exists():
        return

    field_name = _java_constant(item_name)
    content = path.read_text(encoding="utf-8")
    pattern = (
        rf"\n?    public static final Item {re.escape(field_name)} = "
        r"registerItem\([\s\S]*?\);\n"
    )
    updated = re.sub(pattern, "\n", content, count=1)
    creative_pattern = (
        r"        ItemGroupEvents\.modifyEntriesEvent\(ItemGroups\.[A-Z_]+\)"
        rf"\.register\(entries -> entries\.add\({re.escape(field_name)}\)\);\n"
    )
    updated = re.sub(creative_pattern, "", updated)
    updated = re.sub(r"\n{3,}", "\n\n", updated)

    if updated != content:
        path.write_text(updated, encoding="utf-8")


def _remove_empty_generated_dir(path: Path) -> None:
    if not path.exists():
        return

    for child in path.rglob("*"):
        if child.is_file():
            child.unlink()

    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_dir():
            child.rmdir()

    path.rmdir()


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_int(value, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _clamped_int(value, minimum: int, maximum: int, default: int) -> int:
    return max(minimum, min(maximum, _as_int(value, default)))


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _float_literal(value) -> str:
    return f"{_as_float(value, 0.0):g}F"


def _ensure_fabric_api_dependency(workspace_root: Path) -> None:
    _ensure_gradle_fabric_api(workspace_root / "build.gradle")
    _ensure_gradle_property(workspace_root / "gradle.properties")
    _ensure_fabric_mod_dependency(
        workspace_root / "src" / "main" / "resources" / "fabric.mod.json"
    )


def _ensure_gradle_fabric_api(path: Path) -> None:
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8")
    if "net.fabricmc.fabric-api:fabric-api" in content:
        return

    dependency = '    modImplementation "net.fabricmc.fabric-api:fabric-api:${project.fabric_api_version}"\n'
    loader_dependency = re.search(
        r'^[ \t]*modImplementation "net\.fabricmc:fabric-loader:\$\{project\.loader_version\}"[ \t]*$',
        content,
        flags=re.MULTILINE,
    )
    if loader_dependency:
        insert_at = loader_dependency.end()
        content = content[:insert_at] + "\n\n" + dependency.rstrip("\n") + content[insert_at:]
    else:
        dependencies_block = re.search(r"dependencies\s*\{\n", content)
        if not dependencies_block:
            return
        content = (
            content[: dependencies_block.end()]
            + "\n"
            + dependency
            + content[dependencies_block.end() :]
        )

    path.write_text(content, encoding="utf-8")


def _ensure_gradle_property(path: Path) -> None:
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8")
    if re.search(r"^fabric_api_version=", content, flags=re.MULTILINE):
        return

    content = content.rstrip() + f"\nfabric_api_version={FABRIC_API_VERSION}\n"
    path.write_text(content, encoding="utf-8")


def _ensure_fabric_mod_dependency(path: Path) -> None:
    if not path.exists():
        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    if not isinstance(payload, dict):
        return

    depends = payload.setdefault("depends", {})
    if not isinstance(depends, dict):
        depends = {}
        payload["depends"] = depends

    if "fabric-api" in depends:
        return

    depends["fabric-api"] = "*"
    _write_json(path, payload)


def _package_declaration(project: dict, mod_id: str) -> str:
    package_root = str(project.get("package_root") or "com")
    package_name = str(project.get("package_name") or mod_id)
    return ".".join(package_root.split(".") + package_name.split("."))


def _class_name(mod_id: str) -> str:
    return "".join(part.capitalize() for part in mod_id.split("_")) + "Mod"


def _java_constant(value: str) -> str:
    constant = re.sub(r"[^A-Z0-9_]+", "_", value.upper()).strip("_")
    if not constant:
        return "UNNAMED_ITEM"
    if constant[0].isdigit():
        constant = f"ITEM_{constant}"
    return constant


def _title_from_id(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_"))


def _relative_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.relative_to(workspace_root).as_posix()
    except ValueError:
        return path.as_posix()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
