# build_runner.py
# developer: SuperHeroPuppy
# version: 1.0.0

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
        pass

    def is_gradle_available(self, workspace_path: Path | None = None) -> bool:
        return self._resolve_gradle_executable(workspace_path) is not None

    def compile(self, workspace_path: Path, on_output: OutputHandler, on_finish: FinishHandler) -> None:
        self.run_gradle_task(workspace_path, "build", on_output, on_finish)

    def run_gradle_task(
        self,
        workspace_path: Path,
        task: str,
        on_output: OutputHandler,
        on_finish: FinishHandler,
    ) -> None:
        thread = threading.Thread(
            target=self._run_gradle_task,
            args=(workspace_path, task, on_output, on_finish),
            daemon=True,
        )
        thread.start()

    def install_gradle(self,workspace_path: Path,on_output: OutputHandler,on_finish: FinishHandler,) -> None:
        thread = threading.Thread(
            target=self._run_install,
            args=(workspace_path, on_output, on_finish),
            daemon=True,
        )
        thread.start()

    def _run_gradle_task(
        self,
        workspace_path: Path,
        task: str,
        on_output: OutputHandler,
        on_finish: FinishHandler,
    ) -> None:
        command = self._gradle_command(workspace_path, task)
        if not command:
            on_output("No Gradle executable was found.\n")
            on_output("Install Gradle from the toolbar or add a Gradle wrapper to this workspace to run Gradle tasks inside Fabric Studio.\n")
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
        
    def _run_install(self,workspace_path: Path,on_output: OutputHandler,on_finish: FinishHandler,) -> None:
        try:
            gradle_dir = workspace_path / ".gradle-runtime"
            gradle_dir.mkdir(parents=True, exist_ok=True)

            zip_path = gradle_dir / f"gradle-{self.bundled_gradle_version}-bin.zip"

            target_dir = gradle_dir / f"gradle-{self.bundled_gradle_version}"

            url = (
                f"https://services.gradle.org/distributions/"
                f"gradle-{self.bundled_gradle_version}-bin.zip"
            )

            on_output(f"> Downloading {url}\n")

            urllib.request.urlretrieve(url, zip_path)

            if target_dir.exists():
                shutil.rmtree(target_dir)

            on_output(f"> Extracting to {target_dir}\n")

            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(gradle_dir)

            zip_path.unlink(missing_ok=True)

            executable = (
                target_dir / "bin" / "gradle.bat"
            )

            if not executable.exists():
                on_output("Gradle executable not found.\n")
                on_finish(1)
                return

            on_output(
                f"Gradle {self.bundled_gradle_version} installed "
                f"inside workspace.\n"
            )

        except Exception as exc:
            on_output(f"Gradle install failed: {exc}\n")
            on_finish(1)
            return

        on_finish(0)

    def _gradle_command(self, workspace_path: Path, task: str) -> list[str]:
        executable = self._resolve_gradle_executable(workspace_path)
        if executable:
            return [str(executable), task]
        return []

    def _resolve_gradle_executable(self,workspace_path: Path | None,) -> Path | None:

        if not workspace_path:
            return None

        # Prefer wrapper
        gradlew = workspace_path / "gradlew.bat"

        if gradlew.exists():
            return gradlew

        # Fallback local runtime
        bundled = (
            workspace_path
            / ".gradle-runtime"
            / f"gradle-{self.bundled_gradle_version}"
            / "bin"
            / "gradle.bat"
        )

        if bundled.exists():
            return bundled

        return None

    def _build_env(self) -> dict[str, str]:
        return os.environ.copy()
