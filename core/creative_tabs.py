from __future__ import annotations

import json
import re
from pathlib import Path


def safe_name(value: str, fallback: str = "custom_tab") -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", str(value).strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or fallback


def java_constant(value: str, fallback: str = "CUSTOM_TAB") -> str:
    constant = re.sub(r"[^A-Z0-9_]+", "_", str(value).upper()).strip("_")
    if not constant:
        constant = fallback
    if constant[0].isdigit():
        constant = f"TAB_{constant}"
    return constant


def custom_tab_values(project: dict) -> list[str]:
    return [f"custom:{tab['id']}" for tab in creative_tabs(project)]


def custom_tab_id(value: str, project: dict) -> str:
    text = str(value or "").strip()
    if not text.startswith("custom:"):
        return ""

    tab_id = safe_name(text.split(":", 1)[1])
    valid_ids = {tab["id"] for tab in creative_tabs(project)}
    return tab_id if tab_id in valid_ids else ""


def creative_tabs(project: dict) -> list[dict]:
    raw_tabs = project.get("creative_tabs", [])
    if not isinstance(raw_tabs, list):
        return []

    tabs: list[dict] = []
    seen: set[str] = set()
    for raw_tab in raw_tabs:
        if not isinstance(raw_tab, dict):
            continue
        tab_id = safe_name(str(raw_tab.get("id") or raw_tab.get("registry_name") or ""))
        if not tab_id or tab_id in seen:
            continue
        seen.add(tab_id)
        display_name = str(raw_tab.get("display_name") or _title_from_id(tab_id))
        icon_item = _normal_item_identifier(raw_tab.get("icon_item") or "minecraft:book")
        tabs.append(
            {
                "id": tab_id,
                "display_name": display_name,
                "icon_item": icon_item,
            }
        )
    return tabs


def write_custom_creative_tabs(workspace_root: Path, project: dict) -> Path | None:
    tabs = creative_tabs(project)
    if not tabs:
        return None

    mod_id = safe_name(str(project.get("mod_id") or workspace_root.name.lower()))
    package_name = _package_declaration(project, mod_id)
    main_class = _class_name(mod_id)
    java_root = workspace_root / "src" / "main" / "java" / Path(*package_name.split("."))
    path = java_root / "item" / "ModItemGroups.java"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_mod_item_groups_source(package_name, main_class, mod_id, tabs), encoding="utf-8")
    _ensure_main_class(java_root / f"{main_class}.java", package_name, main_class, mod_id)

    lang_path = (
        workspace_root
        / "src"
        / "main"
        / "resources"
        / "assets"
        / mod_id
        / "lang"
        / "en_us.json"
    )
    _update_lang(lang_path, {f"itemGroup.{mod_id}.{tab['id']}": tab["display_name"] for tab in tabs})
    return path


def write_creative_entries(workspace_root: Path, project: dict) -> Path:
    mod_id = safe_name(str(project.get("mod_id") or workspace_root.name.lower()))
    package_name = _package_declaration(project, mod_id)
    main_class = _class_name(mod_id)
    java_root = workspace_root / "src" / "main" / "java" / Path(*package_name.split("."))
    path = java_root / "item" / "ModCreativeEntries.java"
    path.parent.mkdir(parents=True, exist_ok=True)

    records = _generated_records(workspace_root)
    path.write_text(
        _mod_creative_entries_source(package_name, records, project),
        encoding="utf-8",
    )
    _ensure_creative_entries_main_class(
        java_root / f"{main_class}.java",
        package_name,
        main_class,
        mod_id,
    )
    return path


def _ensure_main_class(path: Path, package_name: str, main_class: str, mod_id: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_main_class_source(package_name, main_class, mod_id), encoding="utf-8")
        return

    content = path.read_text(encoding="utf-8")
    import_line = f"import {package_name}.item.ModItemGroups;"
    if import_line not in content:
        content = _insert_import(content, import_line)

    if "public static final String MOD_ID" not in content:
        class_marker = f"public class {main_class} implements ModInitializer {{"
        content = content.replace(
            class_marker,
            f'{class_marker}\n    public static final String MOD_ID = "{mod_id}";',
            1,
        )

    call = "        ModItemGroups.registerItemGroups();"
    if call not in content:
        content = _insert_on_initialize_call(content, call)

    path.write_text(content, encoding="utf-8")


