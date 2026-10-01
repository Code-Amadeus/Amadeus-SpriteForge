import json
import subprocess
import sys
import threading
from copy import deepcopy

import pytest

pytest.importorskip("cv2")

from synthetic import clip_with_take, frame_folder  # noqa: E402
from test_providers import providers, write_prompts  # noqa: E402, F401
from spriteforge.production import prompts  # noqa: E402
from spriteforge.production.api import ProductionApi  # noqa: E402
from spriteforge.production.clips import clip_cost_estimate, generate_clip_take, generation_snapshot, import_clip_take  # noqa: E402
from spriteforge.production.project import add_clip, add_variant, overview, set_clip  # noqa: E402
from spriteforge.production.records import (decide, list_takes, load_owner, load_take, render_freshness,  # noqa: E402
                                           save_take, set_take_note, take_dir)
from spriteforge.production.render import render_clip  # noqa: E402
from spriteforge.workspace import atomic_json  # noqa: E402


def test_variant_copies_current_settings_and_subject_without_takes_or_output(studio):
    source_take = clip_with_take(studio, "smile_loop1", "smile", "smile", 8,
                                 provider="wan-cli", duration=5, resolution="480P", margin=12, speed=2,
                                 mouth="neutral", mouth_source="still")
    source = load_owner(studio.root, "clip", "smile_loop1")
    library = prompts.load_library(studio.root)
    prompts.set_block(library, source["prompt"]["subject"], "Older motion")
    prompts.set_block(library, source["prompt"]["subject"], "Current motion ${character}")
    prompts.save_library(studio.root, library)
    original = (take_dir(studio.root, "clip", "smile_loop1", source_take["id"]) / "take.json").read_bytes()
    clone = ProductionApi(studio.root).post("variant", {"from": "smile_loop1", "id": "smile_loop2"})["clip"]
    for key in ("kind", "from", "to", "phase", "generation", "processing", "playback", "mouth"):
        assert clone[key] == source[key]
    assert clone["acceptedTake"] is None and list_takes(studio.root, "clip", "smile_loop2") == []
    assert not (studio.root / "production/clips/smile_loop2/output").exists()
    library = prompts.load_library(studio.root)
    assert clone["prompt"]["subject"] == "clip.smile_loop2"
    assert prompts.current(library, clone["prompt"]["subject"])["text"] == "Current motion ${character}"
    assert len(library["blocks"][clone["prompt"]["subject"]]["versions"]) == 1
    set_clip(studio.root, "smile_loop2", duration=7, mouth_source="frame:1")
    assert load_owner(studio.root, "clip", "smile_loop1") == source
    assert (take_dir(studio.root, "clip", "smile_loop1", source_take["id"]) / "take.json").read_bytes() == original


def test_invalid_variant_does_not_modify_prompt_library_or_existing_clip(studio):
    add_clip(studio.root, "original", "idle", "idle")
    library = (studio.root / "production/prompts.json").read_bytes()
    owner = (studio.root / "production/clips/original/clip.json").read_bytes()
    (studio.root / "production/clips/orphaned/takes").mkdir(parents=True)
    for source, target in (("original", "original"), ("missing", "new"), ("original", "../unsafe"), ("original", "orphaned")):
        with pytest.raises(ValueError):
            add_variant(studio.root, source, target)
    assert (studio.root / "production/prompts.json").read_bytes() == library
    assert (studio.root / "production/clips/original/clip.json").read_bytes() == owner


def test_based_on_generation_records_metadata_and_preserves_source_snapshots(studio, providers):
    original = import_clip_take(studio.root, "smile_in", frame_folder(studio, "original", "idle", "smile", 8),
                                fps=30, note="source note")
    source_dir = take_dir(studio.root, "clip", "smile_in", original["id"])
    source_files = {path.relative_to(source_dir): path.read_bytes() for path in source_dir.rglob("*") if path.is_file()}
    write_prompts(studio)
    set_clip(studio.root, "smile_in", provider="wan", duration=3, resolution="480P")
    generated = generate_clip_take(studio.root, "smile_in", based_on=original["id"], note="new version note", log=lambda *_: None)
    assert generated["basedOn"] == original["id"] and generated["note"] == "new version note"
    assert generated["owner"] == {"kind": "clip", "id": "smile_in"}
    assert generated["prompt"] != original["prompt"] and generated["state"] == "ready"
    assert sum(request[0] == "POST" for request in providers.requests) == 1
    assert {path.relative_to(source_dir): path.read_bytes() for path in source_dir.rglob("*") if path.is_file()} == source_files
    snapshot = next(take for take in overview(studio.root)["clips"][0]["takes"] if take["id"] == generated["id"])
    assert snapshot["generation"] == {"provider": "wan", "durationS": 3, "resolution": "480P", "seed": None}
    assert snapshot["basedOn"] == original["id"] and snapshot["note"] == "new version note"


