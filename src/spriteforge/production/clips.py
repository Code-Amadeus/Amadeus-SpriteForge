"""Clip takes: prepare provider inputs, import external videos, generate and resume.

Every take directory keeps the exact first/last frame images and the prompt
snapshot it corresponds to. For a generated take they are what was sent; for an
imported take they are the inputs 'production prepare' handed out, recorded as
assumed because the external tool cannot be verified.

A transition with ``generation.lastFrame`` set to ``none`` is generated from its
first frame only: its end pose has no still yet and takes one from the result
(``stills.adopt_frame``). Its takes record that no last frame was sent.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import cv2
import numpy as np

from ..workspace import atomic_json
from . import prompts
from .geometry import composite
from .media import VIDEO_SUFFIXES, copy_durable, encode_png, read_bgra, sorted_pngs, video_info, write_durable
from .prompts import require_complete
from .providers import VideoJob, get_provider
from .records import (canvas_size, clip_settings, load_character, load_owner, load_take, new_take, save_take,
                      still_path, take_dir)
from .stills import still_input, still_prompt
from .tools import load_tools


def clip_prompt(workspace: Path, character: dict, clip: dict) -> dict:
    return prompts.clip_prompt(prompts.load_library(workspace), character, clip)


def upload_image(character: dict, still: np.ndarray, scale: float = 1.0) -> bytes:
    """Opaque canvas image for a provider; an optional scale leaves a safety margin around the subject."""
    flat = composite(still, character["background"])
    if scale != 1.0:
        width, height = canvas_size(character)
        small = cv2.resize(flat, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
        flat = np.empty_like(flat)
        flat[:] = character["background"][::-1]
        y, x = (height - small.shape[0]) // 2, (width - small.shape[1]) // 2
        flat[y:y + small.shape[0], x:x + small.shape[1]] = small
    return encode_png(flat)


def clip_inputs(workspace: Path, character: dict, clip: dict) -> tuple[bytes, bytes | None, dict]:
    """The first and last frame images for a provider; no last frame when the clip is generated from its first only."""
    first_only = clip_settings(clip)["lastFrame"] == "none"
    scale = float(clip["generation"].get("inputScale", 1.0))
    images, record = {}, {"first": None, "last": None}
    for end in ("from",) if first_only else ("from", "to"):
        try:
            path, take = still_path(workspace, clip[end])
        except ValueError as exc:
            if end == "to":
                raise ValueError(f"{exc}: approve one, or generate this transition from its first frame only "
                                 "(lastFrame none) and adopt a frame of the result as that still") from exc
            raise
        images[end] = upload_image(character, read_bgra(path)[0], scale)
        record["first" if end == "from" else "last"] = {"pose": clip[end], "still": take["id"],
                                                         "sha256": hashlib.sha256(images[end]).hexdigest()}
    return images["from"], images.get("to"), record


def _store_inputs(directory: Path, first: bytes, last: bytes | None, record: dict) -> None:
    write_durable(directory / "first.png", first)
    record["first"]["file"] = "first.png"
    if last is not None:
        write_durable(directory / "last.png", last)
        record["last"]["file"] = "last.png"


def prepare(workspace: Path, kind: str, owner_id: str, target: Path) -> list[Path]:
    """Write the exact inputs and prompt for generating a take in an external tool."""
    character = load_character(workspace)
    target = Path(target)
    if target.exists() and any(target.iterdir()):
        raise ValueError(f"Prepare target must be a new or empty directory: {target}")
    files: dict[str, bytes] = {}
    if kind == "clip":
        clip = load_owner(workspace, "clip", owner_id)
        snapshot = clip_prompt(workspace, character, clip)
        files["first.png"], last, _ = clip_inputs(workspace, character, clip)
        if last is not None:
            files["last.png"] = last
    else:
        pose = load_owner(workspace, "pose", owner_id)
        snapshot = still_prompt(workspace, character, pose)
        files["base.png"], _ = still_input(workspace, character)
    files["prompt.txt"] = snapshot["text"].encode()
    files["negative.txt"] = snapshot["negative"].encode()
    written = []
    for name, data in files.items():
        write_durable(target / name, data)
        written.append(target / name)
    atomic_json(target / "prompt.json", snapshot)
    return [*written, target / "prompt.json"]


def import_clip_take(workspace: Path, clip_id: str, media: Path, *, fps: float | None = None, note: str = "") -> dict:
    character, clip = load_character(workspace), load_owner(workspace, "clip", clip_id)
    media = Path(media)
    frames = sorted_pngs(media) if media.is_dir() else []
    if media.is_dir() and (not frames or not fps or fps <= 0):
        raise ValueError("A frame folder import needs PNG frames and --fps")
    if media.is_file() and media.suffix.lower() not in VIDEO_SUFFIXES:
        raise ValueError(f"Clip media must be a video ({', '.join(sorted(VIDEO_SUFFIXES))}) or a PNG frame folder")
    if not media.exists():
        raise ValueError(f"Clip media not found: {media}")
    first, last, inputs = clip_inputs(workspace, character, clip)
    take, directory = new_take(workspace, "clip", clip_id, {"provider": "manual", "file": media.name, "note": note})
    try:
        take["prompt"] = clip_prompt(workspace, character, clip)
        _store_inputs(directory, first, last, inputs)
        take["inputs"] = {**inputs, "assumed": True}
        if frames:
            for index, frame in enumerate(frames):
                copy_durable(frame, directory / "frames" / f"{index:06d}.png")
            size = read_bgra(frames[0])[0].shape
            take["media"] = {"dir": "frames", "fps": float(fps), "count": len(frames), "width": size[1], "height": size[0]}
        else:
            copy_durable(media, directory / f"media{media.suffix.lower()}")
            take["media"] = {"video": f"media{media.suffix.lower()}", **video_info(directory / f"media{media.suffix.lower()}")}
            if fps:
                take["media"]["fps"] = float(fps)
        take["state"] = "ready"
    except Exception as exc:
        take.update(state="failed", error=str(exc))
        raise
    finally:
        save_take(workspace, take)
    return take


def generate_clip_take(workspace: Path, clip_id: str, *, provider: str | None = None, wait: bool = True,
                       dry_run: bool = False, log=print) -> dict:
    character, clip, tools = load_character(workspace), load_owner(workspace, "clip", clip_id), load_tools(workspace)
    name = provider or clip["generation"]["provider"]
    if name == "manual":
        raise ValueError("This clip is generated manually: run 'production prepare', then 'production take import'")
    adapter = get_provider(name, tools)
    snapshot = clip_prompt(workspace, character, clip)
    first, last, inputs = clip_inputs(workspace, character, clip)
    generation = clip["generation"]
    job = VideoJob(snapshot["text"], snapshot["negative"] if adapter.negative_prompt else "", first, last,
                   int(generation["durationS"]), str(generation["resolution"]), generation.get("seed"))
    request = adapter.preview(job)
    if dry_run:
        return {"provider": name, "model": adapter.model, "request": request, "prompt": snapshot}
    require_complete(snapshot)
    adapter.key()  # a missing key or login fails before a take is recorded
    source = {"provider": name, "model": adapter.model, "request": request}
    balance = adapter.balance()
    if balance is not None:
        source["balanceBefore"] = balance
    take, directory = new_take(workspace, "clip", clip_id, source)
    take["prompt"] = {**snapshot, "negativeSent": bool(job.negative)}
    _store_inputs(directory, first, last, inputs)
    take["inputs"] = inputs
    take["state"] = "submitting"
    save_take(workspace, take)
    try:
        take["source"]["taskId"] = adapter.submit(job)
    except Exception as exc:
        take.update(state="failed", error=str(exc))
        save_take(workspace, take)
        raise
    take["state"] = "submitted"
    save_take(workspace, take)
    log(f"Submitted {name} task {take['source']['taskId']} as take {take['id']}"
        + (" (first frame only)" if last is None else ""))
    return finish_take(workspace, take, log=log) if wait else take


def finish_take(workspace: Path, take: dict, *, log=print) -> dict:
    """Poll a submitted take until its video is downloaded or the provider reports failure."""
    if take.get("state") == "submitting":
        raise ValueError(f"Take {take['id']} was interrupted before the provider returned a task id; "
                         "check the provider's task list before generating again")
    if take.get("state") != "submitted":
        raise ValueError(f"Take {take['id']} is {take.get('state')}, not waiting for a provider")
    adapter = get_provider(take["source"]["provider"], load_tools(workspace))
    deadline = time.monotonic() + adapter.timeout_seconds
    while True:
        status, url, detail = adapter.poll(take["source"]["taskId"])
        if status == "succeeded":
            directory = take_dir(workspace, "clip", take["owner"]["id"], take["id"])
            adapter.fetch_result(take["source"]["taskId"], url, directory / "media.mp4")
            take.update(state="ready", media={"video": "media.mp4", **video_info(directory / "media.mp4")})
            balance = adapter.balance()
            if balance is not None:
                take["source"]["balanceAfter"] = balance
            save_take(workspace, take)
            log(f"Take {take['id']} is ready for review")
            return take
        if status == "failed":
            take.update(state="failed", error=detail)
            save_take(workspace, take)
            raise ValueError(f"Provider reported failure for take {take['id']}: {detail}")
        if time.monotonic() > deadline:
            raise ValueError(f"Take {take['id']} is still {detail}; run 'production take resume' later")
        log(f"Take {take['id']}: {detail or 'pending'}")
        time.sleep(adapter.poll_seconds)


def resume_clip_take(workspace: Path, clip_id: str, take_id: str, *, log=print) -> dict:
    return finish_take(workspace, load_take(workspace, "clip", clip_id, take_id), log=log)
