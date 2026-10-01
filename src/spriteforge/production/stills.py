"""Pose stills: import, generate or adopt from a clip, normalise onto the canvas, check and approve.

The source image is kept untouched in its take; ``still.png`` is the RGBA canvas
image that clip endpoints are registered to. The base pose is placed by explicit
framing, and approving it measures the character anchors. Every other pose is
registered to the approved base still, or placed explicitly when a pose change
defeats feature registration. Approval refuses a still whose geometry fails.

A generated still is an image edit of the approved base still. Its take keeps
the exact input image, prompt and request; the provider's image is then
normalised exactly like an imported one.

An adopted still is one frame of a clip take, so that a transition generated from
its first frame alone can define its end pose where its motion ends. The frame
keeps the take's own framing on the canvas (its first frame registered to the
clip's start still) unless it is a rigid copy of the base still.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import numpy as np

from .checks import still_report
from .geometry import (composite, estimate_similarity, fit_placement, framing_placement, is_rigid, measure, placement,
                       warp)
from .media import IMAGE_SUFFIXES, copy_durable, encode_png, image_suffix, media_frames, read_bgra, write_durable, write_png
from .mouth import default_set
from .prompts import load_library, pose_prompt, require_complete
from .providers import ImageJob, get_image_provider
from .records import (canvas_size, clip_settings, decide, load_character, load_owner, load_take, new_take,
                      save_character, save_owner, save_take, still_path, take_dir, take_media_frames)
from .tools import load_tools, run_processor


def matte(tools: dict, image: np.ndarray, background: list[int]) -> np.ndarray:
    """Alpha for one opaque image through the configured alpha processor."""
    with tempfile.TemporaryDirectory(prefix="spriteforge-matte-") as temporary:
        source, target = Path(temporary) / "in", Path(temporary) / "out"
        write_png(source / "000000.png", composite(image, background))
        run_processor(tools, "alpha", source, target)
        matted, has_alpha = read_bgra(target / "000000.png")
    if matted.shape[:2] != image.shape[:2] or not has_alpha:
        raise ValueError("The alpha processor must return an RGBA image of the same size")
    return matted


def still_prompt(workspace: Path, character: dict, pose: dict) -> dict:
    return pose_prompt(load_library(workspace), character, pose)


def still_input(workspace: Path, character: dict) -> tuple[bytes, dict]:
    """The approved base still flattened on the background: what an image editor starts from."""
    path, take = still_path(workspace, character["basePose"])
    image = encode_png(composite(read_bgra(path)[0], character["background"]))
    return image, {"pose": character["basePose"], "still": take["id"], "sha256": hashlib.sha256(image).hexdigest()}


def _require_base(character: dict, pose_id: str) -> None:
    if pose_id != character["basePose"] and not character.get("anchors"):
        raise ValueError(f"Approve a still for the base pose '{character['basePose']}' first")


def import_still(workspace: Path, pose_id: str, source: Path, *, note: str = "",
                 place: tuple[float, float, float] | None = None) -> dict:
    character, pose = load_character(workspace), load_owner(workspace, "pose", pose_id)
    source = Path(source)
    if source.suffix.lower() not in IMAGE_SUFFIXES or not source.is_file():
        raise ValueError(f"Still source must be an image file: {source}")
    _require_base(character, pose_id)
    take, directory = new_take(workspace, "pose", pose_id, {"provider": "manual", "file": source.name, "note": note})
    name = f"source{source.suffix.lower()}"
    try:
        copy_durable(source, directory / name)
        take["prompt"] = still_prompt(workspace, character, pose)
        _normalize(workspace, character, pose, take, name, place)
    except Exception as exc:
        take.update(state="failed", error=str(exc))
        raise
    finally:
        save_take(workspace, take)
    return take


def generate_still(workspace: Path, pose_id: str, provider: str, *, dry_run: bool = False, log=print) -> dict:
    """Edit the approved base still into a pose with an image provider, then normalise the result."""
    character, pose, tools = load_character(workspace), load_owner(workspace, "pose", pose_id), load_tools(workspace)
    if pose_id == character["basePose"]:
        raise ValueError("The base pose is the reference every generated still starts from: import its still")
    _require_base(character, pose_id)
    adapter = get_image_provider(provider, tools)
    snapshot = still_prompt(workspace, character, pose)
    image, inputs = still_input(workspace, character)
    job = ImageJob(snapshot["text"], snapshot["negative"] if adapter.negative_prompt else "", image)
    request = adapter.preview(job)
    if dry_run:
        return {"provider": provider, "model": adapter.model, "request": request, "prompt": snapshot}
    require_complete(snapshot)
    adapter.key()  # a missing key, like a missing alpha processor, fails before a take is recorded
    if not tools.get("alpha"):
        raise ValueError("Provider images are opaque: configure the 'alpha' processor in production/tools.json first")
    take, directory = new_take(workspace, "pose", pose_id, {"provider": provider, "model": adapter.model, "request": request})
    write_durable(directory / "input.png", image)
    take.update(prompt={**snapshot, "negativeSent": bool(job.negative)}, inputs={"base": {**inputs, "file": "input.png"}},
                state="submitting")
    save_take(workspace, take)
    log(f"Sent the {character['basePose']} still to {provider} ({adapter.model}) as take {take['id']}")
    try:
        result = adapter.edit(job)
        name = "source" + image_suffix(result)
        write_durable(directory / name, result)
        take["media"] = {"source": name}
        _normalize(workspace, character, pose, take, name, None)
    except Exception as exc:
        take.update(state="failed", error=str(exc))
        raise
    finally:
        save_take(workspace, take)
    log(f"Take {take['id']}: {take['normalization']['method']}, QA {take['qa']['status']}")
    return take


def adopt_frame(workspace: Path, clip_id: str, take_id: str, *, pose_id: str | None = None, frame: str | int = "last",
                note: str = "", log=print) -> dict:
    """Make a pose still from one frame of a clip take: by default its last frame, for the clip's end pose."""
    character, clip = load_character(workspace), load_owner(workspace, "clip", clip_id)
    pose_id = pose_id or clip["to"]
    pose = load_owner(workspace, "pose", pose_id)
    if pose_id == character["basePose"]:
        raise ValueError("The base pose still is the reference every clip starts from: import it")
    _require_base(character, pose_id)
    source = load_take(workspace, "clip", clip_id, take_id)
    if source.get("state") != "ready":
        raise ValueError(f"Take {take_id} of clip {clip_id} is {source.get('state')}, not ready")
    settings = clip_settings(clip)
    with tempfile.TemporaryDirectory(prefix="spriteforge-adopt-") as temporary:
        frames = media_frames(take_media_frames(workspace, source), load_tools(workspace).get("ffmpeg"), Path(temporary))
        index = _frame_index(frame, len(frames))
        inputs = {}
        if settings["register"]:
            # The take's framing: where registering its first frame to the start still puts the picture.
            start_file, start_take = still_path(workspace, clip["from"])
            framing = estimate_similarity(composite(read_bgra(frames[0])[0], character["background"]),
                                          composite(read_bgra(start_file)[0], character["background"]))[0]
            inputs["start"] = {"pose": clip["from"], "still": start_take["id"]}
        else:  # the frames are already on the canvas, widened by the clip's margin
            framing = placement(1.0, -settings["marginPx"], 0.0)
        take, directory = new_take(workspace, "pose", pose_id, {"provider": "clip", "clip": clip_id, "take": take_id,
                                                               "frame": index, "frames": len(frames), "note": note})
        try:
            name = "source" + frames[index].suffix.lower()
            copy_durable(frames[index], directory / name)
            take["inputs"] = inputs
            _normalize(workspace, character, pose, take, name, None, framing)
        except Exception as exc:
            take.update(state="failed", error=str(exc))
            raise
        finally:
            save_take(workspace, take)
    log(f"Take {take['id']}: frame {index} of {clip_id} take {take_id}, {take['normalization']['method']}, "
        f"QA {take['qa']['status']}")
    return take


