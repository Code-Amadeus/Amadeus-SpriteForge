"""Import a character made with the earlier tools: its SpriteForge workspace and shipped pack.

The shipped pack records what was released: the clips with their frames and timing,
the behavior graph and the mouth overlays. The legacy workspace holds the PNG
sources. ``plan_import`` reads both without writing to them and returns a plan to
review; ``apply_import`` builds production records from a plan and can be run again
after an interruption.

- A clip's source is the legacy folder that holds all its frame names and whose KTX2
  sidecar folder exists (the variant the packager encoded), within the project of the
  legacy graph node with the same id when there is one. When several variants qualify,
  a sidecar that still holds the clip's first texture decides by comparing it with the
  pack's, then the variant the legacy node names. Each folder serves one clip.
- A pose is a set of endpoints that meet: the two ends of a loop, and the tail and
  head joined by a graph edge, when their head anchors agree within the character's
  tolerances. An edge whose ends disagree stays in the graph and is reported. A clip
  outside the graph joins the pose whose endpoint has the most similar face. A pose's
  still is its most typical endpoint.
- Frames keep their pixels. A shorter frame is padded at the top (the runtime aligns
  frames to the bottom), a wider clip keeps its width as a symmetric canvas margin, and
  clips render without registration or locks at the shipped frame interval.
- A speaking loop keeps its shipped mouth set and closed-mouth image: one of its own
  frames, or the still of the pose whose endpoint the pack used.
"""
from __future__ import annotations

import re
import shutil
from collections import Counter
from pathlib import Path, PurePosixPath

import cv2
import numpy as np

from ..character_pack import CHARACTER_PACK_FORMAT
from ..workspace import atomic_json, read_json, resolve_asset
from .checks import graph_report
from .clips import import_clip_take
from .geometry import composite, measure
from .media import read_bgra, sorted_pngs, write_png
from .project import (add_clip, add_pose, export_nodes, graph_sync, init_production, set_clip, set_mouth_set,
                      set_runtime_clips)
from .records import (DEFAULT_TOLERANCES, decide, load_character, load_owner, output_root, production_dir,
                      render_freshness)
from .render import render_clip
from .stills import approve_still, import_still, set_expected

PLAN_FORMAT = "spriteforge.production.legacy-plan.v1"
FACE_BOX = (0.10, 0.03, 0.30)  # half width, top and bottom below the head top, as canvas fractions
WHITE = (255, 255, 255)


def conform(image: np.ndarray, width: int, height: int) -> tuple[np.ndarray, int, int]:
    """The canvas part of a frame, with the top padding and side margin that place it there."""
    h, w = image.shape[:2]
    pad, margin = height - h, (w - width) // 2
    if pad < 0 or w < width or (w - width) % 2:
        raise ValueError(f"A {w}x{h} frame cannot be centred at the bottom of a {width}x{height} canvas")
    return pad_top(image, pad)[:, margin:margin + width], pad, margin


def pad_top(image: np.ndarray, rows: int) -> np.ndarray:
    return np.concatenate([np.zeros((rows, *image.shape[1:]), image.dtype), image]) if rows else image


def _stems(clip: dict) -> list[str]:
    return [PurePosixPath(frame).stem for frame in clip["frames"]]


def _endpoint(path: Path, width: int, height: int) -> dict:
    view, pad, margin = conform(read_bgra(path)[0], width, height)
    metrics = measure(view)
    gray = cv2.cvtColor(composite(view, WHITE), cv2.COLOR_BGR2GRAY).astype(np.float32)
    return {"top": metrics["headTopY"], "centre": metrics["headCenterX"], "gray": gray, "pad": pad, "margin": margin}


def _face_distance(a: dict, b: dict, width: int, height: int) -> float:
    half, top, bottom = FACE_BOX
    x0, x1 = max(0, round(a["centre"] - half * width)), round(a["centre"] + half * width)
    y0, y1 = round(a["top"] + top * height), round(a["top"] + bottom * height)
    return float(np.abs(a["gray"][y0:y1, x0:x1] - b["gray"][y0:y1, x0:x1]).mean())


