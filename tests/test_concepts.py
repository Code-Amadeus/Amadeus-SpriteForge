import hashlib
import io
import json
import subprocess
import sys
import threading

import pytest

cv2 = pytest.importorskip("cv2")
import numpy as np  # noqa: E402

from synthetic import save, still  # noqa: E402
from spriteforge.production import prompts  # noqa: E402
from spriteforge.production.api import ProductionApi  # noqa: E402
from spriteforge.production.clips import prepare  # noqa: E402
from spriteforge.production.concepts import (concept_reference, current_sheet, generate_sheet, grid_spec, import_sheet,  # noqa: E402
                                           list_sheets, load_sheet, reroll_cell, save_sheet, set_cell, sheet_dir, split_grid)
from spriteforge.production.media import encode_png  # noqa: E402
from spriteforge.production.project import add_pose, overview, plan_clips  # noqa: E402
from spriteforge.production.records import list_takes, load_owner, take_dir  # noqa: E402
from spriteforge.production.stills import approve_still, generate_still  # noqa: E402
from spriteforge.workspace import atomic_json  # noqa: E402


def grid_image(width=630, height=400):
    image = np.zeros((height, width, 4), np.uint8)
    for index in range(6):
        row, col = divmod(index, 3)
        image[row * height // 2:(row + 1) * height // 2, col * width // 3:(col + 1) * width // 3] = (
            20 + index * 20, 40 + index * 10, 80 + index * 10, 255)
    return image


@pytest.fixture
def concepts(studio, monkeypatch):
    ids = [f"expr{index}" for index in range(6)]
    for pose in ids:
        add_pose(studio.root, pose, f"Description of {pose}")
    library = prompts.load_library(studio.root)
    for block_id in library["blocks"]:
        text = "${cols} columns and ${rows} rows\n${expressions}" if block_id == "concept.layout" else (
            "Expression ${pose}" if block_id.startswith("pose.") else block_id + " configured")
        prompts.set_block(library, block_id, text)
    prompts.save_library(studio.root, library)

    class FakeImage:
        model = "fake-image"
        negative_prompt = True
        supports_reference = True

        def __init__(self):
            self.calls, self.outputs, self.on_edit = [], [], None
            self.fail = False

        def key(self):
            return "fake-key"

        def preview(self, job):
            return {"input": hashlib.sha256(job.image).hexdigest(), "references": [hashlib.sha256(ref).hexdigest()
                                                                                   for ref in job.references],
                    "size": job.size, "prompt": job.prompt}

        def edit(self, job):
            self.calls.append(job)
            result = self.outputs.pop(0) if self.outputs else encode_png(grid_image())
            callback, self.on_edit = self.on_edit, None
            if callback:
                callback()
            if self.fail:
                raise ValueError("Synthetic provider failure")
            return result

    fake = FakeImage()
    monkeypatch.setattr("spriteforge.production.concepts.get_image_provider", lambda *_: fake)
    monkeypatch.setattr("spriteforge.production.stills.get_image_provider", lambda *_: fake)
    return studio, ids, fake


