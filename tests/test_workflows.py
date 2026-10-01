"""Workflow authority, durable payment receipts and cache semantics, without providers."""
import copy
import hashlib
import io
import threading

import pytest

from synthetic import clip_with_take, still
from spriteforge.production.media import encode_png
from spriteforge.production.api import ProductionApi
from spriteforge.production.studio import usage_summary
from spriteforge.production.workflows import (FORMAT, RUN_LOCK, WorkflowEngine, directory, list_workflows, load_workflow,
                                              paid_receipts, read_run, save_workflow, template_workflow, validate_workflow)


class Operations:
    REGISTRY = {
        "text": {"inputs": {}, "outputs": {"text": "TEXT"}, "paid": False},
        "image-edit": {"inputs": {"prompt": {"type": "TEXT", "required": True}}, "outputs": {"image": "IMAGE"}, "paid": True},
        "preview": {"inputs": {"media": {"type": "IMAGE", "required": True}}, "outputs": {"media": "IMAGE"}, "paid": False},
        "external-processor": {"inputs": {"media": {"type": "IMAGE", "required": True}}, "outputs": {"media": "IMAGE"}, "paid": False},
    }

    def __init__(self):
        self.calls, self.model, self.version = [], "model-one", 1
        self.fail_local, self.fail_paid, self.pending = False, False, False
        self.submissions = 0

    def validate_params(self, workspace, kind, params):
        keys = {"text": {"text"}, "image-edit": {"provider", "pose"}, "preview": set(), "external-processor": {"processor"}}[kind]
        if not isinstance(params, dict) or set(params) - keys:
            raise ValueError("Unknown parameters")
        return copy.deepcopy(params)

    def ports(self, kind, params):
        return {key: self.REGISTRY[kind][key] for key in ("inputs", "outputs")}

    def context(self, workspace, kind, params, *, inputs=None):
        if kind == "text":
            return {"outputs": {"text": {"type": "TEXT", "text": params["text"], "provenance": {}}}, "version": self.version}
        if kind == "image-edit":
            if "{{PLACEHOLDER}}" in (inputs["prompt"] or {}).get("text", ""):
                raise ValueError("Incomplete prompt")
            return {"model": self.model, "outputs": {"image": {"type": "IMAGE", "provenance": {}}}}
        return {"outputs": {"media": inputs.get("media")}}

    def execute(self, workspace, node_dir, kind, params, inputs, *, record, log, previous=None):
        self.calls.append(kind)
        if kind == "text":
            text = params["text"]
            return {"text": {"type": "TEXT", "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(), "provenance": {}}}
        if kind == "image-edit":
            if previous is None:
                self.submissions += 1
                receipt = record({"state": "submitting", "provider": params["provider"], "model": self.model,
                                  "request": {"prompt": inputs["prompt"]["text"]},
                                  "balanceBefore": {"credits": 100}, "balanceAfter": {"credits": 94}})
                assert receipt["workflow"]["id"] and receipt["run"] and receipt["node"]
                if self.pending:
                    record({"state": "submitted", "taskId": "existing-task"})
                    raise ValueError("Synthetic download interruption")
                if self.fail_paid:
                    raise ValueError("Synthetic provider failure")
            else:
                assert previous["taskId"] == "existing-task"
            path = node_dir / "image.png"
            path.write_bytes((inputs["prompt"]["text"] + self.model).encode())
            asset = {"type": "IMAGE", "path": path.relative_to(workspace).as_posix(),
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "provenance": {"provider": {"provider": params["provider"]}}}
            record({"state": "ready", "outputs": {"image": asset}, "provider": params["provider"],
                    "balanceBefore": {"credits": 100}, "balanceAfter": {"credits": 94}})
            return {"image": asset}
        if self.fail_local:
            raise ValueError("Synthetic local failure")
        return {"media": inputs["media"]}


def document(*, provider="gpt-image", pose=None):
    return {"format": FORMAT, "id": "test-workflow", "name": "Test workflow", "version": 1,
            "nodes": [{"id": "text", "kind": "text", "params": {"text": "expression"}, "position": [0, 0]},
                      {"id": "paid", "kind": "image-edit", "params": {"provider": provider, **({"pose": pose} if pose else {})}, "position": [200, 0]},
                      {"id": "show", "kind": "preview", "params": {}, "position": [400, 0]}],
            "links": [{"from": {"node": "text", "port": "text"}, "to": {"node": "paid", "port": "prompt"}},
                      {"from": {"node": "paid", "port": "image"}, "to": {"node": "show", "port": "media"}}], "groups": []}


@pytest.fixture
def engine(studio):
    ops = Operations()
    save_workflow(studio.root, document(), operations=ops)
    return studio, ops, WorkflowEngine(studio.root, operations=ops)


def run(engine, *, rerun=None, confirm_imported=False):
    plan = engine.plan("test-workflow", rerun=rerun)
    return plan, engine.run("test-workflow", plan_hash=plan["planHash"], confirm_paid=plan["paidCount"],
                            confirm_imported=confirm_imported, rerun=rerun, log=lambda *_: None)


def test_cache_paid_count_exact_reuse_and_explicit_rerun_downstream_identity(engine):
    studio, ops, runner = engine
    plan, first = run(runner)
    assert plan["paidCount"] == 1 and plan["paidNodes"][0]["costType"] == "planQuota"
    assert ops.submissions == 1 and first["state"] == "ready"
    plan, second = run(runner)
    assert plan["paidCount"] == 0 and ops.submissions == 1
    assert all(node["cached"] for node in second["nodes"])
    assert second["outputs"]["paid"]["image"]["path"] != first["outputs"]["paid"]["image"]["path"]
    plan, third = run(runner, rerun=["paid"])
    assert plan["paidCount"] == 1 and ops.submissions == 2
    assert third["nodes"][0]["cached"] and not third["nodes"][1]["cached"] and not third["nodes"][2]["cached"]
    assert runner.plan("test-workflow")["paidCount"] == 0
    assert len(paid_receipts(studio.root)) == 2
    assert read_run(studio.root, third["id"])["workflow"]["sha256"]


def test_successful_paid_receipt_survives_later_failure_and_retry(engine):
    studio, ops, runner = engine
    ops.fail_local = True
    plan = runner.plan("test-workflow")
    with pytest.raises(ValueError, match="Synthetic local failure"):
        runner.run("test-workflow", plan_hash=plan["planHash"], confirm_paid=1, log=lambda *_: None)
    [receipt] = paid_receipts(studio.root)
    assert receipt["operation"]["state"] == "ready" and receipt["outputs"]["image"]["path"]
    assert runner.plan("test-workflow")["paidCount"] == 0
    ops.fail_local = False
    _, result = run(runner)
    assert result["state"] == "ready" and ops.submissions == 1


def test_failed_ambiguous_paid_attempt_requires_explicit_rerun(engine):
    _, ops, runner = engine
    ops.fail_paid = True
    plan = runner.plan("test-workflow")
    with pytest.raises(ValueError, match="Synthetic provider failure"):
        runner.run("test-workflow", plan_hash=plan["planHash"], confirm_paid=1, log=lambda *_: None)
    plan = runner.plan("test-workflow")
    assert plan["blocking"] and ops.submissions == 1
    with pytest.raises(ValueError, match="blocked nodes"):
        runner.run("test-workflow", plan_hash=plan["planHash"], confirm_paid=1, log=lambda *_: None)
    ops.fail_paid = False
    _, result = run(runner, rerun=["paid"])
    assert result["state"] == "ready" and ops.submissions == 2


def test_submitted_video_like_receipt_resumes_without_another_request(engine):
    studio, ops, runner = engine
    ops.pending = True
    plan = runner.plan("test-workflow")
    with pytest.raises(ValueError, match="download interruption"):
        runner.run("test-workflow", plan_hash=plan["planHash"], confirm_paid=1, log=lambda *_: None)
    requested_at = paid_receipts(studio.root)[0]["operation"]["requestedAt"]
    plan = runner.plan("test-workflow")
    assert plan["paidCount"] == 0 and plan["nodes"][1]["resume"] and not plan["blocking"]
    _, result = run(runner)
    assert result["state"] == "ready" and ops.submissions == 1
    assert paid_receipts(studio.root)[0]["operation"]["requestedAt"] == requested_at


def test_model_prompt_and_source_fingerprints_change_cache_not_view_geometry(engine):
    studio, ops, runner = engine
    run(runner)
    raw = load_workflow(studio.root, "test-workflow", operations=ops)
    raw["nodes"][0]["position"] = [999, -20]
    save_workflow(studio.root, raw, operations=ops)
    assert runner.plan("test-workflow")["paidCount"] == 0
    ops.model = "model-two"
    assert runner.plan("test-workflow")["paidCount"] == 1
    run(runner)
    ops.version += 1
    assert runner.plan("test-workflow")["paidCount"] == 1


def test_changed_plan_and_wrong_confirmation_never_dispatch(engine):
    _, ops, runner = engine
    plan = runner.plan("test-workflow")
    for count in (0, True, 2):
        with pytest.raises(ValueError, match="Confirm exactly"):
            runner.run("test-workflow", plan_hash=plan["planHash"], confirm_paid=count, log=lambda *_: None)
    ops.model = "changed-after-dialog"
    with pytest.raises(ValueError, match="facts changed"):
        runner.run("test-workflow", plan_hash=plan["planHash"], confirm_paid=1, log=lambda *_: None)
    assert ops.calls == []


def test_import_disclosure_is_host_owned_and_required_once(engine):
    studio, ops, runner = engine
    raw = document()
    raw.update(imported=False, disclosedAt="forged")
    saved = save_workflow(studio.root, raw, imported=True, operations=ops)
    assert saved["imported"] and saved["disclosedAt"] is None
    plan = runner.plan(saved["id"])
    with pytest.raises(ValueError, match="imported workflow"):
        runner.run(saved["id"], plan_hash=plan["planHash"], confirm_paid=1, log=lambda *_: None)
    assert ops.calls == []
    run(runner, confirm_imported=True)
    assert not list_workflows(studio.root, operations=ops)[0]["requiresDisclosure"]
    assert runner.plan(saved["id"])["paidCount"] == 0


@pytest.mark.parametrize("change", ["unknown-node", "command", "cycle", "wrong-type", "duplicate-slot", "path-id", "reserved-id"])
def test_invalid_graphs_never_replace_valid_document(engine, change):
    studio, ops, _ = engine
    before = (directory(studio.root) / "test-workflow.json").read_bytes()
    raw = document()
    if change == "unknown-node":
        raw["nodes"][1]["kind"] = "approve"
    elif change == "command":
        raw["nodes"][1]["params"]["command"] = ["untrusted"]
    elif change == "cycle":
        raw["links"][0]["from"] = {"node": "paid", "port": "image"}
    elif change == "wrong-type":
        raw["links"][0]["from"] = {"node": "show", "port": "media"}
    elif change == "duplicate-slot":
        raw["links"].append(copy.deepcopy(raw["links"][0]))
    elif change == "path-id":
        raw["id"] = "../escape"
    else:
        raw["id"] = "schema"
    with pytest.raises(ValueError):
        save_workflow(studio.root, raw, operations=ops)
    assert (directory(studio.root) / "test-workflow.json").read_bytes() == before
    assert ops.calls == []


def test_incomplete_draft_can_save_but_cannot_run(engine):
    studio, ops, runner = engine
    raw = document()
    raw["links"] = []
    save_workflow(studio.root, raw, operations=ops)
    with pytest.raises(ValueError, match="requires input"):
        runner.plan(raw["id"])
    assert ops.calls == []


def test_cached_paid_artifact_damage_does_not_silently_resubmit(engine):
    studio, ops, runner = engine
    _, result = run(runner)
    (studio.root / result["outputs"]["paid"]["image"]["path"]).write_bytes(b"changed")
    plan = runner.plan("test-workflow")
    assert plan["blocking"] and ops.submissions == 1
    with pytest.raises(ValueError, match="blocked nodes"):
        runner.run("test-workflow", plan_hash=plan["planHash"], confirm_paid=1, log=lambda *_: None)


def test_only_one_workflow_runs_at_a_time(engine):
    _, ops, runner = engine
    plan = runner.plan("test-workflow")
    assert RUN_LOCK.acquire(blocking=False)
    try:
        with pytest.raises(ValueError, match="already running"):
            runner.run("test-workflow", plan_hash=plan["planHash"], confirm_paid=1)
    finally:
        RUN_LOCK.release()
    assert ops.calls == []


def test_workflow_paid_usage_counts_receipt_once_instead_of_candidate_fanout(engine):
    studio, ops, runner = engine
    save_workflow(studio.root, document(provider="wan-cli"), operations=ops)
    run(runner)
    receipts = paid_receipts(studio.root)
    source = {"provider": "wan-cli", "balanceBefore": {"credits": 100}, "balanceAfter": {"credits": 94},
              "workflow": {"id": "test-workflow"}}
    takes = [{"id": str(i), "createdAt": receipts[0]["startedAt"], "source": source} for i in range(2)]
    usage = usage_summary([], [{"takes": takes}], workflow_receipts=receipts)
    assert usage["wan"] == {"usedCredits": 6, "balance": 94}


def test_workflow_plan_quota_usage_counts_paid_image_once(engine):
    studio, _, runner = engine
    _, result = run(runner)
    [receipt] = paid_receipts(studio.root)
    takes = [{"id": str(index), "createdAt": receipt["startedAt"], "source": {"provider": "gpt-image", "workflow": {"id": "test-workflow"}},
              "media": {"source": "source.png"}} for index in range(2)]
    assert usage_summary([{"takes": takes}], [], workflow_receipts=[receipt])["gptImage"]["images"] == 1
    assert result["state"] == "ready"


def test_api_workflow_owner_reservations_block_overlapping_jobs_and_adoption(engine, monkeypatch):
    studio, ops, runner = engine
    save_workflow(studio.root, document(pose="smile"), operations=ops)
    api = ProductionApi(studio.root)
    api.workflows = runner
    pending = []

    class ControlledThread:
        def __init__(self, *, target, **_):
            self.target = target

        def start(self):
            pending.append(self.target)

    monkeypatch.setattr(threading, "Thread", ControlledThread)
    plan = api.post("workflows/plan", {"id": "test-workflow"})
    job = api.post("workflows/run", {"id": "test-workflow", "planHash": plan["planHash"], "confirmPaid": 1})["job"]
    assert job["owners"] == [{"kind": "pose", "id": "smile"}] and job["runId"]
    with pytest.raises(ValueError, match="already running"):
        api.start("generate", "pose", "smile", "gpt-image")
    with pytest.raises(ValueError, match="workflow is already running"):
        api.post("workflows/run", {"id": "test-workflow", "planHash": plan["planHash"], "confirmPaid": 1})
    pending[0]()
    assert api.jobs[job["id"]]["status"] == "succeeded"


def test_guided_and_workflow_image_requests_share_provider_lock_but_local_nodes_do_not(engine, monkeypatch):
    from spriteforge.production.project import add_pose
    studio, ops, runner = engine
    add_pose(studio.root, "other-expression")
    api = ProductionApi(studio.root)
    api.workflows = runner
    pending, observed = [], []

    class TracingLock:
        held = False
        entries = 0

        def __enter__(self):
            assert not self.held
            self.held = True
            self.entries += 1

        def __exit__(self, *_):
            self.held = False

    class ControlledThread:
        def __init__(self, *, target, **_):
            self.target = target

        def start(self):
            pending.append(self.target)

    provider_lock = TracingLock()
    api.provider_locks["gpt-image"] = provider_lock
    monkeypatch.setattr(threading, "Thread", ControlledThread)

    def guided(*args, **kwargs):
        assert provider_lock.held
        observed.append("guided")
        return {"id": "guided-candidate", "qa": {"status": "pass"}}

    monkeypatch.setattr("spriteforge.production.stills.generate_still", guided)
    execute = ops.execute

    def workflow_execute(workspace, node_dir, kind, params, inputs, **kwargs):
        assert provider_lock.held == (kind == "image-edit")
        observed.append(kind)
        return execute(workspace, node_dir, kind, params, inputs, **kwargs)

    monkeypatch.setattr(ops, "execute", workflow_execute)
    api.start("generate", "pose", "other-expression", "gpt-image")
    plan = api.post("workflows/plan", {"id": "test-workflow"})
    api.post("workflows/run", {"id": "test-workflow", "planHash": plan["planHash"], "confirmPaid": 1})
    pending[0]()
    pending[1]()
    assert provider_lock.entries == 2 and api.provider_locks["gpt-image"] is provider_lock
    assert observed == ["guided", "text", "image-edit", "preview"]
    assert all(job["status"] == "succeeded" for job in api.job_list())


def test_real_local_template_outputs_candidate_without_touching_accepted_clip(studio):
    from spriteforge.production.records import load_owner
    accepted = clip_with_take(studio, "loop", "idle", "idle", 6)
    before = load_owner(studio.root, "clip", "loop")
    raw = template_workflow(studio.root, "loop", clip="loop", identifier="local-template")
    save_workflow(studio.root, raw)
    runner = WorkflowEngine(studio.root)
    plan = runner.plan(raw["id"])
    assert plan["paidCount"] == 0
    result = runner.run(raw["id"], plan_hash=plan["planHash"], confirm_paid=0, log=lambda *_: None)
    assert result["state"] == "ready" and load_owner(studio.root, "clip", "loop") == before
    assert result["outputs"]["candidate"]["clip"]["record"]["take"] != accepted["id"]


def test_workflow_upload_retains_image_bytes_as_workspace_input(studio):
    image = encode_png(still(studio, "idle"))
    result = ProductionApi(studio.root).upload("workflow", "", "input.png", io.BytesIO(image), len(image), None, "")
    assert result["asset"]["type"] == "IMAGE"
    assert (studio.root / result["asset"]["path"]).read_bytes() == image


def test_api_workflow_clip_reservation_includes_synchronous_adoption(studio, monkeypatch):
    from spriteforge.production.project import add_clip
    add_clip(studio.root, "reserved", "idle", "idle")
    pending = []

    class ControlledThread:
        def __init__(self, *, target, **_):
            self.target = target

        def start(self):
            pending.append(self.target)

    monkeypatch.setattr(threading, "Thread", ControlledThread)
    monkeypatch.setattr("spriteforge.production.render.adopt_processed_take", lambda *args: {"id": "published"})
    api = ProductionApi(studio.root)
    api._launch("workflow", "workflow", "workflow-one", lambda _: "done", details={"owners": [{"kind": "clip", "id": "reserved"}]})
    with pytest.raises(ValueError, match="already running"):
        api.start("render-take", "clip", "reserved", take_id="candidate")
    with pytest.raises(ValueError, match="already running"):
        api.post("adopt-processed", {"clip": "reserved", "take": "candidate"})
    pending[0]()
    assert api.post("adopt-processed", {"clip": "reserved", "take": "candidate"})["take"]["id"] == "published"


def test_cli_workflow_template_save_and_free_run_share_same_candidate_engine(studio, tmp_path, capsys):
    import argparse
    from spriteforge.production import cli
    from spriteforge.production.records import load_owner
    original = clip_with_take(studio, "loop", "idle", "idle", 6)
    path = tmp_path / "local-workflow.json"
    parser = argparse.ArgumentParser()
    cli.add_parser(parser.add_subparsers(dest="command", required=True))
    cli.run(parser.parse_args(["production", "workflow", "template", "loop", "--workspace", str(studio.root),
                               "--clip", "loop", "--id", "cli-workflow", "--output", str(path)]))
    capsys.readouterr()
    cli.run(parser.parse_args(["production", "workflow", "save", "--workspace", str(studio.root), str(path)]))
    assert '"id": "cli-workflow"' in capsys.readouterr().out
    cli.run(parser.parse_args(["production", "workflow", "run", "--workspace", str(studio.root), "cli-workflow", "--yes-paid", "0"]))
    assert '"state": "ready"' in capsys.readouterr().out
    assert load_owner(studio.root, "clip", "loop")["acceptedTake"] == original["id"]


def test_real_paid_context_fingerprints_selected_prompt_model_and_actual_source_bytes(studio, monkeypatch):
    from spriteforge.production import prompts
    from spriteforge.production.records import still_path
    from spriteforge.production.tools import load_tools, save_tools
    library = prompts.load_library(studio.root)
    for block in library["blocks"]:
        prompts.set_block(library, block, f"Synthetic instruction for {block}")
    prompts.save_library(studio.root, library)
    calls = []

    class FakeAdapter:
        supports_reference = True
        negative_prompt = True

        def __init__(self, config):
            self.model = config["model"]

        def key(self):
            return "fake-test-key"

        def preview(self, job):
            return {"model": self.model, "prompt": job.prompt, "negative": job.negative,
                    "image": hashlib.sha256(job.image).hexdigest()}

        def edit(self, job):
            calls.append(job)
            return encode_png(still(studio, "idle"))

    monkeypatch.setattr("spriteforge.production.workflow_ops.get_image_provider", lambda name, tools: FakeAdapter(tools["providers"][name]))
    raw = template_workflow(studio.root, "final-still", pose="smile", identifier="real-context")
    save_workflow(studio.root, raw)
    runner = WorkflowEngine(studio.root)
    plan = runner.plan(raw["id"])
    result = runner.run(raw["id"], plan_hash=plan["planHash"], confirm_paid=1, log=lambda *_: None)
    assert result["state"] == "ready" and len(calls) == 1
    assert runner.plan(raw["id"])["paidCount"] == 0
    library = prompts.load_library(studio.root)
    prompts.set_block(library, "video.loop", "Unrelated video prompt changed")
    prompts.save_library(studio.root, library)
    assert runner.plan(raw["id"])["paidCount"] == 0
    prompts.set_block(library, "pose.smile", "Changed selected pose instruction")
    prompts.save_library(studio.root, library)
    assert runner.plan(raw["id"])["paidCount"] == 1
    tools = load_tools(studio.root)
    tools["providers"]["qwen-image"]["model"] = "changed-model"
    save_tools(studio.root, tools)
    before = runner.plan(raw["id"])["planHash"]
    path = still_path(studio.root, "idle")[0]
    path.write_bytes(encode_png(still(studio, "smile")))
    after = runner.plan(raw["id"])
    assert after["paidCount"] == 1 and after["planHash"] != before and len(calls) == 1


def test_template_existing_concept_ref_does_not_schedule_a_new_sheet(studio):
    from spriteforge.production.concepts import import_sheet
    from spriteforge.production.project import add_pose
    add_pose(studio.root, "new-expression")
    sheet = import_sheet(studio.root, studio.tmp / "master.png", ["new-expression"], "3x2")
    reference = {"sheet": sheet["id"], "cell": 0}
    raw = template_workflow(studio.root, "final-still", pose="new-expression", concept=reference)
    kinds = [node["kind"] for node in raw["nodes"]]
    assert "concept-cell" in kinds and "concept-sheet" not in kinds
    assert kinds.count("image-edit") == 1


def test_real_concept_provenance_cannot_be_laundered_through_normalize_and_reroute(studio):
    from spriteforge.production.concepts import import_sheet
    from spriteforge.production.project import add_pose
    from spriteforge.production.records import list_takes
    add_pose(studio.root, "new-expression")
    sheet = import_sheet(studio.root, studio.tmp / "master.png", ["new-expression"], "3x2")
    raw = {"format": FORMAT, "id": "concept-origin", "name": "Concept origin", "version": 1,
           "nodes": [{"id": "source", "kind": "concept-cell", "params": {"sheet": sheet["id"], "cell": 0}},
                     {"id": "normalize", "kind": "normalize", "params": {"pose": "new-expression"}},
                     {"id": "reroute", "kind": "reroute", "params": {"type": "IMAGE"}},
                     {"id": "save", "kind": "save-pose-take", "params": {"pose": "new-expression"}}],
           "links": [{"from": {"node": "source", "port": "image"}, "to": {"node": "normalize", "port": "media"}},
                     {"from": {"node": "normalize", "port": "media"}, "to": {"node": "reroute", "port": "input"}},
                     {"from": {"node": "reroute", "port": "output"}, "to": {"node": "save", "port": "image"}}]}
    save_workflow(studio.root, raw)
    with pytest.raises(ValueError, match="Concept images cannot be saved"):
        WorkflowEngine(studio.root).plan(raw["id"])
    assert list_takes(studio.root, "pose", "new-expression") == []


def test_workflow_directory_symlink_cannot_escape_selected_workspace(studio):
    outside = studio.tmp / "outside"
    outside.mkdir()
    link = studio.root / "production/workflows"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlinks are unavailable in this environment")
    try:
        with pytest.raises(ValueError):
            directory(studio.root)
        assert list(outside.iterdir()) == []
    finally:
        link.unlink()
