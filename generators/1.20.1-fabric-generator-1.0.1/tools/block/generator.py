# generator.py
# developer: SuperHeroPuppy
# version: 1.0.0
# generator type: block

from __future__ import annotations

from datetime import datetime
import json
import re
from pathlib import Path

from core.creative_tabs import creative_tabs, custom_tab_id, write_creative_entries, write_custom_creative_tabs


FABRIC_API_VERSION = "0.92.9+1.20.1"
BLOCK_SIDES = ("top", "bottom", "north", "south", "east", "west")
DEFAULT_BLOCK_MODELS = {
    "cube",
    "stairs",
    "slab",
    "fence",
    "fence_gate",
    "door",
    "trapdoor",
    "pane",
    "wall",
}


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
    form_data = _form_data(data, block_name, display_name, mod_id, project)

    java_root = workspace_root / "src" / "main" / "java" / Path(*package_name.split("."))
    resources_root = workspace_root / "src" / "main" / "resources"
    assets_root = resources_root / "assets" / mod_id

    touched_files: list[Path] = []
    _ensure_fabric_api_dependency(workspace_root)
    item_groups_path = write_custom_creative_tabs(workspace_root, project)
    if item_groups_path:
        touched_files.append(item_groups_path)

    mod_blocks_path = java_root / "block" / "ModBlocks.java"
    _write_mod_blocks(mod_blocks_path, package_name, main_class, mod_id, block_name, form_data, project)
    touched_files.append(mod_blocks_path)

    main_class_path = java_root / f"{main_class}.java"
    _update_main_class(main_class_path, package_name, main_class, mod_id, project)
    touched_files.append(main_class_path)

    blockstate_path = assets_root / "blockstates" / f"{block_name}.json"
    block_model_id = _block_model_reference(mod_id, block_name, form_data)
    _write_json(
        blockstate_path,
        _blockstate_payload(block_model_id, form_data),
    )
    touched_files.append(blockstate_path)

    touched_files.extend(_write_block_models(assets_root, mod_id, block_name, form_data))

    item_model_path = assets_root / "models" / "item" / f"{block_name}.json"
    _write_json(item_model_path, _block_item_model_payload(mod_id, block_name, form_data))
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
    touched_files.append(write_creative_entries(workspace_root, project))


def delete(record: dict, workspace_root: Path, tool) -> None:
    block_name = safe_name(record.get("id", "unnamed_block"))
    project = _load_project_info(workspace_root)
    mod_id = safe_name(project.get("mod_id", workspace_root.name.lower()))
    package_name = _package_declaration(project, mod_id)
    main_class = _class_name(mod_id)
    java_root = workspace_root / "src" / "main" / "java" / Path(*package_name.split("."))
    resources_root = workspace_root / "src" / "main" / "resources"
    assets_root = resources_root / "assets" / mod_id

    mod_blocks_path = java_root / "block" / "ModBlocks.java"
    _remove_mod_block(mod_blocks_path, block_name)
    _cleanup_empty_mod_blocks(
        mod_blocks_path,
        java_root / f"{main_class}.java",
        package_name,
    )
    _remove_lang_entry(assets_root / "lang" / "en_us.json", f"block.{mod_id}.{block_name}")
    _remove_mining_tags(resources_root, mod_id, block_name)

    for path in (
        assets_root / "blockstates" / f"{block_name}.json",
        assets_root / "models" / "item" / f"{block_name}.json",
    ):
        if path.exists():
            path.unlink()
    _remove_generated_block_model_family(assets_root, block_name)

    info_path = record.get("_info_path")
    if isinstance(info_path, Path) and info_path.exists():
        _remove_empty_generated_dir(info_path.parent)
    else:
        _remove_empty_generated_dir(workspace_root / "generated" / "block" / block_name)
    write_creative_entries(workspace_root, project)


def _form_data(
    data: dict,
    block_name: str,
    display_name: str,
    mod_id: str,
    project: dict | None = None,
) -> dict:
    textures = data.get("block_textures")
    if not isinstance(textures, dict):
        textures = {}

    normalized_textures = {}
    fallback = f"{mod_id}:block/{block_name}"
    for side in BLOCK_SIDES:
        normalized_textures[side] = _normalize_texture(textures.get(side), fallback)

    model_source = _model_source(data.get("model_source", "default"))
    custom_model = _normalize_model_identifier(data.get("custom_model"), mod_id, "block")
    if model_source == "custom" and not custom_model:
        model_source = "default"

    payload = {
        "registry_name": block_name,
        "display_name": display_name,
        "block_textures": normalized_textures,
        "model_source": model_source,
        "default_model": _default_block_model(data.get("default_model", "cube")),
        "custom_model": custom_model,
        "creative_inventory": _creative_inventory(data.get("creative_inventory", "building_blocks"), project),
        "max_stack_size": _clamped_int(data.get("max_stack_size", 64), 1, 64, 64),
        "hardness": _as_float(data.get("hardness", 1.5), 1.5),
        "resistance": _as_float(data.get("resistance", 6.0), 6.0),
        "sound_group": _sound_group(data.get("sound_group", "stone")),
        "tool_type": _tool_type(data.get("tool_type", "none")),
        "tool_level": _tool_level(data.get("tool_level", "none")),
        "rotation_mode": _rotation_mode(data.get("rotation_mode", "none")),
        "requires_tool": _as_bool(data.get("requires_tool", False)),
        "custom_hitbox_enabled": _as_bool(data.get("custom_hitbox_enabled", False)),
    }
    custom_hitbox = _custom_hitbox(data)
    if custom_hitbox:
        payload["custom_hitbox"] = custom_hitbox

    return payload


