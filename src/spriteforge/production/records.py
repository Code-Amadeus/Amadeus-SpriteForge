"""File-backed production records: character, poses, clips and their takes.

Everything lives under ``<workspace>/production``. A take directory belongs to
one pose (a still image) or one clip (a video), and the owner record names at
most one accepted take. Take status is derived from those two files, so there
is no third copy of the decision that could disagree with them.
"""
from __future__ import annotations

import math
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..workspace import atomic_json, read_json, resolve_asset

ROOT = "production"
CHARACTER_FORMAT = "spriteforge.production.character.v1"
POSE_FORMAT = "spriteforge.production.pose.v1"
CLIP_FORMAT = "spriteforge.production.clip.v1"
TAKE_FORMAT = "spriteforge.production.take.v1"
EDGES = ("left", "right", "top", "bottom")
OWNERS = {"pose": "poses", "clip": "clips"}
PHASES = ("in", "loop", "out")
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
TAKE_ID = re.compile(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{4}")
TAKE_WRITE_LOCK = threading.Lock()
# Reference framing measured on the shipped Kurisu pack: visible width is 71% of the
# canvas width and the head top sits at 2% of the canvas height.
DEFAULT_FRAMING = {"visibleWidth": 0.71, "headTop": 0.02}
DEFAULT_TOLERANCES = {"headTopPx": 3, "headCenterPx": 3, "areaPct": 15}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def recorded_credit_delta(source: dict) -> float | int | None:
    """A balance increase cannot establish generation cost (it may be a top-up)."""
    balances = [source.get(key) for key in ("balanceBefore", "balanceAfter")]
    if not all(isinstance(balance, dict) for balance in balances):
        return None
    values = [balance.get("credits") for balance in balances]
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
               for value in values):
        return None
    delta = values[0] - values[1]
    return delta if math.isfinite(delta) and delta >= 0 else None


