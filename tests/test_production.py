import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from synthetic import CANVAS, clip_with_take, figure, frame_folder, provider_frames, save, still, write_video  # noqa: E402

from spriteforge.character_pack import load_character_pack  # noqa: E402
from spriteforge.exporter import export_pack  # noqa: E402
from spriteforge.production import prompts  # noqa: E402
from spriteforge.production.checks import clip_report  # noqa: E402
from spriteforge.production.clips import import_clip_take, prepare  # noqa: E402
from spriteforge.production.geometry import measure  # noqa: E402
from spriteforge.production.media import read_bgra, sorted_pngs  # noqa: E402
from spriteforge.production.project import add_clip, add_pose, graph_sync, overview, set_clip  # noqa: E402
from spriteforge.production.records import (decide, load_character, load_owner, load_take, read_render,  # noqa: E402
                                            render_freshness)
from spriteforge.production.render import render_clip  # noqa: E402
from spriteforge.production.stills import approve_still, import_still, set_expected  # noqa: E402
from spriteforge.workspace import atomic_json, discover, read_json  # noqa: E402


def accepted_still_take(studio, pose):
    return load_take(studio.root, "pose", pose, load_owner(studio.root, "pose", pose)["acceptedTake"])


def test_base_still_defines_the_canvas_contract(studio):
    character = load_character(studio.root)
    base = measure(still(studio, "idle"))
    assert base["size"] == list(CANVAS) and base["edges"] == ["bottom"]
    assert character["anchors"]["headTopY"] == base["headTopY"] and abs(base["headTopY"] - 0.02 * CANVAS[1]) <= 1
    source = measure(figure(400, 700))
    scale = accepted_still_take(studio, "idle")["normalization"]["matrix"][0][0]
    assert abs(scale * (source["bbox"][2] - source["bbox"][0] + 1) - 0.71 * CANVAS[0]) < 1
    smile = measure(still(studio, "smile"))
    assert abs(smile["headTopY"] - base["headTopY"]) <= 1 and abs(smile["headCenterX"] - base["headCenterX"]) <= 1


def test_still_geometry_gate_and_explicit_pose_offset(studio):
    add_pose(studio.root, "lean")
    source = save(studio.tmp / "lean.png", figure(400, 700))
    take = import_still(studio.root, "lean", source, place=(0.5, 20, 60))
    assert take["qa"]["status"] == "fail"
    with pytest.raises(ValueError, match="Still QA failed"):
        approve_still(studio.root, "lean", take["id"])
    assert load_owner(studio.root, "pose", "lean")["acceptedTake"] is None
    metrics = take["qa"]["metrics"]
    set_expected(studio.root, "lean", metrics["headTopY"], metrics["headCenterX"])
    approve_still(studio.root, "lean", take["id"])
    assert load_owner(studio.root, "pose", "lean")["acceptedTake"] == take["id"]


def test_rigid_edits_are_registered_and_pose_changes_keep_their_framing(studio):
    assert accepted_still_take(studio, "smile")["normalization"]["method"] == "registration"
    changed = still(studio, "idle").copy()
    changed[:, :, :3] = figure(*CANVAS, seed=99)[:, :, :3]  # same silhouette, different content: not a rigid copy
    add_pose(studio.root, "turn")
    take = import_still(studio.root, "turn", save(studio.tmp / "turn.png", changed))
    assert take["normalization"]["method"] == "fit" and take["normalization"]["matrix"] == [[1, 0, 0], [0, 1, 0]]
    assert take["qa"]["status"] == "watch" and [c["check"] for c in take["qa"]["checks"]] == ["framing"]
    approve_still(studio.root, "turn", take["id"])


def test_camera_drift_is_reported(studio):
    add_clip(studio.root, "drifting", "idle", "smile")
    folder = studio.tmp / "drift"
    for index, frame in enumerate(provider_frames(still(studio, "idle"), still(studio, "smile"), 20, drift=(18, 0))):
        save(folder / f"{index:04d}.png", frame)
    take = import_clip_take(studio.root, "drifting", folder, fps=30)
    decide(studio.root, "clip", "drifting", take["id"], "accept")
    render = render_clip(studio.root, "drifting", log=lambda *_: None)
    drift = next(c for c in render["qa"]["checks"] if c["check"] == "drift")
    assert drift["level"] == "fail" and abs(render["registration"]["drift"]["tx"] + 18 / 1.06) < 1