def _frame_index(frame: str | int, count: int) -> int:
    if frame in ("first", "last"):
        index = 0 if frame == "first" else count - 1
    elif isinstance(frame, int) and not isinstance(frame, bool) or isinstance(frame, str) and frame.isdigit():
        index = int(frame)
    else:
        raise ValueError("A frame is 'first', 'last' or a 0-based frame index")
    if not 0 <= index < count:
        raise ValueError(f"Frame {index} is outside the take's {count} frames")
    return index


def _normalize(workspace: Path, character: dict, pose: dict, take: dict, name: str,
               place: tuple[float, float, float] | None, framing: np.ndarray | None = None) -> None:
    """Place a take's source image on the canvas as its still and check it. ``framing`` is where the
    generator's picture sits on the canvas when that is known (a clip take); otherwise it is fitted."""
    directory = take_dir(workspace, "pose", pose["id"], take["id"])
    image, has_alpha = read_bgra(directory / name)
    if not has_alpha:
        image = matte(load_tools(workspace), image, character["background"])
    width, height = canvas_size(character)
    registration = None
    if place is not None:
        matrix, method = placement(*place), "placement"
    elif pose["id"] == character["basePose"]:
        matrix, method = framing_placement(image, width, height, character["framing"]), "framing"
    else:
        # A rigid match means the generator moved the whole picture: undo it. Otherwise
        # the pose itself changed, and the generator's framing is kept for review.
        base_file, base_take = still_path(workspace, character["basePose"])
        take["inputs"].setdefault("base", {"pose": character["basePose"], "still": base_take["id"]})
        base = read_bgra(base_file)[0]
        try:
            matrix, registration = estimate_similarity(composite(image, character["background"]),
                                                       composite(base, character["background"]))
        except ValueError as exc:
            matrix, registration = None, {"error": str(exc)}
        if matrix is not None and is_rigid(registration):
            method = "registration"
        elif framing is not None:
            matrix, method = framing, "clip"
        else:
            matrix, method = fit_placement(image, width, height), "fit"
    still = warp(image, matrix, width, height, (0, 0, 0, 0))
    write_png(directory / "still.png", still)
    normalization = {"method": method, "matrix": np.round(matrix, 6).tolist(),
                     **({"registration": registration} if registration else {})}
    take.update(state="ready", media={"source": name, "still": "still.png"},
                normalization=normalization, qa=qa_for(character, pose, still, normalization))