def _write_mod_blocks(
    path: Path,
    package_name: str,
    main_class: str,
    mod_id: str,
    block_name: str,
    data: dict,
    project: dict,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    field_name = _java_constant(block_name)
    field_line = _block_field_source(field_name, block_name, data)

    if not path.exists():
        path.write_text(
            _mod_blocks_source(package_name, main_class, mod_id, block_name, data, project),
            encoding="utf-8",
        )
        return

    content = path.read_text(encoding="utf-8")
    content = _ensure_imports(content, _block_imports(package_name, project))
    content = _upsert_creative_inventory_entry(content, field_name, data, project)

    field_pattern = (
        rf"    public static final Block {re.escape(field_name)} = "
        r"registerBlock\([\s\S]*?\);\n"
    )
    if re.search(field_pattern, content):
        content = re.sub(field_pattern, field_line, content, count=1)
    else:
        marker = "    private static Block registerBlock("
        if marker in content:
            content = content.replace(marker, field_line + "\n" + marker, 1)
        else:
            content = content.replace("\n}", "\n" + field_line + "}\n", 1)

    content = _upsert_generated_block_helpers(content, data)
    path.write_text(content, encoding="utf-8")


def _mod_blocks_source(
    package_name: str,
    main_class: str,
    mod_id: str,
    block_name: str,
    data: dict,
    project: dict,
) -> str:
    field_name = _java_constant(block_name)
    imports = "\n".join(
        [
            f"import {package_name}.{main_class};",
            *_block_imports(package_name, project),
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
{_creative_inventory_source(field_name, data, project)}\
        System.out.println("Registering blocks for {mod_id}");
    }}
{_generated_block_helper_sources(_required_helper_classes(_block_field_source(field_name, block_name, data), data))}
}}
"""


def _block_imports(package_name: str = "", project: dict | None = None) -> list[str]:
    imports = [
        "import net.fabricmc.fabric.api.item.v1.FabricItemSettings;",
        "import net.fabricmc.fabric.api.itemgroup.v1.ItemGroupEvents;",
        "import net.minecraft.block.AbstractBlock;",
        "import net.minecraft.block.Block;",
        "import net.minecraft.block.BlockSetType;",
        "import net.minecraft.block.BlockState;",
        "import net.minecraft.block.Blocks;",
        "import net.minecraft.block.DoorBlock;",
        "import net.minecraft.block.FenceBlock;",
        "import net.minecraft.block.FenceGateBlock;",
        "import net.minecraft.block.HorizontalFacingBlock;",
        "import net.minecraft.block.PaneBlock;",
        "import net.minecraft.block.ShapeContext;",
        "import net.minecraft.block.PillarBlock;",
        "import net.minecraft.block.SlabBlock;",
        "import net.minecraft.block.StairsBlock;",
        "import net.minecraft.block.TrapdoorBlock;",
        "import net.minecraft.block.WallBlock;",
        "import net.minecraft.block.WoodType;",
        "import net.minecraft.item.BlockItem;",
        "import net.minecraft.item.ItemGroups;",
        "import net.minecraft.item.ItemPlacementContext;",
        "import net.minecraft.registry.Registries;",
        "import net.minecraft.registry.Registry;",
        "import net.minecraft.sound.BlockSoundGroup;",
        "import net.minecraft.state.StateManager;",
        "import net.minecraft.util.Identifier;",
        "import net.minecraft.util.math.BlockPos;",
        "import net.minecraft.util.math.Direction;",
        "import net.minecraft.util.shape.VoxelShape;",
        "import net.minecraft.util.shape.VoxelShapes;",
        "import net.minecraft.world.BlockView;",
    ]
    if package_name and project and creative_tabs(project):
        imports.append(f"import {package_name}.item.ModItemGroups;")
    return imports


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

    shape = _default_block_model(data.get("default_model", "cube"))
    custom_shape = _custom_hitbox_shape_source(data)
    if data.get("model_source") != "custom":
        if shape == "stairs":
            if custom_shape:
                return f"new GeneratedCustomShapeStairsBlock(Blocks.STONE.getDefaultState(), {settings}, {custom_shape})"
            return f"new StairsBlock(Blocks.STONE.getDefaultState(), {settings})"
        if shape == "slab":
            if custom_shape:
                return f"new GeneratedCustomShapeSlabBlock({settings}, {custom_shape})"
            return f"new SlabBlock({settings})"
        if shape == "fence":
            if custom_shape:
                return f"new GeneratedCustomShapeFenceBlock({settings}, {custom_shape})"
            return f"new FenceBlock({settings})"
        if shape == "fence_gate":
            if custom_shape:
                return f"new GeneratedCustomShapeFenceGateBlock({settings}, WoodType.OAK, {custom_shape})"
            return f"new FenceGateBlock({settings}, WoodType.OAK)"
        if shape == "door":
            if custom_shape:
                return f"new GeneratedCustomShapeDoorBlock({settings}.nonOpaque(), BlockSetType.OAK, {custom_shape})"
            return f"new DoorBlock({settings}.nonOpaque(), BlockSetType.OAK)"
        if shape == "trapdoor":
            if custom_shape:
                return f"new GeneratedCustomShapeTrapdoorBlock({settings}.nonOpaque(), BlockSetType.OAK, {custom_shape})"
            return f"new TrapdoorBlock({settings}.nonOpaque(), BlockSetType.OAK)"
        if shape == "pane":
            if custom_shape:
                return f"new GeneratedCustomShapePaneBlock({settings}.nonOpaque(), {custom_shape})"
            return f"new PaneBlock({settings}.nonOpaque())"
        if shape == "wall":
            if custom_shape:
                return f"new GeneratedCustomShapeWallBlock({settings}, {custom_shape})"
            return f"new WallBlock({settings})"

    rotation_mode = _rotation_mode(data.get("rotation_mode", "none"))
    if rotation_mode == "face_player":
        if custom_shape:
            return f"new GeneratedCustomShapeHorizontalFacingBlock({settings}, {custom_shape})"
        return f"new GeneratedHorizontalFacingBlock({settings})"
    if rotation_mode == "pillar":
        if custom_shape:
            return f"new GeneratedCustomShapePillarBlock({settings}, {custom_shape})"
        return f"new PillarBlock({settings})"
    if custom_shape:
        return f"new GeneratedCustomShapeBlock({settings}, {custom_shape})"
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


def _upsert_generated_block_helpers(content: str, data: dict) -> str:
    for class_name in _generated_helper_class_names():
        content = _remove_nested_class(content, class_name)

    helpers = _generated_block_helper_sources(_required_helper_classes(content, data))
    if not helpers:
        return content

    return content.replace("\n}\n", helpers + "}\n", 1)


def _remove_nested_class(content: str, class_name: str) -> str:
    marker = f"    private static class {class_name} "
    start = content.find(marker)
    if start < 0:
        return content

    brace_start = content.find("{", start)
    if brace_start < 0:
        return content

    depth = 0
    for index in range(brace_start, len(content)):
        if content[index] == "{":
            depth += 1
        elif content[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                if end < len(content) and content[end] == "\r":
                    end += 1
                if end < len(content) and content[end] == "\n":
                    end += 1
                return content[:start].rstrip() + "\n" + content[end:].lstrip("\n")

    return content


def _generated_helper_class_names() -> tuple[str, ...]:
    return (
        "GeneratedHorizontalFacingBlock",
        "GeneratedCustomShapeBlock",
        "GeneratedCustomShapeHorizontalFacingBlock",
        "GeneratedCustomShapePillarBlock",
        "GeneratedCustomShapeStairsBlock",
        "GeneratedCustomShapeSlabBlock",
        "GeneratedCustomShapeFenceBlock",
        "GeneratedCustomShapeFenceGateBlock",
        "GeneratedCustomShapeDoorBlock",
        "GeneratedCustomShapeTrapdoorBlock",
        "GeneratedCustomShapePaneBlock",
        "GeneratedCustomShapeWallBlock",
    )


def _required_helper_classes(content: str, data: dict) -> list[str]:
    helpers: list[str] = []
    custom_refs = [name for name in _generated_helper_class_names() if name.startswith("GeneratedCustomShape") and name in content]
    custom_helpers_needed = bool(custom_refs or _custom_hitbox(data))

    if (
        "new GeneratedHorizontalFacingBlock(" in content
        or "GeneratedCustomShapeHorizontalFacingBlock" in content
        or _rotation_mode(data.get("rotation_mode", "none")) == "face_player"
        or custom_helpers_needed
    ):
        helpers.append("GeneratedHorizontalFacingBlock")

    if custom_helpers_needed:
        helpers.extend(
            [
                "GeneratedCustomShapeBlock",
                "GeneratedCustomShapeHorizontalFacingBlock",
                "GeneratedCustomShapePillarBlock",
                "GeneratedCustomShapeStairsBlock",
                "GeneratedCustomShapeSlabBlock",
                "GeneratedCustomShapeFenceBlock",
                "GeneratedCustomShapeFenceGateBlock",
                "GeneratedCustomShapeDoorBlock",
                "GeneratedCustomShapeTrapdoorBlock",
                "GeneratedCustomShapePaneBlock",
                "GeneratedCustomShapeWallBlock",
            ]
        )

    deduped: list[str] = []
    for helper in helpers:
        if helper not in deduped:
            deduped.append(helper)
    return deduped


def _generated_block_helper_sources(helpers: list[str]) -> str:
    if not helpers:
        return ""

    sources = {
        "GeneratedHorizontalFacingBlock": _horizontal_block_class_source({"rotation_mode": "face_player"}),
        "GeneratedCustomShapeBlock": _custom_shape_block_class_source("GeneratedCustomShapeBlock", "Block", "AbstractBlock.Settings settings", "super(settings);"),
        "GeneratedCustomShapeHorizontalFacingBlock": _custom_shape_block_class_source("GeneratedCustomShapeHorizontalFacingBlock", "GeneratedHorizontalFacingBlock", "AbstractBlock.Settings settings", "super(settings);"),
        "GeneratedCustomShapePillarBlock": _custom_shape_block_class_source("GeneratedCustomShapePillarBlock", "PillarBlock", "AbstractBlock.Settings settings", "super(settings);"),
        "GeneratedCustomShapeStairsBlock": _custom_shape_block_class_source("GeneratedCustomShapeStairsBlock", "StairsBlock", "BlockState baseBlockState, AbstractBlock.Settings settings", "super(baseBlockState, settings);"),
        "GeneratedCustomShapeSlabBlock": _custom_shape_block_class_source("GeneratedCustomShapeSlabBlock", "SlabBlock", "AbstractBlock.Settings settings", "super(settings);"),
        "GeneratedCustomShapeFenceBlock": _custom_shape_block_class_source("GeneratedCustomShapeFenceBlock", "FenceBlock", "AbstractBlock.Settings settings", "super(settings);"),
        "GeneratedCustomShapeFenceGateBlock": _custom_shape_block_class_source("GeneratedCustomShapeFenceGateBlock", "FenceGateBlock", "AbstractBlock.Settings settings, WoodType woodType", "super(settings, woodType);"),
        "GeneratedCustomShapeDoorBlock": _custom_shape_block_class_source("GeneratedCustomShapeDoorBlock", "DoorBlock", "AbstractBlock.Settings settings, BlockSetType blockSetType", "super(settings, blockSetType);"),
        "GeneratedCustomShapeTrapdoorBlock": _custom_shape_block_class_source("GeneratedCustomShapeTrapdoorBlock", "TrapdoorBlock", "AbstractBlock.Settings settings, BlockSetType blockSetType", "super(settings, blockSetType);"),
        "GeneratedCustomShapePaneBlock": _custom_shape_block_class_source("GeneratedCustomShapePaneBlock", "PaneBlock", "AbstractBlock.Settings settings", "super(settings);"),
        "GeneratedCustomShapeWallBlock": _custom_shape_block_class_source("GeneratedCustomShapeWallBlock", "WallBlock", "AbstractBlock.Settings settings", "super(settings);"),
    }
    return "".join(sources[helper] for helper in helpers)


def _custom_shape_block_class_source(
    class_name: str,
    parent_class: str,
    constructor_args: str,
    super_call: str,
) -> str:
    return f"""

    private static class {class_name} extends {parent_class} {{
        private final VoxelShape generatedShape;

        {class_name}({constructor_args}, VoxelShape generatedShape) {{
            {super_call}
            this.generatedShape = generatedShape;
        }}

        @Override
        public VoxelShape getOutlineShape(BlockState state, BlockView world, BlockPos pos, ShapeContext context) {{
            return generatedShape;
        }}

        @Override
        public VoxelShape getCollisionShape(BlockState state, BlockView world, BlockPos pos, ShapeContext context) {{
            return generatedShape;
        }}
    }}