def _resolve_sources(legacy: Path, pack: Path, manifest: dict, graph: dict, legacy_nodes: dict,
                     notes: list[str]) -> dict:
    suffix = f"_ktx2_uastc_q{manifest.get('quality')}_z{manifest.get('zcmp')}"
    encoded = sorted(folder.with_name(folder.name[:-len(suffix)]) for folder in (legacy / "projects").glob(f"*/*{suffix}")
                     if folder.is_dir())
    homes = {}
    for node in graph["nodes"]:
        parts = PurePosixPath(str((legacy_nodes.get(node["id"]) or {}).get("root") or "").replace("\\", "/")).parts
        if len(parts) >= 4 and parts[0] == "projects":
            homes[node["label"]] = parts[1:4]  # project, variant, state
    clips, taken, sources = manifest["clips"], set(), {}
    for label in sorted(clips, key=lambda name: name not in homes):  # graph clips first, then the rest
        stems, phase = _stems(clips[label]), clips[label]["phase"]
        project, named, state = homes.get(label, (None, None, None))
        candidates = []
        for variant in encoded:
            if project and variant.parent.name != project or not variant.is_dir():
                continue
            for state_dir in sorted(p for p in variant.iterdir() if p.is_dir() and (not state or p.name == state)):
                folder = state_dir / phase
                sidecar = variant.with_name(variant.name + suffix) / state_dir.name / phase
                if folder not in taken and sidecar.is_dir() and all((folder / f"{s}.png").is_file() for s in stems):
                    candidates.append(folder)
        if len(candidates) > 1:
            shipped = (pack / clips[label]["frames"][0]).read_bytes()
            leftovers = {c: c.parent.parent.with_name(c.parent.parent.name + suffix) / c.parent.name / c.name
                         / f"{stems[0]}.ktx2" for c in candidates}
            same = [c for c, f in leftovers.items() if f.is_file() and f.read_bytes() == shipped]
            candidates = same or [c for c, f in leftovers.items() if not f.is_file()] or candidates
        if len(candidates) > 1:
            candidates = [c for c in candidates if c.parent.parent.name == named] or candidates
        if len(candidates) == 1:
            sources[label] = candidates[0]
            taken.add(candidates[0])
        else:
            sources[label] = None
            found = ", ".join(c.relative_to(legacy).as_posix() for c in candidates) or "none"
            notes.append(f"{label}: {len(candidates)} encoded source folders hold its frames ({found}); "
                         "set clips.{label}.source in the plan")
    return sources


