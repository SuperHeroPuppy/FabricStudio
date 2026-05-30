# Minecraft 1.20.1 Fabric Generator 1.0.1

This generator creates the starter Fabric project that used to live directly in
`core/project_generator.py`.

To add another game version or loader later:

- Copy this folder into `generators/<minecraft-version>-<loader>-generator-<generator-version>`.
- Update `manifest.json` with the new Minecraft version, loader, supported loader versions, and generator version.
- Change `generator.py` for the Gradle plugin, Java version, mappings, loader metadata, and files required by that target.
- Restart FabricStudio so the setup page discovers the new generator.

The core runner calls:

```python
generate_project(data, workspace_root, spec)
```

Return the created workspace path from that function.
