"""Processing candidates cannot replace the graph's published material until adoption."""
import hashlib

import pytest

from synthetic import clip_with_take, frame_folder, save, still
from spriteforge.production.clips import import_clip_take
from spriteforge.production.project import add_clip, overview, set_clip
from spriteforge.production.records import (candidate_render_freshness, load_owner, read_candidate_render,
                                             read_render, render_freshness, save_owner, take_dir, decide)
from spriteforge.production.render import adopt_processed_take, render_clip, render_take
from spriteforge.workspace import atomic_json


def files(directory):
    return {path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob("*") if path.is_file()}


def prepared(studio):
    previous = clip_with_take(studio, "smile_in", "idle", "smile", 6, lock_head=2, lock_tail=2)
    render_clip(studio.root, "smile_in", log=lambda *_: None)
    candidate = import_clip_take(studio.root, "smile_in", frame_folder(studio, "candidate", "idle", "smile", 8), fps=30)
    published = studio.root / "production/clips/smile_in/output"
    return previous, candidate, published


def test_preview_is_separate_until_explicit_adoption(studio):
    previous, candidate, published = prepared(studio)
    original = files(published)
    graph = (studio.root / "graph_config.json").read_bytes()
    take_record = (take_dir(studio.root, "clip", "smile_in", candidate["id"]) / "take.json").read_bytes()
    result = render_take(studio.root, "smile_in", candidate["id"], log=lambda *_: None)
    assert result["qa"]["status"] != "fail"
    assert load_owner(studio.root, "clip", "smile_in")["acceptedTake"] == previous["id"]
    assert files(published) == original
    assert (studio.root / "graph_config.json").read_bytes() == graph
    assert (take_dir(studio.root, "clip", "smile_in", candidate["id"]) / "take.json").read_bytes() == take_record
    summary = next(take for take in overview(studio.root)["clips"][0]["takes"] if take["id"] == candidate["id"])
    assert summary["candidateRender"]["state"] == "current" and summary["candidateRender"]["take"] == candidate["id"]
    adopt_processed_take(studio.root, "smile_in", candidate["id"])
    assert load_owner(studio.root, "clip", "smile_in")["acceptedTake"] == candidate["id"]
    assert read_render(studio.root, "smile_in")["take"] == candidate["id"]
    assert render_freshness(studio.root, load_owner(studio.root, "clip", "smile_in"))[0] == "current"
    preview = take_dir(studio.root, "clip", "smile_in", candidate["id"]) / "processed"
    assert files(published) == files(preview)
    assert (studio.root / "graph_config.json").read_bytes() == graph


def test_replaced_adopted_version_does_not_reenter_queue_unless_restored(studio):
    previous, candidate, _ = prepared(studio)
    render_take(studio.root, "smile_in", candidate["id"], log=lambda *_: None)
    adopt_processed_take(studio.root, "smile_in", candidate["id"])
    takes = overview(studio.root)["clips"][0]["takes"]
    old = next(take for take in takes if take["id"] == previous["id"])
    assert old["status"] == "candidate" and old["needsReview"] is False
    assert not any(take["needsReview"] for take in takes)
    decide(studio.root, "clip", "smile_in", previous["id"], "reject", "Archive the older version")
    decide(studio.root, "clip", "smile_in", previous["id"], "restore")
    restored = next(take for take in overview(studio.root)["clips"][0]["takes"] if take["id"] == previous["id"])
    assert restored["needsReview"] is True


def test_failing_candidate_qa_never_replaces_existing_output(studio, monkeypatch):
    previous, candidate, published = prepared(studio)
    original = files(published)
    monkeypatch.setattr("spriteforge.production.render.clip_report", lambda *args: {
        "status": "fail", "checks": [{"check": "alignment", "level": "fail", "message": "Synthetic blocking finding"}],
    })
    render_take(studio.root, "smile_in", candidate["id"], log=lambda *_: None)
    assert read_candidate_render(studio.root, "smile_in", candidate["id"])["qa"]["status"] == "fail"
    with pytest.raises(ValueError, match="blocking failure"):
        adopt_processed_take(studio.root, "smile_in", candidate["id"])
    assert load_owner(studio.root, "clip", "smile_in")["acceptedTake"] == previous["id"]
    assert files(published) == original
    assert render_freshness(studio.root, load_owner(studio.root, "clip", "smile_in"))[0] == "current"


