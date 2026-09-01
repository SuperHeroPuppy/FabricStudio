"""Minecraft sound-event registration shared by the asset and item generators."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def register_audio_asset(workspace_root: Path, audio_path: Path) -> str:
    """Register an imported OGG as a playable sound and return its full ID."""

    workspace_root = Path(workspace_root)
    audio_path = Path(audio_path)
    project = _load_project_info(workspace_root)
    mod_id = _safe_name(project.get("mod_id", workspace_root.name))
    sounds_root = (
        workspace_root
        / "src"
        / "main"
        / "resources"
        / "assets"
        / mod_id
        / "sounds"
    )
    try:
        relative = audio_path.resolve().relative_to(sounds_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Audio must be inside assets/{mod_id}/sounds.") from exc

    event_name = _normalize_event_name(relative.with_suffix("").as_posix(), mod_id)
    register_sound_event(
        workspace_root,
        event_name,
        f"{mod_id}:{event_name}",
        stream=True,
    )
    return f"{mod_id}:{event_name}"


def sync_audio_assets(workspace_root: Path) -> int:
    """Register existing OGG assets that predate automatic sound events."""

    workspace_root = Path(workspace_root)
    project = _load_project_info(workspace_root)
    mod_id = _safe_name(project.get("mod_id", workspace_root.name))
    sounds_root = (
        workspace_root
        / "src"
        / "main"
        / "resources"
        / "assets"
        / mod_id
        / "sounds"
    )
    sounds_path = _sounds_json_path(workspace_root, mod_id)
    payload = _read_json_object(sounds_path)
    added = 0
    if sounds_root.exists():
        for audio_path in sorted(sounds_root.rglob("*")):
            if not audio_path.is_file() or audio_path.suffix.lower() != ".ogg":
                continue
            event_name = _normalize_event_name(
                audio_path.relative_to(sounds_root).with_suffix("").as_posix(),
                mod_id,
            )
            if event_name in payload:
                continue
            payload[event_name] = {
                "sounds": [{"name": f"{mod_id}:{event_name}", "stream": True}],
            }
            added += 1
    if added:
        _write_json(sounds_path, payload)
    if payload:
        sync_sound_registry(workspace_root)
    return added


def register_sound_event(
    workspace_root: Path,
    event_name: str,
    sound_file: str,
    subtitle_key: str | None = None,
    stream: bool = True,
) -> None:
    """Upsert one ``sounds.json`` entry and its server-side registry field."""

    workspace_root = Path(workspace_root)
    project = _load_project_info(workspace_root)
    mod_id = _safe_name(project.get("mod_id", workspace_root.name))
    event_name = _normalize_event_name(event_name, mod_id)
    sound_file = _normalize_sound_file(sound_file, mod_id)
    sounds_path = _sounds_json_path(workspace_root, mod_id)
    payload = _read_json_object(sounds_path)

    entry: dict[str, object] = {
        "sounds": [{"name": sound_file, "stream": bool(stream)}],
    }
    if subtitle_key:
        entry["subtitle"] = str(subtitle_key)
    payload[event_name] = entry
    _write_json(sounds_path, payload)
    sync_sound_registry(workspace_root)


def unregister_sound_event(workspace_root: Path, event_name: str) -> None:
    workspace_root = Path(workspace_root)
    project = _load_project_info(workspace_root)
    mod_id = _safe_name(project.get("mod_id", workspace_root.name))
    sounds_path = _sounds_json_path(workspace_root, mod_id)
    payload = _read_json_object(sounds_path)
    event_name = _normalize_event_name(event_name, mod_id)
    if event_name in payload:
        del payload[event_name]
        _write_json(sounds_path, payload)
    sync_sound_registry(workspace_root)


def sync_sound_registry(workspace_root: Path) -> Path:
    """Generate ``ModSounds.java`` from the workspace's sound-event keys."""

    workspace_root = Path(workspace_root)
    project = _load_project_info(workspace_root)
    mod_id = _safe_name(project.get("mod_id", workspace_root.name))
    package_name = _package_declaration(project, mod_id)
    main_class = _class_name(mod_id)
    payload = _read_json_object(_sounds_json_path(workspace_root, mod_id))
    event_names = [
        _normalize_event_name(value, mod_id)
        for value in payload
        if isinstance(value, str) and value.strip()
    ]
    event_names = sorted(set(event_names), key=_event_sort_key)

    java_root = workspace_root / "src" / "main" / "java" / Path(*package_name.split("."))
    sounds_class_path = java_root / "sound" / "ModSounds.java"
    sounds_class_path.parent.mkdir(parents=True, exist_ok=True)
    source = _mod_sounds_source(package_name, main_class, mod_id, event_names)
    if not sounds_class_path.exists() or sounds_class_path.read_text(encoding="utf-8") != source:
        sounds_class_path.write_text(source, encoding="utf-8")

    main_path = java_root / f"{main_class}.java"
    _ensure_main_registration(main_path, package_name, main_class, mod_id)
    return sounds_class_path


