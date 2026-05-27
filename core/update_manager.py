from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.data_store import TOOL_BUILD, TOOL_DOWNLOAD_URL, TOOL_UPDATE_URL, TOOL_VERSION


APP_ROOT = Path(__file__).resolve().parent.parent
MINIMUM_MANAGED_BUILD = "dev00001"
USER_AGENT = "FabricStudio Update Manager"


@dataclass(frozen=True)
class UpdateBuild:
    version: str
    build: str
    title: str
    changelog: str
    download_url: str
    source_url: str = ""

    @property
    def label(self) -> str:
        return f"{self.version} {self.build}"


class UpdateManager:
    def __init__(
        self,
        update_url: str = TOOL_UPDATE_URL,
        download_url: str = TOOL_DOWNLOAD_URL,
        current_version: str = TOOL_VERSION,
        current_build: str = TOOL_BUILD,
        updates_dir: Path | None = None,
    ) -> None:
        self.update_url = update_url
        self.download_url = download_url
        self.current_version = current_version
        self.current_build = current_build
        self.app_root = APP_ROOT
        self.updates_dir = updates_dir or self.app_root / "updates"
        self.repository, self.branch = parse_github_source(update_url, download_url)

    def check_latest_update(self) -> UpdateBuild | None:
        info = self._fetch_remote_information()
        tool = info.get("tool", {})
        version = str(tool.get("version") or "")
        build = str(tool.get("build") or "")
        if not build or not self.can_install(build):
            return None
        if compare_builds(build, self.current_build) <= 0:
            return None

        changelog = self._fetch_remote_changelog(version, build)
        return UpdateBuild(
            version=version,
            build=build,
            title=f"FabricStudio {version} {build}",
            changelog=changelog,
            download_url=normalize_download_url(str(tool.get("download_url") or self.download_url), self.repository, self.branch),
            source_url=self._raw_url(f"data/change_logs/{version}_{build}.md"),
        )

    def list_remote_updates(self) -> list[UpdateBuild]:
        builds: list[UpdateBuild] = []
        for item in self._fetch_changelog_items():
            name = str(item.get("name") or "")
            if not name.endswith(".md"):
                continue

            version, build = parse_changelog_name(name)
            if not version or not build:
                continue

            download_url = str(item.get("download_url") or "")
            changelog = self._read_url(download_url) if download_url else "# Failed to load changelog"
            source_zip_url = self._zip_url_for_changelog(name)
            builds.append(
                UpdateBuild(
                    version=version,
                    build=build,
                    title=f"FabricStudio {version} {build}",
                    changelog=changelog,
                    download_url=source_zip_url,
                    source_url=download_url,
                )
            )

        return sorted(builds, key=lambda item: build_sort_key(item.build), reverse=True)

    def can_install(self, build: str) -> bool:
        if compare_builds(build, MINIMUM_MANAGED_BUILD) < 0:
            return False
        return compare_builds(build, self.current_build) != 0

    def install_label(self, build: str) -> str:
        comparison = compare_builds(build, self.current_build)
        if comparison > 0:
            return "Install Update"
        if comparison < 0:
            return "Install Downgrade"
        return "Current Build"

    def download_update(self, update: UpdateBuild) -> Path:
        self.updates_dir.mkdir(parents=True, exist_ok=True)
        filename = f"FabricStudio-{update.version}-{update.build}.zip"
        destination = self.updates_dir / safe_filename(filename)
        self._download_file(update.download_url or self._branch_zip_url(), destination)
        return destination

    def install_update(self, update: UpdateBuild) -> Path:
        archive_path = self.download_update(update)
        updater_path = self._write_updater_script()
        command = [
            sys.executable,
            str(updater_path),
            str(archive_path),
            str(self.app_root),
            str(os.getpid()),
        ]
        creationflags = subprocess.DETACHED_PROCESS if os.name == "nt" else 0
        subprocess.Popen(command, cwd=self.app_root, creationflags=creationflags)
        return archive_path

    def _fetch_remote_information(self) -> dict[str, Any]:
        return json.loads(self._read_url(self._information_url()))

    def _fetch_remote_changelog(self, version: str, build: str) -> str:
        path = f"data/change_logs/{version}_{build}.md"
        try:
            return self._read_url(self._raw_url(path))
        except urllib.error.URLError:
            return f"# FabricStudio {version}\nBuild: {build}\n\nNo remote changelog was found for this build."

    def _fetch_changelog_items(self) -> list[dict[str, Any]]:
        if not self.repository:
            return []
        url = f"https://api.github.com/repos/{self.repository}/contents/data/change_logs?ref={self.branch}"
        payload = json.loads(self._read_url(url))
        if not isinstance(payload, list):
            return []
        return [item for item in payload if isinstance(item, dict)]

    def _raw_url(self, path: str) -> str:
        if not self.repository:
            return ""
        return f"https://raw.githubusercontent.com/{self.repository}/{self.branch}/{path}"

    def _branch_zip_url(self) -> str:
        return normalize_download_url(self.download_url, self.repository, self.branch)

    def _information_url(self) -> str:
        return normalize_update_url(self.update_url, self.repository, self.branch)

    def _commit_zip_url(self, sha: str) -> str:
        if not self.repository:
            return self._branch_zip_url()
        return f"https://github.com/{self.repository}/archive/{sha}.zip"

    def _zip_url_for_changelog(self, filename: str) -> str:
        path = f"data/change_logs/{filename}"
        if not self.repository:
            return self._branch_zip_url()
        url = (
            f"https://api.github.com/repos/{self.repository}/commits"
            f"?path={path}&sha={self.branch}&per_page=1"
        )
        try:
            payload = json.loads(self._read_url(url))
        except (json.JSONDecodeError, urllib.error.URLError):
            return self._branch_zip_url()
        if not isinstance(payload, list) or not payload:
            return self._branch_zip_url()

        sha = str(payload[0].get("sha") or "")
        return self._commit_zip_url(sha) if sha else self._branch_zip_url()

    def _read_url(self, url: str, timeout: int = 12) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")

    def _download_file(self, url: str, destination: Path, timeout: int = 60) -> None:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            destination.write_bytes(response.read())

    def _write_updater_script(self) -> Path:
        self.updates_dir.mkdir(parents=True, exist_ok=True)
        script_path = self.updates_dir / "apply_update.py"
        script_path.write_text(UPDATER_SCRIPT, encoding="utf-8")
        return script_path