def plan_import(legacy: Path, pack: Path) -> dict:
    """Read a legacy workspace and the pack it shipped; return the import plan."""
    legacy, pack = Path(legacy).resolve(), Path(pack).resolve()
    manifest = read_json(pack / "runtime_manifest.json")
    if manifest.get("format") != CHARACTER_PACK_FORMAT:
        raise ValueError("The pack's runtime_manifest.json is not a SpriteForge character pack")
    graph = read_json(pack / manifest["graph"])
    mouth = read_json(pack / manifest["mouthConfig"]) if manifest.get("mouthConfig") else {}
    legacy_nodes = {n["id"]: n for n in read_json(legacy / "graph_config.json").get("nodes", [])}
    clips, notes = manifest["clips"], []
    sources = _resolve_sources(legacy, pack, manifest, graph, legacy_nodes, notes)

    sizes = [read_bgra(folder / f"{_stems(clips[label])[0]}.png")[0].shape[:2] for label, folder in sources.items() if folder]
    if not sizes:
        raise ValueError("No clip source was found in the legacy workspace")
    width = Counter(w for _, w in sizes).most_common(1)[0][0]
    height = max(h for h, w in sizes if w == width)
    if mouth.get("canvas_size") and list(mouth["canvas_size"]) != [width, height]:
        notes.append(f"The mouth config's canvas {mouth['canvas_size']} differs from the frames' {width}x{height}")

    ends: dict[tuple[str, str], dict] = {}
    for label, folder in sources.items():
        if folder is None:
            continue
        stems = _stems(clips[label])
        try:
            for end, stem in (("head", stems[0]), ("tail", stems[-1])):
                ends[(label, end)] = _endpoint(folder / f"{stem}.png", width, height)
        except ValueError as exc:
            sources[label] = None
            ends.pop((label, "head"), None)
            notes.append(f"{label}: {exc}")

    parent = {key: key for key in ends}

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    tolerance = DEFAULT_TOLERANCES

    def compatible(a, b) -> bool:
        return (abs(ends[a]["top"] - ends[b]["top"]) <= tolerance["headTopPx"]
                and abs(ends[a]["centre"] - ends[b]["centre"]) <= tolerance["headCenterPx"])

    def join(a, b, what: str) -> None:
        if a not in ends or b not in ends:
            return
        if compatible(a, b):
            parent[find(a)] = find(b)
        else:
            notes.append(f"{what}: the head top moves {ends[b]['top'] - ends[a]['top']:+d}px and the head centre "
                         f"{ends[b]['centre'] - ends[a]['centre']:+.1f}px, beyond the tolerances; the edge is kept "
                         "and graph QA reports the seam")

    node_label = {n["id"]: n["label"] for n in graph["nodes"]}
    in_graph = set(node_label.values())
    for label, clip in clips.items():
        if clip["loopMode"] == "loop":
            join((label, "tail"), (label, "head"), f"{label} loop")
    for edge in graph["edges"]:
        a, b = node_label[edge["from"]], node_label[edge["to"]]
        if a != b:
            join((a, "tail"), (b, "head"), f"edge {a} -> {b}")
    for label in (name for name in clips if name not in in_graph):
        for end in (("head",) if (label, "tail") not in ends or find((label, "head")) == find((label, "tail"))
                    else ("head", "tail")):
            key = (label, end)
            if key not in ends:
                continue
            nearest = min(((_face_distance(ends[key], ends[other], width, height), other) for other in ends
                           if other[0] in in_graph and compatible(key, other)), default=None)
            if nearest:
                parent[find(key)] = find(nearest[1])
            else:
                notes.append(f"{label} {end}: no pose in the graph has this head position; it gets a pose of its own")

    groups: dict[tuple[str, str], list] = {}
    for key in ends:  # clip order, so poses are named and ordered as the pack lists its clips
        groups.setdefault(find(key), []).append(key)
    root = next(n["label"] for n in graph["nodes"] if n.get("isRoot"))
    if (root, "head") not in ends:
        raise ValueError(f"The root clip {root} has no source; resolve it in the legacy workspace first")
    base_group = find((root, "head"))

    def arrivals(members):
        return [label for label, end in members if end == "tail" and find((label, "head")) != find((label, "tail"))]

    def name_for(members) -> str:
        for label in arrivals(members):
            if "_to_" in label:
                return label.rsplit("_to_", 1)[1]
        for label in arrivals(members):
            stripped = "_".join(token for token in label.split("_") if token != "trans")
            if stripped:
                return stripped
        return members[0][0]

    def typical(members):
        top = float(np.median([ends[m]["top"] for m in members]))
        centre = float(np.median([ends[m]["centre"] for m in members]))
        near = [m for m in members if abs(ends[m]["top"] - top) <= 1 and abs(ends[m]["centre"] - centre) <= 1] or members
        plain = [m for m in near if not ends[m]["margin"]] or near  # a still is the canvas itself, never a cropped view
        return min(plain, key=lambda m: sum(_face_distance(ends[m], ends[o], width, height) for o in members))

    poses, pose_of, used = {}, {}, set()
    for group, members in sorted(groups.items(), key=lambda item: item[0] != base_group):
        name = re.sub(r"[^a-z0-9_-]", "_", (root if group == base_group else name_for(members)).lower())[:64]
        if name in used:
            name = next(f"{name}_{n}" for n in range(2, 1000) if f"{name}_{n}" not in used)
        used.add(name)
        still = typical(members)
        poses[name] = {"still": {"clip": still[0], "end": still[1]},
                       "anchors": {"headTopY": ends[still]["top"], "headCenterX": ends[still]["centre"]},
                       "members": [f"{label}:{end}" for label, end in members]}
        for member in members:
            pose_of[member] = name
    base = next(iter(poses))

    frame_owner = {path: (label, index) for label, clip in clips.items() for index, path in enumerate(clip["frames"])}
    profiles, overlays, expressions = mouth.get("profiles") or {}, manifest.get("mouthOverlays") or {}, mouth.get("expressions") or {}

    def mouth_for(label: str) -> dict | None:
        profile = profiles.get(label)
        if not profile or sources.get(label) is None:
            return None
        if pose_of[(label, "head")] != pose_of[(label, "tail")]:
            notes.append(f"{label}: its mouth profile is dropped because the clip does not start and end on one pose")
            return None
        mouth_set = profile.get("mouth_set") or "neutral"
        if mouth_set not in expressions:
            notes.append(f"{label}: mouth set {mouth_set!r} is not in the pack's expressions")
        owner = frame_owner.get((overlays.get(label) or [None])[0])
        if owner and owner[0] == label:
            return {"set": mouth_set, "closedSource": f"frame:{owner[1]}"}
        if owner and sources.get(owner[0]) and owner[1] in (0, len(clips[owner[0]]["frames"]) - 1):
            pose = pose_of[(owner[0], "head" if owner[1] == 0 else "tail")]
            return {"set": mouth_set, "closedSource": "shared" if pose == base else f"pose:{pose}"}
        notes.append(f"{label}: the shipped closed mouth is not an endpoint or own frame; it uses the shared closed mouth")
        return {"set": mouth_set, "closedSource": "shared"}

    planned = {}
    for label, clip in clips.items():
        folder = sources.get(label)
        spec = {"source": folder.relative_to(legacy).as_posix() if folder else None, "phase": clip["phase"],
                "frames": len(clip["frames"]), "frameIntervalMs": int(clip["frameIntervalMs"]), "loopMode": clip["loopMode"]}
        if folder:
            head = ends[(label, "head")]
            spec.update({"from": pose_of[(label, "head")], "to": pose_of[(label, "tail")],
                         "padTop": head["pad"], "marginPx": head["margin"], "mouth": mouth_for(label)})
            if spec["phase"] not in {"in", "loop", "out"}:
                notes.append(f"{label}: phase {spec['phase']!r} is not a production clip phase")
        planned[label] = spec

    nodes = []
    for node in graph["nodes"]:
        position = {k: legacy_nodes[node["id"]][k] for k in ("x", "y") if k in legacy_nodes.get(node["id"], {})}
        nodes.append({"id": node["id"], "label": node["label"], **({"isRoot": True} if node.get("isRoot") else {}), **position})
    return {"format": PLAN_FORMAT, "legacy": str(legacy), "pack": str(pack),
            "character": {"id": manifest["id"], "displayName": manifest.get("displayName") or manifest["id"],
                          "canvas": [width, height], "basePose": base},
            "mouthSets": {name: {k: value[k] for k in ("cx", "cy", "width", "height", "curve") if k in value}
                          for name, value in expressions.items()},
            "poses": poses, "clips": planned, "runtimeClips": [label for label in clips if label not in in_graph],
            "graph": {"nodes": nodes, "edges": graph["edges"]}, "notes": notes}