def test_grid_split_trims_uniform_outer_ring_and_keeps_row_major_pixels():
    original = grid_image(63, 40)
    padded = np.pad(original, ((3, 3), (4, 4), (0, 0)), constant_values=255)
    cells = split_grid(padded, {"rows": 2, "cols": 3})
    assert len(cells) == 6
    assert all(cell.shape == (20, 21, 4) for cell in cells)
    assert [cell[0, 0].tolist() for cell in cells] == [original[(index // 3) * 20, (index % 3) * 21].tolist()
                                                   for index in range(6)]
    assert sum(cell.shape[0] * cell.shape[1] for cell in split_grid(grid_image(64, 41), grid_spec("3x2"))) == 64 * 41


@pytest.mark.parametrize("value", [None, "6x1", "3x3", {"rows": True, "cols": 3}, {"rows": 2, "cols": 3, "extra": 1}])
def test_unknown_or_oversize_grids_are_rejected(value):
    with pytest.raises(ValueError):
        grid_spec(value)


def test_generated_dimensions_are_candidate_facts_not_an_exact_size_gate(concepts):
    studio, ids, fake = concepts
    raw = encode_png(grid_image(633, 403))
    fake.outputs.append(raw)
    sheet = generate_sheet(studio.root, ids, "3x2", "gpt-image")
    assert len(fake.calls) == 1 and fake.calls[0].size == (1536, 1024)
    assert sheet["state"] == "ready" and sheet["size"] == {"w": 633, "h": 403}
    assert (sheet_dir(studio.root, sheet["id"]) / sheet["sourceFile"]).read_bytes() == raw
    assert [cell["pose"] for cell in sheet["cells"]] == ids
    assert all((sheet_dir(studio.root, sheet["id"]) / cell["file"]).is_file() for cell in sheet["cells"])
    assert all(list_takes(studio.root, "pose", pose) == [] for pose in ids)
    assert all(load_owner(studio.root, "pose", pose)["acceptedTake"] is None for pose in ids)
    snapshot = overview(studio.root)["concepts"][0]
    assert snapshot["current"] and snapshot["version"] == 1


def test_import_preserves_original_jpeg_bytes_and_sparse_slots_need_assignment(concepts):
    studio, ids, fake = concepts
    ok, encoded = cv2.imencode(".jpg", grid_image()[:, :, :3])
    assert ok
    source = studio.tmp / "external.jpg"
    source.write_bytes(encoded.tobytes())
    sheet = import_sheet(studio.root, source, [ids[0]], "3x2")
    assert fake.calls == [] and sheet["sourceFile"] == "source.jpg"
    assert (sheet_dir(studio.root, sheet["id"]) / "source.jpg").read_bytes() == source.read_bytes()
    assert sheet["cells"][1]["pose"] is None
    with pytest.raises(ValueError, match="Assign a pose"):
        set_cell(studio.root, sheet["id"], 1, picked=True)
    updated = set_cell(studio.root, sheet["id"], 1, pose=ids[1], picked=True)
    assert updated["cells"][1]["pose"] == ids[1] and updated["cells"][1]["picked"] is True


def test_reference_still_uses_approved_base_and_snapshot_then_existing_qa_approval(concepts):
    studio, ids, fake = concepts
    sheet = generate_sheet(studio.root, ids, "3x2", "gpt-image")
    set_cell(studio.root, sheet["id"], 0, picked=True)
    reference, provenance = concept_reference(studio.root, sheet["id"], 0, ids[0])
    fake.outputs.append(encode_png(still(studio, "idle")))
    take = generate_still(studio.root, ids[0], "gpt-image", concept={"sheet": sheet["id"], "cell": 0}, log=lambda *_: None)
    assert len(fake.calls) == 2 and fake.calls[-1].references == [reference]
    directory = take_dir(studio.root, "pose", ids[0], take["id"])
    assert take["source"]["concept"] == provenance
    assert (directory / "reference.png").read_bytes() == reference
    assert fake.calls[-1].image == (directory / "input.png").read_bytes()
    assert take["qa"]["status"] != "fail" and load_owner(studio.root, "pose", ids[0])["acceptedTake"] is None
    assert approve_still(studio.root, ids[0], take["id"])["id"] == take["id"]
    with pytest.raises(ValueError, match="Unknown take"):
        approve_still(studio.root, ids[1], sheet["id"])
    with pytest.raises(ValueError, match="assigned to this pose"):
        concept_reference(studio.root, sheet["id"], 0, ids[1])


def test_reroll_is_one_call_and_preserves_original_and_previous_images(concepts):
    studio, ids, fake = concepts
    sheet = generate_sheet(studio.root, ids, "3x2", "gpt-image")
    directory = sheet_dir(studio.root, sheet["id"])
    original = (directory / sheet["cells"][0]["file"]).read_bytes()
    fake.outputs.append(encode_png(grid_image(300, 300)))
    updated = reroll_cell(studio.root, sheet["id"], 0, "gpt-image")
    assert len(fake.calls) == 2
    cell = updated["cells"][0]
    assert len(cell["rerolls"]) == 1 and cell["file"] == cell["rerolls"][0]["file"]
    assert (directory / cell["originalFile"]).read_bytes() == original
    retained = (directory / cell["file"]).read_bytes()
    fake.outputs.append(encode_png(grid_image(400, 400)))
    updated = reroll_cell(studio.root, sheet["id"], 0, "gpt-image")
    assert len(fake.calls) == 3 and (directory / cell["file"]).read_bytes() == retained
    assert len(updated["cells"][0]["rerolls"]) == 2


def test_failed_sheet_keeps_previous_ready_current_and_history_is_pick_only(concepts):
    studio, ids, fake = concepts
    first = generate_sheet(studio.root, ids, "3x2", "gpt-image")
    fake.fail = True
    with pytest.raises(ValueError, match="Synthetic provider failure"):
        generate_sheet(studio.root, ids, "3x2", "gpt-image")
    assert current_sheet(studio.root) == first["id"] and list_sheets(studio.root)[-1]["state"] == "failed"
    fake.fail = False
    latest = generate_sheet(studio.root, ids, "3x2", "gpt-image")
    assert current_sheet(studio.root) == latest["id"]
    assert set_cell(studio.root, first["id"], 0, picked=True)["cells"][0]["picked"]
    before = len(fake.calls)
    with pytest.raises(ValueError, match="read-only"):
        set_cell(studio.root, first["id"], 0, pose=ids[1])
    with pytest.raises(ValueError, match="read-only"):
        reroll_cell(studio.root, first["id"], 0, "gpt-image")
    assert len(fake.calls) == before


@pytest.mark.parametrize("change", ["association", "current-sheet", "history-append"])
def test_reroll_completion_keeps_changed_cell_context_and_pick_state(concepts, change):
    studio, ids, fake = concepts
    sheet = generate_sheet(studio.root, ids, "3x2", "gpt-image")
    source_file = sheet["cells"][0]["file"]

    def callback():
        set_cell(studio.root, sheet["id"], 0, picked=True)
        if change == "association":
            set_cell(studio.root, sheet["id"], 0, pose=ids[1])
        elif change == "current-sheet":
            import_sheet(studio.root, save(studio.tmp / "new-sheet.png", grid_image()), ids, "3x2")
        else:
            record = load_sheet(studio.root, sheet["id"])
            record["cells"][0]["rerolls"].append({"id": "another-attempt", "state": "failed"})
            save_sheet(studio.root, record)

    fake.on_edit = callback
    result = reroll_cell(studio.root, sheet["id"], 0, "gpt-image")
    cell = result["cells"][0]
    assert cell["picked"] is True
    assert cell["rerolls"][0]["state"] == "ready"
    if change in {"association", "current-sheet"}:
        assert cell["file"] == source_file
    if change == "association":
        assert cell["pose"] == ids[1]
    if change == "history-append":
        assert cell["rerolls"][-1] == {"id": "another-attempt", "state": "failed"}


def test_prompt_extension_is_read_only_and_variables_are_context_scoped(concepts):
    studio, ids, fake = concepts
    path = studio.root / "production/prompts.json"
    library = prompts.load_library(studio.root)
    for key in ("concept.layout", "still.reference"):
        library["blocks"].pop(key)
    for key in ("concept", "still-reference"):
        library["templates"].pop(key)
    atomic_json(path, library)
    original = path.read_bytes()
    loaded = prompts.load_library(studio.root)
    assert {"concept", "still-reference"} <= loaded["templates"].keys() and path.read_bytes() == original
    prompts.set_block(loaded, f"pose.{ids[0]}", "${rows} should be unavailable to a pose prompt")
    with pytest.raises(ValueError, match="unknown variable"):
        prompts.pose_prompt(loaded, overview(studio.root)["character"], load_owner(studio.root, "pose", ids[0]))
    with pytest.raises(ValueError, match="placeholder"):
        generate_sheet(studio.root, ids, "3x2", "gpt-image")
    assert fake.calls == [] and list_sheets(studio.root) == []


def test_unknown_pose_dry_run_and_placeholder_gate_never_send_requests(concepts):
    studio, ids, fake = concepts
    preview = generate_sheet(studio.root, ["new-expression"], "3x2", "gpt-image", dry_run=True)
    assert preview["prompt"]["complete"] is False and fake.calls == []
    with pytest.raises(ValueError, match="Unknown pose"):
        load_owner(studio.root, "pose", "new-expression")
    with pytest.raises(ValueError, match="placeholder"):
        generate_sheet(studio.root, ["new-expression"], "3x2", "gpt-image")
    assert load_owner(studio.root, "pose", "new-expression")["acceptedTake"] is None and fake.calls == []


def test_usage_counts_sheet_reroll_and_formal_image_once_from_recorded_sources(concepts):
    studio, ids, fake = concepts
    sheet = generate_sheet(studio.root, ids, "3x2", "gpt-image")
    reroll_cell(studio.root, sheet["id"], 0, "gpt-image")
    fake.outputs.append(encode_png(still(studio, "idle")))
    generate_still(studio.root, ids[0], "gpt-image", concept={"sheet": sheet["id"], "cell": 0}, log=lambda *_: None)
    data = overview(studio.root)
    assert data["usage"]["gptImage"]["images"] == 3


def test_concept_upload_pose_prepare_and_plan_clips_are_local_only(concepts):
    studio, ids, fake = concepts
    api = ProductionApi(studio.root)
    png = encode_png(grid_image())
    uploaded = api.upload("concept", "", "grid.png", io.BytesIO(png), len(png), None, "", poses=ids, grid="3x2")["sheet"]
    assert uploaded["state"] == "ready" and fake.calls == []
    prepare(studio.root, "pose", ids[0], studio.tmp / "prepared")
    assert api.pose_input(ids[0]) == (studio.tmp / "prepared/base.png").read_bytes()
    with pytest.raises(ValueError, match="Unknown pose"):
        api.pose_input("missing")
    graph = (studio.root / "graph_config.json").read_bytes()
    planned = api.post("plan-clips", {"clips": [{"id": "smile_in", "from": "idle", "to": "smile"},
                                               {"id": "smile_loop", "from": "smile", "to": "smile"}]})["clips"]
    assert len(planned) == 2 and all(clip["acceptedTake"] is None for clip in planned)
    assert all(list_takes(studio.root, "clip", clip["id"]) == [] for clip in planned)
    assert (studio.root / "graph_config.json").read_bytes() == graph and fake.calls == []
    with pytest.raises(ValueError, match="no accepted"):
        plan_clips(studio.root, [{"id": "not_created", "from": "idle", "to": ids[0]}])
    with pytest.raises(ValueError, match="Unknown clip"):
        load_owner(studio.root, "clip", "not_created")


def test_cli_import_pick_and_dry_run_share_the_same_records(concepts):
    studio, ids, fake = concepts
    source = save(studio.tmp / "cli-grid.png", grid_image())

    def cli(*args):
        return subprocess.run([sys.executable, "-m", "spriteforge", "production", *map(str, args)], capture_output=True, text=True)

    result = cli("concept", "import", "--workspace", studio.root, source, "--poses", ",".join(ids), "--grid", "3x2")
    assert result.returncode == 0, result.stderr
    sheet = json.loads(result.stdout)
    assert cli("concept", "pick", "--workspace", studio.root, sheet["id"], "0").returncode == 0
    assert load_sheet(studio.root, sheet["id"])["cells"][0]["picked"]
    result = cli("concept", "reroll", "--workspace", studio.root, sheet["id"], "0", "--provider", "qwen-image", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)["request"]["input"]["messages"][0]["content"]) == 3
    result = cli("generate", "--workspace", studio.root, "--pose", ids[0], "--provider", "qwen-image", "--concept",
                 f"{sheet['id']}:0", "--dry-run")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["prompt"]["template"] == "still-reference" and fake.calls == []
    plan_file = studio.tmp / "plan.json"
    atomic_json(plan_file, [{"id": "free_smile", "from": "idle", "to": "smile"}])
    result = cli("clip", "plan", "--workspace", studio.root, "--file", plan_file)
    assert result.returncode == 0 and list_takes(studio.root, "clip", "free_smile") == [] and fake.calls == []


def test_explicit_image_jobs_serialize_per_provider_without_repeating_work(concepts, monkeypatch):
    studio, ids, _ = concepts
    api = ProductionApi(studio.root)
    first_started, release, second_queued, second_started = (threading.Event() for _ in range(4))
    threads, calls = [], []
    real_thread = threading.Thread

    def create_thread(*args, **kwargs):
        thread = real_thread(*args, **kwargs)
        threads.append(thread)
        return thread

    class TrackedLock:
        def __init__(self):
            self.lock, self.guard, self.attempts = threading.Lock(), threading.Lock(), 0

        def __enter__(self):
            with self.guard:
                self.attempts += 1
                if self.attempts == 2:
                    second_queued.set()
            self.lock.acquire()

        def __exit__(self, *_):
            self.lock.release()

    def first(_):
        calls.append("first")
        first_started.set()
        assert release.wait(5)
        return "first-result"

    def second(_):
        second_started.set()
        calls.append("second")
        return "second-result"

    monkeypatch.setattr("spriteforge.production.api.threading.Thread", create_thread)
    api.provider_locks["qwen-image"] = TrackedLock()
    try:
        api._launch("generate", "pose", ids[0], first, provider="qwen-image")
        assert first_started.wait(5)
        api._launch("generate", "pose", ids[1], second, provider="qwen-image")
        assert second_queued.wait(5) and not second_started.is_set()
        with pytest.raises(ValueError, match="already running"):
            api._launch("generate", "pose", ids[1], second, provider="qwen-image")
    finally:
        release.set()
        for thread in threads:
            thread.join(5)
    assert calls == ["first", "second"]
    assert len(api.job_list()) == 2 and all(job["status"] == "succeeded" for job in api.job_list())