def _mod_sounds_source(
    package_name: str,
    main_class: str,
    mod_id: str,
    event_names: list[str],
) -> str:
    constants = _event_constants(event_names)
    fields = "\n".join(
        f'    public static final SoundEvent {constants[event]} = registerSoundEvent("{event}");'
        for event in event_names
    )
    if fields:
        fields += "\n"

    return f"""package {package_name}.sound;

import {package_name}.{main_class};
import net.minecraft.registry.Registries;
import net.minecraft.registry.Registry;
import net.minecraft.sound.SoundEvent;
import net.minecraft.util.Identifier;

public class ModSounds {{
{fields}
    private static SoundEvent registerSoundEvent(String name) {{
        Identifier id = new Identifier({main_class}.MOD_ID, name);
        return Registry.register(Registries.SOUND_EVENT, id, SoundEvent.of(id));
    }}

    public static void registerSoundEvents() {{
        System.out.println("Registering sounds for {mod_id}");
    }}
}}
"""


def _event_constants(event_names: list[str]) -> dict[str, str]:
    used: set[str] = set()
    result: dict[str, str] = {}
    for event_name in event_names:
        base = re.sub(r"[^A-Z0-9_]+", "_", event_name.upper()).strip("_") or "SOUND"
        if base[0].isdigit():
            base = f"SOUND_{base}"
        constant = base
        if constant in used:
            suffix = hashlib.sha1(event_name.encode("utf-8")).hexdigest()[:8].upper()
            constant = f"{base}_{suffix}"
        used.add(constant)
        result[event_name] = constant
    return result


def _event_sort_key(event_name: str) -> tuple[int, str]:
    # Item generator references use simple registry IDs and keep their familiar
    # Java constants if a path-like asset would otherwise collide with one.
    return (0 if re.fullmatch(r"[a-z0-9_]+", event_name) else 1, event_name)


def _ensure_main_registration(
    path: Path,
    package_name: str,
    main_class: str,
    mod_id: str,
) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"""package {package_name};

import {package_name}.sound.ModSounds;
import net.fabricmc.api.ModInitializer;

public class {main_class} implements ModInitializer {{
    public static final String MOD_ID = "{mod_id}";

    @Override
    public void onInitialize() {{
        ModSounds.registerSoundEvents();
        System.out.println("{main_class} loaded.");
    }}
}}
""",
            encoding="utf-8",
        )
        return

    content = path.read_text(encoding="utf-8")
    import_line = f"import {package_name}.sound.ModSounds;"
    if import_line not in content:
        content = _insert_import(content, import_line)
    call = "        ModSounds.registerSoundEvents();"
    if call not in content:
        content = _insert_on_initialize_call(content, call)
    if path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")


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
    method_match = re.search(r"(public void onInitialize\(\) \{\n)", content)
    if not method_match:
        return content
    return content[: method_match.end()] + call + "\n" + content[method_match.end() :]


def _normalize_event_name(value: str, mod_id: str) -> str:
    text = str(value or "").strip().lower().replace("\\", "/")
    if ":" in text:
        namespace, text = text.split(":", 1)
        if _safe_name(namespace) != mod_id:
            raise ValueError(f"Sound events must use the workspace namespace '{mod_id}'.")
    if text.startswith("sounds/"):
        text = text[len("sounds/") :]
    if text.endswith(".ogg"):
        text = text[:-4]
    text = re.sub(r"[^a-z0-9_./-]+", "_", text).strip("_/")
    if not text:
        raise ValueError("Sound event name is required.")
    return text


def _normalize_sound_file(value: str, mod_id: str) -> str:
    text = str(value or "").strip().lower().replace("\\", "/")
    namespace = mod_id
    if ":" in text:
        namespace, text = text.split(":", 1)
        namespace = _safe_name(namespace)
    if text.startswith("sounds/"):
        text = text[len("sounds/") :]
    if text.endswith(".ogg"):
        text = text[:-4]
    text = re.sub(r"[^a-z0-9_./-]+", "_", text).strip("_/")
    if not text:
        raise ValueError("Sound file is required.")
    return f"{namespace}:{text}"


def _sounds_json_path(workspace_root: Path, mod_id: str) -> Path:
    return workspace_root / "src" / "main" / "resources" / "assets" / mod_id / "sounds.json"


def _load_project_info(workspace_root: Path) -> dict:
    path = workspace_root / "project_info.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_json_object(path: Path) -> dict:
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


def _package_declaration(project: dict, mod_id: str) -> str:
    package_root = str(project.get("package_root") or "com")
    package_name = str(project.get("package_name") or mod_id)
    return ".".join(package_root.split(".") + package_name.split("."))


def _class_name(mod_id: str) -> str:
    return "".join(part.capitalize() for part in mod_id.split("_")) + "Mod"


def _safe_name(value: object) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())
    return re.sub(r"_+", "_", cleaned).strip("_") or "mod"