def check_id(value: object, what: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{what} id must be 1-64 lowercase letters, digits, '_' or '-'")
    return value


def production_dir(workspace: Path) -> Path:
    return resolve_asset(workspace, ROOT)


def create_character(workspace: Path, *, character_id: str, display_name: str, width: int, height: int,
                     base_pose: str, background: tuple[int, int, int], cut_edges: list[str]) -> dict:
    path = production_dir(workspace) / "character.json"
    if path.exists():
        raise ValueError("This workspace already has a production character")
    if not display_name.strip() or width < 16 or height < 16:
        raise ValueError("A display name and a canvas of at least 16x16 are required")
    if any(edge not in EDGES for edge in cut_edges) or any(not 0 <= c <= 255 for c in background):
        raise ValueError("Cut edges are left/right/top/bottom and background channels are 0-255")
    character = {"format": CHARACTER_FORMAT, "id": check_id(character_id, "Character"), "displayName": display_name,
                 "basePose": check_id(base_pose, "Pose"), "canvas": {"width": width, "height": height},
                 "background": list(background), "cutEdges": sorted(set(cut_edges), key=EDGES.index),
                 "framing": dict(DEFAULT_FRAMING), "tolerances": dict(DEFAULT_TOLERANCES), "anchors": None}
    atomic_json(path, character)
    return character


def load_character(workspace: Path) -> dict:
    path = production_dir(workspace) / "character.json"
    if not path.is_file():
        raise ValueError("This workspace has no production character; run 'spriteforge production init'")
    character = read_json(path)
    if character.get("format") != CHARACTER_FORMAT:
        raise ValueError("Unsupported production character format")
    return character


def save_character(workspace: Path, character: dict) -> None:
    atomic_json(production_dir(workspace) / "character.json", character)


def canvas_size(character: dict) -> tuple[int, int]:
    return int(character["canvas"]["width"]), int(character["canvas"]["height"])


def owner_dir(workspace: Path, kind: str, owner_id: str) -> Path:
    if kind not in OWNERS:
        raise ValueError("A take belongs to a pose or a clip")
    return resolve_asset(workspace, f"{ROOT}/{OWNERS[kind]}/{check_id(owner_id, kind.title())}")


def load_owner(workspace: Path, kind: str, owner_id: str) -> dict:
    path = owner_dir(workspace, kind, owner_id) / f"{kind}.json"
    if not path.is_file():
        raise ValueError(f"Unknown {kind}: {owner_id}")
    return read_json(path)


def save_owner(workspace: Path, kind: str, record: dict) -> None:
    atomic_json(owner_dir(workspace, kind, record["id"]) / f"{kind}.json", record)


def list_owners(workspace: Path, kind: str) -> list[dict]:
    base = production_dir(workspace) / OWNERS[kind]
    if not base.is_dir():
        return []
    return [read_json(p / f"{kind}.json") for p in sorted(base.iterdir()) if (p / f"{kind}.json").is_file()]


def create_pose(workspace: Path, pose_id: str, description: str = "") -> dict:
    load_character(workspace)
    if (owner_dir(workspace, "pose", pose_id) / "pose.json").exists():
        raise ValueError(f"Pose {pose_id} already exists")
    pose = {"format": POSE_FORMAT, "id": pose_id, "description": description,
            "prompt": {"template": "still", "subject": f"pose.{pose_id}"}, "expected": {}, "acceptedTake": None}
    save_owner(workspace, "pose", pose)
    return pose


def clip_defaults(kind: str) -> dict:
    transition = kind == "transition"
    return {
        "generation": {"provider": "manual", "durationS": 2 if transition else 4, "resolution": "720P",
                       "seed": None, "inputScale": 1.0, "lastFrame": "still"},
        "processing": {"register": True, "interpolate": 1, "pingpong": False, "lockHeadFrames": 6 if transition else 0,
                       "lockTailFrames": 12 if transition else 0, "edgeGuardPx": 0, "marginPx": 0,
                       "cropBlackBorder": False, "cropBlackThreshold": 10, "cropBlackMarginPx": 4},
        "playback": {"speed": 1.0, "loopMode": "once_then_hold" if transition else "loop"},
    }


def create_clip(workspace: Path, clip_id: str, source: str, target: str, *, phase: str | None = None) -> dict:
    from .tools import load_tools

    character = load_character(workspace)
    if (owner_dir(workspace, "clip", clip_id) / "clip.json").exists():
        raise ValueError(f"Clip {clip_id} already exists")
    for pose_id in (source, target):
        load_owner(workspace, "pose", pose_id)
    kind = "loop" if source == target else "transition"
    phase = phase or ("loop" if kind == "loop" else "out" if target == character["basePose"] else "in")
    if phase not in PHASES:
        raise ValueError("Clip phase must be in, loop or out")
    clip = {"format": CLIP_FORMAT, "id": clip_id, "kind": kind, "from": source, "to": target, "phase": phase,
            "prompt": {"template": kind, "subject": f"clip.{clip_id}"}, **clip_defaults(kind),
            "mouth": None, "acceptedTake": None, "notes": ""}
    # Defaults are captured once; existing clips never inherit later Settings changes.
    clip["processing"]["cropBlackBorder"] = load_tools(workspace)["defaults"]["cropBlackBorder"]
    clip_settings(clip)
    save_owner(workspace, "clip", clip)
    return clip


def new_take_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2)


def take_dir(workspace: Path, kind: str, owner_id: str, take_id: str) -> Path:
    if not isinstance(take_id, str) or not TAKE_ID.fullmatch(take_id):
        raise ValueError(f"Invalid take id: {take_id!r}")
    return owner_dir(workspace, kind, owner_id) / "takes" / take_id


def new_take(workspace: Path, kind: str, owner_id: str, source: dict[str, Any]) -> tuple[dict, Path]:
    for _ in range(8):
        take_id = new_take_id()
        directory = take_dir(workspace, kind, owner_id, take_id)
        try:
            directory.mkdir(parents=True)
        except FileExistsError:
            continue
        take = {"format": TAKE_FORMAT, "id": take_id, "owner": {"kind": kind, "id": owner_id},
                "createdAt": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "state": "created", "source": source, "prompt": None, "inputs": {}, "media": None,
                "basedOn": None, "note": source.get("note", ""),
                "rejected": None, "history": [], "error": None}
        return take, directory
    raise ValueError("Could not allocate a unique take id")


def load_take(workspace: Path, kind: str, owner_id: str, take_id: str) -> dict:
    path = take_dir(workspace, kind, owner_id, take_id) / "take.json"
    if not path.is_file():
        raise ValueError(f"Unknown take {take_id} for {kind} {owner_id}")
    return read_json(path)


