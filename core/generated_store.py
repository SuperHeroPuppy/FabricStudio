# generated_store.py
# developer: SuperHeroPuppy
# version: 1.0.0

from pathlib import Path
import json
from typing import Any


class GeneratedStore:
    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path
        self.generated_dir = workspace_path / "generated"
        self.generated_file = self.generated_dir / "generated_info.json"
        self.generated_dir.mkdir(parents=True, exist_ok=True)

        if not self.generated_file.exists():
            self._write({})

    def _read(self) -> dict:
        try:
            return json.loads(self.generated_file.read_text("utf-8"))
        except Exception:
            return {}

    def _write(self, data: dict) -> None:
        self.generated_file.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8"
        )

    def add_entry(self, category: str, name: str, data: dict) -> None:
        store = self._read()

        if category not in store:
            store[category] = {}

        store[category][name] = data
        self._write(store)

    def get_entry(self, category: str, name: str) -> dict | None:
        return self._read().get(category, {}).get(name)

    def update_entry(self, category: str, name: str, data: dict) -> None:
        self.add_entry(category, name, data)