def test_take_decisions_keep_one_accepted_and_archive_rejections(studio):
    add_clip(studio.root, "smile_in", "idle", "smile")
    folder = frame_folder(studio, "frames", "idle", "smile", 6)
    first = import_clip_take(studio.root, "smile_in", folder, fps=30)
    second = import_clip_take(studio.root, "smile_in", folder, fps=30, note="second try")
    assert first["prompt"]["complete"] is False and "clip.smile_in" in first["prompt"]["blocks"]
    assert first["inputs"]["assumed"] and (first["inputs"]["first"]["pose"], first["inputs"]["last"]["pose"]) == ("idle", "smile")
    decide(studio.root, "clip", "smile_in", first["id"], "accept")
    decide(studio.root, "clip", "smile_in", second["id"], "accept")
    statuses = {t["id"]: t["status"] for t in overview(studio.root)["clips"][0]["takes"]}
    assert statuses == {first["id"]: "candidate", second["id"]: "accepted"}
    decide(studio.root, "clip", "smile_in", second["id"], "reject", "hair jitters")
    assert load_owner(studio.root, "clip", "smile_in")["acceptedTake"] is None
    archived = load_take(studio.root, "clip", "smile_in", second["id"])
    assert archived["rejected"]["reason"] == "hair jitters" and (studio.root / "production/clips/smile_in/takes" / second["id"]).is_dir()
    decide(studio.root, "clip", "smile_in", second["id"], "accept")
    assert [h["action"] for h in load_take(studio.root, "clip", "smile_in", second["id"])["history"]] == \
        ["accepted", "rejected", "restored", "accepted"]


def test_prompt_versions_placeholders_and_snapshots(studio):
    library = prompts.load_library(studio.root)
    rendered = prompts.render(library, "transition", "character", {"character": "Demo", "from": "idle", "to": "smile", "duration": 2})
    assert not rendered["complete"] and rendered["blocks"]["character"] == 1
    with pytest.raises(ValueError, match="placeholder"):
        prompts.require_complete(rendered)
    assert prompts.set_block(library, "character", "Demo, ${character}") == 2
    assert prompts.set_block(library, "character", "Demo, ${character}") == 2
    assert prompts.set_block(library, "video.negative", "") == 2
    for block in ("video.invariants", "video.transition"):
        prompts.set_block(library, block, f"{block} for ${{from}} -> ${{to}}")
    prompts.set_block(library, "custom", "subject text")
    rendered = prompts.render(library, "transition", "custom", {"character": "Demo", "from": "idle", "to": "smile", "duration": 2})
    assert rendered["complete"] and rendered["negative"] == ""
    assert rendered["text"].startswith("Demo, Demo\n\nvideo.invariants for idle -> smile")
    assert [v["version"] for v in library["blocks"]["character"]["versions"]] == [1, 2]
    with pytest.raises(ValueError, match="Unknown prompt variable"):
        prompts.set_block(library, "custom", "uses ${unknown}")
    prompts.set_block(library, "custom", "a pose block using ${from}")
    with pytest.raises(ValueError, match="unknown variable"):
        prompts.render(library, "still", "custom", {"character": "Demo", "pose": "p", "description": ""})
    library["templates"]["broken"] = {"blocks": ["missing"], "negative": []}
    with pytest.raises(ValueError, match="unknown block"):
        prompts.validate_library(library)


def test_prepare_writes_exact_provider_inputs(studio):
    add_clip(studio.root, "smile_in", "idle", "smile")
    set_clip(studio.root, "smile_in", input_scale=0.9)
    files = {p.name for p in prepare(studio.root, "clip", "smile_in", studio.tmp / "handoff")}
    assert files == {"first.png", "last.png", "prompt.txt", "negative.txt", "prompt.json"}
    first = cv2.imread(str(studio.tmp / "handoff/first.png"), cv2.IMREAD_UNCHANGED)
    assert first.shape == (CANVAS[1], CANVAS[0], 3)
    assert (first[0, 0] == 255).all() and "PLACEHOLDER" in (studio.tmp / "handoff/prompt.txt").read_text()
    with pytest.raises(ValueError, match="new or empty"):
        prepare(studio.root, "clip", "smile_in", studio.tmp / "handoff")


def test_render_registers_locks_and_times_a_transition(studio):
    clip_with_take(studio, "smile_in", "idle", "smile", 12, interpolate=2, speed=2.0)
    render = render_clip(studio.root, "smile_in", log=lambda *_: None)
    frames = sorted_pngs(studio.root / "production/clips/smile_in/output/in")
    assert len(frames) == render["frameCount"] == 23
    assert (render["frameIntervalMs"], render["loopMode"], render["phase"]) == (8, "once_then_hold", "in")
    head, tail = read_bgra(frames[0])[0], read_bgra(frames[-1])[0]
    assert np.array_equal(head[:, :, 3], still(studio, "idle")[:, :, 3])
    assert np.array_equal(tail[:, :, 3], still(studio, "smile")[:, :, 3])
    middle = measure(read_bgra(frames[11])[0])
    base = load_character(studio.root)["anchors"]
    assert abs(middle["headTopY"] - base["headTopY"]) <= 1 and abs(middle["headCenterX"] - base["headCenterX"]) <= 1
    assert abs(render["registration"]["head"]["scale"] - 1 / 1.06) < 0.01
    assert render["qa"]["status"] in {"pass", "watch"}, render["qa"]["checks"]
    assert render_freshness(studio.root, load_owner(studio.root, "clip", "smile_in"))[0] == "current"
    assert not list((studio.root / "production/clips/smile_in").glob(".work-*"))


