"""Workspace file locks that protect user-owned files from generators."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


LOCKS_PATH = Path(".fabricstudio") / "file_locks.json"


@dataclass
class ProtectionReport:
    """Files restored after a generator attempted to change them."""

    restored: list[Path] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.restored)


@dataclass(frozen=True)
class _Snapshot:
    existed: bool
    content: bytes | None
    mode: int | None
    modified_ns: int | None


class FileLockManager:
    """Persist and enforce generator-only locks for one workspace.

    Locks are logical rather than operating-system read-only flags. Users and
    collaboration peers can still edit a locked file; generator actions are
    wrapped in :meth:`protect_generator_changes` and any locked file is restored
    if the generator writes to or deletes it.
    """

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.config_path = self.workspace_root / LOCKS_PATH

    def locked_paths(self) -> list[Path]:
        return [self.workspace_root / Path(value) for value in self._load()]

    def is_locked(self, path: Path) -> bool:
        relative = self._relative(path)
        return relative in self._load()

    def lock(self, path: Path) -> None:
        target = self._absolute(path)
        if not target.is_file():
            raise ValueError("Only existing files can be locked.")

        relative = self._relative(target)
        locked = self._load()
        if relative not in locked:
            locked.append(relative)
            self._write(locked)

    def unlock(self, path: Path) -> None:
        relative = self._relative(path)
        locked = self._load()
        if relative in locked:
            locked.remove(relative)
            self._write(locked)

    @contextmanager
    def protect_generator_changes(self) -> Iterator[ProtectionReport]:
        """Restore locked files when the wrapped generator action completes."""

        report = ProtectionReport()
        snapshots = {
            relative: self._snapshot(self.workspace_root / Path(relative))
            for relative in self._load()
        }
        try:
            yield report
        finally:
            for relative, snapshot in snapshots.items():
                path = self.workspace_root / Path(relative)
                if self._matches_snapshot(path, snapshot):
                    continue
                self._restore(path, snapshot)
                report.restored.append(path)

    def _load(self) -> list[str]:
        if not self.config_path.exists():
            return []
        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        values = payload.get("locked_files", []) if isinstance(payload, dict) else []
        if not isinstance(values, list):
            return []

        valid: list[str] = []
        for value in values:
            if not isinstance(value, str):
                continue
            try:
                normalized = self._relative(self.workspace_root / Path(value))
            except ValueError:
                continue
            if normalized == LOCKS_PATH.as_posix() or normalized in valid:
                continue
            valid.append(normalized)
        return sorted(valid)

    def _write(self, locked: list[str]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "locked_files": sorted(set(locked))}
        self.config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _absolute(self, path: Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError("File locks must stay inside the workspace.") from exc
        return resolved

    def _relative(self, path: Path) -> str:
        return self._absolute(path).relative_to(self.workspace_root).as_posix()

    @staticmethod
    def _snapshot(path: Path) -> _Snapshot:
        if not path.is_file():
            return _Snapshot(False, None, None, None)
        stat = path.stat()
        return _Snapshot(True, path.read_bytes(), stat.st_mode, stat.st_mtime_ns)

    @staticmethod
    def _matches_snapshot(path: Path, snapshot: _Snapshot) -> bool:
        if not snapshot.existed:
            return not path.exists()
        if not path.is_file():
            return False
        try:
            return path.read_bytes() == snapshot.content
        except OSError:
            return False

    @staticmethod
    def _restore(path: Path, snapshot: _Snapshot) -> None:
        if not snapshot.existed:
            if path.is_file() or path.is_symlink():
                path.unlink()
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(snapshot.content or b"")
        if snapshot.mode is not None:
            os.chmod(path, snapshot.mode)
        if snapshot.modified_ns is not None:
            os.utime(path, ns=(snapshot.modified_ns, snapshot.modified_ns))