def _ensure_creative_entries_main_class(path: Path, package_name: str, main_class: str, mod_id: str) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_main_class_source(package_name, main_class, mod_id), encoding="utf-8")

    content = path.read_text(encoding="utf-8")
    import_line = f"import {package_name}.item.ModCreativeEntries;"
    if import_line not in content:
        content = _insert_import(content, import_line)

    call = "        ModCreativeEntries.registerCreativeEntries();"
    if call not in content:
        content = _insert_on_initialize_call(content, call)

    path.write_text(content, encoding="utf-8")


def _mod_item_groups_source(package_name: str, main_class: str, mod_id: str, tabs: list[dict]) -> str:
    fields = "\n\n".join(_item_group_field(main_class, mod_id, tab) for tab in tabs)
    return f"""package {package_name}.item;

import {package_name}.{main_class};
import net.fabricmc.fabric.api.itemgroup.v1.FabricItemGroup;
import net.minecraft.item.ItemGroup;
import net.minecraft.item.ItemStack;
import net.minecraft.registry.Registries;
import net.minecraft.registry.Registry;
import net.minecraft.registry.RegistryKey;
import net.minecraft.text.Text;
import net.minecraft.util.Identifier;

public class ModItemGroups {{
{fields}

    public static void registerItemGroups() {{
        System.out.println("Registering creative tabs for {mod_id}");
    }}
}}
"""


def _mod_creative_entries_source(package_name: str, records: list[dict], project: dict) -> str:
    entries = _ordered_creative_entries(records, project)
    uses_blocks = any(record.get("type") == "block" for _, record in entries)
    uses_items = any(record.get("type") == "item" for _, record in entries)
    uses_custom_tabs = any(str(tab).startswith("custom:") for tab, _record in entries)
    uses_vanilla_tabs = any(not str(tab).startswith("custom:") for tab, _record in entries)

    imports = [
        "import net.fabricmc.fabric.api.itemgroup.v1.ItemGroupEvents;",
    ]
    if uses_vanilla_tabs:
        imports.append("import net.minecraft.item.ItemGroups;")
    if uses_blocks:
        imports.append(f"import {package_name}.block.ModBlocks;")
    if uses_items:
        imports.append(f"import {package_name}.item.ModItems;")
    if uses_custom_tabs:
        imports.append(f"import {package_name}.item.ModItemGroups;")

    lines = []
    for tab, record in entries:
        group = _creative_tab_event_source(tab)
        field_owner = "ModBlocks" if record.get("type") == "block" else "ModItems"
        field_name = java_constant(str(record.get("id") or ""))
        if group and field_name:
            lines.append(f"        ItemGroupEvents.modifyEntriesEvent({group}).register(entries -> entries.add({field_owner}.{field_name}));")

    body = "\n".join(lines)
    if body:
        body += "\n"

    return f"""package {package_name}.item;

{chr(10).join(imports)}

public class ModCreativeEntries {{
    public static void registerCreativeEntries() {{
{body}    }}
}}
"""


def _ordered_creative_entries(records: list[dict], project: dict) -> list[tuple[str, dict]]:
    grouped: dict[str, list[dict]] = {}
    for record in records:
        tab = _record_creative_inventory(record)
        if not tab or tab == "none":
            continue
        grouped.setdefault(tab, []).append(record)

    order_config = project.get("creative_item_order", {})
    if not isinstance(order_config, dict):
        order_config = {}

    entries: list[tuple[str, dict]] = []
    for tab in sorted(grouped):
        records_for_tab = grouped[tab]
        by_key = {_record_key(record): record for record in records_for_tab}
        configured = order_config.get(tab, [])
        configured_keys = [str(key) for key in configured] if isinstance(configured, list) else []

        ordered: list[dict] = []
        seen: set[str] = set()
        for key in configured_keys:
            record = by_key.get(key)
            if record is not None and key not in seen:
                ordered.append(record)
                seen.add(key)

        remaining = [record for record in records_for_tab if _record_key(record) not in seen]
        remaining.sort(key=lambda record: (str(record.get("display_name") or record.get("id") or ""), str(record.get("type") or "")))
        ordered.extend(remaining)
        entries.extend((tab, record) for record in ordered)

    return entries


