import json
from datetime import datetime, timezone

import pytest

from spriteforge.production.project import add_clip, export_gate, graph_sync, overview, set_clip
from spriteforge.production.records import load_character, output_root, read_render, save_character
from spriteforge.production.studio import issue_summary, usage_summary, variant_groups
from spriteforge.production.tools import load_tools, save_tools, set_ui_defaults
from spriteforge.workspace import atomic_json


def clip(clip_id, kind="loop", source="idle", target="idle", mouth=None, **values):
    return {"id": clip_id, "kind": kind, "from": source, "to": target, "mouth": mouth, **values}


def test_adding_a_take_in_the_same_second_does_not_renumber_versions(studio, monkeypatch):
    from spriteforge.production import records

    class Clock(datetime):
        current = datetime(2040, 1, 1, 1, 1, 1, 100, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.current

    ids = iter(("20400101-010101-ffff", "20400101-010101-0000"))
    monkeypatch.setattr(records, "datetime", Clock)
    monkeypatch.setattr(records, "new_take_id", lambda: next(ids))
    add_clip(studio.root, "loop", "idle", "idle")
    first, _ = records.new_take(studio.root, "clip", "loop", {"provider": "manual"})
    records.save_take(studio.root, first)
    assert overview(studio.root)["clips"][0]["takes"][0]["version"] == 1
    Clock.current = datetime(2040, 1, 1, 1, 1, 1, 200, tzinfo=timezone.utc)
    second, _ = records.new_take(studio.root, "clip", "loop", {"provider": "manual"})
    records.save_take(studio.root, second)
    assert [(take["id"], take["version"]) for take in overview(studio.root)["clips"][0]["takes"]] == [
        (first["id"], 1), (second["id"], 2)]


def test_variants_group_by_endpoints_and_speaking_role():
    records = [clip("idle2"), clip("speaking", mouth={"set": "neutral"}), clip("idle1"),
               clip("smile_in", "transition", "idle", "smile"), clip("smile_out", "transition", "smile", "idle")]
    groups = variant_groups(records)
    assert groups == variant_groups(list(reversed(records)))
    assert {(group["type"], group["from"], group["to"]): group["clips"] for group in groups} == {
        ("loop", "idle", "idle"): ["idle1", "idle2"], ("speaking", "idle", "idle"): ["speaking"],
        ("transition", "idle", "smile"): ["smile_in"], ("transition", "smile", "idle"): ["smile_out"]}


def test_usage_uses_only_recorded_recent_balances_images_and_render_durations():
    at = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)

    def take(take_id, stamp, provider, **source):
        return {"id": take_id, "createdAt": stamp, "source": {"provider": provider, **source}}

    poses = [{"takes": [
        {**take("image", "2026-10-01T12:00:00Z", "gpt-image"), "media": {"source": "source.png"}},
        take("failed-before-image", "2026-10-01T12:00:00Z", "gpt-image"),
        {**take("old-image", "2026-09-24T12:00:00Z", "gpt-image"), "media": {"source": "source.png"}}]}]
    clips = [{"takes": [
        take("old", "2026-09-24T12:00:00Z", "wan-cli", balanceBefore={"credits": 110}, balanceAfter={"credits": 100}),
        take("boundary", "2026-09-25T12:00:00Z", "wan-cli", balanceBefore={"credits": 100}, balanceAfter={"credits": 91}),
        take("recent", "2026-10-01T12:00:00Z", "wan-cli", balanceBefore={"credits": 91}, balanceAfter={"credits": 80}),
        take("future", "2026-10-03T12:00:00Z", "wan-cli", balanceBefore={"credits": 80}, balanceAfter={"credits": 70})],
        "render": {"renderedAt": "2026-10-01T12:00:00Z", "durationS": 2.25}},
        {"render": {"renderedAt": "2026-09-25T12:00:00Z", "durationS": 4}},
        {"render": {"renderedAt": "2026-09-24T12:00:00Z", "durationS": 100}}]
    usage = usage_summary(poses, clips, at=at)
    assert usage["wan"] == {"usedCredits": 20, "balance": 80}
    assert usage["gptImage"] == {"images": 1}
    assert usage["local"] == {"durationS": 6.25, "renders": 2, "unknownDurations": 0}
    assert usage["days"] == 7 and usage["since"] == "2026-09-25T12:00:00+00:00"


