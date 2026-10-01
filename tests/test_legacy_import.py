from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from legacy_fixture import W, build_legacy, pose, windy  # noqa: E402

from spriteforge.character_pack import load_character_pack  # noqa: E402
from spriteforge.exporter import export_pack  # noqa: E402
from spriteforge.production.geometry import measure  # noqa: E402
from spriteforge.production.legacy import apply_import, pad_top, plan_import  # noqa: E402
from spriteforge.production.media import read_bgra, sorted_pngs  # noqa: E402
from spriteforge.production.records import (list_owners, list_takes, load_character, load_owner, output_root,  # noqa: E402
                                            read_render)
from spriteforge.workspace import atomic_json, read_json  # noqa: E402


def quiet(*_):
    pass


@pytest.fixture
def legacy(tmp_path):
    return build_legacy(tmp_path)


def empty_workspace(path: Path) -> Path:
    (path / "projects").mkdir(parents=True)
    atomic_json(path / "graph_config.json", {"nodes": [], "edges": []})
    return path


def fake_encoder(monkeypatch):
    calls = []
    monkeypatch.setattr("spriteforge.exporter.shutil.which", lambda value: "test-encoder")

    def run(args, **kwargs):
        calls.append(args)
        Path(args[-2]).write_bytes(b"\xabKTX 20\xbb\r\n\x1a\n" + b"fixture")
        return SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr("spriteforge.exporter.subprocess.run", run)
    return calls


def test_plan_groups_meeting_endpoints_into_poses_and_finds_the_shipped_variants(legacy):
    plan = plan_import(legacy.root, legacy.pack)
    assert plan["character"] == {"id": "demo", "displayName": "Demo", "canvas": [240, 320], "basePose": "idle"}
    assert list(plan["poses"]) == ["idle", "smile", "lean"]
    assert plan["poses"]["lean"]["anchors"]["headTopY"] == plan["poses"]["idle"]["anchors"]["headTopY"] + 5
    clips = plan["clips"]
    assert clips["idle"]["source"] == "projects/p_idle/frames_alpha_2x_gmfss/idle/loop"
    assert (clips["idle_wide"]["marginPx"], clips["idle_short"]["padTop"]) == (10, 2)
    assert [(clips[c]["from"], clips[c]["to"]) for c in ("smile_trans", "smile_talk", "lean_trans", "lean_talk", "smile")] \
        == [("idle", "smile"), ("smile", "smile"), ("idle", "lean"), ("lean", "lean"), ("smile", "smile")]
    assert (clips["smile_trans"]["frameIntervalMs"], clips["smile_trans"]["loopMode"]) == (8, "once_then_hold")
    assert clips["smile_talk"]["mouth"] == {"set": "smile", "closedSource": "shared"}
    assert clips["lean_talk"]["mouth"] == {"set": "neutral", "closedSource": "frame:6"}
    assert plan["runtimeClips"] == ["smile"] and [n["label"] for n in plan["graph"]["nodes"]][0] == "idle"
    assert len(plan["notes"]) == 1 and plan["notes"][0].startswith("edge lean_talk -> idle: the head top moves -5px")


def test_apply_keeps_the_shipped_frames_and_can_run_again(legacy, tmp_path, monkeypatch):
    plan = plan_import(legacy.root, legacy.pack)
    workspace = empty_workspace(tmp_path / "imported")
    report = apply_import(workspace, plan, log=quiet)
    character = load_character(workspace)
    base = measure(pose())
    assert (character["anchors"]["headTopY"], character["runtimeClips"]) == (base["headTopY"], ["smile"])
    assert load_owner(workspace, "pose", "lean")["expected"] == {"headTopY": base["headTopY"] + 5,
                                                                 "headCenterX": base["headCenterX"]}
    assert set(character["mouthSets"]) == {"neutral", "smile"} and character["mouthSets"]["smile"]["curve"] == 0.4

    def output(clip_id):
        return [read_bgra(p)[0] for p in sorted_pngs(workspace / output_root(clip_id) / "loop")]
    assert np.array_equal(output("idle_short")[0], pad_top(pose()[2:], 2))
    assert all(np.array_equal(frame, windy(10, i)) for i, frame in enumerate(output("idle_wide")))
    transition = read_render(workspace, "smile_trans")
    assert (transition["frameIntervalMs"], transition["loopMode"], transition["registration"]) == (8, "once_then_hold", None)
    assert read_render(workspace, "smile_talk")["mouth"]["closedSource"]["kind"] == "shared"
    assert read_render(workspace, "lean_talk")["mouth"]["closedSource"] == {"kind": "frame", "index": 6}

    graph = read_json(workspace / "graph_config.json")
    assert [(n["label"], n["root"], n["frameIntervalMs"]) for n in graph["nodes"][:2]] == [
        ("idle", output_root("idle"), 21), ("idle_wide", output_root("idle_wide"), 21)]
    labels = {node["node"]: node["label"] for node in report["nodes"]}
    levels = {(labels[e["from"]], labels[e["to"]]): e["level"] for e in report["edges"]}
    assert levels.pop(("lean_talk", "idle")) == "fail" and set(levels.values()) <= {"pass", "watch"}, report
    assert not [node for node in report["nodes"] if node["issues"]], report["nodes"]

    takes = {c["id"]: len(list_takes(workspace, "clip", c["id"])) for c in list_owners(workspace, "clip")}
    apply_import(workspace, plan, log=quiet)
    assert {c["id"]: len(list_takes(workspace, "clip", c["id"])) for c in list_owners(workspace, "clip")} == takes

    fake_encoder(monkeypatch)
    with pytest.raises(ValueError, match="Production QA blocks export"):
        export_pack(workspace, tmp_path / "exported", pack_id="demo", display_name="Demo", version="1")
    graph["edges"] = [edge for edge in graph["edges"] if labels.get(edge["from"]) != "lean_talk" or edge["to"] != "n_idle"]
    atomic_json(workspace / "graph_config.json", graph)
    export_pack(workspace, tmp_path / "exported", pack_id="demo", display_name="Demo", version="1")
    pack = load_character_pack(tmp_path / "exported")
    shipped = read_json(legacy.pack / "runtime_manifest.json")["clips"]
    assert {label: (c["frameIntervalMs"], c["loopMode"], len(c["frames"])) for label, c in pack.manifest["clips"].items()} \
        == {label: (c["frameIntervalMs"], c["loopMode"], len(c["frames"])) for label, c in shipped.items()}
    assert set(pack.mouth_config["profiles"]) == {"smile_talk", "lean_talk"}
    assert pack.mouth_config["profiles"]["lean_talk"]["closed_frame_idx"] in (0, 6)  # a closed frame, by openness


def test_apply_refuses_unresolved_sources_and_used_workspaces(legacy, tmp_path):
    plan = plan_import(legacy.root, legacy.pack)
    unresolved = {**plan, "clips": {**plan["clips"], "idle": {**plan["clips"]["idle"], "source": None}}}
    with pytest.raises(ValueError, match="Resolve the source of idle"):
        apply_import(empty_workspace(tmp_path / "a"), unresolved, log=quiet)
    used = empty_workspace(tmp_path / "b")
    atomic_json(used / "graph_config.json", {"nodes": [{"id": "x", "label": "x", "root": "projects/x"}], "edges": []})
    with pytest.raises(ValueError, match="new workspace"):
        apply_import(used, plan, log=quiet)
    assert W == 240
