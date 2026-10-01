"""Concept sheets are expression references, never approved pose geometry.

Original images and reroll images remain immutable. Only the current ready
sheet's cell association/image pointer can change; historical picks stay usable.
"""
from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from ..workspace import atomic_json, read_json, resolve_asset
from . import prompts
from .media import IMAGE_SUFFIXES, image_suffix, read_bgra, write_durable, write_png
from .providers import ImageJob, get_image_provider
from .records import TAKE_ID, check_id, list_owners, load_character, load_owner, new_take_id, production_dir
from .stills import still_input
from .tools import load_tools

CONCEPT_FORMAT = "spriteforge.production.concept.v1"
SHEET_LOCK = threading.RLock()


def grid_spec(value: object) -> dict:
    if isinstance(value, str):
        try:
            cols, rows = (int(part) for part in value.lower().split("x"))
        except (ValueError, TypeError):
            raise ValueError("Concept grid must be 3x2 or 2x2") from None
        value = {"rows": rows, "cols": cols}
    if not isinstance(value, dict) or set(value) != {"rows", "cols"} or any(
            isinstance(item, bool) or not isinstance(item, int) for item in value.values()) \
            or (value["rows"], value["cols"]) not in {(2, 2), (2, 3)}:
        raise ValueError("Concept grid must be 3x2 or 2x2")
    return dict(value)


def sheet_dir(workspace: Path, sheet_id: str) -> Path:
    if not isinstance(sheet_id, str) or not TAKE_ID.fullmatch(sheet_id):
        raise ValueError("Invalid concept sheet id")
    return resolve_asset(workspace, f"production/concepts/{sheet_id}")


def load_sheet(workspace: Path, sheet_id: str) -> dict:
    path = sheet_dir(workspace, sheet_id) / "sheet.json"
    if not path.is_file():
        raise ValueError(f"Unknown concept sheet {sheet_id}")
    sheet = read_json(path)
    if sheet.get("format") != CONCEPT_FORMAT:
        raise ValueError("Unsupported concept sheet format")
    return sheet


def save_sheet(workspace: Path, sheet: dict) -> None:
    with SHEET_LOCK:
        atomic_json(sheet_dir(workspace, sheet["id"]) / "sheet.json", sheet)


def list_sheets(workspace: Path) -> list[dict]:
    root = production_dir(workspace) / "concepts"
    return sorted((load_sheet(workspace, path.parent.name) for path in root.glob("*/sheet.json")),
                  key=lambda sheet: (sheet["createdAt"], sheet["id"]))


def current_sheet(workspace: Path) -> str | None:
    return next((sheet["id"] for sheet in reversed(list_sheets(workspace)) if sheet["state"] == "ready"), None)


def _poses(workspace: Path, ids: object, grid: dict, *, create: bool) -> tuple[dict, list[dict], dict]:
    if not isinstance(ids, list) or not 1 <= len(ids) <= grid["rows"] * grid["cols"]:
        raise ValueError("Choose between one pose and the grid's cell count")
    checked = [check_id(pose_id, "Pose") for pose_id in ids]
    if len(set(checked)) != len(checked):
        raise ValueError("Concept poses must be unique")
    character, library = load_character(workspace), prompts.load_library(workspace)
    still_input(workspace, character)  # all sheets refer to an approved base
    existing = {pose["id"]: pose for pose in list_owners(workspace, "pose")}
    if any(pose_id == character["basePose"] or (existing.get(pose_id) or {}).get("acceptedTake") for pose_id in checked):
        raise ValueError("New sheets use expressions without an approved still; the base is import-only")
    records = []
    for pose_id in checked:
        if pose_id in existing:
            pose = existing[pose_id]
        elif create:
            from .project import add_pose
            pose = add_pose(workspace, pose_id)
        else:
            pose = {"id": pose_id, "description": "", "prompt": {"subject": f"pose.{pose_id}"}}
        prompts.ensure_subject(library, pose["prompt"]["subject"], f"describe the {pose_id} pose or expression")
        records.append(pose)
    return character, records, library


