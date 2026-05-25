from __future__ import annotations

import os
import shutil
import subprocess
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable


OutputHandler = Callable[[str], None]
FinishHandler = Callable[[int], None]


class BuildRunner:
    bundled_gradle_version = "8.8"

    def __init__(self) -> None:
        self.tools_root = Path.cwd() / "tools"
        self.gradle_root = self.tools_root / "gradle"

    def is_gradle_available(self, workspace_path: Path | None = None) -> bool:
        return self._resolve_gradle_executable(workspace_path) is not None

    def compile(self, workspace_path: Path, on_output: OutputHandler, on_finish: FinishHandler) -> None:
        thread = threading.Thread(
            target=self._run_compile,
            args=(workspace_path, on_output, on_finish),
            daemon=True,
        )
        thread.start()

    def install_gradle(self, on_output: OutputHandler, on_finish: FinishHandler) -> None:
        thread = threading.Thread(
            target=self._run_install,
            args=(on_output, on_finish),
            daemon=True,
        )
        thread.start()

    def _run_compile(self, workspace_path: Path, on_output: OutputHandler, on_finish: FinishHandler) -> None:
        command = self._compile_command(workspace_path)
        if not command:
            on_output("No Gradle executable was found.\n")
            on_output("Install Gradle from the toolbar or add a Gradle wrapper to this workspace to compile inside Fabric Studio.\n")
            on_finish(1)
            return
        on_output(f"> {' '.join(command)}\n")

        try:
            process = subprocess.Popen(
                command,
                cwd=workspace_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                env=self._build_env(),
            )
        except OSError as exc:
            on_output(f"Could not start build: {exc}\n")
            on_finish(1)
            return

        if process.stdout:
            for line in process.stdout:
                on_output(line)

        on_finish(process.wait())

    def _run_install(self, on_output: OutputHandler, on_finish: FinishHandler) -> None:
        try:
            self.gradle_root.mkdir(parents=True, exist_ok=True)
            zip_path = self.gradle_root / f"gradle-{self.bundled_gradle_version}-bin.zip"
            target_dir = self.gradle_root / f"gradle-{self.bundled_gradle_version}"
            url = f"https://services.gradle.org/distributions/gradle-{self.bundled_gradle_version}-bin.zip"
            on_output(f"> Downloading {url}\n")
            urllib.request.urlretrieve(url, zip_path)

            for existing in self.gradle_root.glob("gradle-*"):
                if existing == zip_path:
                    continue
                if existing.is_dir():
                    shutil.rmtree(existing, ignore_errors=True)
                elif existing.is_file():
                    existing.unlink(missing_ok=True)

            if target_dir.exists():
                shutil.rmtree(target_dir)

            on_output(f"> Extracting to {target_dir}\n")
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(self.gradle_root)

            zip_path.unlink(missing_ok=True)
            executable = self._bundled_gradle_executable()
            if executable is None or not executable.exists():
                on_output("Gradle download finished, but the executable could not be found.\n")
                on_finish(1)
                return

            on_output(f"Gradle {self.bundled_gradle_version} installed.\n")
        except Exception as exc:
            on_output(f"Gradle install failed: {exc}\n")
            on_finish(1)
            return
        on_finish(0)

    def _compile_command(self, workspace_path: Path) -> list[str]:
        executable = self._resolve_gradle_executable(workspace_path)
        if executable:
            return [str(executable), "build"]
        return []

    def _resolve_gradle_executable(self, workspace_path: Path | None) -> Path | None:
        if workspace_path:
            gradlew = workspace_path / "gradlew.bat"
            if gradlew.exists():
                return gradlew

        bundled = self._bundled_gradle_executable()
        if bundled and bundled.exists():
            return bundled

        system_gradle = shutil.which("gradle")
        return Path(system_gradle) if system_gradle else None

    def _bundled_gradle_executable(self) -> Path | None:
        candidate = self.gradle_root / f"gradle-{self.bundled_gradle_version}" / "bin" / "gradle.bat"
        return candidate if candidate.exists() else None

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        bundled = self._bundled_gradle_executable()
        if bundled:
            bin_dir = str(bundled.parent)
            env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
        return env