def test_missing_or_stale_preview_cannot_be_adopted(studio):
    previous, candidate, published = prepared(studio)
    original = files(published)
    with pytest.raises(ValueError, match="Process and check"):
        adopt_processed_take(studio.root, "smile_in", candidate["id"])
    render_take(studio.root, "smile_in", candidate["id"], log=lambda *_: None)
    set_clip(studio.root, "smile_in", speed=2)
    assert candidate_render_freshness(studio.root, load_owner(studio.root, "clip", "smile_in"), candidate["id"])[0] == "stale"
    with pytest.raises(ValueError, match="Process and check"):
        adopt_processed_take(studio.root, "smile_in", candidate["id"])
    assert load_owner(studio.root, "clip", "smile_in")["acceptedTake"] == previous["id"]
    assert files(published) == original


def test_failed_adoption_commit_restores_published_output(studio, monkeypatch):
    previous, candidate, published = prepared(studio)
    original = files(published)
    render_take(studio.root, "smile_in", candidate["id"], log=lambda *_: None)

    def fail(*args):
        raise OSError("Synthetic decision write failure")

    monkeypatch.setattr("spriteforge.production.render.decide", fail)
    with pytest.raises(OSError, match="write failure"):
        adopt_processed_take(studio.root, "smile_in", candidate["id"])
    assert load_owner(studio.root, "clip", "smile_in")["acceptedTake"] == previous["id"]
    assert files(published) == original


@pytest.mark.parametrize("register", [True, None, False], ids=["registered", "legacy-register-default", "finished-rgba"])
@pytest.mark.parametrize("legacy_crop", [False, True], ids=["crop-settings", "legacy-crop-defaults"])
def test_registration_recipe_invalidates_only_old_registered_outputs_without_rewriting_records(studio, register, legacy_crop):
    clip = add_clip(studio.root, "loop", "idle", "idle")
    if register is None:
        del clip["processing"]["register"]
    else:
        clip["processing"]["register"] = register
    if legacy_crop:
        for key in ("cropBlackBorder", "cropBlackThreshold", "cropBlackMarginPx"):
            del clip["processing"][key]
    save_owner(studio.root, "clip", clip)
    source = studio.tmp / "finished-rgba"
    for index in range(3):
        save(source / f"{index:04d}.png", still(studio, "idle"))
    accepted = import_clip_take(studio.root, "loop", source, fps=30)
    decide(studio.root, "clip", "loop", accepted["id"], "accept")
    candidate = import_clip_take(studio.root, "loop", source, fps=30)
    published = render_clip(studio.root, "loop", log=lambda *_: None)
    preview = render_take(studio.root, "loop", candidate["id"], log=lambda *_: None)
    clip = load_owner(studio.root, "clip", "loop")
    for rendered in (published, preview):
        assert rendered["recipe"]["processing"] == clip["processing"]
        if register is False:
            assert "registrationMethod" not in rendered["recipe"]
        else:
            assert rendered["recipe"]["registrationMethod"] == "fixed-head"
    assert render_freshness(studio.root, clip) == ("current", [])
    assert candidate_render_freshness(studio.root, clip, candidate["id"]) == ("current", [])

    # These receipts model renders made before the fixed-head algorithm was versioned.
    published["recipe"].pop("registrationMethod", None)
    preview["recipe"].pop("registrationMethod", None)
    atomic_json(studio.root / "production/clips/loop/output/render.json", published)
    atomic_json(take_dir(studio.root, "clip", "loop", candidate["id"]) / "processed/render.json", preview)
    before = files(studio.root / "production/clips/loop")
    expected = ("current", []) if register is False else (
        "stale", ["processing, playback or mouth settings changed"])
    assert render_freshness(studio.root, load_owner(studio.root, "clip", "loop")) == expected
    assert candidate_render_freshness(studio.root, load_owner(studio.root, "clip", "loop"), candidate["id"]) == expected
    state = overview(studio.root)["clips"][0]
    assert state["render"]["state"] == expected[0]
    take = next(take for take in state["takes"] if take["id"] == candidate["id"])
    assert take["candidateRender"]["state"] == expected[0]
    assert files(studio.root / "production/clips/loop") == before