"""


def _update_main_class(
    path: Path,
    package_name: str,
    main_class: str,
    mod_id: str,
    project: dict | None = None,
) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_main_class_source(package_name, main_class, mod_id), encoding="utf-8")
        content = path.read_text(encoding="utf-8")
    else:
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

    if project and creative_tabs(project):
        groups_import = f"import {package_name}.item.ModItemGroups;"
        if groups_import not in content:
            content = _insert_import(content, groups_import)
        group_call = "        ModItemGroups.registerItemGroups();"
        if group_call not in content:
            content = _insert_on_initialize_call(content, group_call)

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


def _upsert_creative_inventory_entry(
    content: str,
    field_name: str,
    data: dict,
    project: dict | None = None,
) -> str:
    vanilla_pattern = (
        r"        ItemGroupEvents\.modifyEntriesEvent\(ItemGroups\.[A-Z_]+\)"
        rf"\.register\(entries -> entries\.add\({re.escape(field_name)}\)\);\n"
    )
    custom_pattern = (
        r"        ItemGroupEvents\.modifyEntriesEvent\(ModItemGroups\.[A-Z0-9_]+\)"
        rf"\.register\(entries -> entries\.add\({re.escape(field_name)}\)\);\n"
    )
    content = re.sub(vanilla_pattern, "", content)
    content = re.sub(custom_pattern, "", content)
    line = _creative_inventory_source(field_name, data, project)
    if not line:
        return content

    marker = "        System.out.println("
    if marker in content:
        return content.replace(marker, line + marker, 1)
    return content


def _creative_inventory_source(field_name: str, data: dict, project: dict | None = None) -> str:
    return ""


def _creative_inventory(value, project: dict | None = None) -> str:
    if project:
        tab_id = custom_tab_id(str(value or ""), project)
        if tab_id:
            return f"custom:{tab_id}"

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


def _block_model_reference(mod_id: str, block_name: str, data: dict) -> str:
    if data.get("model_source") == "custom" and data.get("custom_model"):
        return data["custom_model"]
    return f"{mod_id}:block/{block_name}"


def _blockstate_payload(model: str, data: dict) -> dict:
    if data.get("model_source") != "custom":
        shape = _default_block_model(data.get("default_model", "cube"))
        if shape == "stairs":
            return _stairs_blockstate_payload(model)
        if shape == "slab":
            return _slab_blockstate_payload(model)
        if shape == "fence":
            return _fence_blockstate_payload(model)
        if shape == "fence_gate":
            return _fence_gate_blockstate_payload(model)
        if shape == "door":
            return _door_blockstate_payload(model)
        if shape == "trapdoor":
            return _trapdoor_blockstate_payload(model)
        if shape == "pane":
            return _pane_blockstate_payload(model)
        if shape == "wall":
            return _wall_blockstate_payload(model)

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


def _write_block_models(assets_root: Path, mod_id: str, block_name: str, data: dict) -> list[Path]:
    if data.get("model_source") == "custom" and data.get("custom_model"):
        return []

    model_root = assets_root / "models" / "block"
    touched: list[Path] = []
    for suffix, payload in _block_model_payloads(data).items():
        path = model_root / f"{block_name}{suffix}.json"
        _write_json(path, payload)
        touched.append(path)
    return touched


def _block_model_payloads(data: dict) -> dict[str, dict]:
    shape = _default_block_model(data.get("default_model", "cube"))
    if shape == "stairs":
        textures = _top_bottom_side_textures(data)
        return {
            "": {"parent": "minecraft:block/stairs", "textures": textures},
            "_inner": {"parent": "minecraft:block/inner_stairs", "textures": textures},
            "_outer": {"parent": "minecraft:block/outer_stairs", "textures": textures},
        }
    if shape == "slab":
        textures = _top_bottom_side_textures(data)
        return {
            "": {"parent": "minecraft:block/slab", "textures": textures},
            "_top": {"parent": "minecraft:block/slab_top", "textures": textures},
            "_double": _cube_model_payload(data),
        }
    if shape == "fence":
        textures = _single_texture_map(data)
        return {
            "_post": {"parent": "minecraft:block/fence_post", "textures": textures},
            "_side": {"parent": "minecraft:block/fence_side", "textures": textures},
            "_inventory": {"parent": "minecraft:block/fence_inventory", "textures": textures},
        }
    if shape == "fence_gate":
        textures = _single_texture_map(data)
        return {
            "": {"parent": "minecraft:block/template_fence_gate", "textures": textures},
            "_open": {"parent": "minecraft:block/template_fence_gate_open", "textures": textures},
            "_wall": {"parent": "minecraft:block/template_fence_gate_wall", "textures": textures},
            "_wall_open": {"parent": "minecraft:block/template_fence_gate_wall_open", "textures": textures},
        }
    if shape == "door":
        textures = _door_texture_map(data)
        return {
            "_bottom": {"parent": "minecraft:block/door_bottom", "textures": textures},
            "_bottom_hinge": {"parent": "minecraft:block/door_bottom_rh", "textures": textures},
            "_top": {"parent": "minecraft:block/door_top", "textures": textures},
            "_top_hinge": {"parent": "minecraft:block/door_top_rh", "textures": textures},
        }
    if shape == "trapdoor":
        textures = _single_texture_map(data)
        return {
            "": {"parent": "minecraft:block/template_trapdoor_bottom", "textures": textures},
            "_top": {"parent": "minecraft:block/template_trapdoor_top", "textures": textures},
            "_open": {"parent": "minecraft:block/template_trapdoor_open", "textures": textures},
        }
    if shape == "pane":
        textures = _pane_texture_map(data)
        return {
            "_post": {"parent": "minecraft:block/template_glass_pane_post", "textures": textures},
            "_side": {"parent": "minecraft:block/template_glass_pane_side", "textures": textures},
            "_side_alt": {"parent": "minecraft:block/template_glass_pane_side_alt", "textures": textures},
            "_noside": {"parent": "minecraft:block/template_glass_pane_noside", "textures": textures},
            "_noside_alt": {"parent": "minecraft:block/template_glass_pane_noside_alt", "textures": textures},
        }
    if shape == "wall":
        textures = _wall_texture_map(data)
        return {
            "_post": {"parent": "minecraft:block/template_wall_post", "textures": textures},
            "_side": {"parent": "minecraft:block/template_wall_side", "textures": textures},
            "_side_tall": {"parent": "minecraft:block/template_wall_side_tall", "textures": textures},
            "_inventory": {"parent": "minecraft:block/wall_inventory", "textures": textures},
        }
    return {"": _cube_model_payload(data)}


def _block_item_model_payload(mod_id: str, block_name: str, data: dict) -> dict:
    if data.get("model_source") == "custom" and data.get("custom_model"):
        return {"parent": data["custom_model"]}

    shape = _default_block_model(data.get("default_model", "cube"))
    if shape in {"fence", "wall"}:
        return {"parent": f"{mod_id}:block/{block_name}_inventory"}
    if shape in {"door", "pane"}:
        return {
            "parent": "minecraft:item/generated",
            "textures": {"layer0": data["block_textures"]["top"]},
        }
    return {"parent": f"{mod_id}:block/{block_name}"}


def _cube_model_payload(data: dict) -> dict:
    return {
        "parent": "minecraft:block/cube",
        "textures": {
            "up": data["block_textures"]["top"],
            "down": data["block_textures"]["bottom"],
            "north": data["block_textures"]["north"],
            "south": data["block_textures"]["south"],
            "east": data["block_textures"]["east"],
            "west": data["block_textures"]["west"],
            "particle": data["block_textures"]["top"],
        },
    }


def _top_bottom_side_textures(data: dict) -> dict:
    return {
        "bottom": data["block_textures"]["bottom"],
        "top": data["block_textures"]["top"],
        "side": data["block_textures"]["north"],
        "particle": data["block_textures"]["top"],
    }


def _single_texture_map(data: dict) -> dict:
    texture = data["block_textures"]["north"]
    return {"texture": texture, "particle": texture}


def _door_texture_map(data: dict) -> dict:
    return {
        "bottom": data["block_textures"]["bottom"],
        "top": data["block_textures"]["top"],
        "particle": data["block_textures"]["top"],
    }


def _pane_texture_map(data: dict) -> dict:
    return {
        "pane": data["block_textures"]["north"],
        "edge": data["block_textures"]["top"],
        "particle": data["block_textures"]["north"],
    }


def _wall_texture_map(data: dict) -> dict:
    texture = data["block_textures"]["north"]
    return {"wall": texture, "particle": texture}


def _stairs_blockstate_payload(model: str) -> dict:
    variants = {}
    shape_models = {
        "straight": model,
        "inner_left": f"{model}_inner",
        "inner_right": f"{model}_inner",
        "outer_left": f"{model}_outer",
        "outer_right": f"{model}_outer",
    }
    for facing in _horizontal_facings():
        for half in ("bottom", "top"):
            for shape, shape_model in shape_models.items():
                key = f"facing={facing},half={half},shape={shape}"
                y = _stair_y(facing, half, shape)
                payload = {"model": shape_model, "y": y}
                if half == "top":
                    payload["x"] = 180
                if half == "top" or y != 0:
                    payload["uvlock"] = True
                variants[key] = _clean_rotation(payload)
    return {"variants": variants}


def _slab_blockstate_payload(model: str) -> dict:
    return {
        "variants": {
            "type=bottom": {"model": model},
            "type=top": {"model": f"{model}_top"},
            "type=double": {"model": f"{model}_double"},
        }
    }


def _fence_blockstate_payload(model: str) -> dict:
    multipart = [{"apply": {"model": f"{model}_post"}}]
    for direction in _horizontal_facings():
        multipart.append(
            {
                "when": {direction: "true"},
                "apply": _multipart_side(f"{model}_side", direction),
            }
        )
    return {"multipart": multipart}


def _fence_gate_blockstate_payload(model: str) -> dict:
    variants = {}
    for facing in _horizontal_facings():
        for in_wall in ("false", "true"):
            for open_value in ("false", "true"):
                suffix = ""
                if in_wall == "true":
                    suffix += "_wall"
                if open_value == "true":
                    suffix += "_open"
                key = f"facing={facing},in_wall={in_wall},open={open_value}"
                variants[key] = _clean_rotation(
                    {
                        "model": f"{model}{suffix}",
                        "uvlock": True,
                        "y": _fence_gate_y(facing),
                    }
                )
    return {"variants": variants}


def _door_blockstate_payload(model: str) -> dict:
    variants = {}
    for facing in _horizontal_facings():
        for half in ("lower", "upper"):
            for hinge in ("left", "right"):
                for open_value in ("false", "true"):
                    suffix = "_top" if half == "upper" else "_bottom"
                    if hinge == "right":
                        suffix += "_hinge"
                    key = f"facing={facing},half={half},hinge={hinge},open={open_value}"
                    variants[key] = _clean_rotation(
                        {
                            "model": f"{model}{suffix}",
                            "y": _door_y(facing, hinge, open_value == "true"),
                        }
                    )
    return {"variants": variants}


def _trapdoor_blockstate_payload(model: str) -> dict:
    variants = {}
    for facing in _horizontal_facings():
        for half in ("bottom", "top"):
            for open_value in ("false", "true"):
                suffix = "_open" if open_value == "true" else ("_top" if half == "top" else "")
                key = f"facing={facing},half={half},open={open_value}"
                payload = {"model": f"{model}{suffix}"}
                if open_value == "true":
                    payload["y"] = _facing_y(facing)
                variants[key] = _clean_rotation(payload)
    return {"variants": variants}


def _pane_blockstate_payload(model: str) -> dict:
    multipart = [{"apply": {"model": f"{model}_post"}}]
    side_parts = {
        "north": (f"{model}_side", 0),
        "east": (f"{model}_side", 90),
        "south": (f"{model}_side_alt", 0),
        "west": (f"{model}_side_alt", 90),
    }
    noside_parts = {
        "north": (f"{model}_noside", 0),
        "east": (f"{model}_noside_alt", 0),
        "south": (f"{model}_noside_alt", 90),
        "west": (f"{model}_noside", 270),
    }
    for direction in _horizontal_facings():
        side_model, side_y = side_parts[direction]
        noside_model, noside_y = noside_parts[direction]
        multipart.append(
            {
                "when": {direction: "true"},
                "apply": _clean_rotation({"model": side_model, "y": side_y}),
            }
        )
        multipart.append(
            {
                "when": {direction: "false"},
                "apply": _clean_rotation({"model": noside_model, "y": noside_y}),
            }
        )
    return {"multipart": multipart}


def _wall_blockstate_payload(model: str) -> dict:
    multipart = [{"when": {"up": "true"}, "apply": {"model": f"{model}_post"}}]
    for direction in _horizontal_facings():
        multipart.append(
            {
                "when": {direction: "low"},
                "apply": _multipart_side(f"{model}_side", direction),
            }
        )
        multipart.append(
            {
                "when": {direction: "tall"},
                "apply": _multipart_side(f"{model}_side_tall", direction),
            }
        )
    return {"multipart": multipart}


def _multipart_side(model: str, direction: str) -> dict:
    payload = {"model": model, "uvlock": True, "y": _facing_y(direction)}
    return _clean_rotation(payload)


def _clean_rotation(payload: dict) -> dict:
    if payload.get("x") == 0:
        del payload["x"]
    if payload.get("y") == 0:
        del payload["y"]
    return payload


def _horizontal_facings() -> tuple[str, str, str, str]:
    return ("north", "east", "south", "west")


def _facing_y(facing: str) -> int:
    return {"north": 0, "east": 90, "south": 180, "west": 270}.get(facing, 0)


def _facing_model_y(facing: str) -> int:
    return {"east": 0, "south": 90, "west": 180, "north": 270}.get(facing, 0)


def _fence_gate_y(facing: str) -> int:
    return {"south": 0, "west": 90, "north": 180, "east": 270}.get(facing, 0)


def _stair_y(facing: str, half: str, shape: str) -> int:
    base = _facing_model_y(facing)
    if half == "bottom":
        if shape.endswith("_left"):
            return (base - 90) % 360
        return base
    if shape.endswith("_right"):
        return (base + 90) % 360
    return base


def _door_y(facing: str, hinge: str, opened: bool) -> int:
    y = _facing_model_y(facing)
    if opened:
        y += 90 if hinge == "left" else -90
    return y % 360


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


def _remove_generated_block_model_family(assets_root: Path, block_name: str) -> None:
    model_root = assets_root / "models" / "block"
    for suffix in (
        "",
        "_top",
        "_double",
        "_inner",
        "_outer",
        "_post",
        "_side",
        "_side_alt",
        "_side_tall",
        "_noside",
        "_noside_alt",
        "_inventory",
        "_open",
        "_wall",
        "_wall_open",
        "_bottom",
        "_bottom_hinge",
        "_top_hinge",
    ):
        path = model_root / f"{block_name}{suffix}.json"
        if path.exists():
            path.unlink()


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


def _model_source(value) -> str:
    normalized = safe_name(str(value or "default"))
    return normalized if normalized in {"default", "custom"} else "default"


def _default_block_model(value) -> str:
    normalized = safe_name(str(value or "cube"))
    return normalized if normalized in DEFAULT_BLOCK_MODELS else "cube"


def _custom_hitbox(data: dict) -> dict[str, float] | None:
    if not _as_bool(data.get("custom_hitbox_enabled", False)):
        return None

    hitbox = data.get("custom_hitbox")
    if not isinstance(hitbox, dict):
        hitbox = {}

    raw_values = {
        "min_x": hitbox.get("min_x", data.get("custom_hitbox_min_x", 0)),
        "min_y": hitbox.get("min_y", data.get("custom_hitbox_min_y", 0)),
        "min_z": hitbox.get("min_z", data.get("custom_hitbox_min_z", 0)),
        "max_x": hitbox.get("max_x", data.get("custom_hitbox_max_x", 16)),
        "max_y": hitbox.get("max_y", data.get("custom_hitbox_max_y", 16)),
        "max_z": hitbox.get("max_z", data.get("custom_hitbox_max_z", 16)),
    }

    min_x, max_x = _normalized_hitbox_axis(raw_values["min_x"], raw_values["max_x"], 0, 16)
    min_y, max_y = _normalized_hitbox_axis(raw_values["min_y"], raw_values["max_y"], 0, 16)
    min_z, max_z = _normalized_hitbox_axis(raw_values["min_z"], raw_values["max_z"], 0, 16)
    return {
        "min_x": min_x,
        "min_y": min_y,
        "min_z": min_z,
        "max_x": max_x,
        "max_y": max_y,
        "max_z": max_z,
    }


def _normalized_hitbox_axis(min_value, max_value, fallback_min: float, fallback_max: float) -> tuple[float, float]:
    minimum = _clamped_float(min_value, 0.0, 16.0, fallback_min)
    maximum = _clamped_float(max_value, 0.0, 16.0, fallback_max)
    if maximum <= minimum:
        return fallback_min, fallback_max
    return minimum, maximum


def _custom_hitbox_shape_source(data: dict) -> str:
    hitbox = _custom_hitbox(data)
    if not hitbox:
        return ""

    values = [
        hitbox["min_x"] / 16.0,
        hitbox["min_y"] / 16.0,
        hitbox["min_z"] / 16.0,
        hitbox["max_x"] / 16.0,
        hitbox["max_y"] / 16.0,
        hitbox["max_z"] / 16.0,
    ]
    return "VoxelShapes.cuboid(" + ", ".join(_double_literal(value) for value in values) + ")"


def _normalize_model_identifier(value, mod_id: str, model_type: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return ""

    if ":" not in text:
        text = f"{mod_id}:{model_type}/{text}"

    namespace, path = text.split(":", 1)
    namespace = safe_name(namespace)
    if path.startswith("models/"):
        path = path[len("models/") :]
    path = re.sub(r"[^a-z0-9_./-]+", "_", path.strip().lower()).strip("_/")
    if "/" not in path:
        path = f"{model_type}/{path}"
    if not namespace or not path:
        return ""
    return f"{namespace}:{path}"


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
    custom_creative_pattern = (
        r"        ItemGroupEvents\.modifyEntriesEvent\(ModItemGroups\.[A-Z0-9_]+\)"
        rf"\.register\(entries -> entries\.add\({re.escape(field_name)}\)\);\n"
    )
    updated = re.sub(custom_creative_pattern, "", updated)
    updated = re.sub(r"\n{3,}", "\n\n", updated)
    if updated != content:
        path.write_text(updated, encoding="utf-8")


def _cleanup_empty_mod_blocks(path: Path, main_class_path: Path, package_name: str) -> None:
    if not path.exists():
        _remove_main_class_block_registration(main_class_path, package_name)
        return

    content = path.read_text(encoding="utf-8")
    if re.search(r"public static final Block [A-Z0-9_]+ =", content):
        return

    path.unlink()
    _remove_main_class_block_registration(main_class_path, package_name)


def _remove_main_class_block_registration(path: Path, package_name: str) -> None:
    if not path.exists():
        return

    content = path.read_text(encoding="utf-8")
    import_line = f"import {package_name}.block.ModBlocks;"
    updated = content.replace(import_line + "\n", "")
    updated = updated.replace("        ModBlocks.registerModBlocks();\n", "")
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


def _double_literal(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".") + "D"


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


def _clamped_float(value, minimum: float, maximum: float, default: float) -> float:
    return max(minimum, min(maximum, _as_float(value, default)))


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
