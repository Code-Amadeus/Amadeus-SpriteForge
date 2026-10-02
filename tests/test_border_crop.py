"""One source ROI for the whole clip; crops never alter immutable source media."""
import hashlib

import numpy as np
import pytest

pytest.importorskip("cv2")

from synthetic import CANVAS, clip_with_take, figure, provider_frames, save, still
from spriteforge.production.clips import import_clip_take
from spriteforge.production.media import crop_black_border, read_bgra, sorted_pngs
from spriteforge.production.project import add_clip, add_pose, set_clip
from spriteforge.production.records import (candidate_render_freshness, load_owner, take_dir, take_media_frames)
from spriteforge.production.render import render_clip, render_take
from spriteforge.production.stills import adopt_frame


def hashes(paths):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def quiet(*_):
    pass


def test_union_includes_middle_frame_and_preserves_motion_alpha_and_sources(tmp_path):
    images = []
    for left, top in ((6, 6), (14, 2), (8, 10)):
        image = np.zeros((18, 24, 4), np.uint8)
        image[:, :, 3] = 255  # opaque black protection border
        image[top:top + 3, left:left + 4] = (70, 120, 190, 255)
        image[top + 1, left + 1, 3] = 96
        image[0, :] = (255, 255, 255, 0)  # hidden RGB must not enlarge the union
        image[:, 0] = (255, 255, 255, 0)
        images.append(image)
    paths = [save(tmp_path / "raw" / f"{i}.png", image) for i, image in enumerate(images)]
    original = hashes(paths)
    cropped, metadata = crop_black_border(paths, tmp_path / "cropped", margin=2)
    assert metadata == {"sourceSize": {"width": 24, "height": 18}, "rect": [4, 0, 20, 15],
                        "threshold": 10, "marginPx": 2}
    outputs = [read_bgra(path)[0] for path in cropped]
    assert all(image.shape == (15, 16, 4) for image in outputs)
    for source, output in zip(images, outputs):
        assert np.array_equal(output, source[0:15, 4:20])
        assert np.count_nonzero((output[:, :, :3].max(axis=2) > 10) & (output[:, :, 3] > 0)) == \
            np.count_nonzero((source[:, :, :3].max(axis=2) > 10) & (source[:, :, 3] > 0))
    centres = [np.argwhere((image[:, :, 3] > 0) & (image[:, :, 0] > 10)).mean(axis=0) for image in outputs]
    assert np.array_equal(centres[1] - centres[0], [-4, 8])
    assert np.array_equal(centres[2] - centres[0], [4, 2])
    assert hashes(paths) == original


def test_margin_clamps_to_source_and_black_frames_use_the_same_roi(tmp_path):
    black = np.zeros((8, 10, 4), np.uint8)
    black[:, :, 3] = 255
    content = black.copy()
    content[1:4, 2:5, :3] = 50
    paths = [save(tmp_path / "raw" / "black.png", black), save(tmp_path / "raw" / "content.png", content)]
    cropped, metadata = crop_black_border(paths, tmp_path / "cropped", threshold=10, margin=3)
    assert metadata["rect"] == [0, 0, 8, 7]
    assert all(read_bgra(path)[0].shape == (7, 8, 4) for path in cropped)
    assert np.array_equal(read_bgra(cropped[0])[0], black[:7, :8])


