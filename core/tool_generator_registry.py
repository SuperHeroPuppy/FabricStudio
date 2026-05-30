# tool_generator_registry.py
# developer: SuperHeroPuppy
# version: 1.0.0

from __future__ import annotations

import json

from dataclasses import dataclass

from pathlib import Path


@dataclass
class ToolGeneratorSpec:

    id: str

    name: str

    description: str

    supported: bool

    root: Path

    manifest: dict


def iter_tool_generators(
    generator_root: Path,
) -> list[ToolGeneratorSpec]:

    tools_root = generator_root / "tools"

    if not tools_root.exists():
        return []

    generators: list[ToolGeneratorSpec] = []

    for manifest_path in sorted(
        tools_root.glob("*/manifest.json")
    ):

        try:

            payload = json.loads(
                manifest_path.read_text(
                    encoding="utf-8"
                )
            )

            generators.append(

                ToolGeneratorSpec(

                    id=payload["id"],

                    name=payload["name"],

                    description=payload.get(
                        "description",
                        "",
                    ),

                    supported=payload.get(
                        "supported",
                        True,
                    ),

                    root=manifest_path.parent,

                    # IMPORTANT
                    manifest=payload,
                )
            )

        except Exception as exc:

            print(
                f"Failed to load tool generator "
                f"{manifest_path}: {exc}"
            )

            continue

    return generators