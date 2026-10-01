"""Project-level operations: initialise, plan poses and clips, report status and
connect rendered clips to the behavior graph.

Graph nodes bind to a clip through its stable output root. ``graph_sync`` copies
the render's phase, frame interval and loop mode onto those nodes, and export
refuses a graph whose production-bound nodes are stale, unrendered, out of sync
or failing QA, so a character pack only ever contains reviewed renders.
"""
from __future__ import annotations

import math
import shutil
from copy import deepcopy
from pathlib import Path

from ..graph import validate_graph
from ..workspace import atomic_json, read_json, resolve_asset
from . import prompts
from .records import (accepted_take, bound_clip, canvas_size, check_id, clip_settings, create_character, create_clip, create_pose,
                      list_owners, list_takes, load_character, load_owner, output_root, owner_dir, production_dir, read_render,
                      render_freshness, save_character, save_owner, take_status)
from .mouth import default_set
from .providers import IMAGE_PROVIDERS, PROVIDERS, provider_status
from .tools import default_tools, load_tools, save_tools

CLIP_SETTINGS = {
    "provider": ("generation", "provider", str), "duration": ("generation", "durationS", int),
    "resolution": ("generation", "resolution", str), "seed": ("generation", "seed", int),
    "input_scale": ("generation", "inputScale", float), "last_frame": ("generation", "lastFrame", str),
    "register": ("processing", "register", bool),
    "interpolate": ("processing", "interpolate", int), "margin": ("processing", "marginPx", int),
    "pingpong": ("processing", "pingpong", bool), "lock_head": ("processing", "lockHeadFrames", int),
    "lock_tail": ("processing", "lockTailFrames", int), "edge_guard": ("processing", "edgeGuardPx", int),
    "speed": ("playback", "speed", float), "loop_mode": ("playback", "loopMode", str),
}
CANVAS_FORMAT = "spriteforge.production.canvas.v1"


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


def add_variant(workspace: Path, source_id: str, clip_id: str) -> dict:
    """Create a sibling clip and subject block; takes and renders stay with their owner."""
    source = load_owner(workspace, "clip", source_id)
    path = owner_dir(workspace, "clip", clip_id) / "clip.json"
    if path.parent.exists():
        raise ValueError(f"Clip {clip_id} already exists")
    for pose_id in (source["from"], source["to"]):
        load_owner(workspace, "pose", pose_id)
    library = prompts.load_library(workspace)
    subject = source["prompt"]["subject"]
    text = prompts.current(library, subject)["text"]
    clone = {"format": source["format"], "id": clip_id,
             **deepcopy({key: source[key] for key in ("kind", "from", "to", "phase", "generation", "processing",
                                                     "playback", "mouth")}),
             "prompt": {"template": source["prompt"]["template"], "subject": f"clip.{clip_id}"},
             "acceptedTake": None, "notes": ""}
    clip_settings(clone)
    prompts.set_block(library, clone["prompt"]["subject"], text, library["blocks"][subject].get("description"))
    # Publish the subject first so a visible clip never references a missing block.
    prompts.save_library(workspace, library)
    save_owner(workspace, "clip", clone)
    return clone


def plan_clips(workspace: Path, entries: object) -> list[dict]:
    """Plan explicit clips for approved stills without generating, approving or binding them."""
    if not isinstance(entries, list) or not entries:
        raise ValueError("Clip plan needs a non-empty list")
    ids = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - {"id", "from", "to", "phase"} or not {"id", "from", "to"} <= set(entry):
            raise ValueError("Planned clips need id, from, to and optional phase")
        clip_id = check_id(entry["id"], "Clip")
        if clip_id in ids or owner_dir(workspace, "clip", clip_id).exists():
            raise ValueError(f"Clip {clip_id} already exists or is repeated")
        ids.add(clip_id)
        if entry.get("phase") is not None and entry["phase"] not in {"in", "loop", "out"}:
            raise ValueError("Clip phase must be in, loop or out")
        for pose_id in (entry["from"], entry["to"]):
            accepted_take(workspace, "pose", pose_id)
    return [add_clip(workspace, entry["id"], entry["from"], entry["to"], entry.get("phase")) for entry in entries]


def set_clip(workspace: Path, clip_id: str, *, mouth: str | None = None, mouth_source: str | None = None,
             **changes) -> dict:
    """Change clip settings. ``mouth`` names a mouth set (or 'off'); ``mouth_source`` picks the
    closed-mouth image of the silence overlay: 'shared' (default: the pose's closed mouth),
    'still' (the loop's own pose still), 'frame:N' or 'pose:ID'."""
    clip = load_owner(workspace, "clip", clip_id)
    for name, value in changes.items():
        if value is None:
            continue
        section, key, kind = CLIP_SETTINGS[name]
        clip[section][key] = kind(value)
    if mouth is not None:
        if mouth == "off":
            clip["mouth"] = None
        else:
            if mouth not in (load_character(workspace).get("mouthSets") or {}):
                raise ValueError(f"Unknown mouth set {mouth!r}; define it with 'production mouth set'")
            current = (clip.get("mouth") or {}).get("closedSource") or {"kind": "shared"}
            clip["mouth"] = {"set": mouth, "closedSource": current}
    if mouth_source is not None:
        if not clip.get("mouth"):
            raise ValueError("Choose a mouth set before its closed-mouth source")
        kind, _, value = mouth_source.partition(":")
        clip["mouth"]["closedSource"] = ({"kind": "frame", "index": int(value)} if kind == "frame" and value.isdigit()
                                         else {"kind": "pose", "pose": value} if kind == "pose"
                                         else {"kind": mouth_source})
    if clip["generation"]["provider"] not in {"manual", *PROVIDERS}:
        raise ValueError(f"Unknown video provider {clip['generation']['provider']!r}; available: manual, {', '.join(PROVIDERS)}")
    clip_settings(clip)
    save_owner(workspace, "clip", clip)
    return clip