def save_take(workspace: Path, take: dict) -> None:
    """Producer updates preserve the separately editable on-disk annotation.

    The short lock coordinates threads in this local server. As with existing
    owner/decision writes, simultaneous separate CLI processes are not managed.
    """
    owner = take["owner"]
    path = take_dir(workspace, owner["kind"], owner["id"], take["id"]) / "take.json"
    with TAKE_WRITE_LOCK:
        if path.is_file():
            existing = read_json(path)
            if "note" in existing:
                take["note"] = existing["note"]
        atomic_json(path, take)


def set_take_note(workspace: Path, kind: str, owner_id: str, take_id: str, note: object) -> dict:
    """Change the editable annotation without touching the take's provenance or snapshots."""
    if not isinstance(note, str):
        raise ValueError("A take note must be text")
    load_owner(workspace, kind, owner_id)
    with TAKE_WRITE_LOCK:
        take = load_take(workspace, kind, owner_id, take_id)
        take["note"] = note
        atomic_json(take_dir(workspace, kind, owner_id, take_id) / "take.json", take)
    return take


def list_takes(workspace: Path, kind: str, owner_id: str) -> list[dict]:
    base = owner_dir(workspace, kind, owner_id) / "takes"
    if not base.is_dir():
        return []
    return [read_json(p / "take.json") for p in sorted(base.iterdir()) if (p / "take.json").is_file()]


def take_status(owner: dict, take: dict) -> str:
    if take.get("state") == "failed":
        return "failed"
    if take.get("state") != "ready":
        return "pending"
    if take.get("rejected"):
        return "rejected"
    return "accepted" if owner.get("acceptedTake") == take["id"] else "candidate"


def _log(take: dict, action: str, reason: str) -> None:
    take["history"].append({"at": now(), "action": action, **({"reason": reason} if reason else {})})


def decide(workspace: Path, kind: str, owner_id: str, take_id: str, action: str, reason: str = "") -> dict:
    """Accept, reject or restore a take. Writes are ordered so that an interruption
    between the owner and take files leaves a plain, unaccepted candidate."""
    owner = load_owner(workspace, kind, owner_id)
    take = load_take(workspace, kind, owner_id, take_id)
    if action == "reject" and kind == "clip" and (not isinstance(reason, str) or not reason.strip()):
        raise ValueError("Rejecting a clip take requires a reason")
    reason = str(reason or "").strip()
    if action == "accept":
        if take.get("state") != "ready":
            raise ValueError("Only a ready take can be accepted")
        if take.get("rejected"):
            take["rejected"] = None
            _log(take, "restored", "")
            save_take(workspace, take)
        owner["acceptedTake"] = take_id
        save_owner(workspace, kind, owner)
        _log(take, "accepted", reason)
    elif action == "reject":
        if owner.get("acceptedTake") == take_id:
            owner["acceptedTake"] = None
            save_owner(workspace, kind, owner)
        take["rejected"] = {"at": now(), "reason": reason}
        _log(take, "rejected", reason)
    elif action == "restore":
        if not take.get("rejected"):
            raise ValueError("Only a rejected take can be restored")
        take["rejected"] = None
        _log(take, "restored", reason)
    else:
        raise ValueError("Decision must be accept, reject or restore")
    save_take(workspace, take)
    return take


def accepted_take(workspace: Path, kind: str, owner_id: str) -> dict:
    owner = load_owner(workspace, kind, owner_id)
    if not owner.get("acceptedTake"):
        noun = "still" if kind == "pose" else "take"
        raise ValueError(f"{kind.title()} {owner_id} has no accepted {noun}")
    take = load_take(workspace, kind, owner_id, owner["acceptedTake"])
    if take_status(owner, take) != "accepted":
        raise ValueError(f"The accepted take of {kind} {owner_id} is not ready")
    return take


def still_path(workspace: Path, pose_id: str) -> tuple[Path, dict]:
    take = accepted_take(workspace, "pose", pose_id)
    return take_dir(workspace, "pose", pose_id, take["id"]) / take["media"]["still"], take


def take_media_frames(workspace: Path, take: dict) -> list[Path] | Path:
    """A frame folder take's frames, or the path of its video."""
    directory = take_dir(workspace, "clip", take["owner"]["id"], take["id"])
    media = take.get("media") or {}
    if media.get("dir"):
        return sorted(p for p in directory.joinpath(media["dir"]).glob("*.png") if p.is_file())
    if media.get("video"):
        return directory / media["video"]
    raise ValueError(f"Take {take['id']} has no media")


