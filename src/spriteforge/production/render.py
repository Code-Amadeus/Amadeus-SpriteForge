"""Render the accepted take of a clip into its graph-bindable output directory.

decode -> register both ends to the pose stills -> pingpong -> interpolate
-> alpha -> edge guard -> lock the ends to the stills -> QA -> publish

``production/clips/<id>/output`` is swapped in as a whole after every frame and
render.json are on disk, so a graph root never shows a half-written render.
Frames stream through a hidden work directory instead of memory.
"""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import numpy as np

from ..workspace import atomic_json
from .checks import clip_report
from .clips import take_media_frames
from .geometry import composite, estimate_similarity, lerp_matrix, premultiplied_blend, smoothstep, warp
from .media import copy_durable, decode_video, find_ffmpeg, read_bgra, sorted_pngs, write_png
from .records import (accepted_take, canvas_size, clip_settings, load_character, load_owner, now, output_root, owner_dir,
                      recipe, still_path)
from .tools import load_tools, run_processor

RENDER_FORMAT = "spriteforge.production.render.v1"


def recover_output(clip_directory: Path) -> None:
    """Restore the previous render if a publish was interrupted; drop abandoned work."""
    output = clip_directory / "output"
    previous = sorted(clip_directory.glob(".output-old-*"))
    if previous and not output.exists():
        previous.pop().rename(output)
    for leftover in [*previous, *clip_directory.glob(".work-*")]:
        shutil.rmtree(leftover, ignore_errors=True)


def _checked(directory: Path, count: int, what: str) -> list[Path]:
    frames = sorted_pngs(directory)
    if len(frames) != count:
        raise ValueError(f"The {what} step produced {len(frames)} frames; expected {count}")
    return frames


