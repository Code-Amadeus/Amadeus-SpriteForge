"""Render the accepted take of a clip into its graph-bindable output directory.

decode -> register both ends to the pose stills -> pingpong -> interpolate
-> alpha -> edge guard -> lock the ends to the stills -> QA -> publish

A clip with ``marginPx`` renders onto the canvas widened by that many transparent
columns on each side (for example hair blowing past the canvas); the runtime
centres every frame, so the pose stills are widened the same way. A clip with
``register`` off takes its frames as already placed on that canvas.

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
from .checks import clip_report, expected_anchor, worst
from .clips import take_media_frames
from .geometry import composite, estimate_similarity, lerp_matrix, premultiplied_blend, smoothstep, warp
from .media import copy_durable, decode_video, find_ffmpeg, read_bgra, sorted_pngs, write_png
from .mouth import TONE_WATCH, analyze, harmonize, prior
from .records import (accepted_take, canvas_size, clip_settings, load_character, load_owner, now, output_root, owner_dir,
                      recipe, render_stills, still_path)
from .tools import load_tools, run_processor

RENDER_FORMAT = "spriteforge.production.render.v1"
MOUTH_OVERLAY = ".mouth/closed.png"  # hidden from frame-folder discovery; export encodes it


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


def widen(image: np.ndarray, margin: int) -> np.ndarray:
    """A canvas image on the canvas widened by transparent margins."""
    return np.pad(image, ((0, 0), (margin, margin), (0, 0))) if margin else image


def render_clip(workspace: Path, clip_id: str, *, keep_work: bool = False, log=print) -> dict:
    character, tools = load_character(workspace), load_tools(workspace)
    clip = load_owner(workspace, "clip", clip_id)
    settings = clip_settings(clip)
    take = accepted_take(workspace, "clip", clip_id)
    (start_path, start_take), (end_path, end_take) = still_path(workspace, clip["from"]), still_path(workspace, clip["to"])
    start, end = read_bgra(start_path)[0], read_bgra(end_path)[0]
    margin = settings["marginPx"]
    width, height = canvas_size(character)
    wide_start, wide_end, wide_width = widen(start, margin), widen(end, margin), width + 2 * margin
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
        factor, wrap = settings["interpolate"], clip["kind"] == "loop"
        sequence = 2 * len(source) - 2 if settings["pingpong"] else len(source)
        total = sequence * factor if wrap else (sequence - 1) * factor + 1
        if settings["lockHeadFrames"] + settings["lockTailFrames"] > total:
            raise ValueError(f"Locking {settings['lockHeadFrames']}+{settings['lockTailFrames']} frames needs a longer "
                             f"clip than {total} frames")

        first, native_alpha = read_bgra(source[0])
        needs_alpha = not native_alpha or settings["interpolate"] > 1
        registration = drift = None
        if settings["register"]:
            head_matrix, head_info = estimate_similarity(composite(first, background), composite(start, background))
            tail_matrix, tail_info = estimate_similarity(composite(read_bgra(source[-1])[0], background),
                                                         composite(end, background))
            log(f"{clip_id}: registered head scale {head_info['scale']:.4f}, tail scale {tail_info['scale']:.4f}")
            drift = {"scale": round(tail_info["scale"] / head_info["scale"] - 1, 5),
                     **{key: round(tail_info[key] - head_info[key], 3) for key in ("tx", "ty", "rotationDeg")}}
            registration = {"head": head_info, "tail": tail_info, "drift": drift}
        border = (*background[::-1], 255) if needs_alpha else (0, 0, 0, 0)
        shift = np.array([[0, 0, margin], [0, 0, 0]], np.float64)
        if settings["register"] or needs_alpha or settings["pingpong"] or factor > 1:
            registered = []
            for index, path in enumerate(source):
                frame = read_bgra(path)[0]
                if settings["register"]:
                    matrix = lerp_matrix(head_matrix, tail_matrix, index / (len(source) - 1)) + shift
                    frame = warp(frame, matrix, wide_width, height, border)
                target = work / "registered" / f"{index:06d}.png"
                write_png(target, composite(frame, background) if needs_alpha else frame)
                registered.append(target)
        else:
            registered = list(source)  # already placed on the canvas: nothing to redo before the output
        if settings["pingpong"]:
            for index, path in enumerate(registered[-2:0:-1], start=len(registered)):
                copy_durable(path, work / "registered" / f"{index:06d}.png")
            registered = sorted_pngs(work / "registered")

        frames = registered
        if factor > 1:
            log(f"{clip_id}: interpolating {len(frames)} frames x{factor}")
            run_processor(tools, "interpolate", work / "registered", work / "interpolated", factor=factor, wrap=int(wrap))
            frames = _checked(work / "interpolated", total, "interpolate")
        if needs_alpha:
            log(f"{clip_id}: matting {len(frames)} frames")
            run_processor(tools, "alpha", frames[0].parent, work / "alpha")
            matted = _checked(work / "alpha", len(frames), "alpha")
            if [p.name for p in matted] != [p.name for p in frames]:
                raise ValueError("The alpha processor must keep the input file names")
            frames = matted

        head_n, tail_n = settings["lockHeadFrames"], settings["lockTailFrames"]
        output = work / "output"
        written = []
        for index, path in enumerate(frames):
            frame, has_alpha = read_bgra(path)
            if frame.shape[:2] != (height, wide_width) or (needs_alpha and not has_alpha):
                raise ValueError(f"Frame {path.name} is {frame.shape[1]}x{frame.shape[0]}, not a {wide_width}x{height} "
                                 "RGBA canvas frame" + ("" if settings["register"] else
                                                        "; register the take or set processing.marginPx"))
            frame = _edge_guard(frame, settings["edgeGuardPx"], character["cutEdges"])
            if index < head_n:
                frame = premultiplied_blend(frame, wide_start, 1 - smoothstep(index / head_n))
            if total - 1 - index < tail_n:
                frame = premultiplied_blend(frame, wide_end, 1 - smoothstep((total - 1 - index) / tail_n))
            target = output / clip["phase"] / f"{index:06d}.png"
            write_png(target, frame)
            written.append(target)

        qa = clip_report(character, written, clip["kind"], wide_start, wide_end, drift)
        interval = round(1000 / (fps * factor * settings["speed"]))
        stills = {"from": start_take["id"], "to": end_take["id"]}
        mouth = _mouth_track(workspace, character, clip, written, stills, output, margin, log) if clip.get("mouth") else None
        if mouth:
            qa["checks"] += [{"check": f"mouth.{name}", "level": level, "message": message}
                             for name, level, message in mouth.pop("checks")]
            qa["status"] = worst(c["level"] for c in qa["checks"])
        render = {"format": RENDER_FORMAT, "clip": clip_id, "take": take["id"],
                  "stills": stills, "recipe": recipe(clip), "renderedAt": now(),
                  "phase": clip["phase"], "frameCount": total, "sourceFps": fps, "interpolate": factor,
                  "frameIntervalMs": max(1, interval), "loopMode": settings["loopMode"],
                  "registration": registration, "qa": qa,
                  **({"mouth": mouth} if mouth else {})}
        atomic_json(output / "render.json", render)
        _publish(output, clip_directory / "output")
        log(f"{clip_id}: published {total} frames to {output_root(clip_id)} (QA {qa['status']}, "
            f"{render['frameIntervalMs']} ms/frame)")
        return render
    finally:
        if not keep_work:
            shutil.rmtree(work, ignore_errors=True)


def _mouth_track(workspace: Path, character: dict, clip: dict, frames: list[Path], stills: dict, output: Path,
                 margin: int, log) -> dict:
    """Silence-overlay data for a speaking loop. The closed-mouth image is, by default, the
    shared closed mouth of the loop's pose (the base still for front poses), never frame 0:
    a loop entered through a transition does not necessarily start closed. The image is
    tone-matched to the loop and stored with the render, which is what export encodes."""
    settings = clip["mouth"]
    sets = character.get("mouthSets") or {}
    if settings["set"] not in sets:
        raise ValueError(f"Unknown mouth set {settings['set']!r}; define it with 'production mouth set'")
    source = settings["closedSource"]
    anchors = character.get("anchors") or {}
    expected = expected_anchor(character, load_owner(workspace, "pose", clip["to"]))
    offset = (expected["headCenterX"] - anchors["headCenterX"], expected["headTopY"] - anchors["headTopY"])
    frame_index = None
    if source["kind"] == "frame":
        if source["index"] >= len(frames):
            raise ValueError(f"Mouth closedSource frame {source['index']} is outside the {len(frames)} rendered frames")
        frame_index, image = source["index"], read_bgra(frames[source["index"]])[0]
        closed = {"kind": "frame", "index": frame_index}
    else:
        pose_id = render_stills(workspace, clip).get("mouth", clip["to"])
        path, still_take = still_path(workspace, pose_id)
        image = widen(read_bgra(path)[0], margin)
        if source["kind"] != "still":
            stills["mouth"] = still_take["id"]
        closed = {"kind": source["kind"], "pose": pose_id, "still": still_take["id"]}
    log(f"{clip['id']}: tracking the mouth for silence overlays")
    track = analyze(frames, image, prior(sets[settings["set"]], offset), character["background"], source_is_frame=frame_index)
    overlay, shift = harmonize(image, frames, track["anchorTrack"], track["sourceAnchor"])
    write_png(output / MOUTH_OVERLAY, overlay)
    if abs(shift[0]) > TONE_WATCH:
        track["checks"].append(("tone", "watch", f"The closed mouth needed a {shift[0]:+.1f} L* tone shift for this loop; "
                                                  "consider a closed-mouth source closer to this look"))
    return {"set": settings["set"], "closedSource": closed, "overlay": MOUTH_OVERLAY, "toneShift": shift, **track}


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