def output_root(clip_id: str) -> str:
    """Stable graph root of a clip; it always holds the render of the accepted take."""
    return f"{ROOT}/{OWNERS['clip']}/{check_id(clip_id, 'Clip')}/output"


def bound_clip(root: object) -> str | None:
    """The production clip a graph root shows: its output folder, or the phase folder inside it
    that frame-folder discovery offers. Export gating, mouth export and graph-sync rely on this."""
    parts = str(root or "").replace("\\", "/").strip("/").split("/")
    if len(parts) in (4, 5) and parts[:2] == [ROOT, OWNERS["clip"]] and parts[3] == "output" \
            and (len(parts) == 4 or parts[4] in PHASES) and IDENTIFIER.fullmatch(parts[2]):
        return parts[2]
    return None


def read_render(workspace: Path, clip_id: str) -> dict | None:
    path = resolve_asset(workspace, output_root(clip_id)) / "render.json"
    return read_json(path) if path.is_file() else None


def candidate_output_root(clip_id: str, take_id: str) -> str:
    if not isinstance(take_id, str) or not TAKE_ID.fullmatch(take_id):
        raise ValueError("Invalid take id")
    return f"{ROOT}/{OWNERS['clip']}/{check_id(clip_id, 'Clip')}/takes/{take_id}/processed"


def read_candidate_render(workspace: Path, clip_id: str, take_id: str) -> dict | None:
    path = resolve_asset(workspace, candidate_output_root(clip_id, take_id)) / "render.json"
    return read_json(path) if path.is_file() else None


def clip_settings(clip: dict) -> dict:
    """Validated processing and playback settings of a clip."""
    processing, playback, generation = clip["processing"], clip["playback"], clip["generation"]
    values = {key: processing.get(key, 0)
              for key in ("interpolate", "lockHeadFrames", "lockTailFrames", "edgeGuardPx", "marginPx")}
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values.values()) or values["interpolate"] < 1:
        raise ValueError("processing.interpolate must be >= 1 and lock, edge and margin values non-negative integers")
    register = processing.get("register", True)
    if not isinstance(register, bool):
        raise ValueError("processing.register must be true or false")
    crop_border = processing.get("cropBlackBorder", False)
    crop_threshold = processing.get("cropBlackThreshold", 10)
    crop_margin = processing.get("cropBlackMarginPx", 4)
    if not isinstance(crop_border, bool):
        raise ValueError("processing.cropBlackBorder must be true or false")
    if isinstance(crop_threshold, bool) or not isinstance(crop_threshold, int) or not 0 <= crop_threshold <= 254:
        raise ValueError("processing.cropBlackThreshold must be an integer between 0 and 254")
    if isinstance(crop_margin, bool) or not isinstance(crop_margin, int) or crop_margin < 0:
        raise ValueError("processing.cropBlackMarginPx must be a non-negative integer")
    speed = playback.get("speed", 1.0)
    if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.1 <= speed <= 16:
        raise ValueError("playback.speed must be between 0.1 and 16")
    if playback.get("loopMode") not in {"loop", "once_then_hold"}:
        raise ValueError("playback.loopMode must be loop or once_then_hold")
    if processing.get("pingpong") and clip["kind"] != "loop":
        raise ValueError("pingpong only applies to loop clips")
    duration, scale = generation.get("durationS"), generation.get("inputScale", 1.0)
    if isinstance(duration, bool) or not isinstance(duration, int) or duration < 1 or not 0.5 <= float(scale) <= 1.0:
        raise ValueError("generation.durationS must be a positive integer and inputScale between 0.5 and 1.0")
    last_frame = generation.get("lastFrame", "still")
    if last_frame not in {"still", "none"}:
        raise ValueError("generation.lastFrame must be still or none")
    if last_frame == "none" and clip["kind"] != "transition":
        raise ValueError("Only a transition can be generated without its last frame; a loop must return to its still")
    mouth = clip.get("mouth")
    if mouth is not None:
        source = mouth.get("closedSource") if isinstance(mouth, dict) else None
        if clip["kind"] != "loop":
            raise ValueError("Mouth tracks belong to speaking loops, not transitions")
        if not isinstance(mouth.get("set"), str) or not isinstance(source, dict)                 or source.get("kind") not in {"shared", "still", "frame", "pose"}:
            raise ValueError("mouth needs a mouth set and a closedSource of kind shared, still, frame or pose")
        if source["kind"] == "frame" and (isinstance(source.get("index"), bool) or not isinstance(source.get("index"), int)
                                          or source["index"] < 0):
            raise ValueError("A frame closedSource needs a non-negative output frame index")
        if source["kind"] == "pose":
            check_id(source.get("pose"), "Pose")
    return {**values, "register": register, "cropBlackBorder": crop_border, "cropBlackThreshold": crop_threshold,
            "cropBlackMarginPx": crop_margin, "pingpong": bool(processing.get("pingpong")), "speed": float(speed),
            "loopMode": playback["loopMode"], "lastFrame": last_frame}


