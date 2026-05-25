from pathlib import Path
import json


INFO_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "information.json"
)

with open(INFO_PATH, "r", encoding="utf-8") as f:
    TOOL_INFO = json.load(f)["tool"]


TOOL_NAME = TOOL_INFO["name"]
TOOL_VERSION = TOOL_INFO["version"]
TOOL_BUILD = TOOL_INFO["build"]
TOOL_CHANNEL = TOOL_INFO["release_channel"]