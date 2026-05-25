from pathlib import Path
import json

DATA_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "fabric_versions.json"
)

with open(DATA_PATH, "r", encoding="utf-8") as f:
    DATA = json.load(f)

MINECRAFT_VERSIONS = DATA["minecraft_versions"]
FABRIC_VERSIONS = DATA["fabric_versions"]


def get_fabric_versions(mc_version: str) -> list[str]:
    return FABRIC_VERSIONS.get(mc_version, [])