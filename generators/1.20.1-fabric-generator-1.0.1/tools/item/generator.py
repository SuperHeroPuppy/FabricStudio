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
    form_data = _form_data(data, item_name, display_name, texture_path)

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
    _remove_lang_entry(assets_root / "lang" / "en_us.json", f"item.{mod_id}.{item_name}")

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
    content = _ensure_imports(content, _item_imports(data))

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
            *_item_imports(data),
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


def _form_data(data: dict, item_name: str, display_name: str, texture_path: str) -> dict:
    food_enabled = _as_bool(data.get("food_enabled", False))
    payload = {
        "registry_name": item_name,
        "display_name": display_name,
        "texture": texture_path,
        "food_enabled": food_enabled,
    }

    if food_enabled:
        payload.update(
            {
                "nutrition": _as_int(data.get("nutrition", 4), 4),
                "saturation_modifier": _as_float(data.get("saturation_modifier", 0.3), 0.3),
                "use_animation": _use_animation(data.get("use_animation", "eat")),
                "use_duration_ticks": _as_int(data.get("use_duration_ticks", 32), 32),
                "always_edible": _as_bool(data.get("always_edible", False)),
                "pet_food": _as_bool(data.get("pet_food", False)),
            }
        )

    return payload


def _item_imports(data: dict) -> list[str]:
    imports = [
        "import net.fabricmc.fabric.api.item.v1.FabricItemSettings;",
        "import net.minecraft.item.Item;",
    ]
    if _as_bool(data.get("food_enabled", False)):
        imports.append("import net.minecraft.item.FoodComponent;")
        if _requires_custom_use(data):
            imports.extend(
                [
                    "import net.minecraft.item.ItemStack;",
                    "import net.minecraft.util.UseAction;",
                ]
            )
    return imports


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
    settings = "new FabricItemSettings()"
    if _as_bool(data.get("food_enabled", False)):
        settings += f".food({_food_component_source(data)})"

    item_source = f"new Item({settings})"
    if not _as_bool(data.get("food_enabled", False)) or not _requires_custom_use(data):
        return item_source

    return f"""{item_source} {{
        @Override
        public UseAction getUseAction(ItemStack stack) {{
            return UseAction.{_use_action(data)};
        }}

        @Override
        public int getMaxUseTime(ItemStack stack) {{
            return {_as_int(data.get("use_duration_ticks", 32), 32)};
        }}
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