def apply_import(workspace: Path, plan: dict, *, log=print) -> dict:
    """Build the production character from a plan. Finished steps are skipped on a re-run."""
    if plan.get("format") != PLAN_FORMAT:
        raise ValueError("Not a legacy import plan")
    unresolved = [label for label, spec in plan["clips"].items() if not spec.get("source") or not spec.get("from")]
    if unresolved:
        raise ValueError(f"Resolve the source of {', '.join(unresolved)} in the plan first")
    workspace, legacy = Path(workspace).resolve(), Path(plan["legacy"])
    manifest = read_json(Path(plan["pack"]) / "runtime_manifest.json")
    info = plan["character"]
    width, height = info["canvas"]
    if (production_dir(workspace) / "character.json").is_file():
        character = load_character(workspace)
        if (character["id"], character["basePose"], [character["canvas"]["width"], character["canvas"]["height"]]) \
                != (info["id"], info["basePose"], [width, height]):
            raise ValueError("This workspace already holds a different production character")
    else:
        if read_json(resolve_asset(workspace, "graph_config.json")).get("nodes"):
            raise ValueError("Import into a new workspace: this graph already has nodes")
        init_production(workspace, character_id=info["id"], display_name=info["displayName"], width=width,
                        height=height, base_pose=info["basePose"])
    staging = production_dir(workspace) / ".import"
    try:
        for pose_id in sorted(plan["poses"], key=lambda name: name != info["basePose"]):
            _import_pose(workspace, plan, legacy, manifest, pose_id, staging, log)
        for name, values in plan["mouthSets"].items():
            set_mouth_set(workspace, name, **values)
        for label, spec in plan["clips"].items():
            _import_clip(workspace, legacy, manifest["clips"][label], label, spec, staging, log)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    for label in plan["clips"]:
        if render_freshness(workspace, load_owner(workspace, "clip", label))[0] != "current":
            render_clip(workspace, label, log=log)
    graph = {"nodes": [{**node, "root": output_root(node["label"])} for node in plan["graph"]["nodes"]],
             "edges": plan["graph"]["edges"]}
    atomic_json(resolve_asset(workspace, "graph_config.json"), graph)
    graph_sync(workspace)
    set_runtime_clips(workspace, plan["runtimeClips"])
    graph = read_json(resolve_asset(workspace, "graph_config.json"))
    return graph_report(workspace, {"nodes": export_nodes(workspace, graph), "edges": graph["edges"]},
                        load_character(workspace))


