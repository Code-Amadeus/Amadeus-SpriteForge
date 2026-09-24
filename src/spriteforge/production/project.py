"""Project-level operations: initialise, plan poses and clips, report status and
connect rendered clips to the behavior graph.

Graph nodes bind to a clip through its stable output root. ``graph_sync`` copies
the render's phase, frame interval and loop mode onto those nodes, and export
refuses a graph whose production-bound nodes are stale, unrendered, out of sync
or failing QA, so a character pack only ever contains reviewed renders.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from ..graph import validate_graph
from ..workspace import atomic_json, read_json, resolve_asset
from . import prompts
from .records import (bound_clip, clip_settings, create_character, create_clip, create_pose, list_owners, list_takes,
                      load_character, load_owner, output_root, production_dir, read_render, render_freshness,
                      save_owner, take_status)
from .tools import default_tools, load_tools, save_tools

CLIP_SETTINGS = {
    "provider": ("generation", "provider", str), "duration": ("generation", "durationS", int),
    "resolution": ("generation", "resolution", str), "seed": ("generation", "seed", int),
    "input_scale": ("generation", "inputScale", float), "interpolate": ("processing", "interpolate", int),
    "pingpong": ("processing", "pingpong", bool), "lock_head": ("processing", "lockHeadFrames", int),
    "lock_tail": ("processing", "lockTailFrames", int), "edge_guard": ("processing", "edgeGuardPx", int),
    "speed": ("playback", "speed", float), "loop_mode": ("playback", "loopMode", str),
}


def init_production(workspace: Path, *, character_id: str, display_name: str, width: int, height: int,
                    base_pose: str = "idle", background=(255, 255, 255), cut_edges=("bottom",)) -> dict:
    if not workspace.is_dir():
        raise ValueError("Workspace does not exist; run 'spriteforge init' first")
    character = create_character(workspace, character_id=character_id, display_name=display_name, width=width,
                                 height=height, base_pose=base_pose, background=tuple(background), cut_edges=list(cut_edges))
    if not (production_dir(workspace) / "prompts.json").exists():
        prompts.save_library(workspace, prompts.default_library())
    if not (production_dir(workspace) / "tools.json").exists():
        save_tools(workspace, default_tools())
    add_pose(workspace, base_pose, "Base idle reference")
    return character


def add_pose(workspace: Path, pose_id: str, description: str = "") -> dict:
    pose = create_pose(workspace, pose_id, description)
    library = prompts.load_library(workspace)
    prompts.ensure_subject(library, pose["prompt"]["subject"], f"describe the {pose_id} pose or expression")
    prompts.save_library(workspace, library)
    return pose


def add_clip(workspace: Path, clip_id: str, source: str, target: str, phase: str | None = None) -> dict:
    clip = create_clip(workspace, clip_id, source, target, phase=phase)
    library = prompts.load_library(workspace)
    hint = f"describe the {target} loop motion" if clip["kind"] == "loop" else f"describe the motion from {source} to {target}"
    prompts.ensure_subject(library, clip["prompt"]["subject"], hint)
    prompts.save_library(workspace, library)
    return clip


def set_clip(workspace: Path, clip_id: str, **changes) -> dict:
    clip = load_owner(workspace, "clip", clip_id)
    for name, value in changes.items():
        if value is None:
            continue
        section, key, kind = CLIP_SETTINGS[name]
        clip[section][key] = kind(value)
    if clip["generation"]["provider"] not in {"manual", *load_tools(workspace).get("providers", {})}:
        raise ValueError(f"Unknown provider {clip['generation']['provider']!r}")
    clip_settings(clip)
    save_owner(workspace, "clip", clip)
    return clip


def _summary(owner: dict, take: dict) -> dict:
    keep = ("id", "createdAt", "state", "source", "prompt", "inputs", "media", "normalization", "qa", "rejected",
            "history", "error")
    return {**{k: take.get(k) for k in keep}, "status": take_status(owner, take)}


def overview(workspace: Path) -> dict:
    character = load_character(workspace)
    tools = load_tools(workspace)
    anchors_take = (character.get("anchors") or {}).get("take")
    poses = []
    for pose in list_owners(workspace, "pose"):
        takes = [_summary(pose, t) for t in list_takes(workspace, "pose", pose["id"])]
        accepted = next((t for t in takes if t["status"] == "accepted"), None)
        recheck = bool(accepted and pose["id"] != character["basePose"]
                       and (accepted.get("qa") or {}).get("anchorsTake") != anchors_take)
        poses.append({**pose, "takes": takes, "needsRecheck": recheck})
    clips = []
    for clip in list_owners(workspace, "clip"):
        state, reasons = render_freshness(workspace, clip)
        render = read_render(workspace, clip["id"])
        clips.append({**clip, "takes": [_summary(clip, t) for t in list_takes(workspace, "clip", clip["id"])],
                      "output": output_root(clip["id"]),
                      "render": {"state": state, "reasons": reasons, **({k: render.get(k) for k in (
                          "take", "frameCount", "frameIntervalMs", "loopMode", "phase", "renderedAt", "qa")} if render else {})}})
    providers = {name: {"model": config.get("model"), "keySet": bool(os.environ.get(str(config.get("apiKeyEnv") or "")))}
                 for name, config in (tools.get("providers") or {}).items()}
    return {"character": character, "prompts": prompts.load_library(workspace), "poses": poses, "clips": clips,
            "tools": {"ffmpeg": bool(shutil.which(tools.get("ffmpeg") or "ffmpeg")), "alpha": bool(tools.get("alpha")),
                      "interpolate": bool(tools.get("interpolate")), "providers": providers}}


def graph_sync(workspace: Path, *, add_missing: bool = False) -> dict:
    path = resolve_asset(workspace, "graph_config.json")
    graph = read_json(path) if path.exists() else {"nodes": [], "edges": []}
    changes, added, missing = [], [], []
    bound = set()
    for node in graph["nodes"]:
        clip_id = bound_clip(node.get("root"))
        if clip_id is None:
            continue
        bound.add(clip_id)
        render = read_render(workspace, clip_id)
        if render is None:
            missing.append(clip_id)
            continue
        node["root"] = output_root(clip_id)
        for key in ("phase", "frameIntervalMs", "loopMode"):
            if node.get(key) != render[key]:
                changes.append(f"{node['id']}.{key}: {node.get(key)!r} -> {render[key]!r}")
                node[key] = render[key]
    if add_missing:
        character = load_character(workspace)
        labels = {n["label"] for n in graph["nodes"]}
        bottom = max((n.get("y", 0) for n in graph["nodes"]), default=0)
        for clip in list_owners(workspace, "clip"):
            render = read_render(workspace, clip["id"])
            if clip["id"] in bound or render is None or clip["id"] in labels:
                continue
            index = len(added)
            root = not any(n.get("isRoot") for n in graph["nodes"]) and clip["kind"] == "loop" \
                and clip["to"] == character["basePose"]
            graph["nodes"].append({"id": clip["id"], "label": clip["id"], "root": output_root(clip["id"]),
                                   "phase": render["phase"], "frameIntervalMs": render["frameIntervalMs"],
                                   "loopMode": render["loopMode"], "isRoot": root,
                                   "x": 90 + (index % 6) * 150, "y": bottom + 120 + (index // 6) * 110})
            added.append(clip["id"])
    if changes or added:
        graph = validate_graph(workspace, graph)
        atomic_json(path, graph)
    return {"changes": changes, "added": added, "notRendered": missing}


def export_gate(workspace: Path, graph: dict) -> dict:
    """Refuse an export whose production-bound nodes or seams fail QA."""
    from .checks import graph_report
    report = graph_report(workspace, graph, load_character(workspace))
    problems = [f"{n['label']}: {'; '.join(n['issues'])}" for n in report["nodes"] if n["issues"]]
    problems += [f"{e['from']} -> {e['to']}: seam faceL={e['faceL']} dHeadTop={e['dHeadTop']} dHeadCenter={e['dHeadCenter']}"
                 for e in report["edges"] if e["level"] == "fail"]
    if problems:
        raise ValueError("Production QA blocks export: " + " | ".join(problems[:8]))
    return report