def render_clip(workspace: Path, clip_id: str, *, keep_work: bool = False, log=print) -> dict:
    character, tools = load_character(workspace), load_tools(workspace)
    clip = load_owner(workspace, "clip", clip_id)
    settings = clip_settings(clip)
    take = accepted_take(workspace, "clip", clip_id)
    (start_path, start_take), (end_path, end_take) = still_path(workspace, clip["from"]), still_path(workspace, clip["to"])
    start, end = read_bgra(start_path)[0], read_bgra(end_path)[0]
    width, height = canvas_size(character)
    background = character["background"]
    clip_directory = owner_dir(workspace, "clip", clip_id)
    recover_output(clip_directory)
    work = clip_directory / f".work-{datetime.now():%Y%m%d-%H%M%S-%f}"
    work.mkdir()
    try:
        media = take_media_frames(workspace, take)
        source = decode_video(find_ffmpeg(tools.get("ffmpeg")), media, work / "decoded") if isinstance(media, Path) else media
        if len(source) < 2:
            raise ValueError("A clip needs at least two frames")
        fps = float(take["media"]["fps"])
        log(f"{clip_id}: {len(source)} frames at {fps:g} fps from take {take['id']}")

        first, native_alpha = read_bgra(source[0])
        head_matrix, head_info = estimate_similarity(composite(first, background), composite(start, background))
        tail_matrix, tail_info = estimate_similarity(composite(read_bgra(source[-1])[0], background), composite(end, background))
        log(f"{clip_id}: registered head scale {head_info['scale']:.4f}, tail scale {tail_info['scale']:.4f}")
        needs_alpha = not native_alpha or settings["interpolate"] > 1
        border = (*background[::-1], 255) if needs_alpha else (0, 0, 0, 0)
        registered = []
        for index, path in enumerate(source):
            matrix = lerp_matrix(head_matrix, tail_matrix, index / (len(source) - 1))
            frame = warp(read_bgra(path)[0], matrix, width, height, border)
            target = work / "registered" / f"{index:06d}.png"
            write_png(target, composite(frame, background) if needs_alpha else frame)
            registered.append(target)
        if settings["pingpong"]:
            for index, path in enumerate(registered[-2:0:-1], start=len(registered)):
                copy_durable(path, work / "registered" / f"{index:06d}.png")
            registered = sorted_pngs(work / "registered")

        frames, factor = registered, settings["interpolate"]
        if factor > 1:
            wrap = clip["kind"] == "loop"
            run_processor(tools, "interpolate", work / "registered", work / "interpolated", factor=factor, wrap=int(wrap))
            count = len(frames) * factor if wrap else (len(frames) - 1) * factor + 1
            frames = _checked(work / "interpolated", count, "interpolate")
        if needs_alpha:
            run_processor(tools, "alpha", frames[0].parent, work / "alpha")
            matted = _checked(work / "alpha", len(frames), "alpha")
            if [p.name for p in matted] != [p.name for p in frames]:
                raise ValueError("The alpha processor must keep the input file names")
            frames = matted

        total, head_n, tail_n = len(frames), settings["lockHeadFrames"], settings["lockTailFrames"]
        if head_n + tail_n > total:
            raise ValueError(f"Locking {head_n}+{tail_n} frames needs a longer clip than {total} frames")
        output = work / "output"
        written = []
        for index, path in enumerate(frames):
            frame, has_alpha = read_bgra(path)
            if frame.shape[:2] != (height, width) or (needs_alpha and not has_alpha):
                raise ValueError(f"Frame {path.name} is not a {width}x{height} RGBA canvas frame")
            frame = _edge_guard(frame, settings["edgeGuardPx"], character["cutEdges"])
            if index < head_n:
                frame = premultiplied_blend(frame, start, 1 - smoothstep(index / head_n))
            if total - 1 - index < tail_n:
                frame = premultiplied_blend(frame, end, 1 - smoothstep((total - 1 - index) / tail_n))
            target = output / clip["phase"] / f"{index:06d}.png"
            write_png(target, frame)
            written.append(target)

        drift = {"scale": round(tail_info["scale"] / head_info["scale"] - 1, 5),
                 **{key: round(tail_info[key] - head_info[key], 3) for key in ("tx", "ty", "rotationDeg")}}
        qa = clip_report(character, written, clip["kind"], start, end, drift)
        interval = round(1000 / (fps * factor * settings["speed"]))
        render = {"format": RENDER_FORMAT, "clip": clip_id, "take": take["id"],
                  "stills": {"from": start_take["id"], "to": end_take["id"]}, "recipe": recipe(clip), "renderedAt": now(),
                  "phase": clip["phase"], "frameCount": total, "sourceFps": fps, "interpolate": factor,
                  "frameIntervalMs": max(1, interval), "loopMode": settings["loopMode"],
                  "registration": {"head": head_info, "tail": tail_info, "drift": drift}, "qa": qa}
        atomic_json(output / "render.json", render)
        _publish(output, clip_directory / "output")
        log(f"{clip_id}: published {total} frames to {output_root(clip_id)} (QA {qa['status']}, "
            f"{render['frameIntervalMs']} ms/frame)")
        return render
    finally:
        if not keep_work:
            shutil.rmtree(work, ignore_errors=True)


def _edge_guard(frame: np.ndarray, band: int, cut_edges: list[str]) -> np.ndarray:
    if band <= 0:
        return frame
    frame = frame.copy()
    for edge, region in (("left", np.s_[:, :band]), ("right", np.s_[:, -band:]),
                         ("top", np.s_[:band, :]), ("bottom", np.s_[-band:, :])):
        if edge not in cut_edges:
            frame[region + (3,)] = 0
    return frame


def _publish(staged: Path, output: Path) -> None:
    previous = output.with_name(f".output-old-{datetime.now():%Y%m%d-%H%M%S-%f}")
    if output.exists():
        output.rename(previous)
    staged.rename(output)
    if previous.exists():
        shutil.rmtree(previous, ignore_errors=True)