def test_incomplete_usage_records_are_unknown_rather_than_estimated():
    at = datetime(2026, 10, 2, tzinfo=timezone.utc)
    clips = [{"takes": [{"id": "pending", "createdAt": "2026-10-01T00:00:00Z",
                          "source": {"provider": "wan-cli", "balanceBefore": {"credits": 42}}}],
              "render": {"renderedAt": "2026-10-01T00:00:00Z"}},
             {"render": {"renderedAt": "2026-10-01T00:00:00Z", "durationS": 3.5}}]
    usage = usage_summary([], clips, at=at)
    assert usage["wan"] == {"usedCredits": None, "balance": 42}
    assert usage["local"] == {"durationS": None, "renders": 2, "unknownDurations": 1}
    empty = usage_summary([], [], at=at)
    assert empty["wan"] == {"usedCredits": None, "balance": None}
    assert empty["local"] == {"durationS": None, "renders": 0, "unknownDurations": 0}


def test_issue_summary_preserves_qa_levels_metrics_and_export_scope():
    clips = [clip("bound", render={"state": "stale", "reasons": ["the accepted take changed"], "phase": "loop",
                                  "frameIntervalMs": 33, "loopMode": "loop",
                                  "qa": {"checks": [{"check": "wrap", "level": "fix", "message": "Visible seam", "faceL": 2},
                                                    {"check": "flash", "level": "watch", "message": "Flash", "frames": [3]}]}}),
             clip("unbound", render={"state": "current", "qa": {"checks": [
                 {"check": "broken", "level": "fail", "message": "Broken frame"}]}})]
    graph = {"nodes": [{"id": "n1", "root": output_root("bound"), "phase": "loop", "frameIntervalMs": 20,
                         "loopMode": "loop"}, {"id": "n2", "root": output_root("bound")} ]}
    report = {"nodes": [{"node": "n1", "clip": "bound", "issues": ["Out of date", "Timing mismatch"]}],
              "edges": [{"from": "n1", "to": "n2", "level": "fail", "faceL": 3.1, "dHeadTop": 4, "dHeadCenter": 0}]}
    known = {"clip:bound:flash": {"at": "2026-10-02", "note": "Reviewed"}, "edge:n1->n2": {"note": "Cannot hide failure"}}
    issues = issue_summary([{"id": "smile", "needsRecheck": True}], clips, graph, report, known)
    by_key = {issue["key"]: issue for issue in issues}
    assert by_key["node:n1:stale"]["blocksExport"] is True
    assert by_key["node:n1:frameIntervalMs"]["expected"] == 33
    assert by_key["edge:n1->n2"]["faceL"] == 3.1 and by_key["edge:n1->n2"]["known"] is None
    assert by_key["edge:n1->n2"]["clips"] == ["bound"]
    assert by_key["clip:bound:wrap"]["level"] == "fix" and by_key["clip:bound:wrap"]["blocksExport"] is False
    assert by_key["clip:bound:flash"]["known"] == known["clip:bound:flash"]
    assert by_key["clip:unbound:broken"]["blocksExport"] is False
    assert by_key["pose:smile:recheck"]["level"] == "watch"
    assert [issue["level"] for issue in issues] == ["fail", "fail", "fail", "fail", "fix", "watch", "watch"]


