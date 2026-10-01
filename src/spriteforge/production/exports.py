"""Explicit workspace exports and comparisons against a read-only installed pack.

PNG changes cannot establish a KTX2 texture difference before encoding. Comparison
uses recorded exports of the same source bytes; otherwise it reports unknown.
Runtime pack formats and installation directories are never modified here.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from time import monotonic

from ..character_pack import load_character_pack
from ..exporter import UASTC_LEVEL, ZSTD_LEVEL, export_pack
from ..graph import validate_graph
from ..workspace import atomic_json, clip_frames, read_json, resolve_asset
from .checks import graph_report
from .media import write_durable
from .project import export_mouth, export_nodes
from .records import bound_clip, load_character, load_owner, now, production_dir
from .tools import load_tools

EXPORTS_FORMAT = "spriteforge.production.exports.v1"
EXPORT_LOCK = threading.Lock()


def validate_version(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value) or value.endswith("."):
        raise ValueError("Export version must use 1-64 letters, digits, dots, underscores or hyphens")
    return value


def history(workspace: Path) -> list[dict]:
    path = production_dir(workspace) / "exports.json"
    if not path.is_file():
        return []
    record = read_json(path)
    if record.get("format") != EXPORTS_FORMAT or not isinstance(record.get("exports"), list):
        raise ValueError("Unsupported production/exports.json format")
    return record["exports"]


def suggested_version(workspace: Path) -> str:
    base = datetime.now().strftime("%Y.%m.%d")
    used = {item["version"] for item in history(workspace)}
    version, suffix = base, 1
    while version in used or (production_dir(workspace) / "exports" / version).exists() \
            or (production_dir(workspace) / "exports" / (version + ".graph-layout.json")).exists():
        suffix += 1
        version = f"{base}-{suffix}"
    return version


@lru_cache(maxsize=32768)
def _cached_hash(path: str, modified: int, size: int) -> str:
    # File facts invalidate the bounded cache; installed packs may have many textures.
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash(path: Path) -> str:
    stat = path.stat()
    return _cached_hash(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def _sequence_hash(paths) -> str:
    return hashlib.sha256(json.dumps([_hash(path) for path in paths], separators=(",", ":")).encode()).hexdigest()


def _installed_path(workspace: Path) -> Path | None:
    raw = (load_tools(workspace).get("amadeus") or {}).get("packDir")
    if not raw:
        return None
    path = Path(raw).expanduser()
    return (path if path.is_absolute() else workspace / path).resolve()


def _texture_hashes(pack) -> dict[str, str]:
    return {label: _sequence_hash([*frames, *pack.mouth_overlay_paths.get(label, ())])
            for label, frames in pack.clip_paths.items()}


def _installed(workspace: Path, *, textures: bool = True) -> dict:
    path = _installed_path(workspace)
    if path is None:
        return {"configured": False}
    result = {"configured": True, "path": str(path)}
    try:
        pack = load_character_pack(path)
        result.update(version=pack.manifest["version"], labels=list(pack.manifest["clips"]),
                      manifestSha256=_hash(path / "runtime_manifest.json"))
        if textures:
            result["textureHashes"] = _texture_hashes(pack)
    except (ValueError, OSError, KeyError) as exc:
        result["error"] = str(exc)
    return result


def _scope(workspace: Path) -> tuple[dict, dict, dict]:
    graph = validate_graph(workspace, read_json(resolve_asset(workspace, "graph_config.json")))
    scope = {"nodes": export_nodes(workspace, graph), "edges": graph["edges"]}
    selected = {}
    for node in scope["nodes"]:
        selected.setdefault(node["label"], (node, clip_frames(workspace, node)))
    return graph, scope, selected


def _source_hashes(workspace: Path, scope: dict, selected: dict) -> dict[str, str]:
    overlays = export_mouth(workspace, scope)["overlays"]
    return {label: _sequence_hash([*frames, *([overlays[label]] if label in overlays else [])])
            for label, (_, frames) in selected.items()}


def installed_diff(workspace: Path) -> dict:
    installed = _installed(workspace)
    result = {"configured": installed["configured"], "installedVersion": installed.get("version"),
              "added": [], "updated": [], "removed": [], "unknown": [], "draftNotes": ""}
    if installed.get("path"):
        result["path"] = installed["path"]
    try:
        _, scope, selected = _scope(workspace)
        sources = _source_hashes(workspace, scope, selected)
    except (ValueError, OSError, KeyError) as exc:
        result["error"] = str(exc)
        return result
    if installed.get("error"):
        result["error"] = installed["error"]
        result["unknown"] = [{"label": label, "reason": "installedUnavailable"} for label in selected]
        return result
    installed_labels = set(installed.get("labels", []))
    for label, (node, _) in selected.items():
        item = {"label": label, "clip": bound_clip(node["root"])}
        if label not in installed_labels:
            result["added"].append(item)
            continue
        matching = next((record for record in reversed(history(workspace))
                         if (record.get("sourceHashes") or {}).get(label) == sources[label]
                         and label in (record.get("textureHashes") or {})), None)
        if matching is None:
            result["unknown"].append({**item, "reason": "awaitingEncoding"})
        elif matching["textureHashes"][label] != installed["textureHashes"][label]:
            result["updated"].append({**item, "reason": "textureHashChanged"})
    result["removed"] = [{"label": label} for label in sorted(installed_labels - selected.keys())]
    notes = [f"{name.title()}: {', '.join(item['label'] for item in result[name])}."
             for name in ("added", "updated", "removed") if result[name]]
    if result["unknown"]:
        notes.append("Texture comparison awaits an encoded export for: " + ", ".join(item["label"] for item in result["unknown"]) + ".")
    result["draftNotes"] = "\n".join(notes) or "No recorded texture changes."
    return result


def preflight(workspace: Path) -> dict:
    character, tools = load_character(workspace), load_tools(workspace)
    installed = _installed(workspace, textures=False)
    checks, selected, scope = [], {}, {"nodes": [], "edges": []}
    try:
        _, scope, selected = _scope(workspace)
        report = graph_report(workspace, scope, character)
        problems = [{"node": node["node"], "clip": node["clip"], "message": "; ".join(node["issues"])}
                    for node in report["nodes"] if node["issues"]]
        problems += [{"from": edge["from"], "to": edge["to"], "message": "Graph seam fails QA"}
                     for edge in report["edges"] if edge["level"] == "fail"]
    except (ValueError, OSError, KeyError) as exc:
        problems = [{"message": str(exc)}]
    checks.append({"id": "qa", "level": "fail" if problems else "pass", "facts": {"count": len(problems), "issues": problems}})
    bound_poses = set()
    speaking = []
    for node in scope["nodes"]:
        clip_id = bound_clip(node["root"])
        if clip_id:
            clip = load_owner(workspace, "clip", clip_id)
            bound_poses.update((clip["from"], clip["to"]))
            if clip.get("mouth"):
                speaking.append(node["label"])
    from .records import list_owners
    unfinished = [pose["id"] for pose in list_owners(workspace, "pose") if pose.get("acceptedTake") and pose["id"] not in bound_poses]
    checks.append({"id": "poses", "level": "watch" if unfinished else "pass", "facts": {"poses": unfinished}})
    missing, mouth_error = [], None
    try:
        mouths = export_mouth(workspace, scope)
        missing = [label for label in speaking if label not in mouths["profiles"]
                   or label not in mouths["overlays"] or not mouths["overlays"][label].is_file()]
    except (ValueError, OSError, KeyError) as exc:
        mouth_error, missing = str(exc), speaking
    checks.append({"id": "mouth", "level": "fail" if missing or mouth_error else "pass",
                   "facts": {"count": len(speaking), "missing": missing, **({"error": mouth_error} if mouth_error else {})}})
    checks.append({"id": "canvas", "level": "pass", "facts": dict(character["canvas"])})
    encoder_ready = bool(shutil.which(tools.get("toktx") or "toktx"))
    encoding = {"uastc": UASTC_LEVEL, "zstd": ZSTD_LEVEL}
    checks.append({"id": "encoding", "level": "pass" if encoder_ready else "fail", "facts": {**encoding, "ready": encoder_ready}})
    added = sorted(set(selected) - set(installed.get("labels", []))) if not installed.get("error") else []
    checks.append({"id": "labels", "level": "watch" if added else "pass", "facts": {"labels": added}})
    frames = sum(len(paths) for _, paths in selected.values())
    records = history(workspace)
    measured = next((record for record in reversed(records) if record.get("frames", 0) > 0 and record.get("durationS", 0) > 0), None)
    seconds = round(frames * measured["durationS"] / measured["frames"], 1) if measured else None
    checks.append({"id": "duration", "level": "pass", "facts": {"frames": frames, "seconds": seconds}})
    return {"checks": checks, "blockingCount": len(problems) + sum(check["level"] == "fail" for check in checks if check["id"] != "qa"),
            "frameCount": frames, "durationEstimateS": seconds, "suggestedVersion": suggested_version(workspace),
            "encoding": encoding, "installed": {key: value for key, value in installed.items() if key not in {"labels", "manifestSha256"}},
            "history": [{**{key: value for key, value in record.items() if key not in {"sourceHashes", "textureHashes", "manifestSha256"}},
                         "installed": bool(installed.get("manifestSha256") and installed["manifestSha256"] == record.get("manifestSha256"))}
                        for record in reversed(records)]}


def export_workspace(workspace: Path, version: str, *, notes: str = "", log=print) -> dict:
    version = validate_version(version)
    if not isinstance(notes, str):
        raise ValueError("Release notes must be text")
    output = resolve_asset(workspace, f"production/exports/{version}")
    installed = _installed_path(workspace)
    if installed is not None and (output == installed or output.is_relative_to(installed) or installed.is_relative_to(output)):
        raise ValueError("An export must never write into the installed pack directory")
    if not EXPORT_LOCK.acquire(blocking=False):
        raise ValueError("Another export is running")
    try:
        if output.exists() or any(record["version"] == version for record in history(workspace)):
            raise ValueError("This export version already exists; choose a new version")
        character, tools = load_character(workspace), load_tools(workspace)
        _, scope, selected = _scope(workspace)
        sources = _source_hashes(workspace, scope, selected)
        log(f"Encoding {sum(len(paths) for _, paths in selected.values())} frames with UASTC {UASTC_LEVEL}, zstd {ZSTD_LEVEL}")
        started = monotonic()

        def progress(done, total):
            if done in (1, total) or done % max(1, total // 50) == 0:
                log(f"Encoded {done}/{total} textures")

        manifest = export_pack(workspace, output, pack_id=character["id"], display_name=character["displayName"], version=version,
                               toktx=tools.get("toktx") or "toktx", progress=progress)
        duration = round(monotonic() - started, 3)
        write_durable(output / "RELEASE_NOTES.md", notes.encode("utf-8"))
        pack = load_character_pack(output)
        # A changed source during encoding is not a proven source-to-texture match.
        if sources != _source_hashes(workspace, scope, selected):
            sources = {}
        record = {"version": version, "createdAt": now(), "output": output.relative_to(workspace.resolve()).as_posix(),
                  "frames": manifest["frameCount"], "durationS": duration, "notes": notes,
                  "sourceHashes": sources, "textureHashes": _texture_hashes(pack),
                  "manifestSha256": _hash(output / "runtime_manifest.json")}
        atomic_json(production_dir(workspace) / "exports.json", {"format": EXPORTS_FORMAT, "exports": [*history(workspace), record]})
        log(f"Exported {version}; the installed pack was not changed")
        return {key: value for key, value in record.items() if key not in {"sourceHashes", "textureHashes", "manifestSha256"}}
    finally:
        EXPORT_LOCK.release()
