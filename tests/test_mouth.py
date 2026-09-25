from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from synthetic import CANVAS, OPENING, mouth_centre, talking_clip  # noqa: E402

from spriteforge.character_pack import load_character_pack  # noqa: E402
from spriteforge.exporter import export_pack  # noqa: E402
from spriteforge.production.project import add_clip, set_clip, set_closed_mouth, set_mouth_set  # noqa: E402
from spriteforge.production.records import load_character, load_owner, render_freshness, still_path  # noqa: E402
from spriteforge.production.render import render_clip  # noqa: E402
from spriteforge.workspace import atomic_json  # noqa: E402

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
    assert (studio.root / "production/clips/smile_talk/output" / mouth["overlay"]).is_file() and len(mouth["toneShift"]) == 3


def test_closed_mouth_tone_follows_the_loop(studio):
    """A shared closed mouth from a paler still is shifted to the loop's skin inside the mask only."""
    talking_clip(studio)
    idle_file = still_path(studio.root, "idle")[0]
    pale = cv2.imread(str(idle_file), cv2.IMREAD_UNCHANGED)
    pale[:, :, :3] = np.clip(pale[:, :, :3].astype(int) + 25, 0, 255).astype(np.uint8)
    cv2.imwrite(str(idle_file), pale)  # simulate a closed-mouth still graded brighter than the loop
    render = render_clip(studio.root, "smile_talk", log=lambda *_: None)
    overlay = cv2.imread(str(studio.root / "production/clips/smile_talk/output" / render["mouth"]["overlay"]), cv2.IMREAD_UNCHANGED)
    anchor, (height, width) = render["mouth"]["sourceAnchor"], pale.shape[:2]
    cx, cy = round(anchor["cx"] + width / 2), round(anchor["cy"] + height / 2)
    assert render["mouth"]["toneShift"][0] < -5
    assert overlay[cy + 3, cx + 12, :3].astype(int).sum() < pale[cy + 3, cx + 12, :3].astype(int).sum() - 30
    assert (overlay[5:15, 5:15] == pale[5:15, 5:15]).all()


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
    assert Path(calls[-1][-1]) == studio.root / "production/clips/smile_talk/output/.mouth/closed.png"
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
