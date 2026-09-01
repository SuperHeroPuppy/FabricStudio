# FabricStudio

FabricStudio is a Python desktop workspace manager and code generator for Minecraft mods using the Fabric loader. The included generator currently targets Minecraft 1.20.1.

## Features

- Create and manage Fabric mod workspaces.
- Generate items, blocks, models, language entries, creative tabs, and music-disc assets.
- Import textures, models, and OGG audio. Imported audio is registered as a sound event and can be used with `/playsound <mod_id>:<sound_path>`.
- Lock individual files against generator writes while keeping them manually editable.
- Host or join direct-IP collaboration sessions across Windows, macOS, and Linux.
- Edit project files, preview PNG textures, and run Gradle build/client/server tasks.

## Requirements

- Python 3.13 or newer (tested with Python 3.13.13)
- Java 17 for Minecraft 1.20.1 development
- `customtkinter`
- `pillow`

Install the Python dependencies:

```bash
python -m pip install customtkinter pillow
```

Run FabricStudio:

```bash
python main.py
```

## Generator file locks

Right-click a file in Explorer and choose **Lock from Generators**. A locked file remains editable by you, but generator create, update, and delete actions restore its original contents if a generator tries to change it. Locks are stored per workspace in `.fabricstudio/file_locks.json`.

## Collaboration

Open a workspace and select **Collaborate**.

- **Create Internet Invitation** produces a temporary HTTPS link for a friend on another network. It does not require router port forwarding or reveal the host's home IP to the guest.
- **Start LAN Hosting** keeps using a local address, port, and six-digit code for nearby collaborators.
- Every participant opens a workspace with the same mod ID.
- Joining applies the host's current files, then file changes are synchronized when saved.
- Build caches, Git metadata, runtime folders, and files larger than 32 MiB are excluded.
- Display names default to the neutral `FabricStudio User`; FabricStudio does not read the operating-system account name.

Internet invitations use an accountless Cloudflare Quick Tunnel. If `cloudflared` is unavailable, FabricStudio asks before downloading it from Cloudflare's official GitHub release and verifies the published SHA-256 digest. Quick Tunnels are a development service without an uptime guarantee, and using the connector is subject to Cloudflare's license, terms, and privacy policy.

Collaboration uses last-save-wins whole-file synchronization. Only invite trusted people. Shared cursors and character-level conflict resolution are not included yet.

## Tests

```bash
python -m unittest discover -s tests -v
```

Project home: https://github.com/SuperHeroPuppy/FabricStudio
