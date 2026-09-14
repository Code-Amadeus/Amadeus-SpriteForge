"""Workspace-relative assets shared by discovery, preview and export."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path, PureWindowsPath
from typing import Any


def resolve_asset(workspace: Path, value: str) -> Path:
    workspace = workspace.resolve()
    if not isinstance(value, str) or not value.strip():
        raise ValueError("An asset path is required")
    value = value.replace("\\", "/")
    # Reject foreign absolute paths even on POSIX, and traversal on every OS.
    relative = Path(value)
    if ".." in relative.parts or (PureWindowsPath(value).drive and not relative.is_absolute()):
        raise ValueError("Asset path must stay inside the selected workspace")
    path = (workspace / relative).resolve()
    if not path.is_relative_to(workspace):
        raise ValueError("Asset path must stay inside the selected workspace")
    return path


def relative_asset(workspace: Path, value: str) -> str:
    return resolve_asset(workspace, value).relative_to(workspace.resolve()).as_posix()


def png_frames(workspace: Path, directory: Path) -> list[Path]:
    directory = resolve_asset(workspace, str(directory))
    return [resolve_asset(workspace, str(p)) for p in sorted(directory.glob("*.png")) if p.is_file()]


def clip_frames(workspace: Path, node: dict) -> list[Path]:
    root = resolve_asset(workspace, node["root"])
    phase = node["phase"]
    directory = root if phase == "flat" else resolve_asset(workspace, str(root / phase))
    frames = png_frames(workspace, directory)
    if not frames:
        raise ValueError(f"No PNG frames for {node['label']!r} at {node['root']} ({phase})")
    return frames


def discover(workspace: Path) -> list[dict]:
    """Expose actual PNG folders, including processed variants, without guessing."""
    groups: dict[str, list[dict]] = {}
    for directory, dirs, files in os.walk(workspace, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in {"exports", "__pycache__"}
                         and not (Path(directory) / d).is_symlink())
        if not any(name.endswith(".png") for name in files):
            continue
        path = resolve_asset(workspace, directory)
        relative = path.relative_to(workspace.resolve()).as_posix()
        parts = Path(relative).parts
        project = parts[1] if len(parts) > 1 and parts[0] == "projects" else parts[0] if parts else "workspace"
        groups.setdefault(project, []).append({"id": relative, "label": relative, "root": relative,
                                                "clips": {"flat": sum(name.endswith(".png") for name in files)}})
    return [{"id": "workspace", "label": "Workspace", "projects": [
        {"id": name, "label": name, "states": states} for name, states in sorted(groups.items())
    ]}]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def atomic_json(path: Path, value: Any) -> None:
    """A rejected or interrupted save never truncates the previous graph."""
    content = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