def set_mouth_set(workspace: Path, name: str, **values: float | None) -> dict:
    """Create or change a mouth set: the expected mouth ellipse (canvas-centre pixels) and curve.
    A new set starts from the default derived from the approved base still."""
    character = load_character(workspace)
    sets = dict(character.get("mouthSets") or {})
    current = dict(sets.get(check_id(name, "Mouth set")) or {})
    if not current and character.get("anchors"):
        current = default_set(character["anchors"], *canvas_size(character))
    current.update({k: float(v) for k, v in values.items() if v is not None})
    if set(current) != {"cx", "cy", "width", "height", "curve"} or not all(math.isfinite(v) for v in current.values()) \
            or current["width"] <= 0 or current["height"] <= 0:
        raise ValueError("A mouth set needs finite cx, cy, curve and a positive width and height")
    sets[name] = current
    character["mouthSets"] = sets
    save_character(workspace, character)
    return current


def set_closed_mouth(workspace: Path, source_pose: str | None, *, pose_id: str | None = None) -> dict:
    """Choose whose still is the closed mouth: for the whole character (the shared default,
    normally a front pose) or for one pose such as a side view. None restores the default."""
    if source_pose is not None:
        load_owner(workspace, "pose", source_pose)
    if pose_id is None:
        character = load_character(workspace)
        character["closedMouth"] = source_pose
        save_character(workspace, character)
        return character
    pose = load_owner(workspace, "pose", pose_id)
    pose["closedMouth"] = source_pose
    save_owner(workspace, "pose", pose)
    return pose


def _summary(owner: dict, take: dict) -> dict:
    from .clips import generation_snapshot
    keep = ("id", "createdAt", "state", "source", "prompt", "inputs", "media", "normalization", "qa", "rejected",
            "history", "error", "basedOn")
    return {**{k: take.get(k) for k in keep}, "status": take_status(owner, take),
            "note": take.get("note", (take.get("source") or {}).get("note", "")),
            "generation": generation_snapshot(take)}


def _takes(workspace: Path, kind: str, owner: dict) -> list[dict]:
    takes = sorted(list_takes(workspace, kind, owner["id"]), key=lambda take: (take["createdAt"], take["id"]))
    return [{**_summary(owner, take), "version": index} for index, take in enumerate(takes, 1)]


def _preview(render, library: dict, character: dict, owner: dict) -> dict:
    """A prompt preview that reports a template error instead of failing the whole overview."""
    try:
        return render(library, character, owner)
    except ValueError as exc:
        return {"text": "", "negative": "", "blocks": {}, "placeholders": [], "complete": False, "error": str(exc)}


def overview(workspace: Path) -> dict:
    from .clips import clip_cost_estimate
    from .studio import studio_summary
    from .tools import ui_settings
    character = load_character(workspace)
    tools = load_tools(workspace)
    library = prompts.load_library(workspace)
    anchors_take = (character.get("anchors") or {}).get("take")
    poses = []
    for pose in list_owners(workspace, "pose"):
        takes = _takes(workspace, "pose", pose)
        accepted = next((t for t in takes if t["status"] == "accepted"), None)
        recheck = bool(accepted and pose["id"] != character["basePose"]
                       and (accepted.get("qa") or {}).get("anchorsTake") != anchors_take)
        poses.append({**pose, "takes": takes, "needsRecheck": recheck,
                      "promptPreview": _preview(prompts.pose_prompt, library, character, pose),
                      "referencePromptPreview": _preview(prompts.still_reference_prompt, library, character, pose)})
    clips = []
    for clip in list_owners(workspace, "clip"):
        state, reasons = render_freshness(workspace, clip)
        render = read_render(workspace, clip["id"])
        takes = _takes(workspace, "clip", clip)
        clips.append({**clip, "takes": takes, "costEstimate": clip_cost_estimate(takes, clip["generation"]),
                      "promptPreview": _preview(prompts.clip_prompt, library, character, clip), "output": output_root(clip["id"]),
                      "render": {"state": state, "reasons": reasons, **({k: render.get(k) for k in (
                          "take", "frameCount", "frameIntervalMs", "loopMode", "phase", "renderedAt", "durationS", "qa", "mouth")} if render else {})}})
    providers = {name: {"kind": "video" if name in PROVIDERS else "image" if name in IMAGE_PROVIDERS else None,
                        "model": config.get("model"), **provider_status(name, config)}
                 for name, config in (tools.get("providers") or {}).items()}
    return {"character": character, "prompts": library, "poses": poses, "clips": clips,
            "canvas": canvas_layout(workspace),
            **studio_summary(workspace, character, poses, clips),
            "tools": {"ffmpeg": bool(shutil.which(tools.get("ffmpeg") or "ffmpeg")), "alpha": bool(tools.get("alpha")),
                      "interpolate": bool(tools.get("interpolate")), "providers": providers, **ui_settings(tools)}}