def expected_anchor(character: dict, pose: dict) -> dict:
    anchors = character.get("anchors") or {}
    return {key: (pose.get("expected") or {}).get(key, anchors.get(key)) for key in ("headTopY", "headCenterX")}


def mouth_prior(character: dict, clip: dict, pose: dict) -> dict:
    """The selected mouth set moved with the pose's head offset from the base anchors."""
    name = clip["mouth"]["set"]
    sets = character.get("mouthSets") or {}
    if name not in sets:
        raise ValueError(f"Unknown mouth set {name!r}; define it with 'production mouth set'")
    mouth_set, anchors = sets[name], character.get("anchors") or {}
    expected = expected_anchor(character, pose)
    return {**mouth_set, "cx": mouth_set["cx"] + (expected["headCenterX"] - anchors["headCenterX"]),
            "cy": mouth_set["cy"] + (expected["headTopY"] - anchors["headTopY"])}


def recipe(workspace: Path, clip: dict, *, character: dict | None = None) -> dict:
    """Inputs that determine rendered frames, timing and mouth data, including shared settings."""
    result = {"phase": clip["phase"], "processing": clip["processing"], "playback": clip["playback"]}
    if clip.get("mouth"):
        character = character if character is not None else load_character(workspace)
        guess = mouth_prior(character, clip, load_owner(workspace, "pose", clip["to"]))
        result.update(mouth=clip["mouth"], mouthSet=dict(character["mouthSets"][clip["mouth"]["set"]]), mouthPrior=guess)
    return result


def closed_mouth_pose(character: dict, pose: dict) -> str:
    """The pose whose still is the closed mouth for this pose's speaking loops: the pose's
    own choice, otherwise the character's shared closed mouth (the base still by default)."""
    return pose.get("closedMouth") or character.get("closedMouth") or character["basePose"]


def render_stills(workspace: Path, clip: dict) -> dict[str, str]:
    """The pose stills a render depends on, by role."""
    stills = {"from": clip["from"], "to": clip["to"]}
    source = (clip.get("mouth") or {}).get("closedSource") or {}
    if source.get("kind") == "pose":
        stills["mouth"] = source["pose"]
    elif source.get("kind") == "shared":
        stills["mouth"] = closed_mouth_pose(load_character(workspace), load_owner(workspace, "pose", clip["to"]))
    return stills


def render_freshness(workspace: Path, clip: dict) -> tuple[str, list[str]]:
    """'missing', 'stale' or 'current', with the reasons a render no longer matches its inputs."""
    return _render_freshness(workspace, clip, read_render(workspace, clip["id"]), clip.get("acceptedTake"))


def candidate_render_freshness(workspace: Path, clip: dict, take_id: str) -> tuple[str, list[str]]:
    return _render_freshness(workspace, clip, read_candidate_render(workspace, clip["id"], take_id), take_id)


def _render_freshness(workspace: Path, clip: dict, render: dict | None, take_id: str | None) -> tuple[str, list[str]]:
    if render is None:
        return "missing", ["not rendered"]
    reasons = []
    if render.get("take") != take_id:
        reasons.append("the accepted take changed" if take_id == clip.get("acceptedTake") else "the selected take changed")
    if render.get("recipe") != recipe(workspace, clip):
        reasons.append("processing, playback or mouth settings changed")
    for role, pose_id in render_stills(workspace, clip).items():
        pose = load_owner(workspace, "pose", pose_id)
        if (render.get("stills") or {}).get(role) != pose.get("acceptedTake"):
            reasons.append(f"the {pose_id} still changed")
    return ("stale" if reasons else "current"), sorted(set(reasons), key=reasons.index)