def test_invalid_based_on_and_note_fail_before_any_provider_request_or_take(studio, providers):
    foreign = clip_with_take(studio, "other", "idle", "idle", 8)
    write_prompts(studio)
    set_clip(studio.root, "smile_in", provider="wan")
    api = ProductionApi(studio.root)
    for metadata in ({"based_on": foreign["id"]}, {"based_on": "invalid"}, {"note": ["not text"]}):
        with pytest.raises(ValueError):
            generate_clip_take(studio.root, "smile_in", **metadata)
    for metadata in ({"basedOn": foreign["id"]}, {"note": None}):
        with pytest.raises(ValueError):
            api.post("jobs", {"action": "generate", "clip": "smile_in", **metadata})
    assert providers.requests == [] and list_takes(studio.root, "clip", "smile_in") == [] and api.job_list() == []


def test_based_on_dry_run_does_not_mutate_library_or_record_a_take(studio, providers):
    original = import_clip_take(studio.root, "smile_in", frame_folder(studio, "dry-source", "idle", "smile", 8), fps=30)
    write_prompts(studio)
    library = (studio.root / "production/prompts.json").read_bytes()
    preview = generate_clip_take(studio.root, "smile_in", provider="wan", based_on=original["id"], note="preview",
                                 dry_run=True)
    assert preview["basedOn"] == original["id"] and preview["note"] == "preview"
    assert providers.requests == [] and len(list_takes(studio.root, "clip", "smile_in")) == 1
    assert (studio.root / "production/prompts.json").read_bytes() == library


def test_note_update_changes_only_annotation_and_survives_stale_producer_save(studio):
    original = clip_with_take(studio, "idle_loop", "idle", "idle", 8)
    stale = load_take(studio.root, "clip", "idle_loop", original["id"])
    updated = ProductionApi(studio.root).post("take-note", {"kind": "clip", "owner": "idle_loop", "take": original["id"],
                                                          "note": "reviewer annotation"})["take"]
    assert {key: value for key, value in updated.items() if key != "note"} == {
        key: value for key, value in stale.items() if key != "note"}
    stale["state"] = "submitted"
    save_take(studio.root, stale)
    saved = load_take(studio.root, "clip", "idle_loop", original["id"])
    assert saved["note"] == "reviewer annotation" and saved["state"] == "submitted"
    assert saved["source"] == original["source"] and saved["prompt"] == original["prompt"] and saved["media"] == original["media"]
    with pytest.raises(ValueError, match="note must be text"):
        set_take_note(studio.root, "clip", "idle_loop", original["id"], None)
    assert load_take(studio.root, "clip", "idle_loop", original["id"])["note"] == "reviewer annotation"


def test_old_notes_are_read_without_migrating_source_and_pose_notes_share_boundary(studio):
    original = clip_with_take(studio, "idle_loop", "idle", "idle", 8)
    legacy = deepcopy(original)
    legacy.pop("note")
    legacy.pop("basedOn")
    legacy["source"]["note"] = "legacy annotation"
    path = take_dir(studio.root, "clip", "idle_loop", legacy["id"]) / "take.json"
    atomic_json(path, legacy)
    before = path.read_bytes()
    snapshot = overview(studio.root)["clips"][0]["takes"][0]
    assert snapshot["note"] == "legacy annotation" and snapshot["basedOn"] is None and snapshot["generation"] is None
    assert path.read_bytes() == before
    set_take_note(studio.root, "clip", "idle_loop", original["id"], "edited")
    assert load_take(studio.root, "clip", "idle_loop", original["id"])["source"]["note"] == "legacy annotation"
    pose = load_owner(studio.root, "pose", "idle")
    assert set_take_note(studio.root, "pose", "idle", pose["acceptedTake"], "base note")["note"] == "base note"


