# data_store.py
# developer: SuperHeroPuppy
# version: 1.0.0

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import customtkinter as ctk


DATA_ROOT = Path(__file__).resolve().parent.parent / "data"
GENERATORS_ROOT = DATA_ROOT.parent / "generators"


def read_data_file(filename: str) -> dict[str, Any]:
    path = DATA_ROOT / filename
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"Data file {filename} must contain a JSON object.")
    return data


def write_data_file(filename: str, data: dict[str, Any], indent: int = 4) -> None:
    path = DATA_ROOT / filename
    path.write_text(json.dumps(data, indent=indent), encoding="utf-8")


def get_data_section(filename: str, *keys: str, default: Any = None) -> Any:
    value: Any = read_data_file(filename)

    for key in keys:
        if not isinstance(value, dict) or key not in value:
            if default is not None:
                return default
            path = ".".join(keys)
            raise KeyError(f"Missing data key '{path}' in {filename}.")
        value = value[key]

    return value


TOOL_INFO = get_data_section("information.json", "tool")
TOOL_NAME = TOOL_INFO["name"]
TOOL_VERSION = TOOL_INFO["version"]
TOOL_BUILD = TOOL_INFO["build"]
TOOL_CHANNEL = TOOL_INFO["release_channel"]
TOOL_UPDATE_URL = TOOL_INFO["update_url"]
TOOL_DOWNLOAD_URL = TOOL_INFO["download_url"]

THEME = get_data_section("theme.json")
CUSTOMTKINTER = THEME["customtkinter"]
COLORS = THEME["colors"]


def read_generator_manifests(loader: str | None = None) -> list[dict[str, Any]]:
    if not GENERATORS_ROOT.exists():
        return []

    manifests: list[dict[str, Any]] = []
    for manifest_path in sorted(GENERATORS_ROOT.glob("*/manifest.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(manifest, dict):
            continue
        if loader and str(manifest.get("loader", "")).lower() != loader.lower():
            continue
        manifests.append(manifest)

    return manifests


def get_minecraft_versions(loader: str = "fabric") -> list[str]:
    versions: list[str] = []
    seen: set[str] = set()

    for manifest in read_generator_manifests(loader):
        version = str(manifest.get("minecraft_version", ""))
        if not version or version in seen:
            continue
        seen.add(version)
        versions.append(version)

    return versions


def get_loader_versions(loader: str, mc_version: str) -> list[str]:
    versions: list[str] = []
    seen: set[str] = set()

    for manifest in read_generator_manifests(loader):
        if manifest.get("minecraft_version") != mc_version:
            continue
        for version in manifest.get("loader_versions", []):
            version = str(version)
            if not version or version in seen:
                continue
            seen.add(version)
            versions.append(version)

    return versions


MINECRAFT_VERSIONS = get_minecraft_versions("fabric")
FABRIC_VERSIONS = {
    mc_version: get_loader_versions("fabric", mc_version)
    for mc_version in MINECRAFT_VERSIONS
}


def get_fabric_versions(mc_version: str) -> list[str]:
    return get_loader_versions("fabric", mc_version)


def configure_theme() -> None:
    ctk.set_appearance_mode(CUSTOMTKINTER["appearance_mode"])
    ctk.set_default_color_theme(CUSTOMTKINTER["default_color_theme"])