def test_overview_uses_same_bound_failures_as_export_and_retains_legacy_fields(studio, monkeypatch):
    from synthetic import clip_with_take
    from spriteforge.production.render import render_clip

    clip_with_take(studio, "idle_loop", "idle", "idle", 8)
    clock = iter((10.0, 12.375))
    monkeypatch.setattr("spriteforge.production.render.monotonic", lambda: next(clock))
    render = render_clip(studio.root, "idle_loop", log=lambda *_: None)
    assert render["durationS"] == 2.375 and read_render(studio.root, "idle_loop")["durationS"] == 2.375
    graph_sync(studio.root, add_missing=True)
    set_clip(studio.root, "idle_loop", speed=2)
    result = overview(studio.root)
    assert result["concepts"] == []
    assert result["character"]["basePose"] == "idle" and "prompts" in result and "canvas" in result
    assert result["clips"][0]["render"]["durationS"] == 2.375
    assert result["clips"][0]["takes"][0]["version"] == 1
    stale = next(issue for issue in result["issues"] if issue["key"] == "node:idle_loop:stale")
    assert stale["level"] == "fail" and stale["blocksExport"] is True
    with pytest.raises(ValueError, match="Production QA blocks export"):
        export_gate(studio.root, json.loads((studio.root / "graph_config.json").read_text()))
    assert result["usage"]["local"]["durationS"] == 2.375


def test_overview_reports_a_missing_bound_owner_without_losing_existing_records(studio):
    atomic_json(studio.root / "graph_config.json", {"nodes": [{"id": "missing", "label": "Missing",
                                                              "root": output_root("deleted") }], "edges": []})
    result = overview(studio.root)
    assert len(result["poses"]) == 2
    assert result["issues"][0]["key"] == "node:missing:unknownClip"
    assert result["issues"][0]["blocksExport"] is True


def test_runtime_clips_have_export_blockers_even_without_graph_nodes(studio):
    add_clip(studio.root, "runtime", "idle", "idle")
    character = load_character(studio.root)
    character["runtimeClips"] = ["runtime"]
    save_character(studio.root, character)
    result = overview(studio.root)
    assert next(issue for issue in result["issues"] if issue["key"] == "node:runtime:runtime:missing")["blocksExport"] is True


def test_ui_defaults_preserve_tool_configuration_and_expose_only_safe_fields(studio):
    tools = load_tools(studio.root)
    tools.pop("defaults")  # old workspace needs no migration
    tools["providers"]["wan"]["private"] = "provider-secret"
    tools["defaults"] = {"private": "defaults-secret"}
    tools["amadeus"] = {"packDir": "configured-pack", "private": "path-secret"}
    save_tools(studio.root, tools)
    path = studio.root / "production" / "tools.json"
    before = path.read_bytes()
    assert set_ui_defaults(studio.root, {})["batchConfirmThreshold"] == 3
    assert path.read_bytes() == before
    defaults = set_ui_defaults(studio.root, {"stillProvider": "seedream", "batchConfirmThreshold": 5})
    assert defaults == {"conceptProvider": "qwen-image", "stillProvider": "seedream", "batchConfirmThreshold": 5}
    saved = load_tools(studio.root)
    assert saved["providers"]["wan"]["private"] == "provider-secret"
    assert saved["defaults"]["private"] == "defaults-secret"
    exposed = overview(studio.root)["tools"]
    assert exposed["defaults"] == defaults and exposed["amadeus"] == {"packDir": "configured-pack"}
    assert "secret" not in json.dumps(exposed)


@pytest.mark.parametrize("changes", [{"batchConfirmThreshold": True}, {"batchConfirmThreshold": 0},
                                    {"batchConfirmThreshold": 1.5}, {"stillProvider": "wan"},
                                    {"conceptProvider": "unknown"}, {"providers": {}}, {"apiKey": "secret"}, None])
def test_invalid_ui_settings_never_rewrite_configuration(studio, changes):
    path = studio.root / "production" / "tools.json"
    before = path.read_bytes()
    with pytest.raises(ValueError):
        set_ui_defaults(studio.root, changes)
    assert path.read_bytes() == before


def test_defaults_show_does_not_initialize_an_empty_workspace(tmp_path):
    assert set_ui_defaults(tmp_path, {})["batchConfirmThreshold"] == 3
    assert not (tmp_path / "production").exists()
    with pytest.raises(ValueError, match="no production character"):
        set_ui_defaults(tmp_path, {"batchConfirmThreshold": 4})
    assert not (tmp_path / "production").exists()