def _generated_records(workspace_root: Path) -> list[dict]:
    generated_root = workspace_root / "generated"
    if not generated_root.exists():
        return []

    records: list[dict] = []
    for info_path in sorted(generated_root.glob("*/*/generated_info.json")):
        try:
            payload = json.loads(info_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("type") in {"block", "item"} and payload.get("id"):
            records.append(payload)
    return records


def _record_key(record: dict) -> str:
    return f"{record.get('type')}:{safe_name(str(record.get('id') or ''))}"


def _record_creative_inventory(record: dict) -> str:
    form_data = record.get("form_data", {})
    if not isinstance(form_data, dict):
        form_data = {}
    value = str(form_data.get("creative_inventory") or "").strip()
    if value.startswith("custom:"):
        return f"custom:{safe_name(value.split(':', 1)[1])}"
    normalized = safe_name(value or ("building_blocks" if record.get("type") == "block" else "ingredients"))
    return normalized if normalized in _creative_inventory_groups() else ("building_blocks" if record.get("type") == "block" else "ingredients")


def _creative_tab_event_source(tab: str) -> str:
    if tab.startswith("custom:"):
        return f"ModItemGroups.{java_constant(tab.split(':', 1)[1])}_KEY"
    group = _creative_inventory_groups().get(tab, "")
    return f"ItemGroups.{group}" if group else ""


def _creative_inventory_groups() -> dict[str, str]:
    return {
        "building_blocks": "BUILDING_BLOCKS",
        "colored_blocks": "COLORED_BLOCKS",
        "natural": "NATURAL",
        "functional": "FUNCTIONAL",
        "redstone": "REDSTONE",
        "tools": "TOOLS",
        "combat": "COMBAT",
        "food_and_drink": "FOOD_AND_DRINK",
        "ingredients": "INGREDIENTS",
        "operator": "OPERATOR",
        "none": "",
    }


def _main_class_source(package_name: str, main_class: str, mod_id: str) -> str:
    return f"""package {package_name};

import {package_name}.item.ModItemGroups;
import net.fabricmc.api.ModInitializer;

public class {main_class} implements ModInitializer {{
    public static final String MOD_ID = "{mod_id}";

    @Override
    public void onInitialize() {{
        ModItemGroups.registerItemGroups();
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
    method_match = re.search(r"(public void onInitialize\(\) \{\n)", content, flags=re.MULTILINE)
    if method_match:
        return content[: method_match.end()] + call + "\n" + content[method_match.end() :]
    return content


def _item_group_field(main_class: str, mod_id: str, tab: dict) -> str:
    constant = java_constant(tab["id"])
    return f"""    public static final RegistryKey<ItemGroup> {constant}_KEY = RegistryKey.of(
        Registries.ITEM_GROUP.getKey(),
        new Identifier({main_class}.MOD_ID, "{tab["id"]}")
    );

    public static final ItemGroup {constant} = Registry.register(
        Registries.ITEM_GROUP,
        {constant}_KEY,
        FabricItemGroup.builder()
            .displayName(Text.translatable("itemGroup.{mod_id}.{tab["id"]}"))
            .icon(() -> new ItemStack(Registries.ITEM.get(new Identifier("{tab["icon_item"]}"))))
            .build()
    );"""


def _update_lang(path: Path, values: dict[str, str]) -> None:
    payload = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = {}
        if isinstance(existing, dict):
            payload = existing

    payload.update(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _normal_item_identifier(value) -> str:
    text = str(value or "").strip().lower().replace("\\", "/")
    if text and ":" not in text:
        text = f"minecraft:{text}"
    if ":" not in text:
        return "minecraft:book"
    namespace, item_path = text.split(":", 1)
    namespace = safe_name(namespace, "minecraft")
    item_path = re.sub(r"[^a-z0-9_./-]+", "_", item_path).strip("_/")
    if not namespace or not item_path:
        return "minecraft:book"
    return f"{namespace}:{item_path}"


def _package_declaration(project: dict, mod_id: str) -> str:
    package_root = str(project.get("package_root") or "com")
    package_name = str(project.get("package_name") or mod_id)
    return ".".join(package_root.split(".") + package_name.split("."))


def _class_name(mod_id: str) -> str:
    return "".join(part.capitalize() for part in mod_id.split("_")) + "Mod"


def _title_from_id(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_"))
