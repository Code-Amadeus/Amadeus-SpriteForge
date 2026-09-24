"""Pose stills: import, normalise onto the canvas, check and approve.

The source image is kept untouched in its take; ``still.png`` is the RGBA canvas
image that clip endpoints are registered to. The base pose is placed by explicit
framing, and approving it measures the character anchors. Every other pose is
registered to the approved base still, or placed explicitly when a pose change
defeats feature registration. Approval refuses a still whose geometry fails.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from .checks import still_report
from .geometry import composite, estimate_similarity, framing_placement, measure, placement, warp
from .media import IMAGE_SUFFIXES, copy_durable, read_bgra, write_png
from .prompts import load_library, pose_prompt
from .records import (canvas_size, decide, load_character, load_owner, load_take, new_take, save_character,
                      save_owner, save_take, still_path, take_dir)
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


def import_still(workspace: Path, pose_id: str, source: Path, *, note: str = "",
                 place: tuple[float, float, float] | None = None) -> dict:
    character, pose, tools = load_character(workspace), load_owner(workspace, "pose", pose_id), load_tools(workspace)
    source = Path(source)
    if source.suffix.lower() not in IMAGE_SUFFIXES or not source.is_file():
        raise ValueError(f"Still source must be an image file: {source}")
    image, has_alpha = read_bgra(source)
    is_base = pose_id == character["basePose"]
    if not is_base and not character.get("anchors"):
        raise ValueError(f"Approve a still for the base pose '{character['basePose']}' first")
    take, directory = new_take(workspace, "pose", pose_id, {"provider": "manual", "file": source.name, "note": note})
    try:
        copy_durable(source, directory / f"source{source.suffix.lower()}")
        take["prompt"] = still_prompt(workspace, character, pose)
        if not has_alpha:
            image = matte(tools, image, character["background"])
        width, height = canvas_size(character)
        registration = None
        if place is not None:
            matrix, method = placement(*place), "placement"
        elif is_base:
            matrix, method = framing_placement(image, width, height, character["framing"]), "framing"
        else:
            base_file, base_take = still_path(workspace, character["basePose"])
            take["inputs"] = {"base": {"pose": character["basePose"], "still": base_take["id"]}}
            base = read_bgra(base_file)[0]
            matrix, registration = estimate_similarity(composite(image, character["background"]),
                                                       composite(base, character["background"]))
            method = "registration"
        still = warp(image, matrix, width, height, (0, 0, 0, 0))
        write_png(directory / "still.png", still)
        take.update(state="ready", media={"source": f"source{source.suffix.lower()}", "still": "still.png"},
                    normalization={"method": method, "matrix": np.round(matrix, 6).tolist(),
                                   **({"registration": registration} if registration else {})},
                    qa=qa_for(character, pose, still, registration))
    except Exception as exc:
        take.update(state="failed", error=str(exc))
        raise
    finally:
        save_take(workspace, take)
    return take


def qa_for(character: dict, pose: dict, still: np.ndarray, registration: dict | None) -> dict:
    return {**still_report(character, pose, still, registration), "anchorsTake": (character.get("anchors") or {}).get("take")}


def approve_still(workspace: Path, pose_id: str, take_id: str, reason: str = "") -> dict:
    """Accept a still after re-checking it against the current anchors."""
    character, pose = load_character(workspace), load_owner(workspace, "pose", pose_id)
    take = load_take(workspace, "pose", pose_id, take_id)
    if take.get("state") != "ready":
        raise ValueError("Only a ready still can be approved")
    still = read_bgra(take_dir(workspace, "pose", pose_id, take_id) / take["media"]["still"])[0]
    take["qa"] = qa_for(character, pose, still, (take.get("normalization") or {}).get("registration"))
    save_take(workspace, take)
    if take["qa"]["status"] == "fail":
        failed = "; ".join(c["message"] for c in take["qa"]["checks"] if c["level"] == "fail")
        raise ValueError(f"Still QA failed: {failed}. Re-import with an explicit placement, or record an "
                         "intended offset with 'production pose expect'")
    take = decide(workspace, "pose", pose_id, take_id, "accept", reason)
    if pose_id == character["basePose"]:
        metrics = measure(still)
        character["anchors"] = {"take": take_id, **{k: metrics[k] for k in ("headTopY", "headCenterX", "area", "bbox")}}
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