def qa_for(character: dict, pose: dict, still: np.ndarray, normalization: dict | None) -> dict:
    return {**still_report(character, pose, still, normalization), "anchorsTake": (character.get("anchors") or {}).get("take")}


def approve_still(workspace: Path, pose_id: str, take_id: str, reason: str = "") -> dict:
    """Accept a still after re-checking it against the current anchors."""
    character, pose = load_character(workspace), load_owner(workspace, "pose", pose_id)
    take = load_take(workspace, "pose", pose_id, take_id)
    if take.get("state") != "ready":
        raise ValueError("Only a ready still can be approved")
    still = read_bgra(take_dir(workspace, "pose", pose_id, take_id) / take["media"]["still"])[0]
    take["qa"] = qa_for(character, pose, still, take.get("normalization"))
    save_take(workspace, take)
    if take["qa"]["status"] == "fail":
        failed = "; ".join(c["message"] for c in take["qa"]["checks"] if c["level"] == "fail")
        raise ValueError(f"Still QA failed: {failed}. Re-import with an explicit placement, or record an "
                         "intended offset with 'production pose expect'")
    take = decide(workspace, "pose", pose_id, take_id, "accept", reason)
    if pose_id == character["basePose"]:
        metrics = measure(still)
        character["anchors"] = {"take": take_id, **{k: metrics[k] for k in ("headTopY", "headCenterX", "area", "bbox")}}
        if not character.get("mouthSets"):
            character["mouthSets"] = {"neutral": default_set(character["anchors"], *canvas_size(character))}
        save_character(workspace, character)
    return take


def set_expected(workspace: Path, pose_id: str, head_top: float | None, head_center: float | None) -> dict:
    """Record an intended head offset for a pose (for example a side turn); None clears a value."""
    if pose_id == load_character(workspace)["basePose"]:
        raise ValueError("The base pose defines the anchors and cannot carry an offset")
    pose = load_owner(workspace, "pose", pose_id)
    pose["expected"] = {k: v for k, v in (("headTopY", head_top), ("headCenterX", head_center)) if v is not None}
    save_owner(workspace, "pose", pose)
    return pose
