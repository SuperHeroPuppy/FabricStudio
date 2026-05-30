# generator.py
# developer: SuperHeroPuppy
# version: 1.0.3
# generator type: item

from __future__ import annotations

from datetime import datetime
import json
import re
from pathlib import Path


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
    form_data = {
        "registry_name": item_name,
        "display_name": display_name,
        "texture": texture_path,
    }

    java_root = workspace_root / "src" / "main" / "java" / Path(*package_name.split("."))
    resources_root = workspace_root / "src" / "main" / "resources"
    assets_root = resources_root / "assets" / mod_id

    touched_files: list[Path] = []

    mod_items_path = java_root / "item" / "ModItems.java"
    _write_mod_items(mod_items_path, package_name, main_class, mod_id, item_name)
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

    lang_path = assets_root / "lang" / "en_us.json"
    _update_lang(lang_path, f"item.{mod_id}.{item_name}", display_name)
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
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    field_name = _java_constant(item_name)

    if not path.exists():
        path.write_text(
            _mod_items_source(package_name, main_class, mod_id, item_name),
            encoding="utf-8",
        )
        return

    content = path.read_text(encoding="utf-8")
    if f" {field_name} " in content or f" {field_name}=" in content:
        return

    field_line = (
        f'    public static final Item {field_name} = registerItem("{item_name}", '
        "new Item(new Item.Settings()));\n"
    )

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
) -> str:
    field_name = _java_constant(item_name)
    return f"""package {package_name}.item;

import {package_name}.{main_class};
import net.minecraft.item.Item;
import net.minecraft.registry.Registries;
import net.minecraft.registry.Registry;
import net.minecraft.util.Identifier;

public class ModItems {{
    public static final Item {field_name} = registerItem("{item_name}", new Item(new Item.Settings()));

    private static Item registerItem(String name, Item item) {{
        return Registry.register(Registries.ITEM, new Identifier({main_class}.MOD_ID, name), item);
    }}

    public static void registerModItems() {{
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


def _normalize_texture(texture: str | None, mod_id: str, item_name: str) -> str:
    if not texture:
        return f"{mod_id}:item/{item_name}"

    return texture.replace("\\", "/")


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
