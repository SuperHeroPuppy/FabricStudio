"""Optional Cloudflare Quick Tunnel support for Internet collaboration."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Callable


LATEST_RELEASE_API = "https://api.github.com/repos/cloudflare/cloudflared/releases/latest"
QUICK_TUNNEL_URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def find_cloudflared() -> Path | None:
    bundled = _tools_directory() / ("cloudflared.exe" if os.name == "nt" else "cloudflared")
    if bundled.is_file():
        return bundled
    installed = shutil.which("cloudflared")
    return Path(installed) if installed else None


def install_cloudflared(on_status: Callable[[str], None] | None = None) -> Path:
    """Download the latest official binary and verify its release digest."""

    _status(on_status, "Checking the latest cloudflared release...")
    release = _read_json_url(LATEST_RELEASE_API)
    asset_name = _release_asset_name()
    assets = release.get("assets", []) if isinstance(release, dict) else []
    asset = next(
        (
            value
            for value in assets
            if isinstance(value, dict) and value.get("name") == asset_name
        ),
        None,
    )
    if asset is None:
        raise RuntimeError(f"The latest cloudflared release has no {asset_name} asset.")

    download_url = str(asset.get("browser_download_url") or "")
    digest = str(asset.get("digest") or "")
    if not download_url or not digest.startswith("sha256:"):
        raise RuntimeError("The cloudflared release is missing a verified SHA-256 digest.")

    target = _tools_directory() / ("cloudflared.exe" if os.name == "nt" else "cloudflared")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fabricstudio-cloudflared-") as folder:
        archive = Path(folder) / asset_name
        _status(on_status, f"Downloading {asset_name}...")
        _download(download_url, archive)
        actual_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        expected_digest = digest.split(":", 1)[1].lower()
        if actual_digest.lower() != expected_digest:
            raise RuntimeError("cloudflared download verification failed.")

        candidate = archive
        if asset_name.endswith(".tgz"):
            candidate = Path(folder) / "cloudflared"
            with tarfile.open(archive, "r:gz") as package:
                member = next(
                    (
                        value
                        for value in package.getmembers()
                        if value.isfile() and Path(value.name).name == "cloudflared"
                    ),
                    None,
                )
                if member is None:
                    raise RuntimeError("The cloudflared archive did not contain its executable.")
                source = package.extractfile(member)
                if source is None:
                    raise RuntimeError("Could not read the cloudflared executable.")
                candidate.write_bytes(source.read())

        temporary_target = target.with_name(target.name + ".download")
        shutil.copy2(candidate, temporary_target)
        if os.name != "nt":
            mode = temporary_target.stat().st_mode
            temporary_target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(temporary_target, target)

    _status(on_status, "cloudflared installed.")
    return target


class CloudflareQuickTunnel:
    def __init__(self, executable: Path) -> None:
        self.executable = Path(executable)
        self.process: subprocess.Popen[str] | None = None
        self.public_url = ""
        self._ready = threading.Event()
        self._output: list[str] = []

    def start(self, local_port: int, timeout: float = 45.0) -> str:
        if self.process is not None:
            raise RuntimeError("The Internet tunnel is already running.")
        command = [
            str(self.executable),
            "tunnel",
            "--url",
            f"http://127.0.0.1:{int(local_port)}",
            "--no-autoupdate",
        ]
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
        )
        threading.Thread(
            target=self._read_output,
            name="fabricstudio-cloudflare-tunnel",
            daemon=True,
        ).start()
        if not self._ready.wait(timeout) or not self.public_url:
            details = "\n".join(self._output[-5:]).strip()
            self.stop()
            suffix = f"\n{details}" if details else ""
            raise RuntimeError(f"Could not create the Internet tunnel.{suffix}")
        return self.public_url

    def stop(self) -> None:
        process = self.process
        self.process = None
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def _read_output(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            self._ready.set()
            return
        for line in process.stdout:
            text = line.rstrip()
            self._output.append(text)
            match = QUICK_TUNNEL_URL_PATTERN.search(text)
            if match and not self.public_url:
                self.public_url = match.group(0)
                self._ready.set()
        if not self.public_url:
            self._ready.set()


def _release_asset_name() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        architecture = "arm64"
    elif machine.startswith("arm"):
        architecture = "arm"
    elif machine in {"i386", "i686", "x86"}:
        architecture = "386"
    else:
        architecture = "amd64"
    if system == "windows":
        return f"cloudflared-windows-{architecture}.exe"
    if system == "darwin":
        if architecture not in {"amd64", "arm64"}:
            raise RuntimeError(f"Automatic cloudflared installation is not supported on {machine} macOS.")
        return f"cloudflared-darwin-{architecture}.tgz"
    if system == "linux":
        return f"cloudflared-linux-{architecture}"
    raise RuntimeError(f"Automatic cloudflared installation is not supported on {platform.system()}.")


def _tools_directory() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "FabricStudio" / "tools"
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "FabricStudio" / "tools"
    data_root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return data_root / "fabricstudio" / "tools"


def _read_json_url(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "FabricStudio"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("The cloudflared release response was invalid.")
    return payload


def _download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "FabricStudio"})
    with urllib.request.urlopen(request, timeout=60) as response, target.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)


def _status(callback: Callable[[str], None] | None, message: str) -> None:
    if callback is not None:
        callback(message)
