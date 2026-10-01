"""Saved record facts, shared CLI contracts and local job scheduling boundaries."""
import argparse
import json
import threading

import pytest

from synthetic import clip_with_take
from spriteforge.production import cli
from spriteforge.production.api import ProductionApi
from spriteforge.production.project import add_clip, overview, set_clip
from spriteforge.production.records import output_root, read_render
from spriteforge.production.render import render_clip
from spriteforge.workspace import atomic_json


def test_stats_share_saved_graph_facts_and_count_legacy_png_duration(studio):
    clip_with_take(studio, "loop", "idle", "idle", 6)
    render_clip(studio.root, "loop", log=lambda *_: None)
    legacy = studio.root / "legacy/flat"
    legacy.mkdir(parents=True)
    # Duration only needs the existing PNG inventory, not decoded image metrics.
    for index in range(4):
        (legacy / f"frame-{index}.png").write_bytes(b"not decoded for timing")
    rendered = read_render(studio.root, "loop")
    graph = {"nodes": [{"id": "root", "label": "loop", "isRoot": True, "root": output_root("loop"),
                        **{key: rendered[key] for key in ("phase", "frameIntervalMs", "loopMode")}},
                       {"id": "old", "label": "old loop", "root": "legacy/flat", "phase": "flat", "frameIntervalMs": 100},
                       {"id": "unknown", "label": "Unavailable", "root": "missing", "phase": "flat", "loopMode": "once_then_hold"}],
             "edges": [{"id": "stay", "from": "root", "to": "root", "prob": 1},
                       {"id": "intent", "from": "root", "to": "old", "prob": 0}]}
    atomic_json(studio.root / "graph_config.json", graph)
    before = (studio.root / "graph_config.json").read_bytes()
    api = ProductionApi(studio.root)
    stats = api.behavior_stats("10", "4294967295")
    assert stats == api.behavior_stats("10", "4294967295")
    assert stats["available"] and stats["root"] == "root" and stats["simulation"]["seconds"] == 600
    nodes = {node["id"]: node for group in stats["groups"] for node in group["nodes"]}
    assert nodes["root"]["durationS"] == 6 * 33 / 1000 and nodes["root"]["durationKnown"]
    assert nodes["old"]["durationS"] == .4 and nodes["old"]["durationKnown"]
    assert nodes["unknown"]["durationS"] == 2.5 and not nodes["unknown"]["durationKnown"]
    assert stats["ship"]["unreachable"][0]["label"] == "Unavailable"
    assert stats["ship"]["intentOnly"][0]["id"] == "old"
    assert stats["ship"]["deadEnds"][0]["id"] == "unknown"
    assert sum(group["seconds"] for group in stats["groups"]) == 600
    assert next(row for row in stats["coverage"] if row["pose"] == "idle")["loop"]["available"] == 1
    set_clip(studio.root, "loop", speed=2)
    changed = api.behavior_stats()
    assert changed["ship"]["outOfDate"][0]["id"] == "root"
    assert changed["ship"]["blocking"] == [issue for issue in overview(studio.root)["issues"] if issue["blocksExport"]]
    assert (studio.root / "graph_config.json").read_bytes() == before


@pytest.mark.parametrize("minutes,seed", [(True, 1), (5, 1), (10, True), (10, -1), (10, 2**32), (10, "unknown"), ("nan", 1)])
def test_api_behavior_settings_reject_invalid_values(studio, minutes, seed):
    with pytest.raises(ValueError):
        ProductionApi(studio.root).behavior_stats(minutes, seed)


def test_trigger_uses_mouth_bound_nodes_and_returns_exact_label_failures(studio):
    add_clip(studio.root, "talk", "smile", "smile")
    set_clip(studio.root, "talk", mouth="neutral")
    graph = {"nodes": [{"id": "idle", "label": "idle", "isRoot": True, "root": "unavailable", "phase": "flat"},
                       {"id": "speech", "label": "talk", "root": output_root("talk"), "phase": "loop", "frameIntervalMs": 33}],
             "edges": [{"id": "speech-entry", "from": "idle", "to": "speech", "prob": 0}]}
    atomic_json(studio.root / "graph_config.json", graph)
    api = ProductionApi(studio.root)
    result = api.post("behavior/trigger-test", {"events": [{"atS": 0, "speech": True}, {"atS": 20, "label": "nonexistent"}]})
    assert result["events"][0]["targets"] == ["speech"] and result["events"][0]["reached"]
    assert result["events"][1]["targets"] == [] and result["events"][1]["path"] == []
    assert not result["events"][1]["reachable"]
    assert result["route"][1]["node"] == "speech" and result["route"][1]["edge"] == "speech-entry"
    assert result["transitions"] == 1


