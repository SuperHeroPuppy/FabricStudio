# generator.py
# developer: SuperHeroPuppy
# version: 1.0.1
# minecraft: fabric 1.20.1

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any


YARN_MAPPINGS = "1.20.1+build.10"
JAVA_VERSION = 17


def generate_project(data: Any, workspace_root: Path, spec: Any) -> Path:
    project_path = workspace_root / data.name
    package_path = Path(*_package_parts(data))
    java_root = project_path / "src" / "main" / "java" / package_path
    resources_root = project_path / "src" / "main" / "resources"

    java_root.mkdir(parents=True, exist_ok=True)
    resources_root.mkdir(parents=True, exist_ok=True)

    _write(project_path / "settings.gradle", _settings_gradle(data))
    _write(project_path / "build.gradle", _build_gradle())
    _write(project_path / "gradle.properties", _gradle_properties(data))
    _write(resources_root / "fabric.mod.json", _fabric_mod_json(data))

    assets_root = resources_root / "assets" / data.mod_id
    (assets_root / "textures" / "item").mkdir(parents=True, exist_ok=True)
    (assets_root / "textures" / "block").mkdir(parents=True, exist_ok=True)

    _write(java_root / f"{_class_name(data.mod_id)}.java", _main_class(data))
    _write(project_path / "project_info.json", _project_info(data, spec))

    return project_path


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


def _settings_gradle(data: Any) -> str:
    return f"""
pluginManagement {{
    repositories {{

        maven {{
            url = 'https://maven.fabricmc.net/'
        }}

        gradlePluginPortal()

        mavenCentral()
    }}
}}

rootProject.name = '{data.name}'
"""


def _build_gradle() -> str:
    return f"""
plugins {{
    id 'fabric-loom' version '1.6-SNAPSHOT'
    id 'maven-publish'
}}

version = project.mod_version
group = project.maven_group

base {{
    archivesName = project.archives_base_name
}}

repositories {{

    maven {{
        url = 'https://maven.fabricmc.net/'
    }}

    maven {{
        url = 'https://libraries.minecraft.net/'
    }}

    mavenCentral()
}}

dependencies {{

    minecraft "com.mojang:minecraft:${{project.minecraft_version}}"

    mappings "net.fabricmc:yarn:${{project.yarn_mappings}}:v2"

    modImplementation "net.fabricmc:fabric-loader:${{project.loader_version}}"
}}

tasks.withType(JavaCompile).configureEach {{
    it.options.release = {JAVA_VERSION}
}}

java {{
    withSourcesJar()

    sourceCompatibility = JavaVersion.VERSION_{JAVA_VERSION}
    targetCompatibility = JavaVersion.VERSION_{JAVA_VERSION}
}}
"""


def _gradle_properties(data: Any) -> str:
    group_name = _package_declaration(data)
    return f"""
org.gradle.jvmargs=-Xmx1G
minecraft_version={data.minecraft_version}
yarn_mappings={YARN_MAPPINGS}
loader_version={data.fabric_version}
mod_version=1.0.0
maven_group={group_name}
archives_base_name={data.mod_id}
"""


def _fabric_mod_json(data: Any) -> str:
    package_name = _package_declaration(data)
    payload = {
        "schemaVersion": 1,
        "id": data.mod_id,
        "version": "${version}",
        "name": data.name,
        "description": data.description,
        "authors": [data.author or "Unknown"],
        "environment": "*",
        "entrypoints": {"main": [f"{package_name}.{_class_name(data.mod_id)}"]},
        "depends": {
            "fabricloader": f">={data.fabric_version}",
            "minecraft": data.minecraft_version,
            "java": f">={JAVA_VERSION}",
        },
    }
    return json.dumps(payload, indent=2)


def _main_class(data: Any) -> str:
    class_name = _class_name(data.mod_id)
    package_name = _package_declaration(data)
    return f"""
package {package_name};

import net.fabricmc.api.ModInitializer;

public class {class_name} implements ModInitializer {{
    @Override
    public void onInitialize() {{
        System.out.println("{data.name} loaded.");
    }}
}}
"""


def _project_info(data: Any, spec: Any) -> str:
    payload = asdict(data)

    payload["created_at"] = datetime.now().isoformat(
        timespec="seconds"
    )

    payload["generator"] = {
        "id": spec.id,
        "name": spec.name,
        "version": spec.generator_version,
        "loader": spec.loader,
        "minecraft_version": spec.minecraft_version,

        # IMPORTANT
        "root": str(spec.root),
    }

    return json.dumps(
        payload,
        indent=2,
    )

def _class_name(mod_id: str) -> str:
    return "".join(part.capitalize() for part in mod_id.split("_")) + "Mod"


def _package_parts(data: Any) -> list[str]:
    package_name = data.package_name or data.mod_id
    return data.package_root.split(".") + package_name.split(".")


def _package_declaration(data: Any) -> str:
    return ".".join(_package_parts(data))