def _import_pose(workspace: Path, plan: dict, legacy: Path, manifest: dict, pose_id: str, staging: Path, log) -> None:
    spec, character = plan["poses"][pose_id], load_character(workspace)
    if pose_id != character["basePose"]:
        try:
            load_owner(workspace, "pose", pose_id)
        except ValueError:
            add_pose(workspace, pose_id, f"imported from {spec['still']['clip']} ({spec['still']['end']})")
    if load_owner(workspace, "pose", pose_id).get("acceptedTake"):
        return
    clip_id, end = spec["still"]["clip"], spec["still"]["end"]
    stems = _stems(manifest["clips"][clip_id])
    stem = stems[0] if end == "head" else stems[-1]
    source = legacy / plan["clips"][clip_id]["source"] / f"{stem}.png"
    view, _, _ = conform(read_bgra(source)[0], *plan["character"]["canvas"])
    write_png(staging / f"{pose_id}.png", view)
    take = import_still(workspace, pose_id, staging / f"{pose_id}.png", place=(1.0, 0.0, 0.0),
                        note=f"legacy import: {plan['clips'][clip_id]['source']}/{stem}.png")
    anchors, metrics = character.get("anchors"), take["qa"]["metrics"]
    if pose_id != character["basePose"] and (
            abs(metrics["headTopY"] - anchors["headTopY"]) > character["tolerances"]["headTopPx"]
            or abs(metrics["headCenterX"] - anchors["headCenterX"]) > character["tolerances"]["headCenterPx"]):
        set_expected(workspace, pose_id, metrics["headTopY"], metrics["headCenterX"])
    approve_still(workspace, pose_id, take["id"], "legacy import")
    log(f"pose {pose_id}: still from {clip_id} {end}")


def _import_clip(workspace: Path, legacy: Path, shipped: dict, label: str, spec: dict, staging: Path, log) -> None:
    try:
        load_owner(workspace, "clip", label)
    except ValueError:
        add_clip(workspace, label, spec["from"], spec["to"], spec["phase"])
    mouth = spec.get("mouth") or {}
    set_clip(workspace, label, register=False, crop_black_border=False, margin=spec["marginPx"], interpolate=1, pingpong=False, lock_head=0,
             lock_tail=0, edge_guard=0, speed=1.0, loop_mode=spec["loopMode"], mouth=mouth.get("set"),
             mouth_source=mouth.get("closedSource"))
    if load_owner(workspace, "clip", label).get("acceptedTake"):
        return
    stems, folder = _stems(shipped), legacy / spec["source"]
    if spec["padTop"] or [p.stem for p in sorted_pngs(folder)] != stems:
        stage = staging / label
        shutil.rmtree(stage, ignore_errors=True)
        for index, stem in enumerate(stems):
            write_png(stage / f"{index:06d}.png", pad_top(read_bgra(folder / f"{stem}.png")[0], spec["padTop"]))
        folder = stage
    take = import_clip_take(workspace, label, folder, fps=1000 / spec["frameIntervalMs"],
                            note=f"legacy import: {spec['source']}")
    decide(workspace, "clip", label, take["id"], "accept", "legacy import")
    shutil.rmtree(staging / label, ignore_errors=True)
    log(f"clip {label}: {len(stems)} frames from {spec['source']}")
