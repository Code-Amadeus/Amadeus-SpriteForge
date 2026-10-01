"""Review projects existing QA and records watch annotations independently."""
import json
import subprocess
import sys

import pytest

from synthetic import clip_with_take
from spriteforge.production.api import ProductionApi
from spriteforge.production.checks import EDGE_L, grade, graph_report
from spriteforge.production.geometry import measure
from spriteforge.production.issues import issue_summary, load_review, seam_detail, set_known
from spriteforge.production.media import read_bgra
from spriteforge.production.project import export_gate, graph_sync, overview
from spriteforge.production.records import load_character, output_root, read_render
from spriteforge.production.render import render_clip
from spriteforge.workspace import atomic_json, read_json


def render_record(studio, clip_id, qa):
    path = studio.root / output_root(clip_id) / "render.json"
    record = read_render(studio.root, clip_id)
    record["qa"] = qa
    atomic_json(path, record)


def test_bound_opaque_qa_failure_is_one_canonical_export_blocker(studio):
    clip_with_take(studio, "bound", "idle", "idle", 6)
    render_clip(studio.root, "bound", log=lambda *_: None)
    graph_sync(studio.root, add_missing=True)
    render_record(studio, "bound", {"status": "fail", "checks": []})
    blockers = [issue for issue in overview(studio.root)["issues"] if issue["blocksExport"]]
    assert [issue["key"] for issue in blockers] == ["node:bound:qa"]
    with pytest.raises(ValueError, match="clip QA failed"):
        export_gate(studio.root, read_json(studio.root / "graph_config.json"))
    render_record(studio, "bound", {"status": "pass", "checks": []})
    clip_with_take(studio, "unbound", "idle", "idle", 6)
    render_clip(studio.root, "unbound", log=lambda *_: None)
    render_record(studio, "unbound", {"status": "fail", "checks": [
        {"check": "headTopY", "level": "fail", "message": "Recorded fail", "delta": 7}]})
    issues = overview(studio.root)["issues"]
    assert next(issue for issue in issues if issue["key"] == "clip:unbound:headTopY")["blocksExport"] is False
    assert not any(issue["blocksExport"] for issue in issues)
    assert export_gate(studio.root, read_json(studio.root / "graph_config.json"))["status"] == "pass"


def test_candidate_findings_do_not_block_published_graph_or_include_rejected_takes():
    check = {"check": "alignment", "level": "fail", "message": "Candidate failed", "frames": [1]}
    clips = [{"id": "loop", "acceptedTake": "adopted", "render": {"state": "current", "qa": {"checks": []}},
              "takes": [{"id": "adopted", "candidateRender": {"qa": {"status": "fail", "checks": [check]}}},
                        {"id": "rejected", "rejected": {"reason": "bad"}, "candidateRender": {"qa": {"status": "fail", "checks": [check]}}},
                        {"id": "previous", "needsReview": False, "candidateRender": {"qa": {"status": "fail", "checks": [check]}}},
                        {"id": "new", "needsReview": True, "candidateRender": {"qa": {"status": "fail", "checks": [check]}}},
                        {"id": "opaque", "needsReview": True, "candidateRender": {"qa": {"status": "fail", "checks": []}}}]}]
    issues = issue_summary([], clips, {"nodes": [], "edges": []}, {})
    assert [issue["key"] for issue in issues] == ["clip:loop:take:new:alignment", "clip:loop:take:opaque:status"]
    assert all(issue["candidate"] and not issue["blocksExport"] for issue in issues)
    assert issues[0]["frames"] == [1] and issues[0]["take"] == "new"


def test_known_annotations_require_current_watch_and_survive_reload(studio):
    clip_with_take(studio, "loop", "idle", "idle", 6)
    render_clip(studio.root, "loop", log=lambda *_: None)
    qa = {"status": "watch", "checks": [{"check": "flash", "level": "watch", "message": "Existing flash fact", "frames": [2]}]}
    render_record(studio, "loop", qa)
    key = "clip:loop:flash"
    api = ProductionApi(studio.root)
    assert api.post("review-known", {"key": key, "note": "  Reviewed at slow speed.  "})["known"]["note"] == "Reviewed at slow speed."
    path = studio.root / "production/review.json"
    before = path.read_bytes()
    assert load_review(studio.root)["known"][key] == overview(studio.root)["issues"][0]["known"]
    for body in ({"key": key, "note": ""}, {"key": "missing", "note": "known"}, {"key": key, "clear": 1}):
        with pytest.raises(ValueError):
            api.post("review-known", body)
        assert path.read_bytes() == before
    qa["status"] = qa["checks"][0]["level"] = "fail"
    render_record(studio, "loop", qa)
    assert overview(studio.root)["issues"][0]["known"] is None
    with pytest.raises(ValueError, match="Only a current watch"):
        set_known(studio.root, key, "Cannot hide failure")
    assert path.read_bytes() == before
    result = subprocess.run([sys.executable, "-m", "spriteforge", "production", "review-known", "--workspace",
                             str(studio.root), key, "--clear"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["known"] is None and load_review(studio.root)["known"] == {}


def test_seam_details_reuse_exact_published_endpoints_and_original_qa(studio):
    for name, pose in (("idle_loop", "idle"), ("smile_loop", "smile")):
        clip_with_take(studio, name, pose, pose, 6, margin=14)
        render_clip(studio.root, name, log=lambda *_: None)
    graph = {"nodes": [{"id": "idle", "label": "idle_loop", "root": output_root("idle_loop"), "isRoot": True},
                       {"id": "smile", "label": "smile_loop", "root": output_root("smile_loop")}],
             "edges": [{"id": "entry", "from": "idle", "to": "smile", "prob": 0}]}
    atomic_json(studio.root / "graph_config.json", graph)
    graph_sync(studio.root)
    graph = read_json(studio.root / "graph_config.json")
    character = load_character(studio.root)
    [edge] = graph_report(studio.root, graph, character)["edges"]
    detail = ProductionApi(studio.root).review_seam("edge:idle->smile")
    assert detail["level"] == edge["level"]
    assert {key: detail["metrics"][key] for key in ("faceL", "dHeadTop", "dHeadCenter")} == {
        key: edge[key] for key in ("faceL", "dHeadTop", "dHeadCenter")}
    assert detail["metrics"]["levels"]["faceL"] == (grade(abs(edge["faceL"]), EDGE_L) if edge["faceL"] is not None else "watch")
    for end, index in (("tail", -1), ("head", 0)):
        endpoint = detail[end]
        frames = sorted((studio.root / output_root(endpoint["clip"]) / "loop").glob("*.png"))
        assert studio.root / endpoint["path"] == frames[index]
        pixels = read_bgra(frames[index])[0]
        assert endpoint["size"] == {"w": pixels.shape[1], "h": pixels.shape[0]} and endpoint["marginPx"] == 14
        actual = measure(pixels[:, 14:-14])
        assert endpoint["actual"] == {key: actual[key] for key in ("headTopY", "headCenterX")}
        assert set(endpoint["expected"]) >= {"headTopY", "headCenterX"}
    with pytest.raises(ValueError, match="one current graph edge"):
        seam_detail(studio.root, "edge:not-current->smile")
