"""Clip registration preserves motion by applying one head matrix to every source frame."""
import hashlib

import numpy as np
import pytest

pytest.importorskip("cv2")

from synthetic import CANVAS, clip_with_take, save, still
from spriteforge.production.clips import import_clip_take
from spriteforge.production.geometry import describe, placement, warp
from spriteforge.production.media import read_bgra, sorted_pngs
from spriteforge.production.project import add_clip, set_clip
from spriteforge.production.records import decide, load_owner, take_dir, take_media_frames
from spriteforge.production.render import adopt_processed_take, render_clip, render_take


def hashes(paths):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def quiet(*_):
    pass


@pytest.mark.parametrize("crop,margin,candidate", [(False, 0, False), (False, 12, True), (True, 12, True)])
def test_all_frames_use_fixed_head_matrix_and_tail_motion_remains_a_qa_failure(studio, crop, margin, candidate):
    published = studio.root / "production/clips/motion/output"
    if candidate:
        previous = clip_with_take(studio, "motion", "idle", "idle", 6)
        render_clip(studio.root, "motion", log=quiet)
        published_hashes = hashes(path for path in published.rglob("*") if path.is_file())
    else:
        add_clip(studio.root, "motion", "idle", "idle")
    set_clip(studio.root, "motion", register=True, lock_head=0, lock_tail=0, edge_guard=0,
             interpolate=1, pingpong=False, margin=margin, crop_black_border=crop)
    graph = (studio.root / "graph_config.json").read_bytes()
    folder = studio.tmp / "moving-source"
    base = still(studio, "idle")
    # Both framing and apparent scale change over time. End registration would
    # undo this motion if its matrix were interpolated into the spatial mapping.
    for index in range(9):
        t = index / 8
        source_matrix = placement(1.02 + 0.09 * t, 5 + 20 * t, -1 + 8 * t)
        save(folder / f"{index:04d}.png", warp(base, source_matrix, 320, 390, (0, 0, 0, 0)))
    take = import_clip_take(studio.root, "motion", folder, fps=30)
    raw = take_media_frames(studio.root, take)
    raw_hashes = hashes([*sorted_pngs(folder), *raw])
    record_path = take_dir(studio.root, "clip", "motion", take["id"]) / "take.json"
    record = record_path.read_bytes()
    if candidate:
        render = render_take(studio.root, "motion", take["id"], log=quiet)
        output = take_dir(studio.root, "clip", "motion", take["id"]) / "processed"
    else:
        decide(studio.root, "clip", "motion", take["id"], "accept")
        record = record_path.read_bytes()
        render = render_clip(studio.root, "motion", log=quiet)
        output = published

    registration = render["registration"]
    assert registration["method"] == "fixed-head"
    matrix = np.array(registration["matrix"])
    head_matrix = matrix.copy()
    head_matrix[0, 2] -= margin
    assert describe(head_matrix) == {key: registration["head"][key] for key in describe(head_matrix)}
    assert abs(registration["head"]["scale"] - 1 / 1.02) < 0.01
    source_images = [read_bgra(path)[0] for path in raw]
    if crop:
        x0, y0, x1, y1 = render["sourceCrop"]["rect"]
        source_images = [image[y0:y1, x0:x1] for image in source_images]
        assert render["sourceCrop"]["sourceSize"] == {"width": 320, "height": 390}
    else:
        assert "sourceCrop" not in render
    frames = sorted_pngs(output / render["phase"])
    assert len(frames) == len(raw)
    outputs = [read_bgra(path)[0] for path in frames]
    for source, actual in zip(source_images, outputs):
        expected = warp(source, matrix, CANVAS[0] + 2 * margin, CANVAS[1], (0, 0, 0, 0))
        assert np.array_equal(actual, expected)
    assert not np.array_equal(outputs[0], outputs[-1])
    drift = next(check for check in render["qa"]["checks"] if check["check"] == "drift")
    assert drift["level"] == render["qa"]["status"] == "fail"
    assert abs(registration["drift"]["scale"]) > 0.03 and abs(registration["drift"]["tx"]) > 12
    assert hashes([*sorted_pngs(folder), *raw]) == raw_hashes and record_path.read_bytes() == record
    assert (studio.root / "graph_config.json").read_bytes() == graph
    if candidate:
        with pytest.raises(ValueError, match="blocking failure"):
            adopt_processed_take(studio.root, "motion", take["id"])
        assert load_owner(studio.root, "clip", "motion")["acceptedTake"] == previous["id"]
        assert hashes(path for path in published.rglob("*") if path.is_file()) == published_hashes
