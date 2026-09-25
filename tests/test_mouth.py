import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from synthetic import CANVAS, flatten, save, still  # noqa: E402

from spriteforge.character_pack import load_character_pack  # noqa: E402
from spriteforge.exporter import export_pack  # noqa: E402
from spriteforge.production.clips import import_clip_take  # noqa: E402
from spriteforge.production.project import add_clip, set_clip, set_closed_mouth, set_mouth_set  # noqa: E402
from spriteforge.production.records import decide, load_character, load_owner, render_freshness  # noqa: E402
from spriteforge.production.render import render_clip  # noqa: E402
from spriteforge.workspace import atomic_json  # noqa: E402

OPENING = [0, 2, 4, 6, 4, 2]


def mouth_centre(studio):
    shape = load_character(studio.root)["mouthSets"]["neutral"]
    return round(shape["cx"] + CANVAS[0] / 2), round(shape["cy"] + CANVAS[1] / 2)


def speaking_loop(studio, pose="smile", count=25):
    """A 'generated' speaking loop that starts and ends closed; the head bobs by up to 2 px."""
    base, (mx, my) = still(studio, pose), mouth_centre(studio)
    folder = studio.tmp / f"{pose}_talk"
    bobs = []
    for index in range(count):
        bob = round(2 * math.sin(2 * math.pi * index / count))
        image = cv2.warpAffine(base, np.float32([[1, 0, 0], [0, 1, bob]]), CANVAS, borderValue=(0, 0, 0, 0))
        if OPENING[index % len(OPENING)]:
            cv2.ellipse(image, (mx, my + bob), (7, OPENING[index % len(OPENING)]), 0, 0, 360, (30, 30, 120, 255), -1)
        matrix = np.array([[1.06, 0, 9], [0, 1.06, -5]], np.float32)
        save(folder / f"{index:04d}.png", cv2.warpAffine(flatten(image), matrix, (256, 344), flags=cv2.INTER_CUBIC,
                                                         borderValue=(255, 255, 255)))
        bobs.append(bob)
    return folder, bobs


def talking_clip(studio, clip_id="smile_talk", pose="smile"):
    add_clip(studio.root, clip_id, pose, pose)
    folder, bobs = speaking_loop(studio, pose)
    take = import_clip_take(studio.root, clip_id, folder, fps=30)
    decide(studio.root, "clip", clip_id, take["id"], "accept")
    set_clip(studio.root, clip_id, mouth="neutral")
    return bobs


def test_base_approval_defines_a_neutral_mouth_set_and_loops_default_to_the_shared_closed_mouth(studio):
    shape = load_character(studio.root)["mouthSets"]["neutral"]
    anchors = load_character(studio.root)["anchors"]
    assert shape["cy"] == round(anchors["headTopY"] + 0.29 * CANVAS[1] - CANVAS[1] / 2, 2)
    talking_clip(studio)
    assert load_owner(studio.root, "clip", "smile_talk")["mouth"] == {"set": "neutral", "closedSource": {"kind": "shared"}}
    with pytest.raises(ValueError, match="speaking loops"):
        add_clip(studio.root, "smile_in", "idle", "smile")
        set_clip(studio.root, "smile_in", mouth="neutral")


def test_render_tracks_the_mask_and_ranks_closed_frames(studio):
    bobs = talking_clip(studio)
    render = render_clip(studio.root, "smile_talk", log=lambda *_: None)
    mouth = render["mouth"]
    mx, my = mouth_centre(studio)
    assert mouth["qa"]["roiMethod"] == "motion"
    assert abs(mouth["roi"]["cx"] + CANVAS[0] / 2 - mx) <= 2 and abs(mouth["roi"]["cy"] + CANVAS[1] / 2 - my) <= 2
    track = mouth["anchorTrack"]
    assert len(track) == len(mouth["openness"]) == render["frameCount"]
    moves = [round(entry["cy"] - track[0]["cy"]) for entry in track]
    assert max(abs(a - b) for a, b in zip(moves, bobs)) <= 1
    closed = [i for i in range(len(bobs)) if OPENING[i % len(OPENING)] == 0]
    widest = [i for i in range(len(bobs)) if OPENING[i % len(OPENING)] == max(OPENING)]
    assert max(mouth["openness"][i] for i in closed) < min(mouth["openness"][i] for i in widest)
    assert mouth["closedFrame"] in closed
    idle = load_owner(studio.root, "pose", "idle")["acceptedTake"]
    assert mouth["closedSource"] == {"kind": "shared", "pose": "idle", "still": idle}
    assert render["stills"]["mouth"] == idle and not [c for c in render["qa"]["checks"] if c["check"].startswith("mouth")]


