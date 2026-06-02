# generator.py
# developer: SuperHeroPuppy
# version: 1.0.0
# generator type: block

from __future__ import annotations

from datetime import datetime
import json
import re
from pathlib import Path


FABRIC_API_VERSION = "0.92.9+1.20.1"
BLOCK_SIDES = ("top", "bottom", "north", "south", "east", "west")


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", str(name).strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "unnamed_block"


def generate(data: dict, workspace_root: Path, tool) -> None:
    block_name = safe_name(data.get("registry_name", "unnamed_block"))
    display_name = data.get("display_name") or _title_from_id(block_name)
    project = _load_project_info(workspace_root)
    mod_id = safe_name(project.get("mod_id", workspace_root.name.lower()))
    package_name = _package_declaration(project, mod_id)
    main_class = _class_name(mod_id)
    form_data = _form_data(data, block_name, display_name, mod_id)

    java_root = workspace_root / "src" / "main" / "java" / Path(*package_name.split("."))
    resources_root = workspace_root / "src" / "main" / "resources"
    assets_root = resources_root / "assets" / mod_id

    touched_files: list[Path] = []
    _ensure_fabric_api_dependency(workspace_root)

    mod_blocks_path = java_root / "block" / "ModBlocks.java"
    _write_mod_blocks(mod_blocks_path, package_name, main_class, mod_id, block_name, form_data)
    touched_files.append(mod_blocks_path)

    main_class_path = java_root / f"{main_class}.java"
    _update_main_class(main_class_path, package_name, main_class, mod_id)
    touched_files.append(main_class_path)

    blockstate_path = assets_root / "blockstates" / f"{block_name}.json"
    _write_json(
        blockstate_path,
        _blockstate_payload(mod_id, block_name, form_data),
    )
    touched_files.append(blockstate_path)

    block_model_path = assets_root / "models" / "block" / f"{block_name}.json"
    _write_json(
        block_model_path,
        {
            "parent": "minecraft:block/cube",
            "textures": {
                "up": form_data["block_textures"]["top"],
                "down": form_data["block_textures"]["bottom"],
                "north": form_data["block_textures"]["north"],
                "south": form_data["block_textures"]["south"],
                "east": form_data["block_textures"]["east"],
                "west": form_data["block_textures"]["west"],
                "particle": form_data["block_textures"]["top"],
            },
        },
    )
    touched_files.append(block_model_path)

    item_model_path = assets_root / "models" / "item" / f"{block_name}.json"
    _write_json(item_model_path, {"parent": f"{mod_id}:block/{block_name}"})
    touched_files.append(item_model_path)

    lang_path = assets_root / "lang" / "en_us.json"
    _update_lang(lang_path, f"block.{mod_id}.{block_name}", display_name)
    touched_files.append(lang_path)

    tag_paths = _write_mining_tags(resources_root, mod_id, block_name, form_data)
    touched_files.extend(tag_paths)

    base_root = workspace_root / "generated" / "block" / block_name
    base_root.mkdir(parents=True, exist_ok=True)
    generated_info = {
        "type": "block",
        "id": block_name,
        "display_name": display_name,
        "block_textures": form_data["block_textures"],
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
    block_name = safe_name(record.get("id", "unnamed_block"))
    project = _load_project_info(workspace_root)
    mod_id = safe_name(project.get("mod_id", workspace_root.name.lower()))
    package_name = _package_declaration(project, mod_id)
    java_root = workspace_root / "src" / "main" / "java" / Path(*package_name.split("."))
    resources_root = workspace_root / "src" / "main" / "resources"
    assets_root = resources_root / "assets" / mod_id

    _remove_mod_block(java_root / "block" / "ModBlocks.java", block_name)
    _remove_lang_entry(assets_root / "lang" / "en_us.json", f"block.{mod_id}.{block_name}")
    _remove_mining_tags(resources_root, mod_id, block_name)

    for path in (
        assets_root / "blockstates" / f"{block_name}.json",
        assets_root / "models" / "block" / f"{block_name}.json",
        assets_root / "models" / "item" / f"{block_name}.json",
    ):
        if path.exists():
            path.unlink()

    info_path = record.get("_info_path")
    if isinstance(info_path, Path) and info_path.exists():
        _remove_empty_generated_dir(info_path.parent)
    else:
        _remove_empty_generated_dir(workspace_root / "generated" / "block" / block_name)


def _form_data(data: dict, block_name: str, display_name: str, mod_id: str) -> dict:
    textures = data.get("block_textures")
    if not isinstance(textures, dict):
        textures = {}

    normalized_textures = {}
    fallback = f"{mod_id}:block/{block_name}"
    for side in BLOCK_SIDES:
        normalized_textures[side] = _normalize_texture(textures.get(side), fallback)

    return {
        "registry_name": block_name,
        "display_name": display_name,
        "block_textures": normalized_textures,
        "creative_inventory": _creative_inventory(data.get("creative_inventory", "building_blocks")),
        "max_stack_size": _clamped_int(data.get("max_stack_size", 64), 1, 64, 64),
        "hardness": _as_float(data.get("hardness", 1.5), 1.5),
        "resistance": _as_float(data.get("resistance", 6.0), 6.0),
        "sound_group": _sound_group(data.get("sound_group", "stone")),
        "tool_type": _tool_type(data.get("tool_type", "none")),
        "tool_level": _tool_level(data.get("tool_level", "none")),
        "rotation_mode": _rotation_mode(data.get("rotation_mode", "none")),
        "requires_tool": _as_bool(data.get("requires_tool", False)),
    }


def _write_mod_blocks(
    path: Path,
    package_name: str,
    main_class: str,
    mod_id: str,
    block_name: str,
    data: dict,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    field_name = _java_constant(block_name)
    field_line = _block_field_source(field_name, block_name, data)

    if not path.exists():
        path.write_text(
            _mod_blocks_source(package_name, main_class, mod_id, block_name, data),
            encoding="utf-8",
        )
        return

    content = path.read_text(encoding="utf-8")
    content = _ensure_imports(content, _block_imports())
    content = _upsert_creative_inventory_entry(content, field_name, data)
    content = _upsert_horizontal_block_class(content, data)

    field_pattern = (
        rf"    public static final Block {re.escape(field_name)} = "
        r"registerBlock\([\s\S]*?\);\n"
    )
    if re.search(field_pattern, content):
        content = re.sub(field_pattern, field_line, content, count=1)
        path.write_text(content, encoding="utf-8")
        return

    marker = "    private static Block registerBlock("
    if marker in content:
        content = content.replace(marker, field_line + "\n" + marker, 1)
    else:
        content = content.replace("\n}", "\n" + field_line + "}\n", 1)

    path.write_text(content, encoding="utf-8")


def _mod_blocks_source(
    package_name: str,
    main_class: str,
    mod_id: str,
    block_name: str,
    data: dict,
) -> str:
    field_name = _java_constant(block_name)
    imports = "\n".join(
        [
            f"import {package_name}.{main_class};",
            *_block_imports(),
        ]
    )
    return f"""package {package_name}.block;

{imports}

public class ModBlocks {{
{_block_field_source(field_name, block_name, data).rstrip()}

    private static Block registerBlock(String name, Block block, int maxCount) {{
        Registry.register(Registries.ITEM, new Identifier({main_class}.MOD_ID, name), new BlockItem(block, new FabricItemSettings().maxCount(maxCount)));
        return Registry.register(Registries.BLOCK, new Identifier({main_class}.MOD_ID, name), block);
    }}

    public static void registerModBlocks() {{
{_creative_inventory_source(field_name, data)}\
        System.out.println("Registering blocks for {mod_id}");
    }}
{_horizontal_block_class_source(data)}
}}
"""


def _block_imports() -> list[str]:
    return [
        "import net.fabricmc.fabric.api.item.v1.FabricItemSettings;",
        "import net.fabricmc.fabric.api.itemgroup.v1.ItemGroupEvents;",
        "import net.minecraft.block.AbstractBlock;",
        "import net.minecraft.block.Block;",
        "import net.minecraft.block.BlockSoundGroup;",
        "import net.minecraft.block.BlockState;",
        "import net.minecraft.block.HorizontalFacingBlock;",
        "import net.minecraft.block.PillarBlock;",
        "import net.minecraft.item.BlockItem;",
        "import net.minecraft.item.ItemGroups;",
        "import net.minecraft.item.ItemPlacementContext;",
        "import net.minecraft.registry.Registries;",
        "import net.minecraft.registry.Registry;",
        "import net.minecraft.state.StateManager;",
        "import net.minecraft.util.Identifier;",
        "import net.minecraft.util.math.Direction;",
    ]


def _block_field_source(field_name: str, block_name: str, data: dict) -> str:
    return (
        f'    public static final Block {field_name} = registerBlock("{block_name}", '
        f"{_block_initializer(data)}, {_clamped_int(data.get('max_stack_size', 64), 1, 64, 64)});\n"
    )


def _block_initializer(data: dict) -> str:
    settings = (
        "AbstractBlock.Settings.create()"
        f".strength({_float_literal(data.get('hardness', 1.5))}, {_float_literal(data.get('resistance', 6.0))})"
        f".sounds(BlockSoundGroup.{_sound_group_constant(data.get('sound_group', 'stone'))})"
    )
    if _as_bool(data.get("requires_tool", False)) or data.get("tool_type") != "none" or data.get("tool_level") != "none":
        settings += ".requiresTool()"

    rotation_mode = _rotation_mode(data.get("rotation_mode", "none"))
    if rotation_mode == "face_player":
        return f"new GeneratedHorizontalFacingBlock({settings})"
    if rotation_mode == "pillar":
        return f"new PillarBlock({settings})"
    return f"new Block({settings})"


def _horizontal_block_class_source(data: dict) -> str:
    if _rotation_mode(data.get("rotation_mode", "none")) != "face_player":
        return ""

    return """

    private static class GeneratedHorizontalFacingBlock extends HorizontalFacingBlock {
        GeneratedHorizontalFacingBlock(AbstractBlock.Settings settings) {
            super(settings);
            setDefaultState(getStateManager().getDefaultState().with(FACING, Direction.NORTH));
        }

        @Override
        public BlockState getPlacementState(ItemPlacementContext context) {
            return getDefaultState().with(FACING, context.getHorizontalPlayerFacing().getOpposite());
        }

        @Override
        protected void appendProperties(StateManager.Builder<Block, BlockState> builder) {
            builder.add(FACING);
        }
    }
"""


def _upsert_horizontal_block_class(content: str, data: dict) -> str:
    pattern = (
        r"\n    private static class GeneratedHorizontalFacingBlock "
        r"extends HorizontalFacingBlock \{[\s\S]*?\n    \}\n"
    )
    content = re.sub(pattern, "", content)
    helper = _horizontal_block_class_source(data)
    if not helper and "new GeneratedHorizontalFacingBlock(" in content:
        helper = _horizontal_block_class_source({"rotation_mode": "face_player"})
    if not helper:
        return content

    return content.replace("\n}\n", helper + "}\n", 1)


def _update_main_class(path: Path, package_name: str, main_class: str, mod_id: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_main_class_source(package_name, main_class, mod_id), encoding="utf-8")
        return

    content = path.read_text(encoding="utf-8")
    import_line = f"import {package_name}.block.ModBlocks;"
    if import_line not in content:
        content = _insert_import(content, import_line)

    if "public static final String MOD_ID" not in content:
        class_marker = f"public class {main_class} implements ModInitializer {{"
        replacement = (
            f"{class_marker}\n"
            f'    public static final String MOD_ID = "{mod_id}";'
        )
        content = content.replace(class_marker, replacement, 1)

    call = "        ModBlocks.registerModBlocks();"
    if call not in content:
        content = _insert_on_initialize_call(content, call)

    path.write_text(content, encoding="utf-8")


def _main_class_source(package_name: str, main_class: str, mod_id: str) -> str:
    return f"""package {package_name};

import {package_name}.block.ModBlocks;
import net.fabricmc.api.ModInitializer;

public class {main_class} implements ModInitializer {{
    public static final String MOD_ID = "{mod_id}";

    @Override
    public void onInitialize() {{
        ModBlocks.registerModBlocks();
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


def _ensure_imports(content: str, imports: list[str]) -> str:
    for import_line in imports:
        if import_line not in content:
            content = _insert_import(content, import_line)
    return content


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


def _creative_inventory_source(field_name: str, data: dict) -> str:
    creative_inventory = _creative_inventory(data.get("creative_inventory", "building_blocks"))
    group = _creative_inventory_groups().get(creative_inventory, "")
    if not group:
        return ""

    return (
        f"        ItemGroupEvents.modifyEntriesEvent(ItemGroups.{group})"
        f".register(entries -> entries.add({field_name}));\n"
    )


def _creative_inventory(value) -> str:
    normalized = safe_name(str(value or "building_blocks"))
    return normalized if normalized in _creative_inventory_groups() else "building_blocks"


def _creative_inventory_groups() -> dict[str, str]:
    return {
        "building_blocks": "BUILDING_BLOCKS",
        "natural": "NATURAL",
        "functional": "FUNCTIONAL",
        "redstone": "REDSTONE",
        "colored_blocks": "COLORED_BLOCKS",
        "ingredients": "INGREDIENTS",
        "combat": "COMBAT",
        "tools": "TOOLS",
        "operator": "OPERATOR",
        "none": "",
    }


def _blockstate_payload(mod_id: str, block_name: str, data: dict) -> dict:
    model = f"{mod_id}:block/{block_name}"
    rotation_mode = _rotation_mode(data.get("rotation_mode", "none"))
    if rotation_mode == "face_player":
        return {
            "variants": {
                "facing=north": {"model": model},
                "facing=east": {"model": model, "y": 90},
                "facing=south": {"model": model, "y": 180},
                "facing=west": {"model": model, "y": 270},
            }
        }

    if rotation_mode == "pillar":
        return {
            "variants": {
                "axis=y": {"model": model},
                "axis=x": {"model": model, "x": 90, "y": 90},
                "axis=z": {"model": model, "x": 90},
            }
        }

    return {"variants": {"": {"model": model}}}


def _write_mining_tags(resources_root: Path, mod_id: str, block_name: str, data: dict) -> list[Path]:
    identifier = f"{mod_id}:{block_name}"
    touched: list[Path] = []
    tool_type = _tool_type(data.get("tool_type", "none"))
    if tool_type != "none":
        path = resources_root / "data" / "minecraft" / "tags" / "blocks" / "mineable" / f"{tool_type}.json"
        _update_tag_json(path, identifier)
        touched.append(path)

    tool_level = _tool_level(data.get("tool_level", "none"))
    level_tag = _tool_level_tag(tool_level)
    if level_tag:
        path = resources_root / "data" / "minecraft" / "tags" / "blocks" / f"{level_tag}.json"
        _update_tag_json(path, identifier)
        touched.append(path)

    return touched


def _remove_mining_tags(resources_root: Path, mod_id: str, block_name: str) -> None:
    identifier = f"{mod_id}:{block_name}"
    for tool in ("pickaxe", "axe", "shovel", "hoe"):
        _remove_tag_json_entry(
            resources_root / "data" / "minecraft" / "tags" / "blocks" / "mineable" / f"{tool}.json",
            identifier,
        )

    for level_tag in ("needs_stone_tool", "needs_iron_tool", "needs_diamond_tool"):
        _remove_tag_json_entry(
            resources_root / "data" / "minecraft" / "tags" / "blocks" / f"{level_tag}.json",
            identifier,
        )


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


def _sound_group(value) -> str:
    normalized = safe_name(str(value or "stone"))
    return normalized if normalized in _sound_groups() else "stone"


def _sound_groups() -> dict[str, str]:
    return {
        "stone": "STONE",
        "wood": "WOOD",
        "deepslate": "DEEPSLATE",
        "gravel": "GRAVEL",
        "grass": "GRASS",
        "sand": "SAND",
        "metal": "METAL",
        "glass": "GLASS",
        "wool": "WOOL",
        "copper": "COPPER",
        "amethyst_block": "AMETHYST_BLOCK",
        "calcite": "CALCITE",
        "mud": "MUD",
    }


def _sound_group_constant(value) -> str:
    return _sound_groups()[_sound_group(value)]


def _tool_type(value) -> str:
    normalized = safe_name(str(value or "none"))
    return normalized if normalized in {"none", "pickaxe", "axe", "shovel", "hoe"} else "none"


def _tool_level(value) -> str:
    normalized = safe_name(str(value or "none"))
    return normalized if normalized in {"none", "wood", "stone", "iron", "diamond", "netherite"} else "none"


def _tool_level_tag(value: str) -> str:
    level = _tool_level(value)
    if level == "stone":
        return "needs_stone_tool"
    if level == "iron":
        return "needs_iron_tool"
    if level in {"diamond", "netherite"}:
        return "needs_diamond_tool"
    return ""


def _rotation_mode(value) -> str:
    normalized = safe_name(str(value or "none"))
    return normalized if normalized in {"none", "face_player", "pillar"} else "none"


def _remove_mod_block(path: Path, block_name: str) -> None:
    if not path.exists():
        return

    field_name = _java_constant(block_name)
    content = path.read_text(encoding="utf-8")
    field_pattern = (
        rf"\n?    public static final Block {re.escape(field_name)} = "
        r"registerBlock\([\s\S]*?\);\n"
    )
    updated = re.sub(field_pattern, "\n", content, count=1)
    creative_pattern = (
        r"        ItemGroupEvents\.modifyEntriesEvent\(ItemGroups\.[A-Z_]+\)"
        rf"\.register\(entries -> entries\.add\({re.escape(field_name)}\)\);\n"
    )
    updated = re.sub(creative_pattern, "", updated)
    updated = re.sub(r"\n{3,}", "\n\n", updated)
    if updated != content:
        path.write_text(updated, encoding="utf-8")


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


def _normalize_texture(texture: str | None, fallback: str) -> str:
    if not texture:
        return fallback
    return str(texture).replace("\\", "/")


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
        content = content[: dependencies_block.end()] + "\n" + dependency + content[dependencies_block.end() :]
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
        return "UNNAMED_BLOCK"
    if constant[0].isdigit():
        constant = f"BLOCK_{constant}"
    return constant


def _title_from_id(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_"))


def _float_literal(value) -> str:
    return f"{_as_float(value, 0.0):g}F"


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _clamped_int(value, minimum: int, maximum: int, default: int) -> int:
    return max(minimum, min(maximum, _as_int(value, default)))


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _relative_to_workspace(path: Path, workspace_root: Path) -> str:
    try:
        return path.relative_to(workspace_root).as_posix()
    except ValueError:
        return path.as_posix()


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