def test_cli_stats_and_trigger_share_host_read_model(studio, tmp_path, capsys):
    parser = argparse.ArgumentParser()
    cli.add_parser(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(["production", "behavior", "stats", "--workspace", str(studio.root), "--minutes", "30", "--seed", "8"])
    cli.run(args)
    assert json.loads(capsys.readouterr().out) == ProductionApi(studio.root).behavior_stats(30, 8)
    events = tmp_path / "events.json"
    events.write_text("[]", encoding="utf-8")
    args = parser.parse_args(["production", "behavior", "trigger-test", "--workspace", str(studio.root), "--events", str(events)])
    cli.run(args)
    assert json.loads(capsys.readouterr().out) == ProductionApi(studio.root).behavior_trigger_test(events=[])


def test_render_export_interlock_allows_isolated_candidate_work(studio, monkeypatch):
    for name in ("published", "candidate", "generated"):
        add_clip(studio.root, name, "idle", "idle")
    pending = []

    class ControlledThread:
        def __init__(self, *, target, **_):
            self.target = target

        def start(self):
            pending.append(self.target)

    monkeypatch.setattr(threading, "Thread", ControlledThread)
    monkeypatch.setattr("spriteforge.production.render.render_clip", lambda *args, **kw: {"qa": {"status": "pass"}})
    monkeypatch.setattr("spriteforge.production.render.render_take", lambda *args, **kw: {"qa": {"status": "watch"}})
    monkeypatch.setattr("spriteforge.production.clips.generate_clip_take", lambda *args, **kw: {"id": "generated-take"})
    monkeypatch.setattr("spriteforge.production.exports.export_workspace", lambda *args, **kw: {"version": args[1]})
    adopted = []
    api = ProductionApi(studio.root)

    def adopt(*args):
        assert not api.lock.acquire(blocking=False), "Promotion must own the scheduling lock through publication"
        adopted.append(args)
        return {"id": "accepted"}

    monkeypatch.setattr("spriteforge.production.render.adopt_processed_take", adopt)
    render = api.start("render", "clip", "published")
    with pytest.raises(ValueError, match="published render is running"):
        api.post("export", {"version": "release-one"})
    with pytest.raises(ValueError, match="job for clip published is already running"):
        api.post("adopt-processed", {"clip": "published", "take": "test"})
    assert len(pending) == 1
    pending.pop(0)()
    assert api.jobs[render["id"]]["status"] == "succeeded"
    export = api.post("export", {"version": "release-one"})["job"]
    with pytest.raises(ValueError, match="export is running"):
        api.start("render", "clip", "published")
    with pytest.raises(ValueError, match="export is running"):
        api.post("adopt-processed", {"clip": "published", "take": "test"})
    assert adopted == []
    candidate = api.post("jobs", {"action": "render-take", "clip": "candidate", "take": "test"})["job"]
    generated = api.post("jobs", {"action": "generate", "clip": "generated"})["job"]
    assert candidate["status"] == generated["status"] == "running"
    pending.pop(0)()  # export completes while isolated candidate/generation work remains active
    with pytest.raises(ValueError, match="job for clip candidate is already running"):
        api.post("adopt-processed", {"clip": "candidate", "take": "test"})
    for work in list(pending):
        work()
    assert api.jobs[export["id"]]["status"] == "succeeded" and api.jobs[export["id"]]["result"] == "release-one"
    assert api.post("adopt-processed", {"clip": "published", "take": "test"})["take"]["id"] == "accepted"


def test_cli_candidate_and_versioned_export_delegate_to_owning_functions(studio, monkeypatch, capsys):
    called = []
    monkeypatch.setattr("spriteforge.production.render.render_take", lambda *args: called.append(("process", args)) or {"qa": {"status": "watch"}})
    monkeypatch.setattr("spriteforge.production.render.adopt_processed_take", lambda *args: called.append(("adopt", args)) or {"id": "take"})
    monkeypatch.setattr("spriteforge.production.exports.export_workspace", lambda *args, **kw: called.append(("export", args, kw)) or {"version": args[1]})
    parser = argparse.ArgumentParser()
    cli.add_parser(parser.add_subparsers(dest="command", required=True))
    for action in ("process", "adopt-processed"):
        cli.run(parser.parse_args(["production", "take", action, "--workspace", str(studio.root), "--clip", "loop", "take"]))
    cli.run(parser.parse_args(["production", "export", "--workspace", str(studio.root), "--version", "one", "--notes", "Reviewed."]))
    assert called[0] == ("process", (studio.root, "loop", "take"))
    assert called[1] == ("adopt", (studio.root, "loop", "take"))
    assert called[2] == ("export", (studio.root, "one"), {"notes": "Reviewed."})