def test_rejection_requires_reason_at_shared_api_and_cli_boundary_without_writes(studio):
    original = clip_with_take(studio, "idle_loop", "idle", "idle", 8)
    path = take_dir(studio.root, "clip", "idle_loop", original["id"]) / "take.json"
    owner_path = studio.root / "production/clips/idle_loop/clip.json"
    before, owner_before = path.read_bytes(), owner_path.read_bytes()
    for reason in ("", " \t", None, {"reason": "non-text"}):
        with pytest.raises(ValueError, match="requires a reason"):
            ProductionApi(studio.root).post("decision", {"kind": "clip", "owner": "idle_loop", "take": original["id"],
                                                        "action": "reject", "reason": reason})
    result = subprocess.run([sys.executable, "-m", "spriteforge", "production", "take", "reject", "--workspace",
                             str(studio.root), "--clip", "idle_loop", original["id"]], capture_output=True, text=True)
    assert result.returncode == 1 and "requires a reason" in result.stderr
    assert path.read_bytes() == before and owner_path.read_bytes() == owner_before
    decided = decide(studio.root, "clip", "idle_loop", original["id"], "reject", "  Hair jitters  ")
    assert decided["rejected"]["reason"] == "Hair jitters" and path.is_file()


@pytest.mark.parametrize("provider,request_body", [
    ("wan", {"parameters": {"duration": 4, "resolution": "720P", "seed": 7}}),
    ("seedance", {"duration": 4, "resolution": "720p", "seed": 7}),
    ("wan-cli", {"command": ["frame2video", "--duration", "4", "--resolution", "720P"]}),
])
def test_historical_generation_snapshot_matches_actual_adapter_request_shapes(provider, request_body):
    snapshot = generation_snapshot({"source": {"provider": provider, "request": request_body}})
    assert snapshot == {"provider": provider, "durationS": 4, "resolution": "720P", "seed": None if provider == "wan-cli" else 7}


@pytest.mark.parametrize("source", [{"provider": "manual"}, {"provider": "unknown", "request": {"duration": 4, "resolution": "720P"}},
                                   {"provider": "wan", "request": {}}, {"provider": "wan", "request": {"parameters": []}},
                                   {"provider": "wan", "request": {"parameters": {"duration": True, "resolution": "720P"}}},
                                   {"provider": "wan-cli", "request": {"command": ["--duration"]}}])
def test_unknown_generation_history_remains_unknown(source):
    assert generation_snapshot({"source": source}) is None


def test_credit_estimate_uses_latest_five_matching_complete_nonnegative_deltas():
    takes = []

    def take(index, cost, duration=4, resolution="720P", provider="wan-cli"):
        return {"id": str(index), "createdAt": f"2026-10-02T00:00:{index:02d}+00:00",
                "generation": {"provider": provider, "durationS": duration, "resolution": resolution},
                "source": {"balanceBefore": {"credits": 100}, "balanceAfter": {"credits": 100 - cost}}}

    takes.extend(take(index, cost) for index, cost in enumerate((90, 2, 6, 4, 8, 10)))
    takes.extend((take(6, 50, duration=5), take(7, 50, resolution="480P"), take(8, 50, provider="wan"),
                  take(9, -10), {**take(10, 50), "generation": None},
                  {**take(11, 50), "source": {"balanceBefore": {"credits": 100}}}))
    settings = {"provider": "wan-cli", "durationS": 4, "resolution": "720P"}
    assert clip_cost_estimate(list(reversed(takes)), settings) == {"credits": 6, "samples": 5}
    assert clip_cost_estimate(takes, {**settings, "durationS": 6}) is None
    assert clip_cost_estimate([take(0, -5)], settings) is None
    assert clip_cost_estimate([take(0, 0)], settings) == {"credits": 0, "samples": 1}


def test_note_annotation_does_not_stale_render_but_accepting_another_version_does(studio):
    original = clip_with_take(studio, "idle_loop", "idle", "idle", 8)
    render_clip(studio.root, "idle_loop", log=lambda *_: None)
    set_take_note(studio.root, "clip", "idle_loop", original["id"], "Reviewed render")
    assert render_freshness(studio.root, load_owner(studio.root, "clip", "idle_loop"))[0] == "current"
    alternate = import_clip_take(studio.root, "idle_loop", studio.tmp / "idle_loop", fps=30)
    decide(studio.root, "clip", "idle_loop", alternate["id"], "accept")
    assert render_freshness(studio.root, load_owner(studio.root, "clip", "idle_loop")) == ("stale", ["the accepted take changed"])