def parse_changelog_name(filename: str) -> tuple[str, str]:
    stem = Path(filename).stem
    if "_" not in stem:
        return "", ""
    version, build = stem.rsplit("_", 1)
    return version, build


def build_sort_key(build: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"([A-Za-z_]+)(\d+)", build)
    if not match:
        return (build, -1, build)
    prefix, number = match.groups()
    return (prefix.lower(), int(number), build)


def compare_builds(left: str, right: str) -> int:
    left_key = build_sort_key(left)
    right_key = build_sort_key(right)
    if left_key > right_key:
        return 1
    if left_key < right_key:
        return -1
    return 0


def safe_filename(filename: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", filename)


def parse_github_source(update_url: str, download_url: str) -> tuple[str, str]:
    for url in (update_url, download_url):
        raw_match = re.search(r"raw\.githubusercontent\.com/([^/]+/[^/]+)/([^/]+)/", url)
        if raw_match:
            return raw_match.group(1), raw_match.group(2)

        raw_base_match = re.search(r"raw\.githubusercontent\.com/([^/]+/[^/]+)(?:/)?$", url)
        if raw_base_match:
            return raw_base_match.group(1), "main"

        branch_match = re.search(r"github\.com/([^/]+/[^/]+)/archive/refs/heads/([^/.]+)", url)
        if branch_match:
            return branch_match.group(1), branch_match.group(2)

        repo_match = re.search(r"github\.com/([^/]+/[^/]+)", url)
        if repo_match:
            return repo_match.group(1), "main"

    return "", "main"


def normalize_update_url(update_url: str, repository: str, branch: str) -> str:
    if update_url.endswith(".json"):
        return update_url
    if "raw.githubusercontent.com" in update_url and repository:
        return f"https://raw.githubusercontent.com/{repository}/{branch}/data/information.json"
    if "github.com" in update_url and repository:
        return f"https://raw.githubusercontent.com/{repository}/{branch}/data/information.json"
    return update_url.rstrip("/") + "/data/information.json"


def normalize_download_url(download_url: str, repository: str, branch: str) -> str:
    if download_url.endswith(".zip"):
        return download_url
    if "github.com" in download_url and repository:
        return f"https://github.com/{repository}/archive/refs/heads/{branch}.zip"
    return download_url.rstrip("/") + ".zip"


UPDATER_SCRIPT = textwrap.dedent(
    r'''
    from __future__ import annotations

    import ctypes
    import os
    import shutil
    import sys
    import time
    import zipfile
    from pathlib import Path


    PRESERVE_NAMES = {"workspaces", "updates", ".git"}


    def wait_for_parent(pid: int) -> None:
        if pid <= 0:
            time.sleep(2)
            return

        if os.name == "nt":
            synchronize = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
            if handle:
                ctypes.windll.kernel32.WaitForSingleObject(handle, 60000)
                ctypes.windll.kernel32.CloseHandle(handle)
                return

        for _ in range(120):
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.5)


    def remove_path(path: Path) -> None:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


    def copy_path(source: Path, destination: Path) -> None:
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)


    def find_source_root(staging_dir: Path) -> Path:
        children = [item for item in staging_dir.iterdir()]
        if len(children) == 1 and children[0].is_dir():
            return children[0]
        return staging_dir


    def apply_update(archive_path: Path, install_root: Path, parent_pid: int) -> None:
        wait_for_parent(parent_pid)

        staging_dir = install_root / "updates" / "_staging"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive_path, "r") as archive:
            archive.extractall(staging_dir)

        source_root = find_source_root(staging_dir)

        for item in install_root.iterdir():
            if item.name in PRESERVE_NAMES:
                continue
            remove_path(item)

        for item in source_root.iterdir():
            if item.name in PRESERVE_NAMES:
                continue
            target = install_root / item.name
            if target.exists():
                remove_path(target)
            copy_path(item, target)

        if archive_path.exists():
            archive_path.unlink()
        if staging_dir.exists():
            shutil.rmtree(staging_dir)

        script_path = Path(__file__)
        try:
            script_path.unlink()
        except OSError:
            pass

        updates_dir = install_root / "updates"
        try:
            if updates_dir.exists() and not any(updates_dir.iterdir()):
                updates_dir.rmdir()
        except OSError:
            pass


    if __name__ == "__main__":
        apply_update(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]))
    '''
).lstrip()