def test_loop_pingpong_wrap_and_staleness(studio):
    take = clip_with_take(studio, "smile_loop", "smile", "smile", 10, pingpong=True)
    render = render_clip(studio.root, "smile_loop", log=lambda *_: None)
    assert render["frameCount"] == 18 and render["frameIntervalMs"] == 33 and render["loopMode"] == "loop"
    assert render["qa"]["wrap"]["level"] == "pass"
    other = import_clip_take(studio.root, "smile_loop", studio.tmp / "smile_loop", fps=24)
    decide(studio.root, "clip", "smile_loop", other["id"], "accept")
    state, reasons = render_freshness(studio.root, load_owner(studio.root, "clip", "smile_loop"))
    assert state == "stale" and reasons == ["the accepted take changed"]
    assert read_render(studio.root, "smile_loop")["take"] == take["id"]


def test_graph_sync_and_export_only_accept_current_reviewed_renders(studio, monkeypatch):
    clip_with_take(studio, "idle_loop", "idle", "idle", 8)
    clip_with_take(studio, "smile_in", "idle", "smile", 20)
    clip_with_take(studio, "smile_loop", "smile", "smile", 8)
    for clip_id in ("idle_loop", "smile_in", "smile_loop"):
        render_clip(studio.root, clip_id, log=lambda *_: None)
    result = graph_sync(studio.root, add_missing=True)
    assert result["added"] == ["idle_loop", "smile_in", "smile_loop"]
    graph = read_json(studio.root / "graph_config.json")
    assert [n["isRoot"] for n in graph["nodes"]] == [True, False, False]
    graph["edges"] = [{"id": "a", "from": "idle_loop", "to": "smile_in", "prob": 0},
                      {"id": "b", "from": "smile_in", "to": "smile_loop", "prob": 1},
                      {"id": "c", "from": "smile_loop", "to": "idle_loop", "prob": 1}]
    graph["nodes"][1]["frameIntervalMs"] = 99
    atomic_json(studio.root / "graph_config.json", graph)
    encoded = fake_encoder(monkeypatch)
    with pytest.raises(ValueError, match="run graph-sync"):
        export_pack(studio.root, studio.tmp / "pack", pack_id="demo", display_name="Demo", version="1")
    assert graph_sync(studio.root)["changes"] == ["smile_in.frameIntervalMs: 99 -> 33"]
    export_pack(studio.root, studio.tmp / "pack", pack_id="demo", display_name="Demo", version="1")
    pack = load_character_pack(studio.tmp / "pack")
    assert pack.manifest["clips"]["smile_in"]["loopMode"] == "once_then_hold" and len(encoded) == 36
    other = import_clip_take(studio.root, "smile_loop", studio.tmp / "smile_loop", fps=30)
    decide(studio.root, "clip", "smile_loop", other["id"], "accept")
    with pytest.raises(ValueError, match="accepted take changed"):
        export_pack(studio.root, studio.tmp / "pack2", pack_id="demo", display_name="Demo", version="1")
    assert not (studio.tmp / "pack2").exists()


def test_video_takes_decode_with_explicit_colour_conversion(studio):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is not installed")
    add_clip(studio.root, "smile_in", "idle", "smile")
    frames = provider_frames(still(studio, "idle"), still(studio, "smile"), 24)
    take = import_clip_take(studio.root, "smile_in", write_video(studio.tmp / "take.mp4", frames, 30))
    assert (take["media"]["count"], take["media"]["fps"]) == (24, 30.0)
    decide(studio.root, "clip", "smile_in", take["id"], "accept")
    render = render_clip(studio.root, "smile_in", log=lambda *_: None)
    assert render["frameCount"] == 24 and render["qa"]["status"] != "fail", render["qa"]["checks"]


def test_clip_qa_flags_broken_frames_and_closed_edges(studio, tmp_path):
    character = load_character(studio.root)
    good = still(studio, "idle")
    broken = good.copy()
    broken[: CANVAS[1] // 2, :, 3] = 0
    touching = good.copy()
    touching[40:60, 0, 3] = 255
    paths = [save(tmp_path / "qa" / f"{i}.png", image) for i, image in enumerate([good, broken, good, touching])]
    report = clip_report(character, paths, "transition", good, touching)
    levels = {c["check"]: c["level"] for c in report["checks"]}
    assert levels["broken"] == "fail" and levels["edges"] == "fail" and report["status"] == "fail"


def test_discovery_offers_outputs_not_take_media(studio):
    clip_with_take(studio, "idle_loop", "idle", "idle", 6)
    render_clip(studio.root, "idle_loop", log=lambda *_: None)
    roots = [s["root"] for p in discover(studio.root)[0]["projects"] for s in p["states"]]
    assert roots == ["production/clips/idle_loop/output/loop"]


def fake_encoder(monkeypatch):
    calls = []
    monkeypatch.setattr("spriteforge.exporter.shutil.which", lambda value: "test-encoder")

    def run(args, **kwargs):
        calls.append(args)
        Path(args[-2]).write_bytes(b"\xabKTX 20\xbb\r\n\x1a\n" + b"fixture")
        return SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr("spriteforge.exporter.subprocess.run", run)
    return calls