def test_frame_folder_import_and_mouth_routes_preserve_existing_contracts(studio):
    add_clip(studio.root, "idle_loop", "idle", "idle")
    source = frame_folder(studio, "inside", "idle", "idle", 8)
    # The HTTP route deliberately imports only from the selected workspace.
    target = studio.root / "frames-in"
    target.mkdir()
    for path in source.glob("*.png"):
        (target / path.name).write_bytes(path.read_bytes())
    api = ProductionApi(studio.root)
    take = api.post("import-frames", {"clip": "idle_loop", "path": "frames-in", "fps": 24, "note": "folder import"})["take"]
    assert take["media"]["count"] == 8 and take["media"]["fps"] == 24 and take["note"] == "folder import"
    mouth = api.post("mouth-set", {"name": "neutral", "changes": {"cx": 2.5, "width": 22}})["mouthSet"]
    assert mouth["cx"] == 2.5 and mouth["width"] == 22
    owner = (studio.root / "production/character.json").read_bytes()
    count = len(list_takes(studio.root, "clip", "idle_loop"))
    for body in ({"path": str(source), "fps": 24}, {"path": "../outside", "fps": 24},
                 {"path": "frames-in", "fps": 0}, {"path": "frames-in", "fps": True},
                 {"path": "frames-in", "fps": float("nan")}, {"path": "frames-in", "fps": 24, "note": None}):
        with pytest.raises(ValueError):
            api.post("import-frames", {"clip": "idle_loop", **body})
    for changes in ({"unrecognized": 1}, {"width": -1}, {"cx": float("inf")}):
        with pytest.raises(ValueError):
            api.post("mouth-set", {"name": "neutral", "changes": changes})
    assert len(list_takes(studio.root, "clip", "idle_loop")) == count
    assert (studio.root / "production/character.json").read_bytes() == owner


def test_api_job_passes_based_on_and_note_into_the_take(studio, monkeypatch):
    original = clip_with_take(studio, "idle_loop", "idle", "idle", 8)
    called = []

    def generate(workspace, clip_id, **values):
        called.append((workspace, clip_id, values))
        return {"id": "new-take"}

    class ImmediateThread:
        def __init__(self, *, target, **_):
            self.target = target

        def start(self):
            self.target()

    monkeypatch.setattr("spriteforge.production.clips.generate_clip_take", generate)
    monkeypatch.setattr(threading, "Thread", ImmediateThread)
    result = ProductionApi(studio.root).post("jobs", {"action": "generate", "clip": "idle_loop", "provider": "wan-cli",
                                                   "basedOn": original["id"], "note": "based on first"})["job"]
    assert result["status"] == "succeeded" and result["result"] == "new-take"
    assert called[0][1] == "idle_loop" and called[0][2]["based_on"] == original["id"]
    assert called[0][2]["note"] == "based on first"


def test_cli_variant_note_and_generation_metadata_share_backend(studio):
    original = clip_with_take(studio, "idle_loop", "idle", "idle", 8)

    def cli(*args):
        return subprocess.run([sys.executable, "-m", "spriteforge", "production", *map(str, args)], capture_output=True, text=True)

    assert cli("clip", "variant", "--workspace", studio.root, "idle_loop", "idle_loop2").returncode == 0
    assert list_takes(studio.root, "clip", "idle_loop2") == []
    result = cli("take", "note", "--workspace", studio.root, "--clip", "idle_loop", original["id"], "--note", "CLI note")
    assert result.returncode == 0 and load_take(studio.root, "clip", "idle_loop", original["id"])["note"] == "CLI note"
    result = cli("generate", "--workspace", studio.root, "--clip", "idle_loop", "--provider", "wan", "--dry-run",
                 "--based-on", original["id"], "--note", "dry preview")
    assert result.returncode == 0
    assert json.loads(result.stdout)["basedOn"] == original["id"] and json.loads(result.stdout)["note"] == "dry preview"