def split_grid(image: np.ndarray, grid: dict) -> list[np.ndarray]:
    """Trim an exact uniform ring, then partition all remaining pixels row-first."""
    grid = grid_spec(grid)
    color = image[0, 0]
    if all(np.all(edge == color) for edge in (image[0], image[-1], image[:, 0], image[:, -1])):
        ys, xs = np.where(np.any(image != color, axis=2))
        if len(xs):
            image = image[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    height, width = image.shape[:2]
    if width < grid["cols"] or height < grid["rows"]:
        raise ValueError("Image cannot form non-empty concept cells")
    return [image[row * height // grid["rows"]:(row + 1) * height // grid["rows"],
                  col * width // grid["cols"]:(col + 1) * width // grid["cols"]].copy()
            for row in range(grid["rows"]) for col in range(grid["cols"])]


def _new_sheet(workspace: Path, grid: dict, poses: list[dict], *, sheet_id: str | None = None, **facts) -> dict:
    for _ in range(8):
        identifier = sheet_id or new_take_id()
        try:
            sheet_dir(workspace, identifier).mkdir(parents=True)
            break
        except FileExistsError:
            if sheet_id:
                raise ValueError("Concept sheet id already exists") from None
    else:
        raise ValueError("Could not allocate a concept sheet id")
    sheet = {"format": CONCEPT_FORMAT, "id": identifier,
             "createdAt": datetime.now(timezone.utc).isoformat(timespec="microseconds"), "grid": grid,
             "size": None, "sourceFile": None, "state": "created", "error": None,
             "cells": [{"index": index, "row": index // grid["cols"], "col": index % grid["cols"],
                        "pose": poses[index]["id"] if index < len(poses) else None, "file": f"cells/{index}.png",
                        "originalFile": f"cells/{index}.png", "picked": False, "rerolls": []}
                       for index in range(grid["rows"] * grid["cols"])], **facts}
    save_sheet(workspace, sheet)
    return sheet


def _store_image(workspace: Path, sheet: dict, data: bytes, suffix: str) -> None:
    directory = sheet_dir(workspace, sheet["id"])
    sheet["sourceFile"] = "source" + suffix
    write_durable(directory / sheet["sourceFile"], data)
    image = read_bgra(directory / sheet["sourceFile"])[0]
    sheet["size"] = {"w": image.shape[1], "h": image.shape[0]}
    for cell, pixels in zip(sheet["cells"], split_grid(image, sheet["grid"])):
        write_png(directory / cell["file"], pixels)
        cell["size"] = {"w": pixels.shape[1], "h": pixels.shape[0]}
    sheet["state"] = "ready"


def generate_sheet(workspace: Path, poses: object, grid: object, provider: str, *, dry_run: bool = False,
                   sheet_id: str | None = None, log=print) -> dict:
    grid = grid_spec(grid)
    adapter = get_image_provider(provider, load_tools(workspace))
    character, records, library = _poses(workspace, poses, grid, create=not dry_run)
    snapshot = prompts.concept_prompt(library, character, records, grid)
    image, base = still_input(workspace, character)
    job = ImageJob(snapshot["text"], snapshot["negative"] if adapter.negative_prompt else "", image,
                   size=(grid["cols"] * 512, grid["rows"] * 512))
    request = adapter.preview(job)
    if dry_run:
        return {"provider": provider, "model": adapter.model, "grid": grid, "prompt": snapshot, "request": request}
    prompts.require_complete(snapshot)
    adapter.key()
    sheet = _new_sheet(workspace, grid, records, sheet_id=sheet_id, provider=provider, model=adapter.model,
                       request=request, prompt=snapshot, inputs={"base": {"take": base["still"], "sha256": base["sha256"],
                                                                          "file": "input.png"}})
    write_durable(sheet_dir(workspace, sheet["id"]) / "input.png", image)
    sheet["state"] = "submitting"
    save_sheet(workspace, sheet)
    try:
        log(f"Generating concept sheet {sheet['id']} with {provider}")
        result = adapter.edit(job)  # exactly one explicitly requested call
        _store_image(workspace, sheet, result, image_suffix(result))
    except Exception as exc:
        sheet.update(state="failed", error=str(exc))
        raise
    finally:
        save_sheet(workspace, sheet)
    return sheet


def import_sheet(workspace: Path, source: Path, poses: object, grid: object) -> dict:
    source, grid = Path(source), grid_spec(grid)
    if not source.is_file() or source.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError("Concept import needs an image file")
    split_grid(read_bgra(source)[0], grid)  # invalid sources fail before creating records
    character, records, library = _poses(workspace, poses, grid, create=True)
    image, base = still_input(workspace, character)
    sheet = _new_sheet(workspace, grid, records, provider="manual", model=None, request=None,
                       prompt=prompts.concept_prompt(library, character, records, grid),
                       inputs={"base": {"take": base["still"], "sha256": base["sha256"], "file": "input.png"}, "assumed": True})
    write_durable(sheet_dir(workspace, sheet["id"]) / "input.png", image)
    try:
        _store_image(workspace, sheet, source.read_bytes(), source.suffix.lower())
    except Exception as exc:
        sheet.update(state="failed", error=str(exc))
        raise
    finally:
        save_sheet(workspace, sheet)
    return sheet


def _cell(sheet: dict, index: object) -> dict:
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(sheet["cells"]):
        raise ValueError("Concept cell index is outside the sheet")
    if sheet["state"] != "ready":
        raise ValueError("Concept sheet is not ready")
    return sheet["cells"][index]


def set_cell(workspace: Path, sheet_id: str, index: object, *, picked: bool | None = None,
             pose: str | None = None) -> dict:
    with SHEET_LOCK:
        sheet = load_sheet(workspace, sheet_id)
        cell = _cell(sheet, index)
        if picked is not None and not isinstance(picked, bool):
            raise ValueError("Concept picked must be true or false")
        if pose is not None:
            if current_sheet(workspace) != sheet_id:
                raise ValueError("Historical sheet associations are read-only; picks remain available")
            if pose == load_character(workspace)["basePose"]:
                raise ValueError("The base pose is import-only")
            load_owner(workspace, "pose", pose)
            cell["pose"] = pose
        if picked and not cell["pose"]:
            raise ValueError("Assign a pose before picking this cell")
        if picked is not None:
            cell["picked"] = picked
        save_sheet(workspace, sheet)
        return sheet


def concept_reference(workspace: Path, sheet_id: str, index: object, pose_id: str) -> tuple[bytes, dict]:
    sheet = load_sheet(workspace, sheet_id)
    cell = _cell(sheet, index)
    if cell["pose"] != pose_id:
        raise ValueError("The concept cell must be assigned to this pose")
    data = resolve_asset(workspace, str(sheet_dir(workspace, sheet_id) / cell["file"])).read_bytes()
    return data, {"sheet": sheet_id, "cell": index, "sha256": hashlib.sha256(data).hexdigest()}


def reroll_cell(workspace: Path, sheet_id: str, index: object, provider: str, *, dry_run: bool = False, log=print) -> dict:
    sheet = load_sheet(workspace, sheet_id)
    cell = _cell(sheet, index)
    if current_sheet(workspace) != sheet_id:
        raise ValueError("Historical sheets are read-only; picks remain available")
    if not cell["pose"]:
        raise ValueError("Assign a pose before rerolling this cell")
    character, pose = load_character(workspace), load_owner(workspace, "pose", cell["pose"])
    adapter = get_image_provider(provider, load_tools(workspace))
    if not adapter.supports_reference:
        raise ValueError("This provider does not support concept references")
    reference, provenance = concept_reference(workspace, sheet_id, index, pose["id"])
    source_file = cell["file"]
    image, base = still_input(workspace, character)
    snapshot = prompts.still_reference_prompt(prompts.load_library(workspace), character, pose)
    side = max(cell["size"]["w"], cell["size"]["h"])
    job = ImageJob(snapshot["text"], snapshot["negative"] if adapter.negative_prompt else "", image,
                   references=[reference], size=(side, side))
    request = adapter.preview(job)
    if dry_run:
        return {"provider": provider, "model": adapter.model, "request": request, "prompt": snapshot}
    prompts.require_complete(snapshot)
    adapter.key()
    identifier = new_take_id()
    prefix = f"cells/{index}/rerolls/{identifier}"
    attempt = {"id": identifier, "createdAt": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
               "pose": pose["id"], "provider": provider, "model": adapter.model, "request": request, "prompt": snapshot,
               "inputs": {"base": {"take": base["still"], "sha256": base["sha256"], "file": prefix + "-input.png"},
                          "reference": {**provenance, "file": prefix + "-reference.png"}},
               "state": "submitting", "sourceFile": None, "file": None, "error": None}
    directory = sheet_dir(workspace, sheet_id)
    write_durable(directory / attempt["inputs"]["base"]["file"], image)
    write_durable(directory / attempt["inputs"]["reference"]["file"], reference)
    with SHEET_LOCK:
        sheet = load_sheet(workspace, sheet_id)
        sheet["cells"][index]["rerolls"].append(attempt)
        save_sheet(workspace, sheet)
    try:
        log(f"Rerolling {sheet_id} cell {index} with {provider}")
        result = adapter.edit(job)
        attempt["sourceFile"] = prefix + "-source" + image_suffix(result)
        write_durable(directory / attempt["sourceFile"], result)
        pixels = read_bgra(directory / attempt["sourceFile"])[0]
        attempt.update(file=prefix + ".png", size={"w": pixels.shape[1], "h": pixels.shape[0]}, state="ready")
        write_png(directory / attempt["file"], pixels)
    except Exception as exc:
        attempt.update(state="failed", error=str(exc))
        raise
    finally:
        with SHEET_LOCK:
            sheet = load_sheet(workspace, sheet_id)
            current = sheet["cells"][index]
            position = next(position for position, recorded in enumerate(current["rerolls"]) if recorded["id"] == identifier)
            current["rerolls"][position] = attempt
            if attempt["state"] == "ready" and current_sheet(workspace) == sheet_id \
                    and current["pose"] == pose["id"] and current["file"] == source_file:
                current.update(file=attempt["file"], size=attempt["size"])
            save_sheet(workspace, sheet)
    return sheet
