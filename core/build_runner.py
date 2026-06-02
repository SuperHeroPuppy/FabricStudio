# build_runner.py
# developer: SuperHeroPuppy
# version: 1.0.0

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable


OutputHandler = Callable[[str], None]
FinishHandler = Callable[[int], None]


class BuildRunner:
    bundled_gradle_version = "8.8"
    _process_lock = threading.Lock()
    _active_processes: dict[Path, set[subprocess.Popen]] = {}

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

        workspace_key = self._workspace_key(workspace_path)
        self._register_process(workspace_key, process)

        try:
            if process.stdout:
                for line in process.stdout:
                    on_output(line)

            exit_code = process.wait()
        finally:
            self._unregister_process(workspace_key, process)

        on_finish(exit_code)
        
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

    @classmethod
    def terminate_workspace_processes(
        cls,
        workspace_path: Path,
        include_all_java: bool = False,
    ) -> int:
        workspace_key = cls._workspace_key(workspace_path)
        terminated = 0

        with cls._process_lock:
            tracked = [
                (path, process)
                for path, processes in cls._active_processes.items()
                if cls._is_same_or_child(path, workspace_key)
                for process in list(processes)
            ]

        for _, process in tracked:
            if process.poll() is None:
                terminated += cls._terminate_process_tree(process.pid)

        terminated += cls._terminate_windows_workspace_processes(
            workspace_key,
            include_all_java,
        )
        return terminated

    @classmethod
    def _register_process(cls, workspace_path: Path, process: subprocess.Popen) -> None:
        with cls._process_lock:
            cls._active_processes.setdefault(workspace_path, set()).add(process)

    @classmethod
    def _unregister_process(cls, workspace_path: Path, process: subprocess.Popen) -> None:
        with cls._process_lock:
            processes = cls._active_processes.get(workspace_path)
            if not processes:
                return
            processes.discard(process)
            if not processes:
                del cls._active_processes[workspace_path]

    @classmethod
    def _terminate_process_tree(cls, pid: int) -> int:
        if sys.platform == "win32":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
            return 1 if result.returncode == 0 else 0

        try:
            os.kill(pid, 15)
        except OSError:
            return 0
        return 1

    @classmethod
    def _terminate_windows_workspace_processes(
        cls,
        workspace_path: Path,
        include_all_java: bool = False,
    ) -> int:
        if sys.platform != "win32":
            return 0

        script = r"""
$workspace = [System.IO.Path]::GetFullPath($args[0]).TrimEnd('\')
$includeAllJava = $args[1] -eq '1'
$currentPid = $PID
$names = @('java.exe', 'javaw.exe', 'gradle.exe', 'gradle.bat', 'cmd.exe')
$matches = Get-CimInstance Win32_Process | Where-Object {
    $_.ProcessId -ne $currentPid -and
    ($names -contains $_.Name) -and
    (
        ($_.CommandLine -and $_.CommandLine.Contains($workspace)) -or
        ($includeAllJava -and (@('java.exe', 'javaw.exe') -contains $_.Name))
    )
}
$count = 0
foreach ($process in $matches) {
    try {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
        $count++
    } catch {}
}
Write-Output $count
"""
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    script,
                    str(workspace_path),
                    "1" if include_all_java else "0",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
        except OSError:
            return 0

        try:
            return int((result.stdout or "0").strip().splitlines()[-1])
        except (IndexError, ValueError):
            return 0

    @classmethod
    def _workspace_key(cls, workspace_path: Path) -> Path:
        try:
            return workspace_path.resolve()
        except OSError:
            return workspace_path.absolute()

    @classmethod
    def _is_same_or_child(cls, path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return path == parent