def canvas_layout(workspace: Path) -> dict[str, list[float]]:
    """Card positions on the production canvas, keyed ``pose:<id>`` or ``clip:<id>``. They are
    layout only: no production step reads them, and the behavior graph has its own layout."""
    path = production_dir(workspace) / "canvas.json"
    data = read_json(path) if path.is_file() else {}
    positions = data.get("positions") if isinstance(data, dict) else None
    return positions if isinstance(positions, dict) else {}


def save_canvas_layout(workspace: Path, positions: object) -> dict[str, list[float]]:
    if not isinstance(positions, dict):
        raise ValueError("Canvas positions must map card keys to [x, y]")
    clean = {}
    for key, value in positions.items():
        kind, _, owner_id = str(key).partition(":")
        if kind not in {"pose", "clip"}:
            raise ValueError(f"Unknown canvas card {key!r}")
        check_id(owner_id, kind.title())
        if not isinstance(value, list) or len(value) != 2 or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value):
            raise ValueError(f"Canvas position of {key} must be [x, y]")
        clean[f"{kind}:{owner_id}"] = [round(float(v), 1) for v in value]
    atomic_json(production_dir(workspace) / "canvas.json", {"format": CANVAS_FORMAT, "positions": clean})
    return clean


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
        values = {"root": output_root(clip_id), **{key: render[key] for key in ("phase", "frameIntervalMs", "loopMode")}}
        for key, value in values.items():
            if node.get(key) != value:
                changes.append(f"{node['id']}.{key}: {node.get(key)!r} -> {value!r}")
                node[key] = value
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


def set_runtime_clips(workspace: Path, clip_ids: list[str]) -> list[str]:
    """Clips exported by label without a graph node; Amadeus plays 'smile' and 'sad' after speech."""
    character = load_character(workspace)
    for clip_id in clip_ids:
        load_owner(workspace, "clip", clip_id)
    character["runtimeClips"] = list(dict.fromkeys(clip_ids))
    save_character(workspace, character)
    return character["runtimeClips"]


def export_nodes(workspace: Path, graph: dict) -> list[dict]:
    """The graph's nodes plus the runtime clips as unconnected nodes bound to their renders."""
    labels = {node["label"] for node in graph["nodes"]}
    nodes = list(graph["nodes"])
    for clip_id in load_character(workspace).get("runtimeClips") or []:
        render = read_render(workspace, clip_id)
        if clip_id in labels:
            raise ValueError(f"Runtime clip {clip_id} is also a graph node label")
        if render is None:
            raise ValueError(f"Runtime clip {clip_id} has no render")
        nodes.append({"id": f"runtime:{clip_id}", "label": clip_id, "root": output_root(clip_id),
                      **{key: render[key] for key in ("phase", "frameIntervalMs", "loopMode")}})
    return nodes


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


def export_mouth(workspace: Path, graph: dict, *, no_mouth: bool = False) -> dict:
    """Runtime mouth profiles and closed-mouth images of production-bound speaking loops.

    Profiles are keyed by node label and carry only runtime fields: the mask track and
    size, the closed image's mouth anchor, and the per-frame closedness ranking. The
    overlay is the tone-matched closed mouth stored with the render."""
    character = load_character(workspace)
    sets = character.get("mouthSets") or {}
    result = {"header": {"version": 2, "canvas_size": list(canvas_size(character)), "profile_kind": "runtime_ktx2"},
              "expressions": {}, "profiles": {}, "overlays": {}}
    if no_mouth:
        return result
    for node in graph["nodes"]:
        clip_id = bound_clip(node["root"])
        render = read_render(workspace, clip_id) if clip_id else None
        mouth = (render or {}).get("mouth")
        if not mouth or node["label"] in result["profiles"]:
            continue
        if mouth["set"] not in sets:
            raise ValueError(f"{node['label']}: mouth set {mouth['set']!r} no longer exists")
        result["expressions"][mouth["set"]] = render["recipe"]["mouthSet"]
        result["profiles"][node["label"]] = {
            "mouth_set": mouth["set"], **mouth["roi"], "closed_frame_idx": mouth["closedFrame"],
            "openness": mouth["openness"], "anchor_track": mouth["anchorTrack"],
            "runtime_overlay_anchor": mouth["sourceAnchor"]}
        result["overlays"][node["label"]] = resolve_asset(workspace, output_root(clip_id)) / mouth["overlay"]
    return result
