from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


def upload_mod_icon(workspace: Path, source: Path, meta: dict) -> str:
    mod_id = _safe_name(str(meta.get("mod_id") or workspace.name.lower()))
    target = (
        workspace
        / "src"
        / "main"
        / "resources"
        / "assets"
        / mod_id
        / "icon.png"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    icon_path = f"assets/{mod_id}/icon.png"
    meta["icon"] = icon_path
    return icon_path


def apply_mod_icon(workspace: Path, meta: dict) -> None:
    icon_path = str(meta.get("icon") or "").strip()
    if not icon_path:
        return

    mod_json_path = workspace / "src" / "main" / "resources" / "fabric.mod.json"
    if not mod_json_path.exists():
        return

    try:
        payload = json.loads(mod_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    payload["icon"] = icon_path
    mod_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "mod"