def test_closed_mouth_choices_make_renders_stale(studio):
    talking_clip(studio)
    render_clip(studio.root, "smile_talk", log=lambda *_: None)
    clip = load_owner(studio.root, "clip", "smile_talk")
    set_closed_mouth(studio.root, "smile", pose_id="smile")
    assert render_freshness(studio.root, clip) == ("stale", ["the smile still changed"])
    set_closed_mouth(studio.root, None, pose_id="smile")
    assert render_freshness(studio.root, clip)[0] == "current"
    set_clip(studio.root, "smile_talk", mouth_source="frame:0")
    render = render_clip(studio.root, "smile_talk", log=lambda *_: None)
    assert render["mouth"]["closedSource"] == {"kind": "frame", "index": 0} and "mouth" not in render["stills"]
    set_mouth_set(studio.root, "wide", cx=0, cy=0, width=30, height=10, curve=0.3)
    with pytest.raises(ValueError, match="Unknown mouth set"):
        set_clip(studio.root, "smile_talk", mouth="missing")


def test_export_writes_runtime_profiles_and_closed_mouth_overlays(studio, monkeypatch):
    talking_clip(studio)
    render = render_clip(studio.root, "smile_talk", log=lambda *_: None)
    atomic_json(studio.root / "graph_config.json", {"nodes": [
        {"id": "talk", "label": "smile_speaking", "root": "production/clips/smile_talk/output", "phase": "loop",
         "frameIntervalMs": render["frameIntervalMs"], "loopMode": "loop", "isRoot": True}],
        "edges": [{"id": "self", "from": "talk", "to": "talk", "prob": 1}]})
    calls = fake_encoder(monkeypatch)
    export_pack(studio.root, studio.tmp / "pack", pack_id="demo", display_name="Demo", version="1")
    pack = load_character_pack(studio.tmp / "pack")
    profile = pack.mouth_config["profiles"]["smile_speaking"]
    assert set(profile) == {"mouth_set", "cx", "cy", "width", "height", "closed_frame_idx", "openness",
                            "anchor_track", "runtime_overlay_anchor"}
    assert len(profile["anchor_track"]) == render["frameCount"] and profile["mouth_set"] == "neutral"
    assert pack.mouth_config["expressions"] == {"neutral": load_character(studio.root)["mouthSets"]["neutral"]}
    assert (pack.mouth_config["version"], pack.mouth_config["canvas_size"]) == (2, list(CANVAS))
    assert len(pack.mouth_overlay_paths["smile_speaking"]) == 1
    idle = load_owner(studio.root, "pose", "idle")["acceptedTake"]
    assert Path(calls[-1][-1]) == studio.root / "production/poses/idle/takes" / idle / "still.png"
    export_pack(studio.root, studio.tmp / "bodies", pack_id="demo", display_name="Demo", version="1", no_mouth=True)
    assert load_character_pack(studio.tmp / "bodies").mouth_config == {"expressions": {}, "profiles": {}}


def fake_encoder(monkeypatch):
    calls = []
    monkeypatch.setattr("spriteforge.exporter.shutil.which", lambda value: "test-encoder")

    def run(args, **kwargs):
        calls.append(args)
        Path(args[-2]).write_bytes(b"\xabKTX 20\xbb\r\n\x1a\n" + b"fixture")
        return SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr("spriteforge.exporter.subprocess.run", run)
    return calls