def test_threshold_is_strict_and_transparent_rgb_is_not_content(tmp_path):
    image = np.full((6, 8, 4), (255, 255, 255, 0), np.uint8)
    image[3, 4] = (10, 10, 10, 255)
    path = save(tmp_path / "raw" / "0.png", image)
    with pytest.raises(ValueError, match="no visible pixels above threshold 10"):
        crop_black_border([path], tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()
    image[3, 4] = (11, 11, 11, 1)
    save(path, image)
    cropped, metadata = crop_black_border([path], tmp_path / "cropped", margin=0)
    assert metadata["rect"] == [4, 3, 5, 4]
    assert np.array_equal(read_bgra(cropped[0])[0], image[3:4, 4:5])


def test_mismatched_dimensions_fail_before_any_crop_is_written(tmp_path):
    paths = [save(tmp_path / "raw" / f"{i}.png", np.full(size, 255, np.uint8))
             for i, size in enumerate(((8, 10, 4), (8, 11, 4)))]
    original = hashes(paths)
    with pytest.raises(ValueError, match="same dimensions"):
        crop_black_border(paths, tmp_path / "cropped")
    assert not (tmp_path / "cropped").exists() and hashes(paths) == original
    with pytest.raises(ValueError, match="separate from the source"):
        crop_black_border(paths, paths[0].parent)
    assert hashes(paths) == original


def padded_folder(studio, name, start, end, count, *, middle_extension=False):
    folder = studio.tmp / name
    for index, frame in enumerate(provider_frames(start, end, count)):
        image = np.pad(frame, ((10, 20), (12, 16), (0, 0)))
        if middle_extension and index == count // 2:
            image[3:5, 4:7] = 120
        save(folder / f"{index:04d}.png", image)
    return folder


def test_candidate_crop_is_optional_and_does_not_replace_raw_or_published_media(studio):
    previous = clip_with_take(studio, "smile_in", "idle", "smile", 6, lock_head=2, lock_tail=2)
    render_clip(studio.root, "smile_in", log=quiet)
    published = studio.root / "production/clips/smile_in/output"
    published_hashes = hashes(path for path in published.rglob("*") if path.is_file())
    graph = (studio.root / "graph_config.json").read_bytes()
    folder = padded_folder(studio, "bordered", still(studio, "idle"), still(studio, "smile"), 8)
    candidate = import_clip_take(studio.root, "smile_in", folder, fps=30)
    source = take_media_frames(studio.root, candidate)
    original = hashes([*sorted_pngs(folder), *source])
    record_path = take_dir(studio.root, "clip", "smile_in", candidate["id"]) / "take.json"
    record = record_path.read_bytes()
    disabled = render_take(studio.root, "smile_in", candidate["id"], log=quiet)
    assert "sourceCrop" not in disabled
    set_clip(studio.root, "smile_in", crop_black_border=True, crop_black_margin=0)
    enabled = render_take(studio.root, "smile_in", candidate["id"], log=quiet)
    assert enabled["sourceCrop"] == {"sourceSize": {"width": 284, "height": 374}, "rect": [12, 10, 268, 354],
                                     "threshold": 10, "marginPx": 0}
    assert enabled["qa"]["status"] != "fail", enabled["qa"]
    assert candidate_render_freshness(studio.root, load_owner(studio.root, "clip", "smile_in"), candidate["id"])[0] == "current"
    assert load_owner(studio.root, "clip", "smile_in")["acceptedTake"] == previous["id"]
    assert hashes(path for path in published.rglob("*") if path.is_file()) == published_hashes
    assert record_path.read_bytes() == record and hashes([*sorted_pngs(folder), *source]) == original
    assert (studio.root / "graph_config.json").read_bytes() == graph
    set_clip(studio.root, "smile_in", crop_black_threshold=11)
    assert candidate_render_freshness(studio.root, load_owner(studio.root, "clip", "smile_in"), candidate["id"])[0] == "stale"


def test_adopt_frame_uses_full_clip_union_before_selecting_the_last_frame(studio):
    add_pose(studio.root, "turn")
    add_clip(studio.root, "turn_in", "idle", "turn")
    set_clip(studio.root, "turn_in", last_frame="none", crop_black_border=True, crop_black_margin=0)
    changed = still(studio, "idle").copy()
    changed[:, :, :3] = figure(*CANVAS, seed=99)[:, :, :3]
    folder = padded_folder(studio, "turn_bordered", still(studio, "idle"), changed, 5, middle_extension=True)
    source = import_clip_take(studio.root, "turn_in", folder, fps=30)
    raw = take_media_frames(studio.root, source)
    original = hashes(raw)
    adopted = adopt_frame(studio.root, "turn_in", source["id"], frame="last", log=quiet)
    metadata = adopted["source"]["sourceCrop"]
    assert metadata == {"sourceSize": {"width": 284, "height": 374}, "rect": [4, 3, 268, 354],
                        "threshold": 10, "marginPx": 0}
    adopted_source = take_dir(studio.root, "pose", "turn", adopted["id"]) / adopted["media"]["source"]
    assert np.array_equal(read_bgra(adopted_source)[0], read_bgra(raw[-1])[0][3:354, 4:268])
    assert adopted["source"]["frame"] == 4 and adopted["source"]["frames"] == 5
    assert hashes(raw) == original
    set_clip(studio.root, "turn_in", crop_black_border=False)
    uncropped = adopt_frame(studio.root, "turn_in", source["id"], frame="last", log=quiet)
    uncropped_source = take_dir(studio.root, "pose", "turn", uncropped["id"]) / uncropped["media"]["source"]
    assert "sourceCrop" not in uncropped["source"]
    assert np.array_equal(read_bgra(uncropped_source)[0], read_bgra(raw[-1])[0])
    assert hashes(raw) == original


def test_all_black_candidate_fails_without_touching_existing_published_output(studio):
    previous = clip_with_take(studio, "idle_loop", "idle", "idle", 6)
    render_clip(studio.root, "idle_loop", log=quiet)
    published = studio.root / "production/clips/idle_loop/output"
    original_output = hashes(path for path in published.rglob("*") if path.is_file())
    folder = studio.tmp / "black"
    for index in range(3):
        save(folder / f"{index}.png", np.zeros((CANVAS[1], CANVAS[0], 3), np.uint8))
    candidate = import_clip_take(studio.root, "idle_loop", folder, fps=30)
    raw = take_media_frames(studio.root, candidate)
    original_source = hashes(raw)
    set_clip(studio.root, "idle_loop", crop_black_border=True)
    with pytest.raises(ValueError, match="no visible pixels"):
        render_take(studio.root, "idle_loop", candidate["id"], log=quiet)
    assert load_owner(studio.root, "clip", "idle_loop")["acceptedTake"] == previous["id"]
    assert hashes(path for path in published.rglob("*") if path.is_file()) == original_output
    assert hashes(raw) == original_source
    assert not (take_dir(studio.root, "clip", "idle_loop", candidate["id"]) / "processed").exists()
